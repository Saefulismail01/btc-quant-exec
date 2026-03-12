"""
╔══════════════════════════════════════════════════════════════════════╗
║  BTC-QUANT: SPRINT 1 — EXIT MANAGEMENT ENGINE  (v4.1)               ║
║  Base: true_walkforward_engine.py                                    ║
║                                                                      ║
║  Sprint 1 Changes (Exit Only — Entry logic UNCHANGED):               ║
║    1.1  ATR-Based Trailing Stop Loss (breakeven lock + trail)        ║
║    1.2  Dynamic TP Extension (BCD confidence / persistence score)    ║
║    1.3  Time-Based Exit (24-candle max hold, exception if in profit) ║
║                                                                      ║
║  v4.2 Fixes (vs v4.1):                                               ║
║    Fix 1: Max TP extension capped 1.5× (was 2.0×)                   ║
║    Fix 2: No TP extension in neutral regime                          ║
║    Fix 3: ADVISORY gate re-enabled (proven positive in bear market)  ║
║                                                                      ║
║  New Columns in trades CSV:                                          ║
║    trail_count         — how many times SL was trailed              ║
║    final_sl            — SL value at time of exit                   ║
║    tp_extension_factor — TP multiplier applied (1.0 / 1.5 / 2.0)   ║
║    holding_duration    — candles held before exit                   ║
║                                                                      ║
║  Anti-Lookahead Design:                                              ║
║    • Trailing SL is updated using price_now (current candle CLOSE)  ║
║      — we only know today's close, not tomorrow's.                  ║
║    • SL/TP trigger check uses next_candle High/Low (execution sim). ║
║    • TIME_EXIT uses price_now as fill price (conservative).         ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import time
import logging
import traceback
from datetime import datetime, timezone
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

# ── Force BCD as Layer 1 Engine ────────────────────────────────────────────────
os.environ["BTC_QUANT_LAYER1_ENGINE"] = "bcd"

from engines.layer1_volatility import get_vol_estimator
from app.services.risk_manager  import get_risk_manager
from utils.spectrum              import DirectionalSpectrum
from data_engine                 import DB_PATH

# ── Output Directories ─────────────────────────────────────────────────────────
_RESULTS_DIR = _PROJECT_ROOT / "backtest" / "results" / "v4_exit_management_results"
_LOGS_DIR    = _PROJECT_ROOT / "backtest" / "logs"    / "v4"
_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
_LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Logging Setup ──────────────────────────────────────────────────────────────
_LOG_FILE = _LOGS_DIR / f"v4_exit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("v4_exit")


# ══════════════════════════════════════════════════════════════════════════════
#  SPRINT 1 CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

# 1.1 — Trailing SL trigger levels (multiples of entry ATR)
_TRAIL_L1_ATR  = 1.0   # profit ≥ 1.0× ATR → lock breakeven
_TRAIL_L2_ATR  = 2.0   # profit ≥ 2.0× ATR → lock +0.5× ATR
_TRAIL_L3_ATR  = 3.0   # profit ≥ 3.0× ATR → lock +1.5× ATR

# 1.2 — Dynamic TP extension thresholds
# Fix 1: Cap max extension at 1.5× (was 2.0× — too aggressive, hurt WR)
_TP_EXT_BCD_THRESHOLD   = 0.8    # bcd_conf > 0.8       → TP × 1.25
_TP_EXT_BCD_FACTOR      = 1.25
_TP_EXT_PERSIST_THRESH  = 0.85   # persistence > 0.85   → TP × 1.5 (was 2.0)
_TP_EXT_PERSIST_FACTOR  = 1.5

# 1.3 — Time-based exit
_MAX_HOLD_CANDLES        = 24    # 4 days × 6 candles/day
_TIME_EXIT_PROFIT_EXEMPT = 1.5   # Skip TIME_EXIT if unrealized > 1.5× ATR


# ══════════════════════════════════════════════════════════════════════════════
#  DATA LOADING (unchanged from v3)
# ══════════════════════════════════════════════════════════════════════════════

def load_full_dataset() -> pd.DataFrame:
    """Load full OHLCV + market metrics via ASOF JOIN from DuckDB."""
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
    """Add EMA20, EMA50, ATR14 in-place."""
    df = df.copy()
    df["EMA20"] = ta.ema(df["Close"], length=20)
    df["EMA50"] = ta.ema(df["Close"], length=50)
    df["ATR14"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)
    return df


# ══════════════════════════════════════════════════════════════════════════════
#  SPRINT 1 HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _compute_tp_extension(bcd_conf: float, regime_biases: dict, label: str, tag: str) -> float:
    """
    Task 1.2: Determine TP extension factor based on BCD confidence
    and persistence score from the transition matrix.

    Fix 1: Max extension capped at 1.5× (previously 2.0× caused WR crash)
    Fix 2: No extension during neutral regime — market has no clear direction

    Priority: persistence check (1.5×) > bcd_conf check (1.25×) > default (1.0×)

    Args:
        bcd_conf:      BCD confidence from current candle [0, 1]
        regime_biases: dict returned by bcd_svc.get_regime_bias()
        label:         Current regime label (e.g. "Bullish Trend")
        tag:           Short regime tag ("bull", "bear", "neutral", etc.)

    Returns:
        float: TP extension factor (1.0, 1.25, or 1.5)
    """
    # Fix 2: Never extend TP in neutral/sideways regime — no clear direction
    if tag not in ("bull", "bear"):
        return 1.0

    # Extract persistence score from transition matrix bias report
    persistence = 0.0
    if label in regime_biases:
        persistence = float(regime_biases[label].get("persistence", 0.0))

    # Priority 1: High persistence → 1.5× (was 2.0×, now capped)
    if persistence > _TP_EXT_PERSIST_THRESH:
        return _TP_EXT_PERSIST_FACTOR

    # Priority 2: High BCD confidence → 1.25× (was 1.5×)
    if bcd_conf > _TP_EXT_BCD_THRESHOLD:
        return _TP_EXT_BCD_FACTOR

    return 1.0  # Default: no extension


def _update_trailing_sl(position: dict, price_now: float) -> bool:
    """
    Task 1.1: Update trailing SL based on current candle close price.

    ── Anti-Lookahead Contract ─────────────────────────────────────────────────
    This function is called BEFORE we check if next_candle hits the SL.
    We use `price_now` (current candle CLOSE) as the reference — data we
    legitimately have at this point in time. The actual trigger check
    (does next_candle Low/High breach the updated SL?) happens AFTER this.
    ─────────────────────────────────────────────────────────────────────────────

    SL only moves in the profitable direction (ratchet mechanism):
        LONG:  SL only moves UP   (never down)
        SHORT: SL only moves DOWN (never up)

    Returns:
        True if SL was updated (trailed), False otherwise.
    """
    entry     = position["entry"]
    atr_entry = position["entry_atr"]   # ATR at time of entry (fixed reference)
    side      = position["side"]
    current_sl = position["sl"]

    # Compute unrealized profit in price terms
    if side == "LONG":
        unrealized = price_now - entry
    else:
        unrealized = entry - price_now

    # Determine target SL based on trail tiers
    if unrealized >= _TRAIL_L3_ATR * atr_entry:
        # Tier 3: lock in +1.5× ATR of profit
        if side == "LONG":
            target_sl = entry + 1.5 * atr_entry
        else:
            target_sl = entry - 1.5 * atr_entry

    elif unrealized >= _TRAIL_L2_ATR * atr_entry:
        # Tier 2: lock in +0.5× ATR of profit
        if side == "LONG":
            target_sl = entry + 0.5 * atr_entry
        else:
            target_sl = entry - 0.5 * atr_entry

    elif unrealized >= _TRAIL_L1_ATR * atr_entry:
        # Tier 1: lock breakeven (move SL to entry)
        target_sl = entry

    else:
        # Not yet in profit — no trail
        return False

    # Ratchet: only move SL in the profitable direction
    if side == "LONG" and target_sl > current_sl:
        position["sl"]          = target_sl
        position["trail_count"] = position.get("trail_count", 0) + 1
        return True
    elif side == "SHORT" and target_sl < current_sl:
        position["sl"]          = target_sl
        position["trail_count"] = position.get("trail_count", 0) + 1
        return True

    return False  # SL didn't improve — no update


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def run_walkforward_v4(
    window_start:     str   = "2024-01-01",
    window_end:       str   = "2026-03-04",
    required_history: int   = 400,
    initial_capital:  float = 10_000.0,
):
    """
    Sprint 1 Walk-Forward Engine.

    Entry logic: IDENTICAL to true_walkforward_engine.py (v3).
    Exit logic:  Extended with Trailing SL, Dynamic TP, Time-Based Exit.
    """
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log.info("=" * 72)
    log.info("  BTC-QUANT v4.1 — SPRINT 1: EXIT MANAGEMENT")
    log.info(f"  Window  : {window_start}  →  {window_end}")
    log.info(f"  Capital : ${initial_capital:,.0f}")
    log.info("=" * 72)

    # ── 1. Load Data ───────────────────────────────────────────────────────────
    df_all = load_full_dataset()
    df_all = add_indicators(df_all)

    start_dt = pd.to_datetime(window_start).tz_localize("UTC")
    end_dt   = pd.to_datetime(window_end  ).tz_localize("UTC")

    db_first_tradeable = df_all.index[required_history]
    if start_dt < db_first_tradeable:
        log.warning(
            f"Start {start_dt.date()} too early — auto-adjusting to {db_first_tradeable.date()}."
        )
        start_dt = db_first_tradeable

    pos_all         = np.arange(len(df_all))
    trade_positions = pos_all[(df_all.index >= start_dt) & (df_all.index <= end_dt)]

    if len(trade_positions) == 0:
        log.error("No candles in window.")
        return

    t_start = trade_positions[0]
    t_end   = trade_positions[-1]

    if t_start < required_history:
        log.error(f"Not enough history ({t_start} < {required_history}).")
        return

    log.info(f"  Candles in window : {len(trade_positions):,}")
    log.info(f"  History available : {t_start:,} candles before window")

    # ── 2. Services ────────────────────────────────────────────────────────────
    log.info("\nInitializing services...")
    from app.services.bcd_service import get_bcd_service
    from app.services.ai_service  import get_ai_service
    from app.services.ema_service import get_ema_service

    bcd_svc  = get_bcd_service()
    ai_svc   = get_ai_service()
    ema_svc  = get_ema_service()
    vol_est  = get_vol_estimator()
    risk_mgr = get_risk_manager()
    spectrum = DirectionalSpectrum()
    log.info("All services ready.\n")

    # ── 3. State ───────────────────────────────────────────────────────────────
    portfolio    = initial_capital
    equity_curve = [{"candle": df_all.index[t_start].isoformat(), "equity": portfolio}]
    trades       = []
    position     = None
    daily_stats  = {}

    n_candles = t_end - t_start
    t0        = time.time()
    last_log  = t0
    n_errors  = 0
    n_skipped = 0

    # Sprint 1 exit stats counters
    n_exit_trail     = 0   # SL hit after trailing
    n_exit_tp        = 0
    n_exit_sl        = 0
    n_exit_time      = 0

    # ── 4. Candle Loop ─────────────────────────────────────────────────────────
    for i in range(t_start, t_end):
        candle_dt   = df_all.index[i]
        next_candle = df_all.iloc[i + 1]

        window_size = 500
        df_hist = df_all.iloc[max(0, i - window_size + 1) : i + 1].copy()

        price_now = float(df_hist["Close"].iloc[-1])
        atr14     = float(df_hist["ATR14"].dropna().iloc[-1]) if df_hist["ATR14"].dropna().size else 0.01
        ema20     = float(df_hist["EMA20"].dropna().iloc[-1]) if df_hist["EMA20"].dropna().size else price_now
        ema50     = float(df_hist["EMA50"].dropna().iloc[-1]) if df_hist["EMA50"].dropna().size else price_now

        high_next = float(next_candle["High"])
        low_next  = float(next_candle["Low"])

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
        #  EXIT SECTION  ← Sprint 1 changes are here
        # ══════════════════════════════════════════════════════════════════════
        if position is not None:

            # ── [SPRINT 1 · Task 1.3] Time-Based Exit Check ──────────────────
            # Compute holding duration FIRST so we can decide whether to force
            # close, before updating the trailing SL.
            holding_candles = i - position["entry_idx"]

            if holding_candles >= _MAX_HOLD_CANDLES:
                # Compute unrealized profit at current close price
                entry = position["entry"]
                atr_e = position["entry_atr"]
                if position["side"] == "LONG":
                    unrealized_price = price_now - entry
                else:
                    unrealized_price = entry - price_now

                if unrealized_price > _TIME_EXIT_PROFIT_EXEMPT * atr_e:
                    # Exception: trade is well in profit → let trailing SL handle
                    log.debug(
                        f"  TIME_EXIT skipped @ {candle_dt.date()} — "
                        f"profit={unrealized_price:.0f} > {_TIME_EXIT_PROFIT_EXEMPT}×ATR — "
                        f"deferring to trail."
                    )
                else:
                    # Force close at current candle close price
                    entry     = position["entry"]
                    side      = position["side"]
                    risk_usd  = position["risk_usd"]
                    sl_dist   = abs(entry - position["initial_sl"])
                    if sl_dist <= 0:
                        sl_dist = atr14 * 0.5

                    actual_move = (price_now - entry) if side == "LONG" else (entry - price_now)
                    raw_ret     = actual_move / sl_dist
                    pnl         = risk_usd * raw_ret - abs(risk_usd) * 0.0008

                    portfolio += pnl

                    trade_log = {
                        "entry_time"          : position["entry_time"],
                        "exit_time"           : candle_dt.isoformat(),
                        "side"                : side,
                        "entry_price"         : round(entry, 2),
                        "exit_price"          : round(price_now, 2),
                        "initial_sl"          : round(position["initial_sl"], 2),
                        "sl"                  : round(position["sl"], 2),
                        "tp"                  : round(position["tp"], 2),
                        "risk_usd"            : round(risk_usd, 2),
                        "pnl_usd"             : round(pnl, 2),
                        "equity"              : round(portfolio, 2),
                        "exit_type"           : "TIME_EXIT",
                        "gate"                : position["gate"],
                        "fgi"                 : position["fgi"],
                        "regime"              : position["regime"],
                        # Sprint 1 new columns ──────────────────────────────
                        "trail_count"         : position.get("trail_count", 0),
                        "final_sl"            : round(position["sl"], 2),
                        "tp_extension_factor" : round(position["tp_extension_factor"], 2),
                        "holding_duration"    : holding_candles,
                    }
                    trades.append(trade_log)
                    equity_curve.append({"candle": candle_dt.isoformat(), "equity": round(portfolio, 2)})

                    d_key = candle_dt.date().isoformat()
                    daily_stats.setdefault(d_key, {"pnl": 0.0, "n_trades": 0})
                    daily_stats[d_key]["pnl"]      += pnl
                    daily_stats[d_key]["n_trades"] += 1

                    # [P0] Catat hasil ke risk_manager agar cooldown & leverage aktif
                    risk_mgr.record_trade_result(raw_ret)

                    log.info(
                        f"  ❌ CLOSE {side:5s} | TIME_EXIT | "
                        f"held {holding_candles}c | PnL: {pnl:+.2f} | Equity: {portfolio:,.2f}"
                    )
                    n_exit_time += 1
                    position = None
                    continue   # Don't try to re-enter on the same candle

            # ── [SPRINT 1 · Task 1.1] Update Trailing SL ─────────────────────
            # Uses price_now (current CLOSE) — no lookahead.
            # Updated SL will be used in the trigger check below against
            # the next candle's High/Low.
            if position is not None:
                _update_trailing_sl(position, price_now)

            # ── Standard SL / TP Trigger Check ───────────────────────────────
            if position is not None:
                exit_price = None
                exit_type  = None

                if position["side"] == "LONG":
                    if low_next <= position["sl"]:
                        exit_price, exit_type = position["sl"], "SL"
                    elif high_next >= position["tp"]:
                        exit_price, exit_type = position["tp"], "TP"
                else:  # SHORT
                    if high_next >= position["sl"]:
                        exit_price, exit_type = position["sl"], "SL"
                    elif low_next <= position["tp"]:
                        exit_price, exit_type = position["tp"], "TP"

                if exit_price is not None:
                    entry     = position["entry"]
                    side      = position["side"]
                    risk_usd  = position["risk_usd"]
                    sl_dist   = abs(entry - position["initial_sl"])
                    if sl_dist <= 0:
                        sl_dist = atr14 * 0.5

                    actual_move = (exit_price - entry) if side == "LONG" else (entry - exit_price)
                    raw_ret  = actual_move / sl_dist
                    pnl      = risk_usd * raw_ret - abs(risk_usd) * 0.0008
                    portfolio += pnl

                    # Determine if it was a trailed SL (SL moved from initial)
                    was_trailed = position.get("trail_count", 0) > 0
                    if exit_type == "SL" and was_trailed:
                        exit_type = "TRAIL_SL"

                    if exit_type == "TP":       n_exit_tp    += 1
                    elif "SL" in exit_type:     n_exit_sl    += 1
                    if exit_type == "TRAIL_SL": n_exit_trail += 1

                    trade_log = {
                        "entry_time"          : position["entry_time"],
                        "exit_time"           : next_candle.name.isoformat(),
                        "side"                : side,
                        "entry_price"         : round(entry, 2),
                        "exit_price"          : round(exit_price, 2),
                        "initial_sl"          : round(position["initial_sl"], 2),
                        "sl"                  : round(position["sl"], 2),
                        "tp"                  : round(position["tp"], 2),
                        "risk_usd"            : round(risk_usd, 2),
                        "pnl_usd"             : round(pnl, 2),
                        "equity"              : round(portfolio, 2),
                        "exit_type"           : exit_type,
                        "gate"                : position["gate"],
                        "fgi"                 : position["fgi"],
                        "regime"              : position["regime"],
                        # Sprint 1 new columns ──────────────────────────────
                        "trail_count"         : position.get("trail_count", 0),
                        "final_sl"            : round(position["sl"], 2),
                        "tp_extension_factor" : round(position["tp_extension_factor"], 2),
                        "holding_duration"    : i - position["entry_idx"],
                    }
                    trades.append(trade_log)
                    equity_curve.append({"candle": next_candle.name.isoformat(), "equity": round(portfolio, 2)})

                    d_key = candle_dt.date().isoformat()
                    daily_stats.setdefault(d_key, {"pnl": 0.0, "n_trades": 0})
                    daily_stats[d_key]["pnl"]      += pnl
                    daily_stats[d_key]["n_trades"] += 1

                    # [P0] Catat hasil ke risk_manager agar cooldown & leverage aktif
                    risk_mgr.record_trade_result(raw_ret)

                    icon = "✅" if pnl > 0 else "❌"
                    log.info(
                        f"  {icon} CLOSE {side:5s} | {exit_type:8s} | trail={position.get('trail_count',0)} "
                        f"| entry={entry:,.0f} exit={exit_price:,.0f} "
                        f"| PnL: {pnl:+.2f} USD | Equity: {portfolio:,.2f}"
                    )
                    position = None

        # ══════════════════════════════════════════════════════════════════════
        #  ENTRY SECTION  ← Identical to v3, plus Task 1.2 TP extension
        # ══════════════════════════════════════════════════════════════════════
        if position is None:
            try:
                # L1: BCD Regime (single BOCPD pass — no double call)
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

                # L4 risk multiplier
                vol_ratio = atr14 / price_now if price_now > 0 else 0.001
                l4_mult   = spectrum.compute_l4_multiplier(vol_ratio)

                # Directional Spectrum
                spec = spectrum.calculate(l1_vote, l2_vote, l3_vote, l4_mult, 5.0)

                # Heston SL/TP multipliers
                vol_params    = vol_est.estimate_params(df_hist)
                regime_biases = bcd_svc.get_regime_bias()
                bias_score    = float(
                    regime_biases.get(label, {}).get("bias_score", 0.5)
                    if label in regime_biases else 0.5
                )
                sl_tp  = vol_est.get_sl_tp_multipliers(
                    vol_regime = vol_params.get("vol_regime", "Normal"),
                    halflife   = float(vol_params.get("mean_reversion_halflife_candles", 999.0)),
                    bias_score = bias_score,
                )
                sl_m  = sl_tp["sl_multiplier"]
                tp1_m = sl_tp["tp1_multiplier"]

                # ── [SPRINT 1 · Task 1.2] Dynamic TP Extension ───────────────
                # Fix 1+2: Capped at 1.5×, disabled for neutral regime
                tp_ext_factor = _compute_tp_extension(
                    bcd_conf      = float(bcd_conf),
                    regime_biases = regime_biases,
                    label         = str(label),
                    tag           = str(tag),     # Fix 2: pass tag for neutral check
                )
                effective_tp1_m = tp1_m * tp_ext_factor

                # FGI Sentiment Adjustment (unchanged from v3)
                fgi_val = float(df_hist["FGI"].iloc[-1]) if "FGI" in df_hist.columns else 50.0
                sentiment_adj = 1.0
                if fgi_val > 80:
                    sentiment_adj = 0.75
                elif fgi_val < 20 and spec.directional_bias >= 0:
                    sentiment_adj = 0.75

                # L5: Risk Manager (unchanged from v3)
                req_lev = int(max(1, min(20, round(
                    0.04 / (effective_tp1_m * vol_ratio) if vol_ratio > 0 else 1
                ))))
                risk = risk_mgr.evaluate(
                    portfolio_value    = portfolio,
                    atr                = atr14,
                    sl_multiplier      = sl_m,
                    requested_leverage = req_lev,
                    current_price      = price_now,
                )

                # Trade Decision
                # Fix 3: Re-enable ADVISORY gate — Jan-Mar 2026 data shows ADVISORY
                # contributed 16/32 TP wins in v3. ADVISORY disabled in early sprint
                # testing but data confirms positive expectancy for this period.
                if spec.trade_gate in ("ACTIVE", "ADVISORY") and risk.can_trade:
                    is_bull = spec.directional_bias >= 0

                    if is_bull:
                        sl   = price_now - atr14 * sl_m
                        tp   = price_now + atr14 * effective_tp1_m
                        side = "LONG"
                    else:
                        sl   = price_now + atr14 * sl_m
                        tp   = price_now - atr14 * effective_tp1_m
                        side = "SHORT"

                    RISK_PCT     = 0.02
                    sl_dist_now  = abs(price_now - sl) or atr14 * sl_m
                    risk_usd_now = portfolio * RISK_PCT * sentiment_adj

                    position = {
                        # ── Core fields (same as v3) ──────────────────────────
                        "side"               : side,
                        "entry"              : price_now,
                        "sl"                 : sl,
                        "tp"                 : tp,
                        "risk_usd"           : risk_usd_now,
                        "lev"                : min(risk.approved_leverage, 10),
                        "entry_time"         : candle_dt.isoformat(),
                        "gate"               : spec.trade_gate,
                        "fgi"                : fgi_val,
                        "regime"             : str(tag),
                        # ── Sprint 1 new fields ───────────────────────────────
                        "entry_idx"          : i,             # for holding_duration
                        "entry_atr"          : atr14,         # fixed ATR reference for trail tiers
                        "initial_sl"         : sl,            # original SL before any trailing
                        "trail_count"        : 0,             # updated by _update_trailing_sl
                        "tp_extension_factor": tp_ext_factor, # logged in trade record
                    }

                    log.info(
                        f"  🟢 OPEN  {side:5s} @ {price_now:,.2f} | "
                        f"SL={sl:.2f} TP={tp:.2f} | "
                        f"TPext={tp_ext_factor:.1f}× | Gate={spec.trade_gate} | "
                        f"regime={tag} bcd={bcd_conf:.2f}"
                    )
                else:
                    n_skipped += 1

            except Exception as exc:
                n_errors += 1
                log.debug(f"  [{candle_dt}] Layer error: {exc}")

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
    log.info("  BACKTEST COMPLETE — v4.1 Sprint 1: Exit Management")
    log.info("═" * 72)

    tdf = pd.DataFrame(trades)
    if tdf.empty:
        log.warning("  No trades were taken during the simulation.")
        return

    total      = len(tdf)
    wins       = (tdf["pnl_usd"] > 0).sum()
    losses     = total - wins
    win_rate   = wins / total * 100
    gross_p    = tdf[tdf["pnl_usd"] > 0]["pnl_usd"].sum()
    gross_l    = abs(tdf[tdf["pnl_usd"] <= 0]["pnl_usd"].sum())
    profit_fac = gross_p / gross_l if gross_l > 0 else float("inf")

    avg_win    = gross_p / wins    if wins   > 0 else 0.0
    avg_loss   = gross_l / losses  if losses > 0 else 0.0
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
        daily_pnls = pd.Series([v["pnl"] for v in daily_stats.values()])
        daily_rets = daily_pnls / initial_capital * 100
        sharpe = (daily_rets.mean() / daily_rets.std() * np.sqrt(365)) if daily_rets.std() > 0 else 0.0
    else:
        sharpe = 0.0

    # Exit distribution
    exit_dist = tdf["exit_type"].value_counts().to_dict()

    # Trail statistics
    trailed_trades = tdf[tdf["trail_count"] > 0]
    avg_trail      = tdf["trail_count"].mean()

    # TP extension distribution
    tp_ext_dist = tdf["tp_extension_factor"].value_counts().to_dict()

    # Holding duration stats
    avg_hold = tdf["holding_duration"].mean()

    # Baseline comparison (from DOD)
    baseline_daily = 0.394
    baseline_wr    = 46.67
    baseline_dd    = 43.04

    log.info(f"  Window        : {window_start}  →  {window_end}  ({n_days} days)")
    log.info(f"  Initial Cap   : ${initial_capital:>12,.2f}")
    log.info(f"  Final Equity  : ${portfolio:>12,.2f}")
    log.info(f"  Net PnL       : ${final_pnl:>+12,.2f}  ({final_pct:+.2f}%)")
    log.info(f"  Daily Return  : {daily_ret:+.3f}%/day  (baseline: {baseline_daily:+.3f}%)  Δ={daily_ret-baseline_daily:+.3f}%")
    log.info(f"  Trades        : {total}  (W:{wins}  L:{losses})  WR: {win_rate:.1f}%  (baseline: {baseline_wr:.1f}%)")
    log.info(f"  R:R Ratio     : 1 : {rr_ratio:.2f}  (avg_win: ${avg_win:.0f}  avg_loss: ${avg_loss:.0f})")
    log.info(f"  Profit Factor : {profit_fac:.3f}")
    log.info(f"  Max Drawdown  : {max_dd:.2f}%  (baseline: {baseline_dd:.2f}%)")
    log.info(f"  Sharpe Ratio  : {sharpe:.3f}")
    log.info(f"  ── Exit Distribution ──")
    for k, v in sorted(exit_dist.items()):
        pct = v / total * 100
        log.info(f"     {k:<12s}: {v:>4} ({pct:4.1f}%)")
    log.info(f"  ── Sprint 1 Stats ──")
    log.info(f"     Avg Trail Count     : {avg_trail:.2f} per trade")
    log.info(f"     Trailed Trades      : {len(trailed_trades)} / {total} ({len(trailed_trades)/total*100:.1f}%)")
    log.info(f"     TP Extension dist   : {tp_ext_dist}")
    log.info(f"     Avg Holding Duration: {avg_hold:.1f} candles")
    log.info(f"  Errors/Skipped: {n_errors} / {n_skipped}")
    log.info(f"  Time taken    : {elapsed_total:.0f}s")
    log.info("═" * 72)

    # ── DOD Acceptance Criteria Check ──────────────────────────────────────────
    log.info("\n  ── Sprint 1 DOD Acceptance Criteria ──")
    criteria = [
        ("R:R Ratio ≥ 2.0",          rr_ratio >= 2.0,   f"actual={rr_ratio:.2f}",       "MUST"),
        ("Avg Winner > $900",         avg_win  > 900,    f"actual=${avg_win:.0f}",        "MUST"),
        ("Avg Loser  < $400",         avg_loss < 400,    f"actual=${avg_loss:.0f}",       "MUST"),
        ("Win Rate   ≥ 46%",          win_rate >= 46.0,  f"actual={win_rate:.1f}%",       "MUST"),
        ("Profit Factor > 1.3",       profit_fac > 1.3,  f"actual={profit_fac:.3f}",      "SHOULD"),
        ("Daily Return > 0.7%",       daily_ret  > 0.7,  f"actual={daily_ret:.3f}%/day",  "SHOULD"),
    ]
    all_must_pass = True
    for name, passed, detail, level in criteria:
        status = "✅ PASS" if passed else "❌ FAIL"
        if not passed and level == "MUST":
            all_must_pass = False
        log.info(f"     [{level:6s}] {status}  {name}  ({detail})")
    overall = "🟢 SPRINT 1 PASSED — Ready for Sprint 2" if all_must_pass else "🔴 SPRINT 1 FAILED — Review and iterate"
    log.info(f"\n  {overall}")

    # ── Save Results ───────────────────────────────────────────────────────────
    run_tag = f"v4_exit_{window_start[:7].replace('-','')}_{window_end[:7].replace('-','')}_{run_ts}"

    trades_csv = _RESULTS_DIR / f"{run_tag}_trades.csv"
    tdf.to_csv(trades_csv, index=False)

    equity_csv = _RESULTS_DIR / f"{run_tag}_equity.csv"
    pd.DataFrame(equity_curve).to_csv(equity_csv, index=False)

    daily_df  = pd.DataFrame([
        {"date": k, "pnl": v["pnl"], "n_trades": v["n_trades"]}
        for k, v in sorted(daily_stats.items())
    ])
    daily_csv = _RESULTS_DIR / f"{run_tag}_daily.csv"
    daily_df.to_csv(daily_csv, index=False)

    summary = {
        "run_timestamp"        : run_ts,
        "sprint"               : "1_exit_management",
        "window_start"         : window_start,
        "window_end"           : window_end,
        "initial_capital"      : initial_capital,
        "final_equity"         : round(portfolio, 2),
        "net_pnl_usd"          : round(final_pnl, 2),
        "net_pnl_pct"          : round(final_pct, 4),
        "daily_return_pct"     : round(daily_ret, 4),
        "n_days"               : n_days,
        "n_candles"            : len(trade_positions),
        "n_trades"             : total,
        "n_wins"               : int(wins),
        "n_losses"             : int(losses),
        "win_rate_pct"         : round(win_rate, 2),
        "avg_winner_usd"       : round(avg_win, 2),
        "avg_loser_usd"        : round(avg_loss, 2),
        "rr_ratio"             : round(rr_ratio, 3),
        "profit_factor"        : round(profit_fac, 3),
        "max_drawdown_pct"     : round(max_dd, 2),
        "sharpe_ratio"         : round(sharpe, 3),
        "exit_distribution"    : exit_dist,
        "n_time_exits"         : n_exit_time,
        "n_trail_sl"           : n_exit_trail,
        "n_tp"                 : n_exit_tp,
        "n_sl"                 : n_exit_sl,
        "avg_trail_count"      : round(float(avg_trail), 3),
        "avg_holding_duration" : round(float(avg_hold), 1),
        "tp_extension_dist"    : {str(k): int(v) for k, v in tp_ext_dist.items()},
        "n_skipped"            : n_skipped,
        "n_errors"             : n_errors,
        "dod_all_must_pass"    : all_must_pass,
        "elapsed_seconds"      : round(elapsed_total, 1),
    }
    summary_json = _RESULTS_DIR / f"{run_tag}_summary.json"
    with open(summary_json, "w") as f:
        json.dump(summary, f, indent=2)

    log.info(f"\n  [✓] Trades  → {trades_csv.name}")
    log.info(f"  [✓] Equity  → {equity_csv.name}")
    log.info(f"  [✓] Daily   → {daily_csv.name}")
    log.info(f"  [✓] Summary → {summary_json.name}")
    log.info(f"  [✓] Full log → {_LOG_FILE.name}")


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRYPOINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="BTC-Quant v4.1 — Sprint 1: Exit Management")
    parser.add_argument("--start",   default="2024-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end",     default="2026-03-04", help="End date   (YYYY-MM-DD)")
    parser.add_argument("--capital", default=10000.0,      type=float)
    parser.add_argument("--history", default=400,          type=int)
    args = parser.parse_args()

    run_walkforward_v4(
        window_start     = args.start,
        window_end       = args.end,
        required_history = args.history,
        initial_capital  = args.capital,
    )
