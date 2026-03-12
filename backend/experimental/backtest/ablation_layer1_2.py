"""
╔══════════════════════════════════════════════════════════════════════╗
║  BTC-QUANT: ABLATION STUDY - LAYER 1 + 2 (BCD + EMA)                ║
║  Simulates BCD Regime filtered by EMA Alignment.                     ║
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
_BACKEND_DIR = str(Path(__file__).resolve().parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

os.environ["BTC_QUANT_LAYER1_ENGINE"] = "bcd"

from engines.layer1_volatility import get_vol_estimator
from app.services.risk_manager import get_risk_manager
from utils.spectrum import DirectionalSpectrum
from data_engine import DB_PATH

# ── Output Directories ─────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(_BACKEND_DIR).parent
_RESULTS_DIR  = _PROJECT_ROOT / "backtest" / "results" / "ablation"
_LOGS_DIR     = _PROJECT_ROOT / "backtest" / "logs" / "ablation"
_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
_LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Logging Setup ──────────────────────────────────────────────────────────────
_LOG_FILE = _LOGS_DIR / f"ablation_l12_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("ablation_l12")

def load_full_dataset() -> pd.DataFrame:
    with duckdb.connect(DB_PATH, read_only=True) as con:
        df = con.execute("""
            SELECT o.timestamp, o.open AS Open, o.high AS High, o.low AS Low, o.close AS Close, o.volume AS Volume,
                   COALESCE(o.cvd, 0.0) AS CVD, COALESCE(m.funding_rate, 0.0) AS Funding,
                   COALESCE(m.open_interest, 0.0) AS OI, COALESCE(m.fgi_value, 50.0) AS FGI
            FROM btc_ohlcv_4h o
            ASOF LEFT JOIN market_metrics m ON o.timestamp >= m.timestamp
            ORDER BY o.timestamp ASC
        """).fetchdf()
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.set_index("datetime")

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["EMA20"] = ta.ema(df["Close"], length=20)
    df["EMA50"] = ta.ema(df["Close"], length=50)
    df["ATR14"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)
    return df

def run_ablation_l12(window_start: str, window_end: str, initial_capital: float = 10000.0):
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log.info(f"STARTING ABLATION: L1 + L2 | Window: {window_start} -> {window_end}")
    
    df_all = load_full_dataset()
    df_all = add_indicators(df_all)
    
    start_dt = pd.to_datetime(window_start).tz_localize("UTC")
    end_dt   = pd.to_datetime(window_end  ).tz_localize("UTC")
    
    warmup = 400
    db_first = df_all.index[warmup]
    if start_dt < db_first: start_dt = db_first
    
    trade_pos = np.where((df_all.index >= start_dt) & (df_all.index <= end_dt))[0]
    if len(trade_pos) == 0: return

    from app.services.bcd_service import get_bcd_service
    from app.services.ema_service import get_ema_service
    hmm_svc  = get_bcd_service()
    ema_svc  = get_ema_service()
    
    portfolio = initial_capital
    trades = []
    position = None
    daily_stats = {}
    t0 = time.time()
    last_log = t0

    for idx in trade_pos:
        candle_dt = df_all.index[idx]
        next_candle = df_all.iloc[idx + 1]
        df_hist = df_all.iloc[max(0, idx - 500 + 1) : idx + 1].copy()
        
        price_now = float(df_hist["Close"].iloc[-1])
        atr14 = float(df_hist["ATR14"].iloc[-1]) if not pd.isna(df_hist["ATR14"].iloc[-1]) else 0.01

        if position is not None:
            exit_price, exit_type = None, None
            if position["side"] == "LONG":
                if next_candle["Low"] <= position["sl"]: exit_price, exit_type = position["sl"], "SL"
                elif next_candle["High"] >= position["tp"]: exit_price, exit_type = position["tp"], "TP"
            else:
                if next_candle["High"] >= position["sl"]: exit_price, exit_type = position["sl"], "SL"
                elif next_candle["Low"] <= position["tp"]: exit_price, exit_type = position["tp"], "TP"
            
            if exit_price:
                move = (exit_price - position["entry"]) if position["side"] == "LONG" else (position["entry"] - exit_price)
                pnl = position["risk_usd"] * (move / abs(position["entry"] - position["sl"])) - (position["risk_usd"] * 0.0008)
                portfolio += pnl
                trades.append({
                    "entry_time": position["entry_time"], "exit_time": next_candle.name.isoformat(),
                    "side": position["side"], "pnl_usd": round(pnl, 2), "equity": round(portfolio, 2)
                })
                position = None

        if position is None:
            try:
                # EMA Trend Logic
                ema20 = df_hist["EMA20"].iloc[-1]
                ema50 = df_hist["EMA50"].iloc[-1]
                raw_trend = "BULL" if price_now > ema50 else "BEAR"
                
                l2_aligned, _, _ = ema_svc.get_alignment(df_hist, raw_trend)
                label, tag, _ = hmm_svc.get_regime_with_posterior(df_hist, 0)
                
                # Entry Confluence L1 + L2
                if l2_aligned:
                    side = None
                    if tag == "bull" and raw_trend == "BULL": side = "LONG"
                    elif tag == "bear" and raw_trend == "BEAR": side = "SHORT"
                    
                    if side:
                        sl_m, tp_m = 2.0, 3.0
                        sl = price_now - atr14 * sl_m if side == "LONG" else price_now + atr14 * sl_m
                        tp = price_now + atr14 * tp_m if side == "LONG" else price_now - atr14 * tp_m
                        position = {
                            "side": side, "entry": price_now, "sl": sl, "tp": tp,
                            "risk_usd": portfolio * 0.02, "entry_time": candle_dt.isoformat()
                        }
            except: pass

        if time.time() - last_log >= 60:
            log.info(f"  ▶ [{candle_dt.date()}] Equity: ${portfolio:,.0f} | Trades: {len(trades)}")
            last_log = time.time()

    summary = {"final_equity": round(portfolio, 2), "net_pnl_pct": round((portfolio/initial_capital-1)*100, 2), "n_trades": len(trades)}
    with open(_RESULTS_DIR / f"summary_l12_{run_ts}.json", "w") as f: json.dump(summary, f, indent=2)
    log.info(f"COMPLETED. Final Equity: ${portfolio:,.2f}")

if __name__ == "__main__":
    run_ablation_l12("2023-01-24", "2026-03-03")
