"""
╔══════════════════════════════════════════════════════════════════════╗
║  BTC-QUANT: v4.5 — GOLDEN vs HESTON WALK-FORWARD COMPARISON         ║
║                                                                      ║
║  Tujuan:                                                             ║
║    Menjawab pertanyaan: apakah Heston adaptive SL/TP lebih baik     ║
║    atau lebih buruk dari fixed SL/TP pada Golden Model v4.4?         ║
║                                                                      ║
║  Metodologi:                                                         ║
║    Kedua model berjalan PARALEL pada candle yang SAMA.               ║
║    Entry signal identik (L1 BCD + L2 EMA + L3 MLP + L4 Spectrum).   ║
║    Perbedaan HANYA pada SL/TP dan position sizing:                   ║
║                                                                      ║
║    MODEL A — Golden (v4.4 identik):                                  ║
║      - SL fixed : price × 1.333%                                     ║
║      - TP fixed : price × 0.71%                                      ║
║      - Size     : Fixed $1,000 × 15x = $15,000 notional             ║
║      - Max hold : 6 candles                                          ║
║                                                                      ║
║    MODEL B — Heston Adaptive:                                        ║
║      - SL       : price ± ATR × sl_multiplier  (Heston regime)      ║
║      - TP1      : price ± ATR × tp1_multiplier (Heston regime)      ║
║      - Size     : Dynamic via RiskManager (2% equity / sl_pct)      ║
║      - Leverage : Adaptive (safe mode = 5x cap)                     ║
║      - Max hold : 6 candles                                          ║
║                                                                      ║
║  Hipotesis yang diuji:                                               ║
║    H0: Heston tidak memberikan perbedaan signifikan vs Golden.       ║
║    H1: Heston meningkatkan win rate / profit factor.                 ║
║    H2: Heston menurunkan drawdown (volatility-aware risk mgmt).      ║
║                                                                      ║
║  Output:                                                             ║
║    - v4_5_golden_*_summary.json   (identik dengan v4.4 run baru)    ║
║    - v4_5_heston_*_summary.json   (Heston model results)            ║
║    - v4_5_comparison_*_report.json (head-to-head comparison)        ║
║    - v4_5_comparison_*_trades.csv  (both models side by side)       ║
║                                                                      ║
║  PENTING: File v4.4 yang sudah ada TIDAK diubah/dihapus.            ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import time
import logging
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pandas_ta as ta

# ── Path Setup ─────────────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_BACKEND_DIR  = str(_PROJECT_ROOT / "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

os.environ["BTC_QUANT_LAYER1_ENGINE"] = "bcd"

from utils.spectrum import DirectionalSpectrum
from data_engine    import DB_PATH

# ── Output Directories ─────────────────────────────────────────────────────────
_RESULTS_DIR = _PROJECT_ROOT / "backtest" / "results" / "v4_5_comparison_results"
_LOGS_DIR    = _PROJECT_ROOT / "backtest" / "logs"    / "v4_5"
_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
_LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Logging ────────────────────────────────────────────────────────────────────
_LOG_FILE = _LOGS_DIR / f"v4_5_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("v4_5")


# ══════════════════════════════════════════════════════════════════════════════
#  MODEL A — GOLDEN CONSTANTS (identik v4.4, tidak boleh diubah)
# ══════════════════════════════════════════════════════════════════════════════

GOLDEN_POSITION_USD = 1_000.0    # Fixed position size
GOLDEN_LEVERAGE     = 15.0       # Fixed leverage
GOLDEN_NOTIONAL     = GOLDEN_POSITION_USD * GOLDEN_LEVERAGE  # $15,000

GOLDEN_SL_PCT       = 0.01333   # 1.333% SL dari entry
GOLDEN_TP_PCT       = 0.0071    # 0.71%  TP dari entry
GOLDEN_MAX_HOLD     = 6         # Max candles

FEE_RATE            = 0.0004    # 0.04% per leg (taker)


# ══════════════════════════════════════════════════════════════════════════════
#  MODEL B — HESTON CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

HESTON_INITIAL_CAPITAL  = 10_000.0   # Independen dari Golden
HESTON_RISK_PER_TRADE   = 2.0        # 2% equity per trade
HESTON_MAX_LEVERAGE     = 5          # Safe mode (sesuai LEVERAGE_SAFE_MODE=true)
HESTON_MIN_LEVERAGE     = 1
HESTON_MAX_HOLD         = 6          # Sama dengan Golden untuk apple-to-apple
HESTON_CONSEC_LOSS_CAP  = 3          # De-leverage setelah 3 loss beruntun


# ══════════════════════════════════════════════════════════════════════════════
#  UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def calc_pnl_fixed(side: str, entry: float, exit_price: float) -> float:
    """PnL untuk Golden model — fixed $15,000 notional."""
    if side == "LONG":
        price_return = (exit_price - entry) / entry
    else:
        price_return = (entry - exit_price) / entry
    fee_usd = GOLDEN_NOTIONAL * FEE_RATE * 2
    return round(GOLDEN_NOTIONAL * price_return - fee_usd, 2)


def calc_pnl_dynamic(
    side: str, entry: float, exit_price: float,
    notional: float, fee_usd: float
) -> float:
    """PnL untuk Heston model — dynamic notional."""
    if side == "LONG":
        price_return = (exit_price - entry) / entry
    else:
        price_return = (entry - exit_price) / entry
    return round(notional * price_return - fee_usd, 2)


def check_sl_tp(
    side: str, sl: float, tp: float,
    c_high: float, c_low: float, c_close: float
):
    """
    Cek SL/TP menggunakan High/Low candle (bukan hanya close).
    Priority: SL > TP (konservatif).
    Return (exit_price, exit_type) atau None.
    """
    if side == "LONG":
        if c_low <= sl:
            return sl, "SL"
        if c_high >= tp:
            return (c_close, "TRAIL_TP") if c_close >= tp else (tp, "TP")
    else:  # SHORT
        if c_high >= sl:
            return sl, "SL"
        if c_low <= tp:
            return (c_close, "TRAIL_TP") if c_close <= tp else (tp, "TP")
    return None


def record_trade(trades, daily_stats, equity_curve, position, exit_price,
                 exit_type, exit_time, pnl, portfolio, holding_candles, model_tag):
    entry = position["entry"]
    side  = position["side"]
    actual_move = (
        (exit_price - entry) / entry * 100 if side == "LONG"
        else (entry - exit_price) / entry * 100
    )
    trade = {
        "model"            : model_tag,
        "entry_time"       : position["entry_time"],
        "exit_time"        : exit_time,
        "side"             : side,
        "entry_price"      : round(entry, 2),
        "exit_price"       : round(exit_price, 2),
        "sl"               : round(position["sl"], 2),
        "tp"               : round(position["tp"], 2),
        "sl_pct"           : round(position.get("sl_pct", 0), 6),
        "tp_pct"           : round(position.get("tp_pct", 0), 6),
        "notional"         : round(position.get("notional", GOLDEN_NOTIONAL), 2),
        "leverage"         : position.get("leverage", GOLDEN_LEVERAGE),
        "pnl_usd"          : round(pnl, 2),
        "equity"           : round(portfolio, 2),
        "exit_type"        : exit_type,
        "gate"             : position["gate"],
        "regime"           : position["regime"],
        "bcd_conf"         : position["bcd_conf"],
        "holding_candles"  : holding_candles,
        "actual_move_pct"  : round(actual_move, 4),
        # Heston-specific info (None for Golden)
        "vol_regime"       : position.get("vol_regime", "N/A"),
        "heston_sl_mult"   : position.get("heston_sl_mult", None),
        "heston_tp_mult"   : position.get("heston_tp_mult", None),
    }
    trades.append(trade)
    equity_curve.append({"candle": exit_time, "equity": round(portfolio, 2)})

    d_key = exit_time[:10]
    daily_stats.setdefault(d_key, {"pnl": 0.0, "n_trades": 0})
    daily_stats[d_key]["pnl"]      += pnl
    daily_stats[d_key]["n_trades"] += 1


def compute_stats(trades_list, initial_capital, window_start, window_end, model_tag):
    """Hitung semua statistik dari list trade."""
    if not trades_list:
        return {"model": model_tag, "n_trades": 0, "error": "No trades taken"}

    tdf = pd.DataFrame(trades_list)
    total      = len(tdf)
    wins       = (tdf["pnl_usd"] > 0).sum()
    losses     = total - wins
    win_rate   = wins / total * 100
    gross_p    = tdf[tdf["pnl_usd"] > 0]["pnl_usd"].sum()
    gross_l    = abs(tdf[tdf["pnl_usd"] <= 0]["pnl_usd"].sum())
    profit_fac = gross_p / gross_l if gross_l > 0 else float("inf")
    avg_win    = gross_p / wins   if wins   > 0 else 0.0
    avg_loss   = gross_l / losses if losses > 0 else 0.0
    rr_ratio   = avg_win / avg_loss if avg_loss > 0 else float("inf")

    final_equity = tdf["equity"].iloc[-1]
    final_pnl    = final_equity - initial_capital
    final_pct    = (final_equity / initial_capital - 1) * 100
    n_days       = (pd.to_datetime(window_end) - pd.to_datetime(window_start)).days
    daily_ret    = final_pct / n_days if n_days > 0 else 0.0

    # Max drawdown dari equity curve
    eq          = tdf["equity"].tolist()
    eq_series   = pd.Series([initial_capital] + eq)
    running_max = eq_series.cummax()
    dd_pct      = (eq_series - running_max) / running_max * 100
    max_dd      = abs(dd_pct.min())

    # Sharpe dari daily PnL
    daily_pnls = tdf.groupby(tdf["exit_time"].str[:10])["pnl_usd"].sum()
    daily_rets = daily_pnls / initial_capital * 100
    sharpe     = (daily_rets.mean() / daily_rets.std() * np.sqrt(365)
                  if daily_rets.std() > 0 else 0.0)

    exit_dist = tdf["exit_type"].value_counts().to_dict()
    avg_hold  = tdf["holding_candles"].mean()

    # Regime breakdown
    regime_summary = {}
    for regime, grp in tdf.groupby("regime"):
        r_wins = (grp["pnl_usd"] > 0).sum()
        regime_summary[str(regime)] = {
            "trades"   : len(grp),
            "win_rate" : round(r_wins / len(grp) * 100, 1),
            "total_pnl": round(grp["pnl_usd"].sum(), 2),
        }

    # Vol regime breakdown (Heston only)
    vol_regime_summary = {}
    if "vol_regime" in tdf.columns and tdf["vol_regime"].iloc[0] != "N/A":
        for vr, grp in tdf.groupby("vol_regime"):
            vr_wins = (grp["pnl_usd"] > 0).sum()
            vol_regime_summary[str(vr)] = {
                "trades"   : len(grp),
                "win_rate" : round(vr_wins / len(grp) * 100, 1),
                "total_pnl": round(grp["pnl_usd"].sum(), 2),
            }

    return {
        "model"            : model_tag,
        "window_start"     : window_start,
        "window_end"       : window_end,
        "initial_capital"  : initial_capital,
        "final_equity"     : round(final_equity, 2),
        "net_pnl_usd"      : round(final_pnl, 2),
        "net_pnl_pct"      : round(final_pct, 4),
        "daily_return_pct" : round(daily_ret, 4),
        "n_days"           : n_days,
        "n_trades"         : total,
        "n_wins"           : int(wins),
        "n_losses"         : int(losses),
        "win_rate_pct"     : round(win_rate, 2),
        "avg_winner_usd"   : round(avg_win, 2),
        "avg_loser_usd"    : round(avg_loss, 2),
        "rr_ratio"         : round(rr_ratio, 3),
        "profit_factor"    : round(profit_fac, 3),
        "max_drawdown_pct" : round(max_dd, 2),
        "sharpe_ratio"     : round(sharpe, 3),
        "avg_hold_candles" : round(float(avg_hold), 2),
        "exit_distribution": exit_dist,
        "regime_summary"   : regime_summary,
        "vol_regime_summary": vol_regime_summary,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  DATA LOADING
# ══════════════════════════════════════════════════════════════════════════════

def load_full_dataset() -> pd.DataFrame:
    log.info("Loading full dataset from DuckDB...")
    with duckdb.connect(DB_PATH, read_only=True) as con:
        df = con.execute("""
            SELECT
                o.timestamp,
                o.open   AS Open,
                o.high   AS High,
                o.low    AS Low,
                o.close  AS Close,
                o.volume AS Volume,
                COALESCE(o.cvd, 0.0)           AS CVD,
                COALESCE(m.funding_rate, 0.0)  AS Funding,
                COALESCE(m.open_interest, 0.0) AS OI,
                COALESCE(m.fgi_value, 50.0)    AS FGI
            FROM btc_ohlcv_4h o
            ASOF LEFT JOIN market_metrics m ON o.timestamp >= m.timestamp
            ORDER BY o.timestamp ASC
        """).fetchdf()
    if df.empty:
        raise RuntimeError("DuckDB returned empty dataset.")
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("datetime")
    log.info(f"Loaded {len(df)} candles | {df.index[0]} → {df.index[-1]}")
    return df


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["EMA20"] = ta.ema(df["Close"], length=20)
    df["EMA50"] = ta.ema(df["Close"], length=50)
    df["ATR14"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)
    return df


# ══════════════════════════════════════════════════════════════════════════════
#  HESTON SIMPLE RISK MANAGER (standalone, no singleton dependency)
# ══════════════════════════════════════════════════════════════════════════════

class HestonRiskState:
    """
    Lightweight intraday risk state untuk Heston model backtest.
    Tidak pakai singleton agar independent dari produksi.
    """
    def __init__(self):
        self.consecutive_losses = 0
        self.consecutive_wins   = 0
        self.daily_pnl_pct      = 0.0

    def get_leverage(self, requested: int) -> int:
        """De-leverage setelah 3+ loss beruntun."""
        lev = min(requested, HESTON_MAX_LEVERAGE)
        if self.consecutive_losses >= HESTON_CONSEC_LOSS_CAP:
            lev = max(HESTON_MIN_LEVERAGE, lev // 2)
        return lev

    def record(self, pnl_pct: float):
        if pnl_pct < 0:
            self.consecutive_losses += 1
            self.consecutive_wins    = 0
        else:
            self.consecutive_wins   += 1
            if self.consecutive_wins >= 2:
                self.consecutive_losses = 0


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def run_v4_5_comparison(
    window_start:     str   = "2024-01-01",
    window_end:       str   = "2026-03-04",
    required_history: int   = 400,
    initial_capital:  float = 10_000.0,
):
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log.info("=" * 72)
    log.info("  BTC-QUANT v4.5 — GOLDEN vs HESTON COMPARISON")
    log.info(f"  Window   : {window_start}  →  {window_end}")
    log.info(f"  Capital  : ${initial_capital:,.0f} (each model)")
    log.info("─" * 72)
    log.info("  MODEL A (Golden)  : SL fixed 1.333% | TP fixed 0.71% | $1k×15x")
    log.info("  MODEL B (Heston)  : SL/TP adaptive ATR×mult | Dynamic sizing | 5x cap")
    log.info("=" * 72)

    # ── 1. Load Data ───────────────────────────────────────────────────────────
    df_all = load_full_dataset()
    df_all = add_indicators(df_all)

    start_dt = pd.to_datetime(window_start).tz_localize("UTC")
    end_dt   = pd.to_datetime(window_end).tz_localize("UTC")

    db_first = df_all.index[required_history]
    if start_dt < db_first:
        log.warning(f"Auto-adjusting start → {db_first.date()}")
        start_dt = db_first

    pos_all   = np.arange(len(df_all))
    trade_pos = pos_all[(df_all.index >= start_dt) & (df_all.index <= end_dt)]

    if len(trade_pos) == 0:
        log.error("No candles in window.")
        return

    t_start = trade_pos[0]
    t_end   = trade_pos[-1]
    log.info(f"  Candles in window : {len(trade_pos):,} | History: {t_start:,} candles\n")

    # ── 2. Services ────────────────────────────────────────────────────────────
    log.info("Initializing services...")
    from app.use_cases.bcd_service import get_bcd_service
    from app.use_cases.ai_service  import get_ai_service
    from app.use_cases.ema_service import get_ema_service
    from app.core.engines.layer1_volatility import VolatilityRegimeEstimator

    bcd_svc  = get_bcd_service()
    ai_svc   = get_ai_service()
    ema_svc  = get_ema_service()
    vol_est  = VolatilityRegimeEstimator()   # Heston estimator (bukan singleton)
    spectrum = DirectionalSpectrum()
    log.info("All services ready.\n")

    # ── 3. State — Model A (Golden) ────────────────────────────────────────────
    portfolio_g    = initial_capital
    position_g     = None
    trades_g       = []
    daily_g        = {}
    equity_g       = [{"candle": df_all.index[t_start].isoformat(), "equity": portfolio_g}]
    n_skip_g = n_err_g = 0
    n_sl_g = n_tp_g = n_trail_g = n_time_g = 0

    # ── 4. State — Model B (Heston) ────────────────────────────────────────────
    portfolio_h    = initial_capital
    position_h     = None
    trades_h       = []
    daily_h        = {}
    equity_h       = [{"candle": df_all.index[t_start].isoformat(), "equity": portfolio_h}]
    risk_state_h   = HestonRiskState()
    n_skip_h = n_err_h = 0
    n_sl_h = n_tp_h = n_trail_h = n_time_h = 0

    # ── 5. Candle Loop ─────────────────────────────────────────────────────────
    t0 = time.time()
    last_log = t0
    n_candles = t_end - t_start

    log.info("Starting candle loop...\n")

    for i in range(t_start, t_end):
        candle_dt   = df_all.index[i]
        next_candle = df_all.iloc[i + 1]

        df_hist   = df_all.iloc[max(0, i - 500 + 1) : i + 1].copy()
        price_now = float(df_hist["Close"].iloc[-1])
        atr14     = float(df_hist["ATR14"].dropna().iloc[-1]) if df_hist["ATR14"].dropna().size else price_now * 0.01
        ema20     = float(df_hist["EMA20"].dropna().iloc[-1]) if df_hist["EMA20"].dropna().size else price_now
        ema50     = float(df_hist["EMA50"].dropna().iloc[-1]) if df_hist["EMA50"].dropna().size else price_now

        c_high  = float(next_candle["High"])
        c_low   = float(next_candle["Low"])
        c_close = float(next_candle["Close"])

        # EMA trend
        if ema20 > ema50 and price_now > ema20:
            raw_trend = "BULL"
        elif ema20 < ema50 and price_now < ema20:
            raw_trend = "BEAR"
        elif price_now > ema50:
            raw_trend = "BULL"
        else:
            raw_trend = "BEAR"

        exit_time = next_candle.name.isoformat()

        # ══════════════════════════════════════════════════════════════════════
        #  EXIT — MODEL A (Golden)
        # ══════════════════════════════════════════════════════════════════════
        if position_g is not None:
            holding = i - position_g["entry_idx"]
            hit = check_sl_tp(position_g["side"], position_g["sl"], position_g["tp"],
                               c_high, c_low, c_close)
            if hit:
                ep, et = hit
                pnl = calc_pnl_fixed(position_g["side"], position_g["entry"], ep)
                portfolio_g += pnl
                if et == "SL":            n_sl_g    += 1
                elif et == "TP":          n_tp_g    += 1
                elif et == "TRAIL_TP":    n_trail_g += 1
                record_trade(trades_g, daily_g, equity_g, position_g,
                             ep, et, exit_time, pnl, portfolio_g, holding + 1, "GOLDEN")
                log.debug(f"  [G] CLOSE {position_g['side']} | {et} | PnL={pnl:+.2f} | Eq={portfolio_g:,.2f}")
                position_g = None

            elif holding >= GOLDEN_MAX_HOLD - 1:
                ep  = c_close
                pnl = calc_pnl_fixed(position_g["side"], position_g["entry"], ep)
                portfolio_g += pnl
                n_time_g += 1
                record_trade(trades_g, daily_g, equity_g, position_g,
                             ep, "TIME_EXIT", exit_time, pnl, portfolio_g, holding + 1, "GOLDEN")
                log.debug(f"  [G] CLOSE {position_g['side']} | TIME_EXIT | PnL={pnl:+.2f}")
                position_g = None

        # ══════════════════════════════════════════════════════════════════════
        #  EXIT — MODEL B (Heston)
        # ══════════════════════════════════════════════════════════════════════
        if position_h is not None:
            holding = i - position_h["entry_idx"]
            hit = check_sl_tp(position_h["side"], position_h["sl"], position_h["tp"],
                               c_high, c_low, c_close)
            if hit:
                ep, et = hit
                pnl = calc_pnl_dynamic(
                    position_h["side"], position_h["entry"], ep,
                    position_h["notional"], position_h["fee_usd"]
                )
                portfolio_h += pnl
                # Catat PnL% untuk risk state
                sl_dist = abs(position_h["entry"] - position_h["sl"]) / position_h["entry"]
                risk_state_h.record(pnl / position_h.get("size_usd", 1000.0) * 100)
                if et == "SL":            n_sl_h    += 1
                elif et == "TP":          n_tp_h    += 1
                elif et == "TRAIL_TP":    n_trail_h += 1
                record_trade(trades_h, daily_h, equity_h, position_h,
                             ep, et, exit_time, pnl, portfolio_h, holding + 1, "HESTON")
                log.debug(f"  [H] CLOSE {position_h['side']} | {et} | PnL={pnl:+.2f} | Eq={portfolio_h:,.2f}")
                position_h = None

            elif holding >= HESTON_MAX_HOLD - 1:
                ep  = c_close
                pnl = calc_pnl_dynamic(
                    position_h["side"], position_h["entry"], ep,
                    position_h["notional"], position_h["fee_usd"]
                )
                portfolio_h += pnl
                risk_state_h.record(pnl / position_h.get("size_usd", 1000.0) * 100)
                n_time_h += 1
                record_trade(trades_h, daily_h, equity_h, position_h,
                             ep, "TIME_EXIT", exit_time, pnl, portfolio_h, holding + 1, "HESTON")
                log.debug(f"  [H] CLOSE {position_h['side']} | TIME_EXIT | PnL={pnl:+.2f}")
                position_h = None

        # Skip entry jika kedua posisi masih terbuka
        if position_g is not None and position_h is not None:
            continue

        # ══════════════════════════════════════════════════════════════════════
        #  ENTRY SIGNAL — identik untuk kedua model
        # ══════════════════════════════════════════════════════════════════════
        if portfolio_g < GOLDEN_POSITION_USD and portfolio_h < 100:
            break

        try:
            # L1: BCD
            label, tag, bcd_conf, hmm_states, hmm_index = \
                bcd_svc.get_regime_and_states(df_hist, funding_rate=0)

            # Skip neutral (konsisten dengan v4.4 yang menggunakan neutral guard)
            if any(kw in label.lower() for kw in ("neutral", "sideways", "lv_sw", "hv_sw", "unknown")):
                if position_g is None: n_skip_g += 1
                if position_h is None: n_skip_h += 1
                continue

            l1_bull = (tag == "bull")
            l1_vote = float(bcd_conf if l1_bull else -bcd_conf)

            # L2: EMA
            l2_aligned, _, _ = ema_svc.get_alignment(df_hist, raw_trend)
            l2_vote = (
                1.0 if (l2_aligned and raw_trend == "BULL")
                else (-1.0 if (l2_aligned and raw_trend == "BEAR") else 0.0)
            )

            # L3: MLP AI
            ai_bias, ai_conf = ai_svc.get_confidence(
                df_hist, hmm_states=hmm_states, hmm_index=hmm_index
            )
            conf_norm = (max(50.0, min(100.0, float(ai_conf))) - 50.0) / 50.0
            l3_vote   = conf_norm if str(ai_bias) == "BULL" else -conf_norm

            # L4: Vol multiplier
            vol_ratio = atr14 / price_now if price_now > 0 else 0.001
            l4_mult   = spectrum.compute_l4_multiplier(vol_ratio)

            # Spectrum
            spec = spectrum.calculate(l1_vote, l2_vote, l3_vote, l4_mult, 5.0)

            if spec.trade_gate not in ("ACTIVE", "ADVISORY"):
                if position_g is None: n_skip_g += 1
                if position_h is None: n_skip_h += 1
                continue

            is_bull = spec.directional_bias >= 0
            side    = "LONG" if is_bull else "SHORT"

            # ── HESTON: Estimasi regime volatilitas ──────────────────────────
            heston_params = vol_est.estimate_params(df_hist)
            vol_regime_h  = heston_params.get("vol_regime", "Normal")
            halflife_h    = float(heston_params.get("mean_reversion_halflife_candles", 999.0))

            # Heston multiplier (pakai bias_score default 0.5 — tidak ada Modul A)
            sl_tp_mults = vol_est.get_sl_tp_multipliers(
                vol_regime = vol_regime_h,
                halflife   = halflife_h,
                bias_score = 0.5,
            )
            h_sl_m  = sl_tp_mults["sl_multiplier"]
            h_tp1_m = sl_tp_mults["tp1_multiplier"]

            entry_time = candle_dt.isoformat()
            common_info = {
                "side"     : side,
                "entry"    : price_now,
                "entry_idx": i,
                "entry_time": entry_time,
                "gate"     : spec.trade_gate,
                "regime"   : str(tag),
                "bcd_conf" : round(float(bcd_conf), 4),
            }

            # ── ENTRY — MODEL A (Golden) ──────────────────────────────────────
            if position_g is None and portfolio_g >= GOLDEN_POSITION_USD:
                if side == "LONG":
                    sl_g = price_now * (1.0 - GOLDEN_SL_PCT)
                    tp_g = price_now * (1.0 + GOLDEN_TP_PCT)
                else:
                    sl_g = price_now * (1.0 + GOLDEN_SL_PCT)
                    tp_g = price_now * (1.0 - GOLDEN_TP_PCT)

                position_g = {
                    **common_info,
                    "sl"         : sl_g,
                    "tp"         : tp_g,
                    "sl_pct"     : GOLDEN_SL_PCT,
                    "tp_pct"     : GOLDEN_TP_PCT,
                    "notional"   : GOLDEN_NOTIONAL,
                    "leverage"   : GOLDEN_LEVERAGE,
                    "vol_regime" : "N/A",
                    "heston_sl_mult": None,
                    "heston_tp_mult": None,
                }
                log.info(
                    f"  [G] OPEN {side:5s} @ {price_now:,.0f} | "
                    f"SL={sl_g:,.0f} ({GOLDEN_SL_PCT*100:.3f}%) | "
                    f"TP={tp_g:,.0f} ({GOLDEN_TP_PCT*100:.3f}%) | "
                    f"regime={tag} gate={spec.trade_gate}"
                )

            # ── ENTRY — MODEL B (Heston) ──────────────────────────────────────
            if position_h is None and portfolio_h >= 100:
                if side == "LONG":
                    sl_h  = price_now - atr14 * h_sl_m
                    tp_h  = price_now + atr14 * h_tp1_m
                else:
                    sl_h  = price_now + atr14 * h_sl_m
                    tp_h  = price_now - atr14 * h_tp1_m

                # Hitung actual SL% untuk sizing
                sl_pct_h = abs(price_now - sl_h) / price_now
                sl_pct_h = max(sl_pct_h, 0.003)  # floor 0.3%
                tp_pct_h = abs(price_now - tp_h) / price_now

                # Position sizing: risk 2% equity / sl_pct
                risk_frac    = HESTON_RISK_PER_TRADE / 100.0
                size_pct     = min(risk_frac / sl_pct_h * 100.0, 100.0)
                size_usd     = portfolio_h * (size_pct / 100.0)

                # Leverage: dynamic (requested = 1/sl_pct * 0.04 rule, capped)
                req_lev      = max(1, min(20, round(0.04 / sl_pct_h)))
                leverage_h   = risk_state_h.get_leverage(req_lev)
                notional_h   = size_usd * leverage_h
                fee_usd_h    = notional_h * FEE_RATE * 2

                position_h = {
                    **common_info,
                    "sl"            : sl_h,
                    "tp"            : tp_h,
                    "sl_pct"        : round(sl_pct_h, 6),
                    "tp_pct"        : round(tp_pct_h, 6),
                    "notional"      : round(notional_h, 2),
                    "leverage"      : leverage_h,
                    "size_usd"      : round(size_usd, 2),
                    "fee_usd"       : round(fee_usd_h, 4),
                    "vol_regime"    : vol_regime_h,
                    "heston_sl_mult": h_sl_m,
                    "heston_tp_mult": h_tp1_m,
                }
                log.info(
                    f"  [H] OPEN {side:5s} @ {price_now:,.0f} | "
                    f"SL={sl_h:,.0f} ({sl_pct_h*100:.3f}%, ×{h_sl_m}) | "
                    f"TP={tp_h:,.0f} ({tp_pct_h*100:.3f}%, ×{h_tp1_m}) | "
                    f"size=${size_usd:.0f}×{leverage_h}x | "
                    f"vol={vol_regime_h} regime={tag}"
                )

        except Exception as exc:
            if position_g is None: n_err_g += 1
            if position_h is None: n_err_h += 1
            log.warning(f"  [ERROR] {candle_dt.date()} | {type(exc).__name__}: {exc}")
            continue

        # Progress heartbeat
        now = time.time()
        if now - last_log >= 15:
            pct     = (i - t_start) / max(n_candles, 1) * 100
            elapsed = now - t0
            eta_s   = (elapsed / max(pct, 0.01)) * (100 - pct)
            log.info(
                f"  ▶ [{candle_dt.strftime('%Y-%m-%d')}] {pct:5.1f}%"
                f"  │ [G] Eq=${portfolio_g:>9,.0f} T={len(trades_g):>4}"
                f"  │ [H] Eq=${portfolio_h:>9,.0f} T={len(trades_h):>4}"
                f"  │ ETA: {eta_s/60:.1f}m"
            )
            last_log = now

    elapsed_total = time.time() - t0

    # ══════════════════════════════════════════════════════════════════════════
    #  RESULTS
    # ══════════════════════════════════════════════════════════════════════════
    log.info("\n" + "═" * 72)
    log.info("  BACKTEST COMPLETE — v4.5 Comparison")
    log.info("═" * 72)

    stats_g = compute_stats(trades_g, initial_capital, window_start, window_end, "GOLDEN_v4.4")
    stats_h = compute_stats(trades_h, initial_capital, window_start, window_end, "HESTON_v4.5")

    # ── Head-to-head comparison ────────────────────────────────────────────────
    def delta(key, better_if="higher"):
        vg = stats_g.get(key, 0)
        vh = stats_h.get(key, 0)
        if isinstance(vg, (int, float)) and isinstance(vh, (int, float)):
            diff = vh - vg
            if better_if == "higher":
                winner = "HESTON" if diff > 0 else ("GOLDEN" if diff < 0 else "TIE")
            else:  # lower is better (drawdown)
                winner = "HESTON" if diff < 0 else ("GOLDEN" if diff > 0 else "TIE")
            return {"golden": vg, "heston": vh, "delta": round(diff, 4), "winner": winner}
        return {"golden": vg, "heston": vh}

    comparison = {
        "run_timestamp"     : run_ts,
        "window_start"      : window_start,
        "window_end"        : window_end,
        "initial_capital"   : initial_capital,
        "elapsed_seconds"   : round(elapsed_total, 1),
        "metrics": {
            "net_pnl_pct"       : delta("net_pnl_pct",       "higher"),
            "win_rate_pct"      : delta("win_rate_pct",       "higher"),
            "profit_factor"     : delta("profit_factor",      "higher"),
            "max_drawdown_pct"  : delta("max_drawdown_pct",   "lower"),
            "sharpe_ratio"      : delta("sharpe_ratio",       "higher"),
            "rr_ratio"          : delta("rr_ratio",           "higher"),
            "daily_return_pct"  : delta("daily_return_pct",   "higher"),
            "n_trades"          : delta("n_trades",           "higher"),
            "avg_winner_usd"    : delta("avg_winner_usd",     "higher"),
            "avg_loser_usd"     : delta("avg_loser_usd",      "lower"),
        },
        "golden_skipped"    : n_skip_g,
        "heston_skipped"    : n_skip_h,
        "golden_errors"     : n_err_g,
        "heston_errors"     : n_err_h,
    }

    # Count wins per metric
    heston_wins = sum(
        1 for m in comparison["metrics"].values()
        if isinstance(m, dict) and m.get("winner") == "HESTON"
    )
    golden_wins = sum(
        1 for m in comparison["metrics"].values()
        if isinstance(m, dict) and m.get("winner") == "GOLDEN"
    )
    ties = sum(
        1 for m in comparison["metrics"].values()
        if isinstance(m, dict) and m.get("winner") == "TIE"
    )

    if heston_wins > golden_wins:
        comparison["verdict"] = f"🟢 HESTON WINS ({heston_wins}/{len(comparison['metrics'])} metrics)"
    elif golden_wins > heston_wins:
        comparison["verdict"] = f"🏆 GOLDEN WINS ({golden_wins}/{len(comparison['metrics'])} metrics)"
    else:
        comparison["verdict"] = f"🟡 TIE ({ties} tied metrics)"

    # ── Print Summary ─────────────────────────────────────────────────────────
    log.info(f"\n  {'Metric':<22} {'GOLDEN':>12} {'HESTON':>12} {'Δ':>10} {'Winner':<10}")
    log.info("  " + "─" * 68)
    for metric, data in comparison["metrics"].items():
        if isinstance(data, dict) and "delta" in data:
            g_val = data["golden"]
            h_val = data["heston"]
            delta_val = data["delta"]
            winner = data.get("winner", "")
            icon = "◀" if winner == "GOLDEN" else ("▶" if winner == "HESTON" else "=")
            log.info(
                f"  {metric:<22} {g_val:>12.3f} {h_val:>12.3f} "
                f"{delta_val:>+10.3f} {icon} {winner:<10}"
            )
    log.info(f"\n  {comparison['verdict']}")
    log.info(f"  GOLDEN : {golden_wins} wins | HESTON : {heston_wins} wins | TIE: {ties}")
    log.info("═" * 72)

    # ── Save Results ───────────────────────────────────────────────────────────
    run_tag = f"v4_5_{window_start[:7].replace('-','')}_{window_end[:7].replace('-','')}_{run_ts}"

    # Model A — Golden
    with open(_RESULTS_DIR / f"{run_tag}_golden_summary.json", "w") as f:
        json.dump(stats_g, f, indent=2)

    # Model B — Heston
    with open(_RESULTS_DIR / f"{run_tag}_heston_summary.json", "w") as f:
        json.dump(stats_h, f, indent=2)

    # Comparison report
    with open(_RESULTS_DIR / f"{run_tag}_comparison_report.json", "w") as f:
        json.dump(comparison, f, indent=2)

    # Combined trades CSV (both models side by side)
    all_trades = trades_g + trades_h
    if all_trades:
        pd.DataFrame(all_trades).to_csv(
            _RESULTS_DIR / f"{run_tag}_all_trades.csv", index=False
        )

    # Separate CSVs per model
    if trades_g:
        pd.DataFrame(trades_g).to_csv(
            _RESULTS_DIR / f"{run_tag}_golden_trades.csv", index=False
        )
    if trades_h:
        pd.DataFrame(trades_h).to_csv(
            _RESULTS_DIR / f"{run_tag}_heston_trades.csv", index=False
        )

    log.info(f"\n  [✓] Golden Summary  → {run_tag}_golden_summary.json")
    log.info(f"  [✓] Heston Summary  → {run_tag}_heston_summary.json")
    log.info(f"  [✓] Comparison      → {run_tag}_comparison_report.json")
    log.info(f"  [✓] All Trades      → {run_tag}_all_trades.csv")
    log.info(f"  [✓] Log             → {_LOG_FILE.name}")
    log.info(f"  [✓] Time taken      : {elapsed_total:.0f}s\n")

    return comparison


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRYPOINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="BTC-Quant v4.5 — Golden vs Heston Walk-Forward Comparison"
    )
    parser.add_argument("--start",
        default="2024-01-01",
        help="Start date YYYY-MM-DD (default: 2024-01-01)")
    parser.add_argument("--end",
        default="2026-03-04",
        help="End date YYYY-MM-DD (default: 2026-03-04)")
    parser.add_argument("--capital",
        default=10000.0, type=float,
        help="Initial capital per model (default: 10000)")
    parser.add_argument("--history",
        default=400, type=int,
        help="Required history candles before window (default: 400)")
    parser.add_argument("--quick",
        action="store_true",
        help="Quick test: run only 2026-01-01 to 2026-03-04")
    args = parser.parse_args()

    if args.quick:
        log.info("  [QUICK MODE] Running 2026-01 → 2026-03 only")
        run_v4_5_comparison(
            window_start     = "2026-01-01",
            window_end       = "2026-03-04",
            required_history = args.history,
            initial_capital  = args.capital,
        )
    else:
        run_v4_5_comparison(
            window_start     = args.start,
            window_end       = args.end,
            required_history = args.history,
            initial_capital  = args.capital,
        )
