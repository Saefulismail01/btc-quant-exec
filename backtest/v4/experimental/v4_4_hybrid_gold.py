"""
╔══════════════════════════════════════════════════════════════════════╗
║  BTC-QUANT: v4.4 HYBRID GOLD ENGINE                                   ║
║  Goal: Win Rate 57% | R:R >= 1.0                                     ║
║                                                                      ║
║  STRATEGI UTAMA:                                                     ║
║    1. Half-Risk SL Lock: Jika candle 1 profit, SL pindah ke -0.66%    ║
║       (memberi napas lebih besar dari Breakeven 0%).                 ║
║    2. BCD TP Extension: Jika BCD Confidence > 0.85, TP naik 1.5x.    ║
║    3. Maintain SL 1.33%: Menjaga akurasi entry tetap tinggi.         ║
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
_LOG_FILE = _LOGS_DIR / f"v4_4_hybrid_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("v4_4_hybrid")


# ══════════════════════════════════════════════════════════════════════════════
#  TRADE PLAN CONSTANTS 
# ══════════════════════════════════════════════════════════════════════════════

POSITION_USD = 1_000.0          # Fixed position size per trade
LEVERAGE     = 15.0             # Fixed 15x leverage
NOTIONAL     = POSITION_USD * LEVERAGE  # $15,000

FEE_RATE     = 0.0004           # 0.04% taker fee per leg
FEE_USD      = NOTIONAL * FEE_RATE * 2  # $12 per round-trip

SL_PCT       = 0.01333          # 1.333% SL dari entry (Standard v4)
TP_MIN_PCT   = 0.0071           # 0.71% TP target dari entry (Standard v4)

MAX_HOLD_CANDLES = 6            # Safety net: 6 candles = 24 jam

# Hybrid Multipliers
HALF_RISK_RATIO     = 0.5       # SL pindah ke 50% dari resiko awal (bukan 0/breakeven)
TP_EXT_BCD_CONF     = 0.85      # Ambang batas BCD untuk perpanjang TP
TP_EXT_FACTOR       = 1.5       # TP dikalikan 1.5x jika BCD yakin


# ══════════════════════════════════════════════════════════════════════════════
#  CALCULATIONS
# ══════════════════════════════════════════════════════════════════════════════

def calc_pnl(side: str, entry: float, exit_price: float) -> float:
    if side == "LONG":
        price_return = (exit_price - entry) / entry
    else:
        price_return = (entry - exit_price) / entry
    return round(NOTIONAL * price_return - FEE_USD, 2)


def floating_pnl_pct(side: str, entry: float, current_price: float) -> float:
    if side == "LONG":
        return (current_price - entry) / entry
    else:
        return (entry - current_price) / entry


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
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("datetime")
    return df


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["EMA20"] = ta.ema(df["Close"], length=20)
    df["EMA50"] = ta.ema(df["Close"], length=50)
    df["ATR14"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)
    return df


# ══════════════════════════════════════════════════════════════════════════════
#  EXIT CHECKER
# ══════════════════════════════════════════════════════════════════════════════

def check_sl_tp(side, sl, tp, c_high, c_low, c_close) -> tuple[float, str] | None:
    if side == "LONG":
        if c_low <= sl: return sl, "SL"
        if c_high >= tp: return (c_close, "TRAIL_TP") if c_close >= tp else (tp, "TP")
    else:
        if c_high >= sl: return sl, "SL"
        if c_low <= tp: return (c_close, "TRAIL_TP") if c_close <= tp else (tp, "TP")
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def run_hybrid_gold(
    window_start:     str   = "2024-01-01",
    window_end:       str   = "2026-03-04",
    required_history: int   = 400,
    initial_capital:  float = 10_000.0,
):
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log.info("=" * 72)
    log.info("  BTC-QUANT v4.4 — HYBRID GOLD ENGINE (WR 57% Target)")
    log.info(f"  Window  : {window_start}  →  {window_end}")
    log.info(f"  Rules   : Half-Risk SL ({HALF_RISK_RATIO*100}%) | BCD TP Ext ({TP_EXT_FACTOR}x)")
    log.info("=" * 72)

    df_all = load_full_dataset()
    df_all = add_indicators(df_all)

    start_dt = pd.to_datetime(window_start).tz_localize("UTC")
    end_dt   = pd.to_datetime(window_end).tz_localize("UTC")

    pos_all         = np.arange(len(df_all))
    trade_positions = pos_all[(df_all.index >= start_dt) & (df_all.index <= end_dt)]

    # Services
    from app.services.bcd_service import get_bcd_service
    from app.services.ai_service  import get_ai_service
    from app.services.ema_service import get_ema_service
    bcd_svc  = get_bcd_service()
    ai_svc   = get_ai_service()
    ema_svc  = get_ema_service()
    spectrum = DirectionalSpectrum()

    # State
    portfolio    = initial_capital
    equity_curve = [{"candle": df_all.index[trade_positions[0]].isoformat(), "equity": portfolio}]
    trades       = []
    position     = None 

    t_start = trade_positions[0]
    t_end   = trade_positions[-1]

    for i in range(t_start, t_end):
        candle_dt   = df_all.index[i]
        next_candle = df_all.iloc[i + 1]
        df_hist     = df_all.iloc[max(0, i - 500 + 1) : i + 1].copy()
        price_now   = float(df_hist["Close"].iloc[-1])
        
        c_high  = float(next_candle["High"])
        c_low   = float(next_candle["Low"])
        c_close = float(next_candle["Close"])

        # ── EXIT SECTION ──────────────────────────────────────────────────────
        if position is not None:
            holding = i - position["entry_idx"]
            
            # 1. Check Technical Exit (SL/TP)
            hit = check_sl_tp(position["side"], position["sl"], position["tp"], c_high, c_low, c_close)
            if hit:
                exit_price, exit_type = hit
                # Rename SL if it was already tightened
                if exit_type == "SL" and position.get("risk_tightened"):
                    exit_type = "HALF_RISK_SL"
                
                pnl = calc_pnl(position["side"], position["entry"], exit_price)
                portfolio += pnl
                _record_trade(trades, equity_curve, position, exit_price, exit_type, next_candle.name.isoformat(), pnl, portfolio, holding+1)
                icon = "✅" if pnl > 0 else "❌"
                log.info(f"  {icon} CLOSE {position['side']:5s} | {exit_type:15s} | PnL: {pnl:+.2f} | Equity: {portfolio:,.2f}")
                position = None
                continue

            # 2. Rule-Based Exit / Adjustment (Candle 1 close)
            if holding == 1:
                fpnl_pct = floating_pnl_pct(position["side"], position["entry"], c_close)
                
                if fpnl_pct <= 0:
                    # RULE 1: Still negative? Exit now. (Mencegah kian dalam)
                    exit_price = c_close
                    pnl = calc_pnl(position["side"], position["entry"], exit_price)
                    portfolio += pnl
                    _record_trade(trades, equity_curve, position, exit_price, "TIME_EXIT_LOSS", next_candle.name.isoformat(), pnl, portfolio, 1)
                    log.info(f"  ❌ CLOSE {position['side']:5s} | TIME_EXIT_LOSS | PnL: {pnl:+.2f} | Equity: {portfolio:,.2f}")
                    position = None
                else:
                    # RULE 2: Profit? Tighten risk to HALF (not zero) for breathing room
                    entry = position["entry"]
                    tight_sl_dist = (entry * SL_PCT) * HALF_RISK_RATIO
                    if position["side"] == "LONG":
                        position["sl"] = entry - tight_sl_dist
                    else:
                        position["sl"] = entry + tight_sl_dist
                    position["risk_tightened"] = True
                    log.info(f"  🛡️ HALF-RISK LOCK | {position['side']} | PnL {fpnl_pct*100:+.2f}% | SL Move to {position['sl']:.0f}")

            # 3. Safety Net (Max Hold)
            elif holding >= MAX_HOLD_CANDLES - 1:
                exit_price = c_close
                pnl = calc_pnl(position["side"], position["entry"], exit_price)
                portfolio += pnl
                _record_trade(trades, equity_curve, position, exit_price, "MAX_HOLD_EXIT", next_candle.name.isoformat(), pnl, portfolio, holding+1)
                log.info(f"  ⏰ CLOSE {position['side']:5s} | MAX_HOLD_EXIT  | PnL: {pnl:+.2f} | Equity: {portfolio:,.2f}")
                position = None

            continue

        # ── ENTRY SECTION ─────────────────────────────────────────────────────
        try:
            # EMA proxy
            ema20 = float(df_hist["EMA20"].iloc[-1])
            ema50 = float(df_hist["EMA50"].iloc[-1])
            raw_trend = "BULL" if price_now > ema50 else "BEAR"

            # Layers
            label, tag, bcd_conf, hmm_states, hmm_index = bcd_svc.get_regime_and_states(df_hist, funding_rate=0)
            l1_vote = float(bcd_conf if tag == "bull" else -bcd_conf)
            
            l2_aligned, _, _ = ema_svc.get_alignment(df_hist, raw_trend)
            l2_vote = 1.0 if (l2_aligned and raw_trend=="BULL") else (-1.0 if (l2_aligned and raw_trend=="BEAR") else 0.0)
            
            ai_bias, ai_conf = ai_svc.get_confidence(df_hist, hmm_states=hmm_states, hmm_index=hmm_index)
            conf_norm = (max(50.0, min(100.0, float(ai_conf))) - 50.0) / 50.0
            l3_vote = conf_norm if str(ai_bias) == "BULL" else -conf_norm
            
            spec = spectrum.calculate(l1_vote, l2_vote, l3_vote, 1.0, 5.0)

            if spec.trade_gate in ("ACTIVE", "ADVISORY"):
                side = "LONG" if spec.directional_bias >= 0 else "SHORT"
                
                # DYNAMIC TP EXTENSION
                tp_mult = 1.0
                if bcd_conf > TP_EXT_BCD_CONF:
                    tp_mult = TP_EXT_FACTOR
                    log.info(f"  🚀 BCD TP EXTENSION ACTIVE ({TP_EXT_FACTOR}x) | Conf: {bcd_conf:.2f}")

                tp_val = price_now * (1.0 + (TP_MIN_PCT * tp_mult)) if side == "LONG" else price_now * (1.0 - (TP_MIN_PCT * tp_mult))
                sl_val = price_now * (1.0 - SL_PCT) if side == "LONG" else price_now * (1.0 + SL_PCT)

                position = {
                    "side": side, "entry": price_now, "sl": sl_val, "tp": tp_val, "initial_sl": sl_val,
                    "entry_idx": i, "entry_time": candle_dt.isoformat(), "gate": spec.trade_gate,
                    "regime": str(tag), "bcd_conf": round(float(bcd_conf), 4), "risk_tightened": False
                }
                log.info(f"  🟢 OPEN {side:5s} @ {price_now:,.0f} | SL: {sl_val:,.0f} | TP: {tp_val:,.0f} | Equity: {portfolio:,.2f}")

        except Exception as e:
            continue

        # Heartbeat every 10 seconds
        now = time.time()
        if i % 100 == 0:
            pct = (i - t_start) / max(1, t_end - t_start) * 100
            log.info(f"  📊 Progress: {pct:.1f}% | Equity: {portfolio:,.2f} | Trades: {len(trades)}")


    # Summary & Save
    _save_results(trades, equity_curve, initial_capital, portfolio, run_ts)


def _record_trade(trades, equity_curve, pos, exit_p, exit_type, exit_time, pnl, portfolio, holding):
    trades.append({
        "entry_time": pos["entry_time"], "exit_time": exit_time, "side": pos["side"],
        "entry_price": round(pos["entry"], 2), "exit_price": round(exit_p, 2),
        "pnl_usd": round(pnl, 2), "exit_type": exit_type, "regime": pos["regime"],
        "holding_candles": holding, "equity": round(portfolio, 2)
    })
    equity_curve.append({"candle": exit_time, "equity": round(portfolio, 2)})

def _save_results(trades, equity_curve, initial, final, ts):
    tdf = pd.DataFrame(trades)
    if tdf.empty: return
    
    wins = (tdf["pnl_usd"] > 0).sum()
    wr = wins / len(tdf) * 100
    avg_w = tdf[tdf["pnl_usd"] > 0]["pnl_usd"].mean()
    avg_l = abs(tdf[tdf["pnl_usd"] <= 0]["pnl_usd"].mean())
    rr = avg_w / avg_l if avg_l > 0 else 0
    
    log.info("\n" + "═"*40 + "\n  FINAL HYBRID GOLD SUMMARY\n" + "═"*40)
    log.info(f"  Net PnL   : ${final-initial:>10,.2f} ({(final/initial-1)*100:+.2f}%)")
    log.info(f"  Win Rate  : {wr:.1f}%")
    log.info(f"  R:R Ratio : 1:{rr:.2f}")
    log.info(f"  Trades    : {len(tdf)}")
    
    run_tag = f"v4_4_hybrid_gold_{ts}"
    tdf.to_csv(_RESULTS_DIR / f"{run_tag}_trades.csv", index=False)
    with open(_RESULTS_DIR / f"{run_tag}_summary.json", "w") as f:
        json.dump({"net_pnl_pct": (final/initial-1)*100, "win_rate_pct": wr, "n_trades": len(tdf), "rr_ratio": rr}, f, indent=2)

if __name__ == "__main__":
    run_hybrid_gold()
