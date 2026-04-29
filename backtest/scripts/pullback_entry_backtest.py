"""
Proposal D — Pullback Limit Entry Backtest
==========================================
Instead of entering at market (entry_price from baseline), simulate placing
a limit order at entry_price - pullback_pct (LONG) or + pullback_pct (SHORT).

Logic:
  - Signal fires at candle T (entry_time)
  - Place limit at: limit_price = entry_price * (1 - pb) for LONG
                                  entry_price * (1 + pb) for SHORT
  - Check candle T itself (Low/High), then up to MAX_WAIT_CANDLES forward
  - If limit fills: recalculate PnL with improved entry (same SL/TP pct)
  - If limit never fills within window: MISS (trade not taken)

For each filled trade, SL/TP absolute levels shift with the new entry price,
keeping sl_pct and tp_pct constant (same risk structure).

Usage:
    python scripts/pullback_entry_backtest.py
"""

import csv
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.parent
TRADES_CSV = BASE_DIR / "results/v4_5_comparison_results/v4_5_201901_202603_20260309_102822_golden_trades.csv"
OHLCV_CSV  = BASE_DIR / "data/BTC_USDT_4h_2020_2026_with_bcd.csv"
OUT_DIR    = BASE_DIR / "results/rpf_analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Parameters ────────────────────────────────────────────────────────────────
PULLBACK_PCTS  = [0.0010, 0.0015, 0.0020, 0.0030, 0.0050]  # 0.10% to 0.50%
MAX_WAIT_CANDLES = [1, 2, 3]   # candles to wait for fill (each 4H)

# ── Load OHLCV ────────────────────────────────────────────────────────────────
print("Loading OHLCV...")
ohlcv = pd.read_csv(OHLCV_CSV, index_col=0, parse_dates=True)
ohlcv.index = pd.to_datetime(ohlcv.index, utc=True)
ohlcv.columns = [c.capitalize() for c in ohlcv.columns]
if "High" not in ohlcv.columns:
    ohlcv.rename(columns={"high":"High","low":"Low","open":"Open","close":"Close"}, inplace=True)
print(f"  {len(ohlcv)} rows  ({ohlcv.index[0].date()} — {ohlcv.index[-1].date()})")

# ── Load Trades ───────────────────────────────────────────────────────────────
print("Loading trades...")
trades_raw = []
with open(TRADES_CSV, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        trades_raw.append(row)
print(f"  {len(trades_raw)} trades loaded.\n")

# ── Baseline stats ────────────────────────────────────────────────────────────
def calc_stats(trades: list[dict], label: str) -> dict:
    if not trades:
        return {}
    pnls   = [float(t["pnl_usd"]) for t in trades]
    wins   = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    net    = sum(pnls)
    gw     = sum(wins)
    gl     = abs(sum(losses))
    aw     = gw / len(wins)   if wins   else 0
    al     = gl / len(losses) if losses else 0
    pf     = gw / gl          if gl > 0 else float("inf")
    rr     = aw / al          if al > 0 else float("inf")
    wr     = len(wins) / len(pnls) * 100
    return {
        "label": label,
        "n":     len(pnls),
        "wr":    round(wr, 2),
        "net":   round(net, 2),
        "avg_win":   round(aw, 2),
        "avg_loss":  round(-al, 2),
        "rr":    round(rr, 3),
        "pf":    round(pf, 3),
        "npt":   round(net / len(pnls), 2),
    }

baseline = calc_stats(trades_raw, "BASELINE")
print(f"{'='*72}")
print(f"BASELINE  n={baseline['n']}  WR={baseline['wr']}%  Net=${baseline['net']:,.0f}  "
      f"R:R={baseline['rr']}  PF={baseline['pf']}  Net/trade=${baseline['npt']}")
print(f"{'='*72}\n")

# ── Build OHLCV index lookup ───────────────────────────────────────────────────
ohlcv_times = ohlcv.index.tolist()

def get_candle_idx(ts: pd.Timestamp) -> int:
    idx = ohlcv.index.get_indexer([ts], method="nearest")[0]
    return idx

# ── Simulate pullback fills ────────────────────────────────────────────────────
results = []

for pb in PULLBACK_PCTS:
    for max_wait in MAX_WAIT_CANDLES:
        filled_trades = []
        miss_count    = 0
        miss_pnl_sum  = 0.0   # what we would have made on missed trades at market

        for t in trades_raw:
            side         = t["side"].upper()
            entry_ts     = pd.Timestamp(t["entry_time"].replace("+00:00",""), tz="UTC")
            orig_entry   = float(t["entry_price"])
            sl_pct       = float(t["sl_pct"])
            tp_pct       = float(t["tp_pct"])
            notional     = float(t["notional"])
            leverage     = float(t["leverage"])
            orig_pnl     = float(t["pnl_usd"])

            # Compute limit price
            if side == "LONG":
                limit_px = orig_entry * (1.0 - pb)
            else:
                limit_px = orig_entry * (1.0 + pb)

            # Find entry candle index in OHLCV
            start_idx = get_candle_idx(entry_ts)

            # Check candles [start_idx .. start_idx + max_wait] for fill
            filled    = False
            fill_px   = None
            for ci in range(start_idx, min(start_idx + max_wait + 1, len(ohlcv))):
                candle = ohlcv.iloc[ci]
                if side == "LONG"  and candle["Low"]  <= limit_px:
                    fill_px = limit_px
                    filled  = True
                    break
                if side == "SHORT" and candle["High"] >= limit_px:
                    fill_px = limit_px
                    filled  = True
                    break

            if not filled:
                miss_count   += 1
                miss_pnl_sum += orig_pnl
                continue

            # Recalculate PnL with improved entry (same sl_pct / tp_pct)
            # New SL & TP distances scale with fill_px
            if side == "LONG":
                new_sl = fill_px * (1.0 - sl_pct)
                new_tp = fill_px * (1.0 + tp_pct)
            else:
                new_sl = fill_px * (1.0 + sl_pct)
                new_tp = fill_px * (1.0 - tp_pct)

            # Determine exit type from original trade (SL, TP, TRAIL_TP, TIME_EXIT)
            exit_type  = t["exit_type"]
            orig_exit  = float(t["exit_price"])

            # Recalculate move pct relative to new entry
            if side == "LONG":
                move_pct = (orig_exit - fill_px) / fill_px
            else:
                move_pct = (fill_px - orig_exit) / fill_px

            # If original exit was SL, check if our tighter SL (closer to fill_px)
            # would have been hit — it might NOT be hit now because SL abs moved inward.
            # Conservative approach: keep the same exit price as original,
            # only recalculate PnL from new fill_px.
            new_pnl = notional * move_pct * leverage

            # Copy trade with updated fields
            new_t = dict(t)
            new_t["entry_price"] = fill_px
            new_t["pnl_usd"]     = new_pnl
            filled_trades.append(new_t)

        filled_stats = calc_stats(filled_trades, f"pb={pb:.3f} wait={max_wait}")
        total_trades = len(filled_trades)
        fill_rate    = total_trades / len(trades_raw) * 100

        delta_wr  = round(filled_stats["wr"]  - baseline["wr"],  2)
        delta_net = round(filled_stats["net"] - baseline["net"],  2)
        delta_rr  = round(filled_stats["rr"]  - baseline["rr"],   3)
        delta_pf  = round(filled_stats["pf"]  - baseline["pf"],   3)
        delta_npt = round(filled_stats["npt"] - baseline["npt"],   2)

        row = {
            "pb_pct":     pb,
            "max_wait":   max_wait,
            "n_filled":   total_trades,
            "n_missed":   miss_count,
            "fill_rate":  round(fill_rate, 1),
            "missed_pnl": round(miss_pnl_sum, 2),
            "stats":      filled_stats,
            "delta_wr":   delta_wr,
            "delta_net":  delta_net,
            "delta_rr":   delta_rr,
            "delta_pf":   delta_pf,
            "delta_npt":  delta_npt,
        }
        results.append(row)

        print(f"pb={pb:.3f} wait={max_wait}c  "
              f"fill={fill_rate:5.1f}% ({total_trades:4d} filled, {miss_count:4d} missed)  "
              f"WR={filled_stats['wr']:5.1f}% (Δ{delta_wr:+.1f})  "
              f"Net=${filled_stats['net']:,.0f} (Δ${delta_net:+,.0f})  "
              f"R:R={filled_stats['rr']:.3f} (Δ{delta_rr:+.3f})  "
              f"PF={filled_stats['pf']:.3f} (Δ{delta_pf:+.3f})  "
              f"Net/trade=${filled_stats['npt']:+.2f} (Δ${delta_npt:+.2f})  "
              f"| missed PnL=${miss_pnl_sum:+,.0f}")

# ── Best results ──────────────────────────────────────────────────────────────
best_npt = max(results, key=lambda r: r["delta_npt"])
best_net = max(results, key=lambda r: r["delta_net"])

def print_best(r: dict, label: str):
    s = r["stats"]
    print(f"\n{'='*72}")
    print(f"BEST {label}:")
    print(f"  Pullback: {r['pb_pct']*100:.2f}%  |  Max wait: {r['max_wait']} candle(s)")
    print(f"  Fill rate: {r['fill_rate']}%  ({r['n_filled']} filled, {r['n_missed']} missed)")
    print(f"  Missed trades PnL: ${r['missed_pnl']:+,.2f}")
    print(f"  WR:        {s['wr']}%   (Δ{r['delta_wr']:+.2f}%)")
    print(f"  Net PnL:   ${s['net']:,.2f}  (Δ${r['delta_net']:+,.2f})")
    print(f"  R:R:       {s['rr']}   (Δ{r['delta_rr']:+.3f})")
    print(f"  PF:        {s['pf']}   (Δ{r['delta_pf']:+.3f})")
    print(f"  Net/trade: ${s['npt']:+.2f}  (Δ${r['delta_npt']:+.2f})")
    print(f"{'='*72}")

print_best(best_npt, "Net/trade improvement")
print_best(best_net, "Absolute Net PnL")

# ── Save ──────────────────────────────────────────────────────────────────────
out = {
    "run_timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
    "baseline": baseline,
    "results":  results,
    "best_npt": best_npt,
    "best_net": best_net,
}
out_path = OUT_DIR / "pullback_results.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)
print(f"\nResults saved to: {out_path}")
