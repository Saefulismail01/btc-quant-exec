"""
╔══════════════════════════════════════════════════════════════╗
║  BTC-QUANT: Walk-Forward Validation Engine v2               ║
║  Strategy: BCD Regime = Primary Signal                      ║
║                                                              ║
║  Logic (matches actual production system):                   ║
║    Bullish Trend  → LONG                                    ║
║    Bearish Trend  → SHORT                                   ║
║    Sideways       → NO TRADE (skip)                         ║
║                                                              ║
║  Exit: At regime change, SL, or TP hit                      ║
║  This tests whether BCD regime labels have real edge.       ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
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

# ── Configuration ────────────────────────────────────────────
FEE_RATE = 0.0004          # 0.04% per trade (Binance taker)
# SL/TP now determined by VolatilityRegimeEstimator per-trade


def run_regime_backtest(df: pd.DataFrame, window_name: str = "Full") -> tuple | dict:
    """
    Backtest BCD regime signals on historical data.
    
    Strategy:
        - When regime = Bullish Trend → go LONG at candle close
        - When regime = Bearish Trend → go SHORT at candle close
        - When regime = Sideways → close any position, skip
        - Exit on: regime flip, SL hit, TP hit
    """
    import pandas_ta as ta
    
    t0 = time.time()

    print(f"\n{'═'*60}")
    print(f"  REGIME BACKTEST: {window_name}")
    print(f"  Data: {len(df)} candles")
    print(f"{'═'*60}")

    if len(df) < 200:
        print(f"  [!] Insufficient data ({len(df)} rows)")
        return {"window": window_name, "error": "insufficient_data"}

    # ── Step 0: Initialize Heston vol estimator ──────────────
    vol_est = VolatilityRegimeEstimator()
    vol_params = vol_est.estimate_params(df)
    vol_regime_h = vol_params.get("vol_regime", "Normal")
    halflife_h = float(vol_params.get("mean_reversion_halflife_candles", 999.0))

    # ── Step 1: Train BCD and get regime labels ──────────────
    print("  [1/2] Training BCD...")
    bcd = BayesianChangepointModel()
    bcd.train_global(df)
    states, idx = bcd.get_state_sequence_raw(df)
    
    if states is None:
        print("  [!] BCD training failed.")
        return {"window": window_name, "error": "bcd_failed"}

    # Map state IDs to labels for the valid index
    regime_series = pd.Series(
        [bcd.state_map.get(int(s), "Unknown") for s in states],
        index=idx,
        name="regime"
    )
    
    # Compute ATR for SL/TP
    df["ATR14"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)
    
    bcd_time = time.time() - t0
    n_cp = len(bcd._changepoints)

    # Get SL/TP multipliers from Heston (regime-aware)
    bias_score = 0.5  # neutral default for backtest
    if hasattr(bcd, 'get_regime_bias'):
        bias_all = bcd.get_regime_bias()
        # Use avg bias score
        bias_vals = [v.get("bias_score", 0.5) for v in bias_all.values() if isinstance(v, dict)]
        if bias_vals:
            bias_score = sum(bias_vals) / len(bias_vals)

    sl_tp = vol_est.get_sl_tp_multipliers(vol_regime_h, halflife_h, bias_score)
    sl_mult = sl_tp["sl_multiplier"]
    tp_mult = sl_tp["tp1_multiplier"]
    preset  = sl_tp["preset_name"]

    print(f"  [1/2] BCD done in {bcd_time:.1f}s | {n_cp} changepoints")
    print(f"  [1/2] Heston: regime={vol_regime_h} preset={preset} SL={sl_mult}× TP={tp_mult}×")
    
    # Regime distribution
    regime_counts = regime_series.value_counts()
    for r, c in regime_counts.items():
        print(f"    {r:30s}: {c:4d} candles ({c/len(regime_series)*100:.1f}%)")

    # ── Step 2: Simulate trading ─────────────────────────────
    print("  [2/2] Simulating trades...")

    trades = []
    position = None  # {'side': 'LONG'|'SHORT', 'entry': float, 'sl': float, 'tp': float, 'entry_idx': int}

    valid_df = df.loc[idx].copy()
    valid_df["regime"] = regime_series.values

    for i in range(len(valid_df) - 1):
        row = valid_df.iloc[i]
        next_row = valid_df.iloc[i + 1]
        
        close = float(row["Close"])
        high_next = float(next_row["High"])
        low_next = float(next_row["Low"])
        close_next = float(next_row["Close"])
        regime = row["regime"]
        atr = float(row["ATR14"]) if not pd.isna(row["ATR14"]) else close * 0.01
        
        # ── Check exit conditions for existing position ──────
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
                    # Regime changed → exit at current close
                    exit_price = close
                    exit_type = "REGIME_FLIP"
            else:  # SHORT
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
                # Calculate PnL
                if position["side"] == "LONG":
                    pnl_pct = (exit_price / position["entry"] - 1) * 100
                else:
                    pnl_pct = (1 - exit_price / position["entry"]) * 100
                
                pnl_pct -= FEE_RATE * 2 * 100  # Round-trip fees
                
                trades.append({
                    "entry_i": position["entry_i"],
                    "exit_i": i,
                    "side": position["side"],
                    "entry": position["entry"],
                    "exit": exit_price,
                    "exit_type": exit_type,
                    "pnl_pct": round(pnl_pct, 4),
                    "regime": position["entry_regime"],
                    "duration": i - position["entry_i"],
                })
                position = None
        
        # ── Check entry conditions ───────────────────────────
        if position is None:
            if regime == "Bullish Trend":
                position = {
                    "side": "LONG",
                    "entry": close,
                    "sl": close - atr * sl_mult,
                    "tp": close + atr * tp_mult,
                    "entry_i": i,
                    "entry_regime": regime,
                }
            elif regime == "Bearish Trend":
                position = {
                    "side": "SHORT",
                    "entry": close,
                    "sl": close + atr * sl_mult,
                    "tp": close - atr * tp_mult,
                    "entry_i": i,
                    "entry_regime": regime,
                }
            # Sideways → no trade

    # Close any remaining position at last close
    if position is not None:
        last_close = float(valid_df.iloc[-1]["Close"])
        if position["side"] == "LONG":
            pnl_pct = (last_close / position["entry"] - 1) * 100
        else:
            pnl_pct = (1 - last_close / position["entry"]) * 100
        pnl_pct -= FEE_RATE * 2 * 100
        trades.append({
            "entry_i": position["entry_i"],
            "exit_i": len(valid_df) - 1,
            "side": position["side"],
            "entry": position["entry"],
            "exit": last_close,
            "exit_type": "EOD",
            "pnl_pct": round(pnl_pct, 4),
            "regime": position["entry_regime"],
            "duration": len(valid_df) - 1 - position["entry_i"],
        })

    # ── Results ──────────────────────────────────────────────
    if not trades:
        print("  No trades generated.")
        return {"window": window_name, "error": "no_trades"}

    trades_df = pd.DataFrame(trades)
    
    total = len(trades_df)
    wins = (trades_df["pnl_pct"] > 0).sum()
    losses = (trades_df["pnl_pct"] <= 0).sum()
    win_rate = wins / total * 100
    
    total_pnl = trades_df["pnl_pct"].sum()
    avg_win = trades_df[trades_df["pnl_pct"] > 0]["pnl_pct"].mean() if wins > 0 else 0
    avg_loss = trades_df[trades_df["pnl_pct"] <= 0]["pnl_pct"].mean() if losses > 0 else 0
    
    # Daily return estimate
    total_candles = len(valid_df)
    total_days = total_candles / 6.0
    daily_return = total_pnl / total_days if total_days > 0 else 0
    
    # Max Drawdown (on cumulative PnL)
    cumul = trades_df["pnl_pct"].cumsum().values
    running_max = np.maximum.accumulate(cumul)
    drawdowns = cumul - running_max
    max_dd = float(np.min(drawdowns)) if len(drawdowns) > 0 else 0
    
    # Profit Factor
    gross_profit = trades_df[trades_df["pnl_pct"] > 0]["pnl_pct"].sum()
    gross_loss = abs(trades_df[trades_df["pnl_pct"] <= 0]["pnl_pct"].sum())
    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    
    # Per exit-type breakdown
    exit_stats = {}
    for et in trades_df["exit_type"].unique():
        sub = trades_df[trades_df["exit_type"] == et]
        exit_stats[et] = {
            "count": len(sub),
            "win_rate": round((sub["pnl_pct"] > 0).mean() * 100, 1),
            "avg_pnl": round(sub["pnl_pct"].mean(), 3),
        }
    
    # Per side breakdown
    side_stats = {}
    for side in ["LONG", "SHORT"]:
        sub = trades_df[trades_df["side"] == side]
        if len(sub) > 0:
            side_stats[side] = {
                "count": len(sub),
                "win_rate": round((sub["pnl_pct"] > 0).mean() * 100, 1),
                "avg_pnl": round(sub["pnl_pct"].mean(), 3),
                "total_pnl": round(sub["pnl_pct"].sum(), 2),
            }

    elapsed = time.time() - t0

    summary = {
        "window": window_name,
        "total_trades": total,
        "wins": int(wins),
        "losses": int(losses),
        "win_rate_pct": round(win_rate, 2),
        "total_pnl_pct": round(total_pnl, 2),
        "daily_return_pct": round(daily_return, 3),
        "avg_win_pct": round(avg_win, 3),
        "avg_loss_pct": round(avg_loss, 3),
        "max_drawdown_pct": round(max_dd, 2),
        "profit_factor": round(pf, 3),
        "exit_stats": exit_stats,
        "side_stats": side_stats,
        "elapsed_sec": round(elapsed, 1),
    }

    print(f"\n{'─'*50}")
    print(f"  ═══ RESULTS: {window_name} ({elapsed:.0f}s) ═══")
    print(f"  Total Trades          : {total}")
    print(f"  Win Rate              : {win_rate:.1f}%")
    print(f"  Total PnL (1x)        : {total_pnl:+.2f}%")
    print(f"  Daily Return (avg)    : {daily_return:+.3f}%/day")
    print(f"  Avg Win / Avg Loss    : {avg_win:+.3f}% / {avg_loss:.3f}%")
    print(f"  Max Drawdown          : {max_dd:.2f}%")
    print(f"  Profit Factor         : {pf:.3f}")
    print(f"\n  By Exit Type:")
    for et, s in exit_stats.items():
        print(f"    {et:15s}: n={s['count']:3d}  WR={s['win_rate']:5.1f}%  AvgPnL={s['avg_pnl']:+.3f}%")
    print(f"\n  By Side:")
    for side, s in side_stats.items():
        print(f"    {side:6s}: n={s['count']:3d}  WR={s['win_rate']:5.1f}%  TotalPnL={s['total_pnl']:+.2f}%  AvgPnL={s['avg_pnl']:+.3f}%")

    return summary, trades_df


def main():
    print("\n" + "═"*70)
    print("  BTC-QUANT: BCD v3 Regime Backtest Engine")
    print("  Strategy: Bullish→LONG, Bearish→SHORT, Sideways→SKIP")
    print("  Exit: Regime flip / SL / TP")
    print("═"*70)

    db = DuckDBManager(DB_PATH)
    full_df = db.get_latest_ohlcv(limit=8000)

    if len(full_df) < 300:
        print(f"\n  [!] Insufficient data: {len(full_df)} candles.")
        return

    print(f"\n  Total data: {len(full_df)} candles")
    print(f"  Date range: {full_df.index[0]} to {full_df.index[-1]}")

    all_results = []
    all_details = []

    if "timestamp" in full_df.columns:
        windows = [
            ("2023 Full", datetime(2023, 1, 1), datetime(2024, 1, 1)),
            ("2024 H2",   datetime(2024, 7, 1), datetime(2025, 1, 1)),
            ("2025-2026", datetime(2025, 1, 1), datetime(2026, 12, 31)),
        ]

        for name, start, end in windows:
            start_ms = int(start.timestamp() * 1000)
            end_ms   = int(end.timestamp() * 1000)
            window_df = full_df[
                (full_df["timestamp"] >= start_ms) & (full_df["timestamp"] < end_ms)
            ].copy()

            if len(window_df) < 200:
                print(f"\n  [!] Skipping {name}: only {len(window_df)} candles")
                continue

            result = run_regime_backtest(window_df, window_name=name)
            if isinstance(result, tuple):
                summary, detail_df = result
                all_results.append(summary)
                all_details.append(detail_df)
            else:
                all_results.append(result)
    else:
        result = run_regime_backtest(full_df, window_name="Full Dataset")
        if isinstance(result, tuple):
            summary, detail_df = result
            all_results.append(summary)
            all_details.append(detail_df)
        else:
            all_results.append(result)

    # ── Aggregate ────────────────────────────────────────────
    print("\n" + "═"*70)
    print("  ═══ AGGREGATE SUMMARY ═══")
    print("═"*70)

    valid = [r for r in all_results if "error" not in r]
    if valid:
        tbl = pd.DataFrame([{
            "Window": r["window"],
            "Trades": r["total_trades"],
            "WR": f"{r['win_rate_pct']:.1f}%",
            "PnL": f"{r['total_pnl_pct']:+.2f}%",
            "Daily": f"{r['daily_return_pct']:+.3f}%",
            "MaxDD": f"{r['max_drawdown_pct']:.2f}%",
            "PF": f"{r['profit_factor']:.2f}",
            "Time": f"{r['elapsed_sec']:.0f}s",
        } for r in valid])
        print(tbl.to_string(index=False))

        # Save
        out_dir = Path(_BACKEND_DIR).parent / "backtest" / "results"
        out_dir.mkdir(parents=True, exist_ok=True)

        pd.DataFrame(valid).to_csv(out_dir / "bcd_walk_forward_summary.csv", index=False)
        print(f"\n  [✓] Summary → {out_dir / 'bcd_walk_forward_summary.csv'}")

        if all_details:
            pd.concat(all_details, ignore_index=True).to_csv(
                out_dir / "bcd_walk_forward_details.csv", index=False)
            print(f"  [✓] Details → {out_dir / 'bcd_walk_forward_details.csv'}")

        # Verdict
        avg_wr    = np.mean([r["win_rate_pct"]    for r in valid])
        avg_daily = np.mean([r["daily_return_pct"] for r in valid])
        avg_pf    = np.mean([r["profit_factor"]   for r in valid])

        print(f"\n  Avg OOS Win Rate  : {avg_wr:.1f}%")
        print(f"  Avg Daily Return  : {avg_daily:+.3f}%")
        print(f"  Avg Profit Factor : {avg_pf:.2f}")

        if avg_wr >= 52 and avg_daily > 0 and avg_pf > 1.0:
            print("\n  ✅ VERDICT: BCD regime strategy PASSES validation.")
        elif avg_wr >= 50 and avg_pf >= 1.0:
            print("\n  ⚠️  VERDICT: MARGINAL — profitable but below 52% WR target.")
        else:
            print("\n  ❌ VERDICT: FAIL — strategy not profitable OOS at current settings.")
    else:
        print("  No valid results.")


if __name__ == "__main__":
    main()
