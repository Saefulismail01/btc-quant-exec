"""
BTC-QUANT: Full System Backtest Engine (BCD + Risk Management)
Validates the target of 3% daily returns using compounding equity and 2% risk.
"""

import sys
import time
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

_BACKEND_DIR = str(Path(__file__).resolve().parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from data_engine import DuckDBManager, DB_PATH
from engines.layer1_bcd import BayesianChangepointModel
from engines.layer1_volatility import VolatilityRegimeEstimator

# --- Configuration ---
INITIAL_CAPITAL = 10000.0
RISK_PER_TRADE = 0.02          # Risk 2% of equity per trade
FEE_RATE = 0.0004              # 0.04% taker fee Binance

def run_compounding_backtest(df: pd.DataFrame, window_name: str) -> dict:
    import pandas_ta as ta
    t0 = time.time()
    
    print(f"\n{'═'*60}")
    print(f"  COMPOUNDING BACKTEST: {window_name}")
    print(f"  Data: {len(df)} candles")
    print(f"{'═'*60}")
    
    # ── 1. Volatility Regime ──
    vol_est = VolatilityRegimeEstimator()
    vol_params = vol_est.estimate_params(df)
    vol_regime_h = vol_params.get("vol_regime", "Normal")
    halflife_h = float(vol_params.get("mean_reversion_halflife_candles", 999.0))
    
    # ── 2. Train BCD ──
    bcd = BayesianChangepointModel()
    bcd.train_global(df)
    states, idx = bcd.get_state_sequence_raw(df)
    
    regime_series = pd.Series([bcd.state_map.get(int(s), "Unknown") for s in states], index=idx, name="regime")
    
    df["ATR14"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)
    
    sl_tp = vol_est.get_sl_tp_multipliers(vol_regime_h, halflife_h, 0.5)
    sl_mult = sl_tp["sl_multiplier"]
    tp_mult = sl_tp["tp1_multiplier"]
    
    # ── 3. Simulate Trades ──
    valid_df = df.loc[idx].copy()
    valid_df["regime"] = regime_series.values
    
    trades = []
    equity = INITIAL_CAPITAL
    equity_curve = []
    position = None
    
    consecutive_losses = 0
    
    for i in range(len(valid_df) - 1):
        row = valid_df.iloc[i]
        next_row = valid_df.iloc[i + 1]
        
        close = float(row["Close"])
        high_next = float(next_row["High"])
        low_next = float(next_row["Low"])
        close_next = float(next_row["Close"])
        regime = row["regime"]
        atr = float(row["ATR14"]) if not pd.isna(row["ATR14"]) else close * 0.01
        ts = row.name if hasattr(row, 'name') else i
        
        # Track daily equity for daily loss limits (simplified to just tracking peak)
        
        if position is not None:
            exit_price = None
            exit_type = None
            
            if position["side"] == "LONG":
                if low_next <= position["sl"]:
                    exit_price = position["sl"]
                    exit_type = "SL"
                elif high_next >= position["tp"]:
                    exit_price = position["tp"]
                    exit_type = "TP"
                elif regime != "Bullish Trend":
                    exit_price = close
                    exit_type = "REGIME_FLIP"
            else:
                if high_next >= position["sl"]:
                    exit_price = position["sl"]
                    exit_type = "SL"
                elif low_next <= position["tp"]:
                    exit_price = position["tp"]
                    exit_type = "TP"
                elif regime != "Bearish Trend":
                    exit_price = close
                    exit_type = "REGIME_FLIP"
            
            if exit_price is not None:
                # Calculate PnL in $
                entry_price = position["entry"]
                position_size_usd = position["size_usd"]
                
                if position["side"] == "LONG":
                    price_change_pct = (exit_price / entry_price) - 1
                else:
                    price_change_pct = 1 - (exit_price / entry_price)
                
                # Deduct fees (entry + exit)
                gross_pnl = position_size_usd * price_change_pct
                fee_cost = position_size_usd * FEE_RATE * 2
                net_pnl = gross_pnl - fee_cost
                
                equity += net_pnl
                
                # Risk manager adjustments
                if net_pnl > 0:
                    consecutive_losses = 0
                else:
                    consecutive_losses += 1
                
                trades.append({
                    "entry_time": position["time"],
                    "exit_time": ts,
                    "side": position["side"],
                    "entry": entry_price,
                    "exit": exit_price,
                    "exit_type": exit_type,
                    "size_usd": position_size_usd,
                    "net_pnl": net_pnl,
                    "equity": equity
                })
                position = None
                
        equity_curve.append({"time": ts, "equity": equity})
                
        if position is None:
            # Risk Management: Sizing
            # Distance to SL in %
            sl_dist_pct = (atr * sl_mult) / close
            
            # Risk reduction if losing streak
            current_risk_pct = RISK_PER_TRADE
            if consecutive_losses >= 3:
                current_risk_pct = RISK_PER_TRADE / 2.0  # Cut risk in half
                
            risk_usd = equity * current_risk_pct
            
            # Position size = risk_usd / sl_dist_pct
            # (If SL triggers, we lose exactly risk_usd + fees)
            target_pos_size = risk_usd / sl_dist_pct if sl_dist_pct > 0 else 0
            
            # Cap max leverage at 20x for safety
            target_pos_size = min(target_pos_size, equity * 20)
            
            if regime == "Bullish Trend" and target_pos_size > 0:
                position = {
                    "side": "LONG",
                    "entry": close,
                    "sl": close - atr * sl_mult,
                    "tp": close + atr * tp_mult,
                    "size_usd": target_pos_size,
                    "time": ts
                }
            elif regime == "Bearish Trend" and target_pos_size > 0:
                position = {
                    "side": "SHORT",
                    "entry": close,
                    "sl": close + atr * sl_mult,
                    "tp": close - atr * tp_mult,
                    "size_usd": target_pos_size,
                    "time": ts
                }
                
    elapsed = time.time() - t0
    
    if not trades:
        print("No trades executed.")
        return {}
        
    trades_df = pd.DataFrame(trades)
    
    total = len(trades_df)
    wins = (trades_df["net_pnl"] > 0).sum()
    win_rate = wins / total * 100
    
    total_net_pnl = equity - INITIAL_CAPITAL
    roi_pct = (total_net_pnl / INITIAL_CAPITAL) * 100
    
    days = len(valid_df) / 6.0
    daily_return = roi_pct / days if days > 0 else 0
    
    peaks = pd.Series([x['equity'] for x in equity_curve]).cummax()
    drawdowns = (pd.Series([x['equity'] for x in equity_curve]) - peaks) / peaks * 100
    max_dd = drawdowns.min()
    
    gross_profit = trades_df[trades_df["net_pnl"] > 0]["net_pnl"].sum()
    gross_loss = abs(trades_df[trades_df["net_pnl"] <= 0]["net_pnl"].sum())
    pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    print(f"\n  ═══ RESULTS: {window_name} ═══")
    print(f"  Initial Equity   : ${INITIAL_CAPITAL:,.2f}")
    print(f"  Final Equity     : ${equity:,.2f}")
    print(f"  Net PnL          : {roi_pct:+.2f}% (${total_net_pnl:+,.2f})")
    print(f"  Total Trades     : {total}")
    print(f"  Win Rate         : {win_rate:.1f}%")
    print(f"  Daily Return     : {daily_return:+.3f}%/day")
    print(f"  Max Drawdown     : {max_dd:.2f}%")
    print(f"  Profit Factor    : {pf:.2f}")

    return {
        "window": window_name,
        "equity_start": INITIAL_CAPITAL,
        "equity_end": equity,
        "roi_pct": roi_pct,
        "daily_return": daily_return,
        "max_dd": max_dd,
        "win_rate": win_rate,
        "trades": total,
        "pf": pf,
        "df": trades_df
    }

def main():
    print("\n" + "═"*70)
    print("  BTC-QUANT: Full BCD Compounding Backtest Engine")
    print("  Data: Nov 2022 - Mar 2026")
    print("  Rules: 2% Risk/Trade | Compounding Equity | 0.04% Fee")
    print("═"*70)

    db = DuckDBManager(DB_PATH)
    full_df = db.get_latest_ohlcv(limit=10000)

    if len(full_df) < 300:
         print("Not enough data.")
         return
         
    # Convert index to datetime if it's timestamp
    if "timestamp" in full_df.columns:
        full_df.index = pd.to_datetime(full_df["timestamp"], unit='ms')

    # Run for the whole available window
    res_full = run_compounding_backtest(full_df, "Nov 2022 - Present (Full)")
    
    # Run partitioned
    windows = [
        ("2022-2023 Bear/Recovery", "2022-11-01", "2024-01-01"),
        ("2024 Bull Market", "2024-01-01", "2025-01-01"),
        ("2025-2026 Latest", "2025-01-01", "2026-12-31"),
    ]
    
    results = []
    
    for w_name, start_date, end_date in windows:
        sub_df = full_df[(full_df.index >= start_date) & (full_df.index < end_date)]
        if len(sub_df) > 200:
            res = run_compounding_backtest(sub_df, w_name)
            if res:
                results.append(res)
                
    # Save results
    out_dir = Path(_BACKEND_DIR).parent / "backtest" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    if res_full and "df" in res_full:
        res_full["df"].to_csv(out_dir / "bcd_compounding_full_trades.csv", index=False)
        print(f"\n[✓] Extracted full trade log to: {out_dir / 'bcd_compounding_full_trades.csv'}")

if __name__ == "__main__":
    main()
