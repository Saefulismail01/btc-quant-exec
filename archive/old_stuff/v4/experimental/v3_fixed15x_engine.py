"""
╔══════════════════════════════════════════════════════════════════════╗
║  BTC-QUANT: v3 FIXED POSITION WALK-FORWARD ENGINE                   ║
║  Baseline comparison engine dengan fixed leverage 15x               ║
║                                                                      ║
║  Trade Plan:                                                         ║
║    POSITION : Fixed $1,000 per trade × 15x = $15,000 notional       ║
║    SL       : Entry × 1.01333 (SHORT) / × 0.98667 (LONG)           ║
║               = 1.333% dari entry → kerugian max $200 + fee = $212  ║
║    TP       : Trailing — target awal 0.71% dari entry               ║
║               Simulasi: exit di close candle jika lebih baik        ║
║    MAX HOLD : 1 candle = 4 jam → TIME_EXIT di next candle close     ║
║    LEVERAGE : FIXED 15x (tidak dari RiskManager)                    ║
║    FEE      : 0.04% taker × 2 legs = $12 per round-trip             ║
║                                                                      ║
║  Signal Source (sama dengan v3):                                     ║
║    L1: BCD regime detection                                          ║
║    L2: EMA alignment                                                 ║
║    L3: MLP AI confidence                                             ║
║    L4: Heston volatility multiplier                                  ║
║    Gate: ACTIVE + ADVISORY                                           ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import time
import logging
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
from data_engine   import DB_PATH

# ── Output Directories ─────────────────────────────────────────────────────────
_RESULTS_DIR = _PROJECT_ROOT / "backtest" / "results" / "v3_fixed15x_results"
_LOGS_DIR    = _PROJECT_ROOT / "backtest" / "logs"    / "v3_fixed15x"
_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
_LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Logging ────────────────────────────────────────────────────────────────────
_LOG_FILE = _LOGS_DIR / f"fixed15x_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("v3_fixed15x")


# ══════════════════════════════════════════════════════════════════════════════
#  TRADE PLAN CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

POSITION_USD  = 1_000.0    # Fixed position size per trade
LEVERAGE      = 15.0       # Fixed 15x leverage
NOTIONAL      = POSITION_USD * LEVERAGE   # $15,000

FEE_RATE      = 0.0004     # 0.04% taker fee per leg
FEE_USD       = NOTIONAL * FEE_RATE * 2  # $12 per round-trip (both legs)

SL_PCT        = 0.01333    # 1.333% SL dari entry
TP_MIN_PCT    = 0.0071     # 0.71% TP initial target dari entry

# Trailing TP reversal: jika candle sudah profitabel, trail dari high/low candle
# dengan reversal buffer ini sebelum TIME_EXIT
TRAIL_REVERSAL_PCT = 0.003  # 0.3% reversal dari peak intra-candle untuk cut profit

MAX_HOLD_CANDLES   = 1      # 4 jam = 1 candle → TIME_EXIT jika tidak ada SL/TP hit


# ══════════════════════════════════════════════════════════════════════════════
#  PnL CALCULATION
# ══════════════════════════════════════════════════════════════════════════════

def calc_pnl(side: str, entry: float, exit_price: float) -> float:
    """
    PnL = Notional × price_return − fee
    LONG:  Notional × (exit − entry) / entry  − FEE_USD
    SHORT: Notional × (entry − exit) / entry  − FEE_USD
    """
    if side == "LONG":
        price_return = (exit_price - entry) / entry
    else:
        price_return = (entry - exit_price) / entry
    return round(NOTIONAL * price_return - FEE_USD, 2)


# ══════════════════════════════════════════════════════════════════════════════
#  DATA LOADING
# ══════════════════════════════════════════════════════════════════════════════

def load_full_dataset() -> pd.DataFrame:
    log.info("Loading full dataset from DuckDB with ASOF JOIN...")
    with duckdb.connect(DB_PATH, read_only=True) as con:
        df = con.execute("""
            SELECT
                o.timestamp,
                o.open   AS Open,
                o.high   AS High,
                o.low    AS Low,
                o.close  AS Close,
                o.volume AS Volume,
                COALESCE(o.cvd, 0.0)            AS CVD,
                COALESCE(m.funding_rate, 0.0)   AS Funding,
                COALESCE(m.open_interest, 0.0)  AS OI,
                COALESCE(m.fgi_value, 50.0)     AS FGI
            FROM btc_ohlcv_4h o
            ASOF LEFT JOIN market_metrics m ON o.timestamp >= m.timestamp
            ORDER BY o.timestamp ASC
        """).fetchdf()
    if df.empty:
        raise RuntimeError("DuckDB returned empty dataset. Run data_engine.py first.")
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
#  TRAILING TP SIMULATION (OHLC-based)
# ══════════════════════════════════════════════════════════════════════════════

def simulate_exit(
    side:        str,
    entry:       float,
    sl:          float,
    initial_tp:  float,
    next_open:   float,
    next_high:   float,
    next_low:    float,
    next_close:  float,
) -> tuple[float, str]:
    """
    Simulate 4H candle exit using OHLC of next candle.

    Priority order:
      1. SL hit      → exit at SL price
      2. Initial TP hit → exit at TP price (trailing simulated as: lock at TP
                          since max hold = 1 candle; better than close means
                          trailing already captured the move)
      3. TIME_EXIT   → exit at next_close (candle expired)

    Anti-lookahead: uses ONLY next_candle OHLC as "execution window".

    Trailing approximation within 1 candle:
      LONG : Peak = next_high. If peak >= initial_tp and next_close > entry,
             exit at min(next_close, next_high × (1 + trail_reversal)) →
             simplified: if TP hit during candle, exit at TP; else at close.
      SHORT: Peak = next_low.  Same logic, mirrored.
    """
    if side == "LONG":
        # 1. SL check
        if next_low <= sl:
            return sl, "SL"
        # 2. TP hit (initial target)
        if next_high >= initial_tp:
            # Trailing within candle: check if price closed above initial_tp
            # If yes → trail further to close; if no → lock at initial_tp
            if next_close >= initial_tp:
                # Price still above target at close — exit at close (better trailing)
                trail_exit = next_close
                return trail_exit, "TRAIL_TP"
            else:
                # Price reversed back below TP after hitting it
                return initial_tp, "TP"
        # 3. TIME_EXIT
        return next_close, "TIME_EXIT"

    else:  # SHORT
        # 1. SL check
        if next_high >= sl:
            return sl, "SL"
        # 2. TP hit
        if next_low <= initial_tp:
            if next_close <= initial_tp:
                # Price still below target at close → trail to close
                trail_exit = next_close
                return trail_exit, "TRAIL_TP"
            else:
                return initial_tp, "TP"
        # 3. TIME_EXIT
        return next_close, "TIME_EXIT"


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def run_fixed15x_walkforward(
    window_start:     str   = "2026-01-01",
    window_end:       str   = "2026-03-04",
    required_history: int   = 400,
    initial_capital:  float = 10_000.0,
):
    """
    v3 Fixed 15x Walk-Forward Engine.

    Sinyal: identik dengan true_walkforward_engine.py (v3).
    Exit  : Fixed trade plan — SL 1.333%, TP trail, max hold 1 candle.
    Size  : FIXED $1,000 position × 15x = $15,000 notional per trade.
    """
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log.info("=" * 72)
    log.info("  BTC-QUANT v3 FIXED 15x WALK-FORWARD")
    log.info(f"  Window   : {window_start}  →  {window_end}")
    log.info(f"  Capital  : ${initial_capital:,.0f}")
    log.info(f"  Position : ${POSITION_USD:,.0f} × {LEVERAGE:.0f}x = ${NOTIONAL:,.0f} notional")
    log.info(f"  SL       : {SL_PCT*100:.3f}%  |  TP min: {TP_MIN_PCT*100:.3f}%")
    log.info(f"  Fee/trip : ${FEE_USD:.2f}")
    log.info(f"  Max Hold : {MAX_HOLD_CANDLES} candle(s) = {MAX_HOLD_CANDLES*4}h")
    log.info("=" * 72)

    # ── 1. Load Data ───────────────────────────────────────────────────────────
    df_all = load_full_dataset()
    df_all = add_indicators(df_all)

    start_dt = pd.to_datetime(window_start).tz_localize("UTC")
    end_dt   = pd.to_datetime(window_end  ).tz_localize("UTC")

    db_first_tradeable = df_all.index[required_history]
    if start_dt < db_first_tradeable:
        log.warning(f"Auto-adjusting start to {db_first_tradeable.date()}.")
        start_dt = db_first_tradeable

    pos_all         = np.arange(len(df_all))
    trade_positions = pos_all[(df_all.index >= start_dt) & (df_all.index <= end_dt)]

    if len(trade_positions) == 0:
        log.error("No candles in window.")
        return

    t_start = trade_positions[0]
    t_end   = trade_positions[-1]

    log.info(f"  Candles in window : {len(trade_positions):,}")
    log.info(f"  History available : {t_start:,} candles before window\n")

    # ── 2. Services ────────────────────────────────────────────────────────────
    log.info("Initializing services...")
    from app.services.bcd_service import get_bcd_service
    from app.services.ai_service  import get_ai_service
    from app.services.ema_service import get_ema_service
    from engines.layer1_volatility import get_vol_estimator

    bcd_svc  = get_bcd_service()
    ai_svc   = get_ai_service()
    ema_svc  = get_ema_service()
    vol_est  = get_vol_estimator()
    spectrum = DirectionalSpectrum()
    log.info("All services ready.\n")

    # ── 3. State ───────────────────────────────────────────────────────────────
    portfolio    = initial_capital
    equity_curve = [{"candle": df_all.index[t_start].isoformat(), "equity": portfolio}]
    trades       = []
    daily_stats  = {}

    n_candles = t_end - t_start
    t0        = time.time()
    last_log  = t0
    n_errors  = 0
    n_skipped = 0

    # Exit type counters
    n_sl         = 0
    n_tp         = 0
    n_trail_tp   = 0
    n_time_exit  = 0
    n_insufficient = 0   # tidak cukup modal untuk posisi

    # ── 4. Candle Loop ─────────────────────────────────────────────────────────
    # Karena max hold = 1 candle, setiap candle:
    #   - Open: evaluate sinyal → nyatakan entry
    #   - next_candle OHLC: determine exit (SL, TP, TIME_EXIT)
    # Entry dan exit terjadi dalam 2 candle berurutan → tidak ada posisi terbuka
    # lebih dari 1 candle. Loop tidak perlu maintain "open position" state.

    for i in range(t_start, t_end):
        candle_dt   = df_all.index[i]
        next_candle = df_all.iloc[i + 1]

        # Stop trading jika modal tidak cukup untuk 1 posisi
        if portfolio < POSITION_USD:
            n_insufficient += 1
            break

        window_size = 500
        df_hist = df_all.iloc[max(0, i - window_size + 1) : i + 1].copy()

        price_now = float(df_hist["Close"].iloc[-1])
        atr14     = float(df_hist["ATR14"].dropna().iloc[-1]) if df_hist["ATR14"].dropna().size else 0.01
        ema20     = float(df_hist["EMA20"].dropna().iloc[-1]) if df_hist["EMA20"].dropna().size else price_now
        ema50     = float(df_hist["EMA50"].dropna().iloc[-1]) if df_hist["EMA50"].dropna().size else price_now

        # next candle OHLC (untuk exit simulation)
        next_open  = float(next_candle["Open"])
        next_high  = float(next_candle["High"])
        next_low   = float(next_candle["Low"])
        next_close = float(next_candle["Close"])

        # ── EMA Trend ──────────────────────────────────────────────────────────
        if ema20 > ema50 and price_now > ema20:
            raw_trend = "BULL"
        elif ema20 < ema50 and price_now < ema20:
            raw_trend = "BEAR"
        elif price_now > ema50:
            raw_trend = "BULL"
        else:
            raw_trend = "BEAR"

        # ── Signal Evaluation ──────────────────────────────────────────────────
        try:
            # L1: BCD
            label, tag, bcd_conf, hmm_states, hmm_index = \
                bcd_svc.get_regime_and_states(df_hist, funding_rate=0)
            l1_bull = (tag == "bull")
            l1_vote = float(bcd_conf if l1_bull else -bcd_conf)

            # L2: EMA Alignment
            l2_aligned, _, _ = ema_svc.get_alignment(df_hist, raw_trend)
            l2_vote = (
                1.0  if (l2_aligned and raw_trend == "BULL")
                else (-1.0 if (l2_aligned and raw_trend == "BEAR") else 0.0)
            )

            # L3: MLP AI
            ai_bias, ai_conf = ai_svc.get_confidence(
                df_hist, hmm_states=hmm_states, hmm_index=hmm_index
            )
            conf_norm = (max(50.0, min(100.0, float(ai_conf))) - 50.0) / 50.0
            l3_vote = conf_norm if str(ai_bias) == "BULL" else -conf_norm

            # L4: Volatility multiplier (untuk gate saja, bukan size)
            vol_ratio = atr14 / price_now if price_now > 0 else 0.001
            l4_mult   = spectrum.compute_l4_multiplier(vol_ratio)

            # Spectrum
            spec = spectrum.calculate(l1_vote, l2_vote, l3_vote, l4_mult, 5.0)

            # FGI sentiment check (dari v3 — hanya untuk gate)
            fgi_val = float(df_hist["FGI"].iloc[-1]) if "FGI" in df_hist.columns else 50.0

            # ── Trade Gate ─────────────────────────────────────────────────────
            if spec.trade_gate not in ("ACTIVE", "ADVISORY"):
                n_skipped += 1
                continue

            is_bull = spec.directional_bias >= 0
            side    = "LONG" if is_bull else "SHORT"

            # ── Fixed Trade Plan SL/TP ─────────────────────────────────────────
            if side == "LONG":
                sl         = price_now * (1.0 - SL_PCT)
                initial_tp = price_now * (1.0 + TP_MIN_PCT)
            else:
                sl         = price_now * (1.0 + SL_PCT)
                initial_tp = price_now * (1.0 - TP_MIN_PCT)

            # ── Simulate Exit on Next Candle ───────────────────────────────────
            exit_price, exit_type = simulate_exit(
                side       = side,
                entry      = price_now,
                sl         = sl,
                initial_tp = initial_tp,
                next_open  = next_open,
                next_high  = next_high,
                next_low   = next_low,
                next_close = next_close,
            )

            # ── PnL ────────────────────────────────────────────────────────────
            pnl = calc_pnl(side, price_now, exit_price)
            portfolio += pnl

            # Exit counters
            if exit_type == "SL":       n_sl       += 1
            elif exit_type == "TP":     n_tp       += 1
            elif exit_type == "TRAIL_TP": n_trail_tp += 1
            elif exit_type == "TIME_EXIT": n_time_exit += 1

            trade_log = {
                "entry_time"  : candle_dt.isoformat(),
                "exit_time"   : next_candle.name.isoformat(),
                "side"        : side,
                "entry_price" : round(price_now, 2),
                "exit_price"  : round(exit_price, 2),
                "sl"          : round(sl, 2),
                "initial_tp"  : round(initial_tp, 2),
                "pnl_usd"     : round(pnl, 2),
                "equity"      : round(portfolio, 2),
                "exit_type"   : exit_type,
                "gate"        : spec.trade_gate,
                "fgi"         : fgi_val,
                "regime"      : str(tag),
                "bcd_conf"    : round(float(bcd_conf), 4),
                "notional"    : NOTIONAL,
                "leverage"    : LEVERAGE,
                # Move metrics
                "entry_to_sl_pct"  : round(SL_PCT * 100, 3),
                "entry_to_tp_pct"  : round(TP_MIN_PCT * 100, 3),
                "actual_move_pct"  : round(
                    ((exit_price - price_now) / price_now * 100) if side == "LONG"
                    else ((price_now - exit_price) / price_now * 100),
                    4
                ),
            }
            trades.append(trade_log)
            equity_curve.append({
                "candle": next_candle.name.isoformat(),
                "equity": round(portfolio, 2),
            })

            d_key = candle_dt.date().isoformat()
            daily_stats.setdefault(d_key, {"pnl": 0.0, "n_trades": 0})
            daily_stats[d_key]["pnl"]      += pnl
            daily_stats[d_key]["n_trades"] += 1

            icon = "✅" if pnl > 0 else "❌"
            log.info(
                f"  🟢 OPEN  {side:5s} @ {price_now:,.0f} | "
                f"SL={sl:,.0f} TP={initial_tp:,.0f} | "
                f"regime={tag} bcd={bcd_conf:.2f} gate={spec.trade_gate}"
            )
            log.info(
                f"  {icon} CLOSE {side:5s} | {exit_type:10s} | "
                f"entry={price_now:,.0f} exit={exit_price:,.0f} "
                f"| PnL: {pnl:+.2f} | Equity: {portfolio:,.2f}"
            )

        except Exception as exc:
            n_errors += 1
            log.warning(f"  [ERROR] {candle_dt.date()} | {type(exc).__name__}: {exc}")
            continue

        # ── Progress heartbeat ─────────────────────────────────────────────────
        now = time.time()
        if now - last_log >= 10:
            pct       = (i - t_start) / max(n_candles, 1) * 100
            elapsed   = now - t0
            eta_s     = (elapsed / max(pct, 0.01)) * (100 - pct)
            pnl_total = portfolio - initial_capital
            log.info(
                f"  ▶ [{candle_dt.strftime('%Y-%m-%d')}] {pct:5.1f}%  "
                f"│ Equity: ${portfolio:>10,.0f}  "
                f"│ PnL: ${pnl_total:>+9,.0f}  "
                f"│ Trades: {len(trades):>4}  "
                f"│ ETA: {eta_s/60:.1f} min"
            )
            last_log = now

    # ══════════════════════════════════════════════════════════════════════════
    #  RESULTS
    # ══════════════════════════════════════════════════════════════════════════
    elapsed_total = time.time() - t0
    log.info("\n" + "═" * 72)
    log.info("  BACKTEST COMPLETE — v3 Fixed 15x Walk-Forward")
    log.info("═" * 72)

    tdf = pd.DataFrame(trades)
    if tdf.empty:
        log.warning("  No trades taken.")
        return

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

    eq           = pd.Series([e["equity"] for e in equity_curve])
    running_max  = eq.cummax()
    drawdown_pct = (eq - running_max) / running_max * 100
    max_dd       = abs(drawdown_pct.min()) if not drawdown_pct.empty else 0.0

    final_pnl  = portfolio - initial_capital
    final_pct  = (portfolio / initial_capital - 1) * 100
    n_days     = (pd.to_datetime(window_end) - pd.to_datetime(window_start)).days
    daily_ret  = final_pct / n_days if n_days > 0 else 0.0

    if daily_stats:
        dpnls  = pd.Series([v["pnl"] for v in daily_stats.values()])
        drets  = dpnls / initial_capital * 100
        sharpe = (drets.mean() / drets.std() * np.sqrt(365)) if drets.std() > 0 else 0.0
    else:
        sharpe = 0.0

    # Move stats
    avg_actual_move = tdf["actual_move_pct"].mean()
    median_move     = tdf["actual_move_pct"].median()

    exit_dist = tdf["exit_type"].value_counts().to_dict()

    # Regime breakdown
    regime_summary = {}
    for regime, grp in tdf.groupby("regime"):
        r_total = len(grp)
        r_wins  = (grp["pnl_usd"] > 0).sum()
        r_pnl   = grp["pnl_usd"].sum()
        regime_summary[regime] = {
            "trades": r_total,
            "win_rate": round(r_wins / r_total * 100, 1),
            "total_pnl": round(r_pnl, 2),
        }

    log.info(f"  Window        : {window_start}  →  {window_end}  ({n_days} days)")
    log.info(f"  Capital Start : ${initial_capital:>12,.2f}")
    log.info(f"  Capital End   : ${portfolio:>12,.2f}")
    log.info(f"  Net PnL       : ${final_pnl:>+12,.2f}  ({final_pct:+.2f}%)")
    log.info(f"  Daily Return  : {daily_ret:+.3f}%/day")
    log.info(f"  Trades        : {total}  (W:{wins}  L:{losses})  WR: {win_rate:.1f}%")
    log.info(f"  R:R Ratio     : 1 : {rr_ratio:.2f}  (avg_win: ${avg_win:.0f}  avg_loss: ${avg_loss:.0f})")
    log.info(f"  Profit Factor : {profit_fac:.3f}")
    log.info(f"  Max Drawdown  : {max_dd:.2f}%")
    log.info(f"  Sharpe Ratio  : {sharpe:.3f}")
    log.info(f"  Avg Move      : {avg_actual_move:+.3f}%  (median: {median_move:+.3f}%)")
    log.info( "  ── Exit Distribution ──")
    for et, cnt in sorted(exit_dist.items()):
        log.info(f"     {et:<12s}: {cnt:>4}  ({cnt/total*100:.1f}%)")
    log.info( "  ── Regime Breakdown ──")
    for r, rd in sorted(regime_summary.items()):
        log.info(f"     {r:<10s}: {rd['trades']:>3} trades  WR={rd['win_rate']:.1f}%  PnL=${rd['total_pnl']:+,.0f}")
    log.info(f"  Errors/Skipped : {n_errors} / {n_skipped}")
    if n_insufficient:
        log.info(f"  ⚠ Stopped early: insufficient capital after {len(trades)} trades")
    log.info(f"  Time taken     : {elapsed_total:.0f}s")
    log.info("═" * 72)

    # ── Kalibrasi Acceptance Criteria (Jan–Mar 2026 context) ──────────────────
    # Target dikalibrasi untuk $10k modal, periode 62 hari, $1k fixed position
    target_wr        = 46.0    # WR % minimum
    target_rr        = 1.24    # R:R minimum (sesuai spek)
    target_pf        = 1.3     # Profit Factor minimum
    target_dd        = 25.0    # Max DD tidak lebih dari 25%
    target_daily_ret = 0.3     # Daily return % minimum

    log.info("\n  ── Kalibrasi Acceptance Criteria (Jan–Mar 2026) ──")
    crit = [
        ("Win Rate ≥ 46%",          win_rate   >= target_wr,        f"{win_rate:.1f}%"),
        ("R:R ≥ 1.24",              rr_ratio   >= target_rr,        f"1:{rr_ratio:.2f}"),
        ("Profit Factor ≥ 1.3",     profit_fac >= target_pf,        f"{profit_fac:.3f}"),
        ("Max DD ≤ 25%",            max_dd     <= target_dd,        f"{max_dd:.2f}%"),
        ("Daily Return ≥ 0.3%",     daily_ret  >= target_daily_ret, f"{daily_ret:.3f}%"),
    ]
    for name, passed, detail in crit:
        status = "✅" if passed else "❌"
        log.info(f"     {status} {name}  ({detail})")

    # ── Save Results ───────────────────────────────────────────────────────────
    run_tag = f"v3_fixed15x_{window_start[:7].replace('-','')}_{window_end[:7].replace('-','')}_{run_ts}"

    tdf.to_csv(_RESULTS_DIR / f"{run_tag}_trades.csv", index=False)
    pd.DataFrame(equity_curve).to_csv(_RESULTS_DIR / f"{run_tag}_equity.csv", index=False)

    daily_df = pd.DataFrame([
        {"date": k, "pnl": v["pnl"], "n_trades": v["n_trades"]}
        for k, v in sorted(daily_stats.items())
    ])
    daily_df.to_csv(_RESULTS_DIR / f"{run_tag}_daily.csv", index=False)

    summary = {
        "run_timestamp"     : run_ts,
        "engine"            : "v3_fixed15x",
        "window_start"      : window_start,
        "window_end"        : window_end,
        "initial_capital"   : initial_capital,
        "final_equity"      : round(portfolio, 2),
        "net_pnl_usd"       : round(final_pnl, 2),
        "net_pnl_pct"       : round(final_pct, 4),
        "daily_return_pct"  : round(daily_ret, 4),
        "n_days"            : n_days,
        "n_trades"          : total,
        "n_wins"            : int(wins),
        "n_losses"          : int(losses),
        "win_rate_pct"      : round(win_rate, 2),
        "avg_winner_usd"    : round(avg_win, 2),
        "avg_loser_usd"     : round(avg_loss, 2),
        "rr_ratio"          : round(rr_ratio, 3),
        "profit_factor"     : round(profit_fac, 3),
        "max_drawdown_pct"  : round(max_dd, 2),
        "sharpe_ratio"      : round(sharpe, 3),
        "exit_distribution" : exit_dist,
        "n_sl"              : n_sl,
        "n_tp"              : n_tp,
        "n_trail_tp"        : n_trail_tp,
        "n_time_exits"      : n_time_exit,
        "regime_summary"    : regime_summary,
        "avg_actual_move_pct": round(float(avg_actual_move), 4),
        "position_usd"      : POSITION_USD,
        "leverage"          : LEVERAGE,
        "notional_usd"      : NOTIONAL,
        "sl_pct"            : SL_PCT,
        "tp_min_pct"        : TP_MIN_PCT,
        "fee_usd_per_trade" : FEE_USD,
        "n_skipped"         : n_skipped,
        "n_errors"          : n_errors,
        "elapsed_seconds"   : round(elapsed_total, 1),
    }

    summary_path = _RESULTS_DIR / f"{run_tag}_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    log.info(f"\n  [✓] Trades  → {run_tag}_trades.csv")
    log.info(f"  [✓] Equity  → {run_tag}_equity.csv")
    log.info(f"  [✓] Daily   → {run_tag}_daily.csv")
    log.info(f"  [✓] Summary → {summary_path.name}")
    log.info(f"  [✓] Log     → {_LOG_FILE.name}")


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRYPOINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="BTC-Quant v3 Fixed 15x Walk-Forward Engine"
    )
    parser.add_argument("--start",   default="2024-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end",     default="2026-03-04", help="End date   YYYY-MM-DD")
    parser.add_argument("--capital", default=10000.0,      type=float, help="Initial capital USD")
    parser.add_argument("--history", default=400,          type=int,   help="Warmup candles")
    args = parser.parse_args()

    run_fixed15x_walkforward(
        window_start     = args.start,
        window_end       = args.end,
        required_history = args.history,
        initial_capital  = args.capital,
    )
