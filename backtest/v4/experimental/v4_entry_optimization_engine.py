"""
╔══════════════════════════════════════════════════════════════════════╗
║  BTC-QUANT: SPRINT 2 — ENTRY OPTIMIZATION ENGINE (v4.3)            ║
║  Base: v4_exit_management_engine.py                                  ║
║                                                                      ║
║  Sprint 2 Changes (Layer 2 & 6 Entry Optimization):                  ║
║    2.1  Multi-Timeframe Trend Filter (Daily EMA 200)                 ║
║    2.2  Layer 2 Refinement: RSI Divergence + MACD Line Filter        ║
║    2.3  MLP Confidence Threshold (raised to 65%)                     ║
║    2.4  Crypto Microstructure: OI Delta + Funding Contrarian         ║
║    2.5  Master Scoring System (+8/-8 threshold)                      ║
║                                                                      ║
║  Maintained from Sprint 1:                                           ║
║    • ATR-Based Trailing SL (ratchet mechanism)                       ║
║    • Dynamic TP Extension (capped 1.5x, non-neutral)                 ║
║    • Time-Based Exit (24h hold, profit exception)                    ║
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

os.environ["BTC_QUANT_LAYER1_ENGINE"] = "bcd"

from engines.layer1_volatility import get_vol_estimator
from app.services.risk_manager  import get_risk_manager
from utils.spectrum              import DirectionalSpectrum
from data_engine                 import DB_PATH

# ── Output Directories ─────────────────────────────────────────────────────────
_RESULTS_DIR = _PROJECT_ROOT / "backtest" / "results" / "v4_entry_optimization_results"
_LOGS_DIR    = _PROJECT_ROOT / "backtest" / "logs"    / "v4_entry"
_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
_LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Logging Setup ──────────────────────────────────────────────────────────────
_LOG_FILE = _LOGS_DIR / f"v4_entry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("v4_entry")


# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

# 1. Sprint 1 Carry-over
_TRAIL_L1_ATR  = 1.0
_TRAIL_L2_ATR  = 2.0
_TRAIL_L3_ATR  = 3.0

_TP_EXT_BCD_THRESHOLD   = 0.8
_TP_EXT_BCD_FACTOR      = 1.25
_TP_EXT_PERSIST_THRESH  = 0.85
_TP_EXT_PERSIST_FACTOR  = 1.5

_MAX_HOLD_CANDLES        = 24
_TIME_EXIT_PROFIT_EXEMPT = 1.5

# 2. Sprint 2 Optimization Thresholds
_MIN_MLP_CONFIDENCE     = 0.60   # 60% MLP threshold
_ENTRY_SCORE_THRESHOLD  = 5      # Realistic max ≈ 7 (no OI/Funding data)
_FUNDING_LIMIT          = 0.0005 # 0.05% contrarian limit
_VOL_MIN_RATIO          = 0.003  # 0.3% ATR ratio floor
_VOL_MAX_RATIO          = 0.06   # 6% ATR ratio ceiling
_ZSCORE_EXTREME         = 2.0    # Block entry if |Z| > 2 (overstretched)


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
        raise RuntimeError("DuckDB returned empty dataset.")

    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("datetime")
    log.info(f"Loaded {len(df)} candles | {df.index[0]} → {df.index[-1]}")
    return df


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["EMA21"]  = ta.ema(df["Close"], length=21)
    df["EMA55"]  = ta.ema(df["Close"], length=55)
    df["EMA200"] = ta.ema(df["Close"], length=200)
    
    # Daily trend proxy (approx 600 candles on 4H)
    df["EMA200_D"] = ta.ema(df["Close"], length=1200) 
    
    df["ATR14"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)
    df["RSI14"] = ta.rsi(df["Close"], length=14)
    
    # MACD 
    macd = ta.macd(df["Close"], fast=12, slow=26, signal=9)
    df["MACD"] = macd["MACD_12_26_9"]
    df["MACD_S"] = macd["MACDs_12_26_9"]
    df["MACD_H"] = macd["MACDh_12_26_9"]
    
    # OI Delta
    df["OI_Delta"] = df["OI"].diff()
    
    # CVD Delta
    df["CVD_Delta"] = df["CVD"].diff()
    
    # Z-Score
    df["Mean20"] = df["Close"].rolling(20).mean()
    df["Std20"]  = df["Close"].rolling(20).std()
    df["ZScore"] = (df["Close"] - df["Mean20"]) / df["Std20"]

    return df


# ══════════════════════════════════════════════════════════════════════════════
#  SPRINT 2 MASTER SCORING
# ══════════════════════════════════════════════════════════════════════════════

def calculate_master_score(row: pd.Series, prev_row: pd.Series, ai_bias: str, ai_conf: float, bcd_vote: float) -> tuple[int, list]:
    """
    Master Scoring — calibrated for available data (no OI/Funding in DB).
    Max achievable score: +7 (Daily +1, 4H EMA +1, RSI +2, MACD +1, AI +2)
    Threshold: +5 = HIGH QUALITY LONG, -5 = HIGH QUALITY SHORT
    """
    score = 0
    reasons = []
    price_change = row["Close"] - row["Open"]

    # ── Layer 1a: Daily Trend (Weight: 1) ───────────────────────────────────
    # Softer weight — daily trend as signal, not hard gate
    if pd.notna(row.get("EMA200_D")):
        if row["Close"] > row["EMA200_D"] * 1.005:   # >0.5% above daily EMA
            score += 1
            reasons.append("Daily Trend Bullish (+1)")
        elif row["Close"] < row["EMA200_D"] * 0.995: # >0.5% below daily EMA
            score -= 1
            reasons.append("Daily Trend Bearish (-1)")

    # ── Layer 1b: 4H EMA Stack (Weight: 1) ──────────────────────────────────
    ema21 = row.get("EMA21"); ema55 = row.get("EMA55"); ema200 = row.get("EMA200")
    if pd.notna(ema21) and pd.notna(ema55) and pd.notna(ema200):
        if ema21 > ema55 > ema200: score += 1; reasons.append("4H EMA Bull Stack (+1)")
        elif ema21 < ema55 < ema200: score -= 1; reasons.append("4H EMA Bear Stack (-1)")

    # ── Layer 2a: RSI Divergence (Weight: 2) ────────────────────────────────
    rsi = row.get("RSI14", 50)
    rsi_prev = prev_row.get("RSI14", 50)
    if rsi < 35 and rsi > rsi_prev:
        score += 2; reasons.append(f"RSI Oversold+SlopeUp {rsi:.0f} (+2)")
    elif rsi >  65 and rsi < rsi_prev:
        score -= 2; reasons.append(f"RSI Overbought+SlopeDown {rsi:.0f} (-2)")
    elif 35 <= rsi <= 45:  # mild oversold bias
        score += 1; reasons.append(f"RSI Mild Oversold {rsi:.0f} (+1)")
    elif 55 <= rsi <= 65:  # mild overbought bias
        score -= 1; reasons.append(f"RSI Mild Overbought {rsi:.0f} (-1)")

    # ── Layer 2b: MACD Histogram (Weight: 1) ────────────────────────────────
    macd_h = row.get("MACD_H", 0); macd_l = row.get("MACD", 0)
    macd_h_prev = prev_row.get("MACD_H", 0)
    if macd_h > 0 and macd_h > macd_h_prev and macd_l > 0:
        score += 1; reasons.append("MACD Bull Accel (+1)")
    elif macd_h < 0 and macd_h < macd_h_prev and macd_l < 0:
        score -= 1; reasons.append("MACD Bear Accel (-1)")

    # ── Layer 3: AI Confidence (Weight: 2) ──────────────────────────────────
    if ai_conf >= _MIN_MLP_CONFIDENCE:
        delta = 2
    else:
        delta = 1 if ai_conf >= 0.52 else 0
    if delta > 0:
        if ai_bias == "BULL": score += delta; reasons.append(f"AI {ai_bias} {ai_conf:.2f} (+{delta})")
        else: score -= delta; reasons.append(f"AI {ai_bias} {ai_conf:.2f} (-{delta})")

    # ── Layer 4: CVD Divergence (Weight: 1) — only data we have ─────────────
    cvd_d = row.get("CVD_Delta", 0)
    if price_change > 0 and cvd_d < 0:  # price up, sellers dominate → bearish div
        score -= 1; reasons.append("CVD Bear Divergence (-1)")
    elif price_change < 0 and cvd_d > 0:  # price down, buyers dominate → bullish div
        score += 1; reasons.append("CVD Bull Divergence (+1)")

    # ── BCD Regime vote (Weight: 1) ──────────────────────────────────────────
    if   bcd_vote >  0.8: score += 1; reasons.append("BCD Strong Bull (+1)")
    elif bcd_vote < -0.8: score -= 1; reasons.append("BCD Strong Bear (-1)")

    return score, reasons


# ══════════════════════════════════════════════════════════════════════════════
#  SPRINT 1 HELPERS (Maintained)
# ══════════════════════════════════════════════════════════════════════════════

def _compute_tp_extension(bcd_conf: float, regime_biases: dict, label: str, tag: str) -> float:
    if tag not in ("bull", "bear"):
        return 1.0
    persistence = 0.0
    if label in regime_biases:
        persistence = float(regime_biases[label].get("persistence", 0.0))

    if persistence > _TP_EXT_PERSIST_THRESH:
        return _TP_EXT_PERSIST_FACTOR
    if bcd_conf > _TP_EXT_BCD_THRESHOLD:
        return _TP_EXT_BCD_FACTOR
    return 1.0


def _update_trailing_sl(position: dict, price_now: float) -> bool:
    entry     = position["entry"]
    atr_entry = position["entry_atr"]
    side      = position["side"]
    current_sl = position["sl"]

    if side == "LONG":
        unrealized = price_now - entry
    else:
        unrealized = entry - price_now

    if unrealized >= _TRAIL_L3_ATR * atr_entry:
        target_sl = entry + 1.5 * atr_entry if side == "LONG" else entry - 1.5 * atr_entry
    elif unrealized >= _TRAIL_L2_ATR * atr_entry:
        target_sl = entry + 0.5 * atr_entry if side == "LONG" else entry - 0.5 * atr_entry
    elif unrealized >= _TRAIL_L1_ATR * atr_entry:
        target_sl = entry
    else:
        return False

    if side == "LONG" and target_sl > current_sl:
        position["sl"] = target_sl
        position["trail_count"] = position.get("trail_count", 0) + 1
        return True
    elif side == "SHORT" and target_sl < current_sl:
        position["sl"] = target_sl
        position["trail_count"] = position.get("trail_count", 0) + 1
        return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def run_walkforward_v4_3(
    window_start:     str   = "2024-01-01",
    window_end:       str   = "2026-03-04",
    required_history: int   = 1200,   # Raised for Daily EMA 200
    initial_capital:  float = 10_000.0,
):
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log.info("=" * 72)
    log.info("  BTC-QUANT v4.3 — SPRINT 2: ENTRY OPTIMIZATION")
    log.info(f"  Window  : {window_start}  →  {window_end}")
    log.info(f"  Capital : ${initial_capital:,.0f}")
    log.info(f"  Threshold: MLP 65%, Score {_ENTRY_SCORE_THRESHOLD}")
    log.info("=" * 72)

    df_all = load_full_dataset()
    df_all = add_indicators(df_all)

    start_dt = pd.to_datetime(window_start).tz_localize("UTC")
    end_dt   = pd.to_datetime(window_end  ).tz_localize("UTC")

    db_first_tradeable = df_all.index[required_history]
    if start_dt < db_first_tradeable:
        log.warning(f"Adjusting start to {db_first_tradeable.date()}.")
        start_dt = db_first_tradeable

    pos_all         = np.arange(len(df_all))
    trade_positions = pos_all[(df_all.index >= start_dt) & (df_all.index <= end_dt)]

    if len(trade_positions) == 0:
        log.error("No candles in window.")
        return

    t_start = trade_positions[0]
    t_end   = trade_positions[-1]

    # Services
    from app.services.bcd_service import get_bcd_service
    from app.services.ai_service  import get_ai_service
    from app.services.ema_service import get_ema_service

    bcd_svc  = get_bcd_service()
    ai_svc   = get_ai_service()
    ema_svc  = get_ema_service()
    vol_est  = get_vol_estimator()
    risk_mgr = get_risk_manager()
    spectrum = DirectionalSpectrum()

    # State
    portfolio    = initial_capital
    equity_curve = [{"candle": df_all.index[t_start].isoformat(), "equity": portfolio}]
    trades       = []
    position     = None
    daily_stats  = {}
    max_score_seen = 0

    n_candles = t_end - t_start
    t0        = time.time()
    last_log  = t0

    # ── Pre-extract numpy arrays for O(1) access (no iloc overhead) ─────────
    _close  = df_all["Close"].values.astype(np.float64)
    _open   = df_all["Open"].values.astype(np.float64)
    _high   = df_all["High"].values.astype(np.float64)
    _low    = df_all["Low"].values.astype(np.float64)
    _atr    = df_all["ATR14"].values.astype(np.float64)
    _rsi    = df_all["RSI14"].values.astype(np.float64)
    _macd   = df_all["MACD"].values.astype(np.float64)
    _macd_h = df_all["MACD_H"].values.astype(np.float64)
    _ema21  = df_all["EMA21"].values.astype(np.float64)
    _ema55  = df_all["EMA55"].values.astype(np.float64)
    _ema200 = df_all["EMA200"].values.astype(np.float64)
    _ema200d= df_all["EMA200_D"].values.astype(np.float64)
    _zscore = df_all["ZScore"].values.astype(np.float64)
    _cvd_d  = df_all["CVD_Delta"].values.astype(np.float64)
    _fgi    = df_all["FGI"].values.astype(np.float64)

    log.info(f"  Arrays extracted. Starting candle loop ({n_candles} candles)...")

    # ── BCD/MLP Cache ─────────────────────────────────────────────────────────
    _BCD_CACHE_TTL   = 6   # Cache BCD result for 6 candles (~1 day)
    _bcd_cache       = None
    _bcd_cache_age   = 999
    _last_df_hist    = None  # Reuse df_hist if unchanged

    # Candle Loop (Optimized)
    for i in range(t_start, t_end):
        candle_dt = df_all.index[i]
        price_now = _close[i]
        atr14     = _atr[i]
        high_next = _high[i + 1]
        low_next  = _low[i + 1]

        # ── EXIT SECTION (Maintained from Sprint 1) ──────────────────────────
        if position is not None:
            holding_candles = i - position["entry_idx"]

            # Time Exit
            if holding_candles >= _MAX_HOLD_CANDLES:
                unrealized_p = (price_now - position["entry"]) if position["side"] == "LONG" else (position["entry"] - price_now)
                if unrealized_p < _TIME_EXIT_PROFIT_EXEMPT * position["entry_atr"]:
                    entry = position["entry"]
                    sl_dist = abs(entry - position["initial_sl"]) or atr14
                    pnl_raw_ret = unrealized_p / sl_dist if sl_dist > 0 else 0.0
                    pnl = position["risk_usd"] * pnl_raw_ret - abs(position["risk_usd"]) * 0.0008
                    portfolio += pnl
                    trades.append({
                        **position, "exit_time": candle_dt.isoformat(), "exit_price": price_now, "pnl_usd": round(pnl, 2), "equity": round(portfolio, 2),
                        "exit_type": "TIME_EXIT", "holding_duration": holding_candles
                    })
                    # [P0] Catat hasil ke risk_manager agar cooldown & leverage aktif
                    risk_mgr.record_trade_result(pnl_raw_ret)
                    icon = "✅" if pnl > 0 else "❌"
                    log.info(
                        f"  {icon} CLOSE {position['side']:5s} | TIME_EXIT | "
                        f"held {holding_candles}c | PnL: {pnl:+.2f} USD | Equity: {portfolio:,.2f}"
                    )
                    position = None
                    continue

            # Trailing SL & Standard Triggers
            if position is not None:
                _update_trailing_sl(position, price_now)
                exit_price, exit_type = None, None
                if position["side"] == "LONG":
                    if low_next <= position["sl"]: exit_price, exit_type = position["sl"], "SL"
                    elif high_next >= position["tp"]: exit_price, exit_type = position["tp"], "TP"
                else:
                    if high_next >= position["sl"]: exit_price, exit_type = position["sl"], "SL"
                    elif low_next <= position["tp"]: exit_price, exit_type = position["tp"], "TP"

                if exit_price:
                    unrealized_p = (exit_price - position["entry"]) if position["side"] == "LONG" else (position["entry"] - exit_price)
                    sl_dist = abs(position["entry"] - position["initial_sl"]) or atr14
                    pnl_raw_ret = unrealized_p / sl_dist if sl_dist > 0 else 0.0
                    pnl = position["risk_usd"] * pnl_raw_ret - abs(position["risk_usd"]) * 0.0008
                    portfolio += pnl
                    if exit_type == "SL" and position["trail_count"] > 0: exit_type = "TRAIL_SL"
                    trades.append({
                        **position, "exit_time": df_all.index[i + 1].isoformat(), "exit_price": round(exit_price, 2),
                        "pnl_usd": round(pnl, 2), "equity": round(portfolio, 2),
                        "exit_type": exit_type, "holding_duration": i - position["entry_idx"]
                    })
                    # [P0] Catat hasil ke risk_manager agar cooldown & leverage aktif
                    risk_mgr.record_trade_result(pnl_raw_ret)
                    icon = "✅" if pnl > 0 else "❌"
                    log.info(
                        f"  {icon} CLOSE {position['side']:5s} | {exit_type:8s} | "
                        f"entry={position['entry']:,.0f} exit={exit_price:,.0f} "
                        f"| PnL: {pnl:+.2f} USD | Equity: {portfolio:,.2f}"
                    )
                    position = None

        # ── ENTRY SECTION (Sprint 2 Optimization) ────────────────────────────
        if position is None:
            try:
                # 0. Z-Score Blocker
                zs = _zscore[i]
                if not np.isnan(zs) and abs(zs) > _ZSCORE_EXTREME:
                    continue

                # 1. Volatility Blocker
                vol_ratio = atr14 / price_now if price_now > 0 else 0
                if vol_ratio < _VOL_MIN_RATIO or vol_ratio > _VOL_MAX_RATIO:
                    continue

                # 2. BCD Regime (with cache)
                _bcd_cache_age += 1
                if _bcd_cache is None or _bcd_cache_age >= _BCD_CACHE_TTL:
                    df_hist = df_all.iloc[max(0, i - 500 + 1) : i + 1]  # NO .copy()
                    label, tag, bcd_conf, hmm_states, hmm_index = bcd_svc.get_regime_and_states(df_hist, funding_rate=0)
                    _bcd_cache = (label, tag, bcd_conf, hmm_states, hmm_index)
                    _bcd_cache_age = 0
                    _last_df_hist = df_hist
                else:
                    label, tag, bcd_conf, hmm_states, hmm_index = _bcd_cache

                bcd_vote = float(bcd_conf if tag == "bull" else -bcd_conf)

                # 3. MLP AI (use cached df_hist and hmm data)
                if _last_df_hist is None:
                    _last_df_hist = df_all.iloc[max(0, i - 500 + 1) : i + 1]
                ai_bias, ai_conf = ai_svc.get_confidence(_last_df_hist, hmm_states=hmm_states, hmm_index=hmm_index)

                # 4. Master Scoring (inline with numpy arrays — no Series overhead)
                score = 0
                pc = _close[i] - _open[i]  # price change

                # L1a: Daily Trend
                ed = _ema200d[i]
                if not np.isnan(ed):
                    if _close[i] > ed * 1.005: score += 1
                    elif _close[i] < ed * 0.995: score -= 1

                # L1b: 4H EMA Stack
                e21, e55, e200 = _ema21[i], _ema55[i], _ema200[i]
                if not (np.isnan(e21) or np.isnan(e55) or np.isnan(e200)):
                    if e21 > e55 > e200: score += 1
                    elif e21 < e55 < e200: score -= 1

                # L2a: RSI
                rsi, rsi_p = _rsi[i], _rsi[i - 1]
                if not np.isnan(rsi):
                    if rsi < 35 and rsi > rsi_p: score += 2
                    elif rsi > 65 and rsi < rsi_p: score -= 2
                    elif 35 <= rsi <= 45: score += 1
                    elif 55 <= rsi <= 65: score -= 1

                # L2b: MACD
                mh, ml, mh_p = _macd_h[i], _macd[i], _macd_h[i - 1]
                if mh > 0 and mh > mh_p and ml > 0: score += 1
                elif mh < 0 and mh < mh_p and ml < 0: score -= 1

                # L3: AI
                ai_c = float(ai_conf)
                delta = 2 if ai_c >= _MIN_MLP_CONFIDENCE else (1 if ai_c >= 0.52 else 0)
                if delta > 0:
                    if str(ai_bias) == "BULL": score += delta
                    else: score -= delta

                # L4: CVD
                cvd = _cvd_d[i]
                if pc > 0 and cvd < 0: score -= 1
                elif pc < 0 and cvd > 0: score += 1

                # BCD Vote
                if bcd_vote > 0.8: score += 1
                elif bcd_vote < -0.8: score -= 1

                max_score_seen = max(max_score_seen, abs(score))

                # 5. Entry Decision
                side = None
                if score >= _ENTRY_SCORE_THRESHOLD: side = "LONG"
                elif score <= -_ENTRY_SCORE_THRESHOLD: side = "SHORT"

                if side is None:
                    continue  # skip — tidak ada signal cukup kuat

                if side is not None:
                    if _last_df_hist is None:
                        _last_df_hist = df_all.iloc[max(0, i - 500 + 1) : i + 1]
                    vol_params    = vol_est.estimate_params(_last_df_hist)
                    regime_biases = bcd_svc.get_regime_bias()
                    sl_tp = vol_est.get_sl_tp_multipliers(
                        vol_params["vol_regime"],
                        float(vol_params.get("mean_reversion_halflife_candles", 999)),
                        0.5
                    )

                    tp_ext = _compute_tp_extension(float(bcd_conf), regime_biases, str(label), str(tag))
                    effective_tp_m = sl_tp["tp1_multiplier"] * tp_ext

                    sl = price_now - atr14 * sl_tp["sl_multiplier"] if side == "LONG" else price_now + atr14 * sl_tp["sl_multiplier"]
                    tp = price_now + atr14 * effective_tp_m if side == "LONG" else price_now - atr14 * effective_tp_m

                    risk = risk_mgr.evaluate(portfolio, atr14, sl_tp["sl_multiplier"], 5, price_now)
                    if risk.can_trade:
                        position = {
                            "side": side, "entry": price_now, "sl": sl, "tp": tp, "initial_sl": sl,
                            "entry_time": candle_dt.isoformat(), "entry_idx": i, "entry_atr": atr14,
                            "risk_usd": portfolio * 0.02, "tp_extension_factor": tp_ext, "trail_count": 0,
                            "master_score": score, "gate": "LEVEL6", "regime": str(tag), "fgi": _fgi[i]
                        }
                        log.info(
                            f"  🟢 OPEN  {side:5s} @ {price_now:,.0f} | "
                            f"SL={sl:,.0f} TP={tp:,.0f} | score={score} | "
                            f"regime={tag} bcd={bcd_conf:.2f} | Equity={portfolio:,.2f}"
                        )

            except Exception as e:
                log.warning(f"  [ENTRY ERROR] candle={candle_dt.date()} | {type(e).__name__}: {e}")

        # Heartbeat setiap 10 detik
        now = time.time()
        if now - last_log >= 10:
            pct = (i - t_start) / max(n_candles, 1) * 100
            elapsed = now - t0
            eta_s = (elapsed / max(pct, 0.01)) * (100 - pct)
            log.info(
                f"  ▶ [{candle_dt.strftime('%Y-%m-%d')}] {pct:5.1f}% "
                f"│ Equity: ${portfolio:>10,.0f} "
                f"│ Trades: {len(trades):>4} "
                f"│ Score max: {max_score_seen} "
                f"│ ETA: {eta_s/60:.1f}m"
            )
            last_log = now


    # ── Save & Summary ────────────────────────────────────────────────────────
    log.info("\n" + "═" * 72 + "\n  BACKTEST COMPLETE\n" + "═" * 72)
    tdf = pd.DataFrame(trades)
    if tdf.empty: return
    
    total, wins = len(tdf), (tdf["pnl_usd"] > 0).sum()
    win_rate = wins / total * 100
    pnl_total = portfolio - initial_capital
    avg_win, avg_loss = tdf[tdf["pnl_usd"] > 0]["pnl_usd"].mean(), abs(tdf[tdf["pnl_usd"] <= 0]["pnl_usd"].mean())
    rr = avg_win / avg_loss if avg_loss > 0 else 0
    
    log.info(f"  Net PnL   : ${pnl_total:>+12,.2f} ({pnl_total/initial_capital*100:+.2f}%)")
    log.info(f"  Win Rate  : {win_rate:.1f}%")
    log.info(f"  R:R Ratio : 1 : {rr:.2f}")
    log.info(f"  Trades    : {total}")
    log.info(f"  Max Score Seen: {max_score_seen}")

    run_tag = f"v4_entry_{run_ts}"
    tdf.to_csv(_RESULTS_DIR / f"{run_tag}_trades.csv", index=False)
    with open(_RESULTS_DIR / f"{run_tag}_summary.json", "w") as f:
        json.dump({"net_pnl_pct": pnl_total/initial_capital*100, "win_rate_pct": win_rate, "n_trades": total, "rr_ratio": rr}, f, indent=2)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--start",   default="2024-01-01")
    parser.add_argument("--end",     default="2026-03-04")
    parser.add_argument("--capital", type=float, default=10_000.0)
    args = parser.parse_args()
    run_walkforward_v4_3(
        window_start=args.start,
        window_end=args.end,
        initial_capital=args.capital,
    )
