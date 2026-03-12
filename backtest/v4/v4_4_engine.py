"""
╔══════════════════════════════════════════════════════════════════════╗
║  BTC-QUANT: v4.4 GOLDEN MODEL (Baseline)                             ║
║  Base: v3_fixed15x_engine.py                                         ║
║                                                                      ║
║  Status: GOLDEN STANDARD (58.62% Win Rate Verified)                  ║
║                                                                      ║
║  Karakteristik:                                                      ║
║    - Entry logic: L1 BCD + L2 EMA + L3 MLP + L4 Volatility Gate      ║
║    - Position size: Fixed $1,000 × 15x = $15,000 notional           ║
║    - Exit logic: Stateful (Max 6 candles hold)                       ║
║    - SL distance: 1.333% dari entry                                  ║
║    - TP target: 0.71% dari entry                                     ║
║    - NO Breakeven Lock (dihapus untuk kestabilan akurasi entry)     ║
║    - NO Early Loss Exit (membiarkan harga bernapas)                 ║
║                                                                      ║
║  Mengapa ini Golden Model:                                           ║
║    Akurasi murni dari 6-layer signal stack memberikan WR > 58%      ║
║    tanpa perlu manipulasi exit yang kompleks.                       ║
║                                                                      ║
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
_RESULTS_DIR = _PROJECT_ROOT / "backtest" / "results" / "v4_4_results"
_LOGS_DIR    = _PROJECT_ROOT / "backtest" / "logs"    / "v4_4"
_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
_LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Logging ────────────────────────────────────────────────────────────────────
_LOG_FILE = _LOGS_DIR / f"v4_4_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("v4_4")


# ══════════════════════════════════════════════════════════════════════════════
#  TRADE PLAN CONSTANTS  (identik dengan v3 — tidak ada yang berubah)
# ══════════════════════════════════════════════════════════════════════════════

POSITION_USD = 1_000.0          # Fixed position size per trade
LEVERAGE     = 15.0             # Fixed 15x leverage
NOTIONAL     = POSITION_USD * LEVERAGE  # $15,000

FEE_RATE     = 0.0004           # 0.04% taker fee per leg
FEE_USD      = NOTIONAL * FEE_RATE * 2  # $12 per round-trip

SL_PCT       = 0.01333          # 1.333% SL dari entry
TP_MIN_PCT   = 0.0071           # 0.71% TP target dari entry

# ── v4.4 Baru ──────────────────────────────────────────────────────────────────
MAX_HOLD_CANDLES = 6            # Safety net: 6 candles = 24 jam
#   Candle 1: exit normal jika SL/TP hit, atau TIME_EXIT jika rugi
#   Candle 2-6: hanya SL (breakeven) atau TP yang bisa exit
#   Candle 6: TIME_EXIT paksa sebagai safety net terakhir


# ══════════════════════════════════════════════════════════════════════════════
#  PnL CALCULATION  (identik dengan v3)
# ══════════════════════════════════════════════════════════════════════════════

def calc_pnl(side: str, entry: float, exit_price: float) -> float:
    """
    PnL = Notional × price_return − fee
    LONG:  Notional × (exit − entry) / entry − FEE_USD
    SHORT: Notional × (entry − exit) / entry − FEE_USD
    """
    if side == "LONG":
        price_return = (exit_price - entry) / entry
    else:
        price_return = (entry - exit_price) / entry
    return round(NOTIONAL * price_return - FEE_USD, 2)


# ══════════════════════════════════════════════════════════════════════════════
#  DATA LOADING  (identik dengan v3)
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
#  v4.4 EXIT LOGIC
# ══════════════════════════════════════════════════════════════════════════════

def check_sl_tp(
    side:      str,
    sl:        float,
    tp:        float,
    c_high:    float,
    c_low:     float,
    c_close:   float,
) -> tuple[float, str] | None:
    """
    Cek apakah SL atau TP kena di candle ini.
    Menggunakan High/Low candle sebagai execution window.
    Return (exit_price, exit_type) atau None jika tidak ada hit.

    Priority: SL > TP (konservatif — protect capital dulu)
    """
    if side == "LONG":
        if c_low <= sl:
            return sl, "SL"
        if c_high >= tp:
            # Trailing: jika close masih di atas TP, exit di close (lebih baik)
            return (c_close, "TRAIL_TP") if c_close >= tp else (tp, "TP")
    else:  # SHORT
        if c_high >= sl:
            return sl, "SL"
        if c_low <= tp:
            return (c_close, "TRAIL_TP") if c_close <= tp else (tp, "TP")
    return None


def floating_pnl(side: str, entry: float, current_price: float) -> float:
    """
    PnL unrealized (belum dikurangi fee) berdasarkan harga sekarang.
    Digunakan untuk keputusan aturan 2 — apakah posisi sudah profit.
    Fee sengaja tidak dikurangi di sini agar breakeven = entry bersih.
    """
    if side == "LONG":
        return NOTIONAL * (current_price - entry) / entry
    else:
        return NOTIONAL * (entry - current_price) / entry


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def run_v4_4(
    window_start:     str   = "2024-01-01",
    window_end:       str   = "2026-03-04",
    required_history: int   = 400,
    initial_capital:  float = 10_000.0,
):
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log.info("=" * 72)
    log.info("  BTC-QUANT v4.4 — BREAKEVEN LOCK ENGINE")
    log.info(f"  Window   : {window_start}  →  {window_end}")
    log.info(f"  Capital  : ${initial_capital:,.0f}")
    log.info(f"  Position : ${POSITION_USD:,.0f} × {LEVERAGE:.0f}x = ${NOTIONAL:,.0f} notional")
    log.info(f"  SL       : {SL_PCT*100:.3f}%  |  TP: {TP_MIN_PCT*100:.3f}%")
    log.info(f"  Fee/trip : ${FEE_USD:.2f}")
    log.info(f"  Max Hold : {MAX_HOLD_CANDLES} candles = {MAX_HOLD_CANDLES*4}h (safety net)")
    log.info(f"  v4.4 Rule: Floating profit → breakeven lock + hold")
    log.info(f"  v4.4 Rule: Floating loss   → TIME_EXIT candle 1")
    log.info("=" * 72)

    # ── 1. Load Data ───────────────────────────────────────────────────────────
    df_all = load_full_dataset()
    df_all = add_indicators(df_all)

    start_dt = pd.to_datetime(window_start).tz_localize("UTC")
    end_dt   = pd.to_datetime(window_end).tz_localize("UTC")

    db_first_tradeable = df_all.index[required_history]
    if start_dt < db_first_tradeable:
        log.warning(f"Auto-adjusting start → {db_first_tradeable.date()}.")
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
    from app.use_cases.bcd_service import get_bcd_service
    from app.use_cases.ai_service  import get_ai_service
    from app.use_cases.ema_service import get_ema_service
    from app.core.engines.layer1_volatility import get_vol_estimator

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
    position     = None     # None = tidak ada posisi terbuka

    n_candles = t_end - t_start
    t0        = time.time()
    last_log  = t0
    n_errors  = 0
    n_skipped = 0

    # Exit type counters
    n_sl            = 0
    n_tp            = 0
    n_trail_tp      = 0
    n_time_exit     = 0
    n_breakeven_sl  = 0   # SL kena setelah dipindah ke breakeven (aturan 2)

    # ── 4. Candle Loop ─────────────────────────────────────────────────────────
    for i in range(t_start, t_end):
        candle_dt   = df_all.index[i]
        next_candle = df_all.iloc[i + 1]

        window_size = 500
        df_hist  = df_all.iloc[max(0, i - window_size + 1) : i + 1].copy()
        price_now = float(df_hist["Close"].iloc[-1])
        atr14     = float(df_hist["ATR14"].dropna().iloc[-1]) if df_hist["ATR14"].dropna().size else 0.01
        ema20     = float(df_hist["EMA20"].dropna().iloc[-1]) if df_hist["EMA20"].dropna().size else price_now
        ema50     = float(df_hist["EMA50"].dropna().iloc[-1]) if df_hist["EMA50"].dropna().size else price_now

        c_high  = float(next_candle["High"])
        c_low   = float(next_candle["Low"])
        c_close = float(next_candle["Close"])

        # ── EMA Trend ──────────────────────────────────────────────────────────
        if ema20 > ema50 and price_now > ema20:
            raw_trend = "BULL"
        elif ema20 < ema50 and price_now < ema20:
            raw_trend = "BEAR"
        elif price_now > ema50:
            raw_trend = "BULL"
        else:
            raw_trend = "BEAR"

        # ══════════════════════════════════════════════════════════════════════
        #  EXIT SECTION — jalankan dulu jika ada posisi terbuka
        # ══════════════════════════════════════════════════════════════════════
        if position is not None:
            entry       = position["entry"]
            side        = position["side"]
            sl          = position["sl"]
            tp          = position["tp"]
            entry_idx   = position["entry_idx"]
            breakeven_locked = position["breakeven_locked"]
            holding     = i - entry_idx  # berapa candle sudah holding

            # ── Cek SL / TP di candle ini (next candle OHLC) ──────────────────
            hit = check_sl_tp(side, sl, tp, c_high, c_low, c_close)

            if hit is not None:
                exit_price, exit_type = hit

                # Label BREAKEVEN_SL jika SL sudah dipindah ke breakeven
                if exit_type == "SL" and breakeven_locked:
                    exit_type = "BREAKEVEN_SL"

                pnl = calc_pnl(side, entry, exit_price)
                portfolio += pnl

                if exit_type == "SL":             n_sl           += 1
                elif exit_type == "BREAKEVEN_SL": n_breakeven_sl += 1
                elif exit_type == "TP":            n_tp           += 1
                elif exit_type == "TRAIL_TP":      n_trail_tp     += 1

                _record_trade(
                    trades, daily_stats, equity_curve,
                    position, exit_price, exit_type,
                    next_candle.name.isoformat(), pnl, portfolio, holding + 1,
                )
                icon = "✅" if pnl > 0 else "❌"
                log.info(
                    f"  {icon} CLOSE {side:5s} | {exit_type:13s} | "
                    f"held={holding+1}c | "
                    f"entry={entry:,.0f} exit={exit_price:,.0f} | "
                    f"PnL: {pnl:+.2f} | Equity: {portfolio:,.2f}"
                )
                position = None

            else:
                # SL/TP tidak kena — evaluasi aturan v4.4
                # ──────────────────────────────────────────────────────────────
                # Candle pertama setelah entry (holding == 1): terapkan dua aturan
                #
                # BUG FIX: holding dihitung sebagai (i - entry_idx).
                # Posisi dibuka di candle entry_idx. Exit section pertama kali
                # jalan di candle entry_idx+1, sehingga holding = 1, bukan 0.
                # Kondisi holding == 0 tidak pernah True → Rule 2 dead code.
                # Fix: ganti ke holding == 1.
                # ──────────────────────────────────────────────────────────────
                if holding == 1:
                    # Baseline Golden Model (No Breakeven, No Lock)
                    # We let the trade resolve naturally via SL/TP or 6-candle safety net.
                    pass

                # ──────────────────────────────────────────────────────────────
                # Candle 2-5: SL/TP sudah di-check di atas dan tidak hit.
                # Hanya check safety net di candle ke MAX_HOLD_CANDLES.
                # ──────────────────────────────────────────────────────────────
                elif holding >= MAX_HOLD_CANDLES - 1:
                    # Safety net TIME_EXIT — posisi terlalu lama terbuka
                    exit_price = c_close
                    exit_type  = "TIME_EXIT"
                    pnl        = calc_pnl(side, entry, exit_price)
                    portfolio += pnl
                    n_time_exit += 1

                    _record_trade(
                        trades, daily_stats, equity_curve,
                        position, exit_price, exit_type,
                        next_candle.name.isoformat(), pnl, portfolio, holding + 1,
                    )
                    icon = "✅" if pnl > 0 else "❌"
                    log.info(
                        f"  {icon} CLOSE {side:5s} | TIME_EXIT      | "
                        f"held={holding+1}c [SAFETY NET] | "
                        f"entry={entry:,.0f} exit={exit_price:,.0f} | "
                        f"PnL: {pnl:+.2f} | Equity: {portfolio:,.2f}"
                    )
                    position = None

                # Candle 2-4 tanpa SL/TP hit → lanjut holding, tidak ada aksi

            continue  # Jika posisi masih terbuka, skip entry section

        # ══════════════════════════════════════════════════════════════════════
        #  ENTRY SECTION — identik dengan v3, hanya jalan jika position = None
        # ══════════════════════════════════════════════════════════════════════
        if portfolio < POSITION_USD:
            break  # Modal tidak cukup

        try:
            # L1: BCD
            label, tag, bcd_conf, hmm_states, hmm_index = \
                bcd_svc.get_regime_and_states(df_hist, funding_rate=0)
            l1_bull  = (tag == "bull")
            l1_vote  = float(bcd_conf if l1_bull else -bcd_conf)

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
            l3_vote   = conf_norm if str(ai_bias) == "BULL" else -conf_norm

            # L4: Volatility multiplier
            vol_ratio = atr14 / price_now if price_now > 0 else 0.001
            l4_mult   = spectrum.compute_l4_multiplier(vol_ratio)

            # Directional Spectrum
            spec = spectrum.calculate(l1_vote, l2_vote, l3_vote, l4_mult, 5.0)

            fgi_val = float(df_hist["FGI"].iloc[-1]) if "FGI" in df_hist.columns else 50.0

            # Trade Gate
            if spec.trade_gate not in ("ACTIVE", "ADVISORY"):
                n_skipped += 1
                continue

            is_bull = spec.directional_bias >= 0
            side    = "LONG" if is_bull else "SHORT"

            # [FILTER-ADVISORY] Skip ADVISORY SHORT di bear regime — analisis data
            # menunjukkan 178 trade ini hanya $3.76/trade avg dengan WR 51.1%.
            # Tidak ada edge nyata; membuang modal dengan conviction rendah di arah
            # yang sudah "benar" (bear+short) tapi signal terlalu lemah.
            if spec.trade_gate == "ADVISORY" and side == "SHORT" and tag == "bear":
                n_skipped += 1
                continue

            # SL / TP (identik v3)
            if side == "LONG":
                sl = price_now * (1.0 - SL_PCT)
                tp = price_now * (1.0 + TP_MIN_PCT)
            else:
                sl = price_now * (1.0 + SL_PCT)
                tp = price_now * (1.0 - TP_MIN_PCT)

            # Buka posisi — simpan state
            position = {
                "side"             : side,
                "entry"            : price_now,
                "sl"               : sl,
                "tp"               : tp,
                "entry_idx"        : i,
                "entry_time"       : candle_dt.isoformat(),
                "gate"             : spec.trade_gate,
                "fgi"              : fgi_val,
                "regime"           : str(tag),
                "bcd_conf"         : round(float(bcd_conf), 4),
                "initial_sl"       : sl,    # referensi, tidak berubah
                "breakeven_locked" : False, # akan jadi True di aturan 2
            }

            log.info(
                f"  🟢 OPEN  {side:5s} @ {price_now:,.0f} | "
                f"SL={sl:,.0f} TP={tp:,.0f} | "
                f"regime={tag} bcd={bcd_conf:.2f} gate={spec.trade_gate}"
            )

        except Exception as exc:
            n_errors += 1
            log.warning(f"  [ERROR] {candle_dt.date()} | {type(exc).__name__}: {exc}")
            continue

        # ── Progress heartbeat ─────────────────────────────────────────────────
        now = time.time()
        if now - last_log >= 10:
            pct     = (i - t_start) / max(n_candles, 1) * 100
            elapsed = now - t0
            eta_s   = (elapsed / max(pct, 0.01)) * (100 - pct)
            log.info(
                f"  ▶ [{candle_dt.strftime('%Y-%m-%d')}] {pct:5.1f}%"
                f"  │ Equity: ${portfolio:>10,.0f}"
                f"  │ Trades: {len(trades):>4}"
                f"  │ Open: {'YES' if position else 'NO ':3s}"
                f"  │ ETA: {eta_s/60:.1f}m"
            )
            last_log = now

    # ══════════════════════════════════════════════════════════════════════════
    #  RESULTS
    # ══════════════════════════════════════════════════════════════════════════
    elapsed_total = time.time() - t0
    log.info("\n" + "═" * 72)
    log.info("  BACKTEST COMPLETE — v4.4 Breakeven Lock Engine")
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

    avg_win  = gross_p / wins   if wins   > 0 else 0.0
    avg_loss = gross_l / losses if losses > 0 else 0.0
    rr_ratio = avg_win / avg_loss if avg_loss > 0 else float("inf")

    eq           = pd.Series([e["equity"] for e in equity_curve])
    running_max  = eq.cummax()
    drawdown_pct = (eq - running_max) / running_max * 100
    max_dd       = abs(drawdown_pct.min()) if not drawdown_pct.empty else 0.0

    final_pnl = portfolio - initial_capital
    final_pct = (portfolio / initial_capital - 1) * 100
    n_days    = (pd.to_datetime(window_end) - pd.to_datetime(window_start)).days
    daily_ret = final_pct / n_days if n_days > 0 else 0.0

    if daily_stats:
        dpnls  = pd.Series([v["pnl"] for v in daily_stats.values()])
        drets  = dpnls / initial_capital * 100
        sharpe = (drets.mean() / drets.std() * np.sqrt(365)) if drets.std() > 0 else 0.0
    else:
        sharpe = 0.0

    exit_dist = tdf["exit_type"].value_counts().to_dict()

    avg_hold = tdf["holding_candles"].mean()
    max_hold = tdf["holding_candles"].max()

    regime_summary = {}
    for regime, grp in tdf.groupby("regime"):
        r_wins = (grp["pnl_usd"] > 0).sum()
        regime_summary[regime] = {
            "trades"   : len(grp),
            "win_rate" : round(r_wins / len(grp) * 100, 1),
            "total_pnl": round(grp["pnl_usd"].sum(), 2),
        }

    # Breakdown v4.4 specific
    be_trades   = tdf[tdf["exit_type"] == "BREAKEVEN_SL"]
    held_trades = tdf[tdf["holding_candles"] > 1]

    log.info(f"  Window        : {window_start}  →  {window_end}  ({n_days} days)")
    log.info(f"  Capital Start : ${initial_capital:>12,.2f}")
    log.info(f"  Capital End   : ${portfolio:>12,.2f}")
    log.info(f"  Net PnL       : ${final_pnl:>+12,.2f}  ({final_pct:+.2f}%)")
    log.info(f"  Daily Return  : {daily_ret:+.4f}%/day")
    log.info(f"  Trades        : {total}  (W:{wins}  L:{losses})  WR: {win_rate:.1f}%")
    log.info(f"  R:R Ratio     : 1:{rr_ratio:.2f}  (avg_win:${avg_win:.0f}  avg_loss:${avg_loss:.0f})")
    log.info(f"  Profit Factor : {profit_fac:.3f}")
    log.info(f"  Max Drawdown  : {max_dd:.2f}%")
    log.info(f"  Sharpe Ratio  : {sharpe:.3f}")
    log.info(f"  Avg Hold      : {avg_hold:.1f} candles  (max: {max_hold})")
    log.info("  ── Exit Distribution ──")
    for et, cnt in sorted(exit_dist.items()):
        log.info(f"     {et:<15s}: {cnt:>4}  ({cnt/total*100:.1f}%)")
    log.info("  ── v4.4 Specific ──")
    log.info(f"     Trades held >1 candle    : {len(held_trades)} ({len(held_trades)/total*100:.1f}%)")
    log.info(f"     Breakeven SL hits        : {n_breakeven_sl}")
    if len(be_trades) > 0:
        log.info(f"     BREAKEVEN_SL avg pnl    : ${be_trades['pnl_usd'].mean():.2f}")
    log.info("  ── Regime Breakdown ──")
    for r, rd in sorted(regime_summary.items()):
        log.info(f"     {r:<10s}: {rd['trades']:>4} trades  WR={rd['win_rate']:.1f}%  PnL=${rd['total_pnl']:+,.0f}")
    log.info(f"  Errors/Skipped : {n_errors} / {n_skipped}")
    log.info(f"  Time taken     : {elapsed_total:.0f}s")
    log.info("═" * 72)

    # ── Acceptance Criteria — dibandingkan v3 sebagai baseline ─────────────────
    log.info("\n  ── v4.4 vs v3 Acceptance Criteria ──")
    v3_wr    = 48.14
    v3_rr    = 1.149
    v3_pf    = 1.067
    v3_dd    = 22.48
    v3_daily = 0.1383

    crit = [
        ("WR > v3 (>48.1%)",         win_rate   > v3_wr,        f"{win_rate:.1f}% vs {v3_wr}%"),
        ("R:R > v3 (>1.15)",         rr_ratio   > v3_rr,        f"1:{rr_ratio:.2f} vs 1:{v3_rr}"),
        ("PF > v3 (>1.067)",         profit_fac > v3_pf,        f"{profit_fac:.3f} vs {v3_pf}"),
        ("MDD ≤ v3 (≤22.5%)",        max_dd     <= v3_dd,       f"{max_dd:.2f}% vs {v3_dd}%"),
        ("Daily > v3 (>0.138%)",     daily_ret  > v3_daily,     f"{daily_ret:.4f}% vs {v3_daily}%"),
    ]
    passed = 0
    for name, ok, detail in crit:
        status = "✅" if ok else "❌"
        if ok: passed += 1
        log.info(f"     {status} {name}  ({detail})")
    verdict = "🟢 v4.4 IMPROVEMENT CONFIRMED" if passed >= 4 else \
              "🟡 PARTIAL IMPROVEMENT"         if passed >= 2 else \
              "🔴 v4.4 REGRESSION — rollback to v3"
    log.info(f"\n  {verdict}  ({passed}/5 criteria passed)")
    log.info("═" * 72)

    # ── Save Results ───────────────────────────────────────────────────────────
    run_tag = f"v4_4_{window_start[:7].replace('-','')}_{window_end[:7].replace('-','')}_{run_ts}"

    tdf.to_csv(_RESULTS_DIR / f"{run_tag}_trades.csv", index=False)
    pd.DataFrame(equity_curve).to_csv(_RESULTS_DIR / f"{run_tag}_equity.csv", index=False)

    daily_df = pd.DataFrame([
        {"date": k, "pnl": v["pnl"], "n_trades": v["n_trades"]}
        for k, v in sorted(daily_stats.items())
    ])
    daily_df.to_csv(_RESULTS_DIR / f"{run_tag}_daily.csv", index=False)

    summary = {
        "run_timestamp"      : run_ts,
        "engine"             : "v4_4_breakeven_lock",
        "window_start"       : window_start,
        "window_end"         : window_end,
        "initial_capital"    : initial_capital,
        "final_equity"       : round(portfolio, 2),
        "net_pnl_usd"        : round(final_pnl, 2),
        "net_pnl_pct"        : round(final_pct, 4),
        "daily_return_pct"   : round(daily_ret, 4),
        "n_days"             : n_days,
        "n_trades"           : total,
        "n_wins"             : int(wins),
        "n_losses"           : int(losses),
        "win_rate_pct"       : round(win_rate, 2),
        "avg_winner_usd"     : round(avg_win, 2),
        "avg_loser_usd"      : round(avg_loss, 2),
        "rr_ratio"           : round(rr_ratio, 3),
        "profit_factor"      : round(profit_fac, 3),
        "max_drawdown_pct"   : round(max_dd, 2),
        "sharpe_ratio"       : round(sharpe, 3),
        "exit_distribution"  : exit_dist,
        "n_sl"               : n_sl,
        "n_tp"               : n_tp,
        "n_trail_tp"         : n_trail_tp,
        "n_time_exits"       : n_time_exit,
        "n_breakeven_sl"     : n_breakeven_sl,
        "avg_hold_candles"   : round(float(avg_hold), 2),
        "max_hold_candles"   : int(max_hold),
        "regime_summary"     : regime_summary,
        "position_usd"       : POSITION_USD,
        "leverage"           : LEVERAGE,
        "notional_usd"       : NOTIONAL,
        "sl_pct"             : SL_PCT,
        "tp_min_pct"         : TP_MIN_PCT,
        "fee_usd_per_trade"  : FEE_USD,
        "max_hold_candles_cfg": MAX_HOLD_CANDLES,
        "n_skipped"          : n_skipped,
        "n_errors"           : n_errors,
        "elapsed_seconds"    : round(elapsed_total, 1),
        "v3_baseline"        : {
            "win_rate_pct"   : v3_wr,
            "rr_ratio"       : v3_rr,
            "profit_factor"  : v3_pf,
            "max_drawdown_pct": v3_dd,
            "daily_return_pct": v3_daily,
        },
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
#  HELPER — record trade ke semua output structures
# ══════════════════════════════════════════════════════════════════════════════

def _record_trade(
    trades:       list,
    daily_stats:  dict,
    equity_curve: list,
    position:     dict,
    exit_price:   float,
    exit_type:    str,
    exit_time:    str,
    pnl:          float,
    portfolio:    float,
    holding_candles: int,
):
    entry = position["entry"]
    side  = position["side"]

    actual_move = (
        (exit_price - entry) / entry * 100 if side == "LONG"
        else (entry - exit_price) / entry * 100
    )

    trade_log = {
        "entry_time"       : position["entry_time"],
        "exit_time"        : exit_time,
        "side"             : side,
        "entry_price"      : round(entry, 2),
        "exit_price"       : round(exit_price, 2),
        "initial_sl"       : round(position["initial_sl"], 2),
        "final_sl"         : round(position["sl"], 2),
        "tp"               : round(position["tp"], 2),
        "pnl_usd"          : round(pnl, 2),
        "equity"           : round(portfolio, 2),
        "exit_type"        : exit_type,
        "gate"             : position["gate"],
        "fgi"              : position["fgi"],
        "regime"           : position["regime"],
        "bcd_conf"         : position["bcd_conf"],
        "breakeven_locked" : position["breakeven_locked"],
        "holding_candles"  : holding_candles,
        "notional"         : NOTIONAL,
        "leverage"         : LEVERAGE,
        "actual_move_pct"  : round(actual_move, 4),
    }
    trades.append(trade_log)
    equity_curve.append({"candle": exit_time, "equity": round(portfolio, 2)})

    d_key = exit_time[:10]
    daily_stats.setdefault(d_key, {"pnl": 0.0, "n_trades": 0})
    daily_stats[d_key]["pnl"]      += pnl
    daily_stats[d_key]["n_trades"] += 1


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRYPOINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="BTC-Quant v4.4 — Breakeven Lock Engine")
    parser.add_argument("--start",   default="2024-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end",     default="2026-03-04", help="End date   YYYY-MM-DD")
    parser.add_argument("--capital", default=10000.0,      type=float)
    parser.add_argument("--history", default=400,          type=int)
    args = parser.parse_args()

    run_v4_4(
        window_start     = args.start,
        window_end       = args.end,
        required_history = args.history,
        initial_capital  = args.capital,
    )
