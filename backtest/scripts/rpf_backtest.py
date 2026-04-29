"""
Range Position Filter (RPF) Backtest — Proposal A
================================================
Tests whether skipping entries when price is in the top/bottom N% of
the rolling 24h/48h range improves performance vs. baseline GOLDEN v4.4.

Usage:
    python scripts/rpf_backtest.py

Output:
    - Console summary table
    - results/rpf_analysis/rpf_results.json
"""

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent.parent
TRADES_CSV   = BASE_DIR / "results/v4_5_comparison_results/v4_5_201901_202603_20260309_102822_golden_trades.csv"
OHLCV_CSV    = BASE_DIR / "data/BTC_USDT_4h_2020_2026_with_bcd.csv"
OUT_DIR      = BASE_DIR / "results/rpf_analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Parameters ────────────────────────────────────────────────────────────────
# Range position thresholds: skip LONG if price > upper, skip SHORT if price < lower
THRESHOLD_PAIRS = [
    (0.20, 0.80),   # tight: skip top/bottom 20%
    (0.25, 0.75),
    (0.30, 0.70),   # baseline proposal A
    (0.35, 0.65),
    (0.40, 0.60),   # aggressive: only trade in middle 20%
]
RANGE_WINDOWS_H = [24, 48, 72]   # rolling window in hours → candles = hours / 4

# ── Load OHLCV ────────────────────────────────────────────────────────────────
print("Loading OHLCV data...")
try:
    ohlcv = pd.read_csv(OHLCV_CSV, index_col=0, parse_dates=True)
    ohlcv.index = pd.to_datetime(ohlcv.index, utc=True)
    # Normalise column names
    rename = {c: c.capitalize() for c in ohlcv.columns}
    ohlcv.rename(columns=rename, inplace=True)
    if "High" not in ohlcv.columns:
        ohlcv.rename(columns={"high": "High", "low": "Low", "open": "Open", "close": "Close"}, inplace=True)
    print(f"  OHLCV loaded: {len(ohlcv)} rows  ({ohlcv.index[0].date()} to {ohlcv.index[-1].date()})")
except Exception as e:
    print(f"ERROR loading OHLCV: {e}")
    sys.exit(1)

# Pre-compute rolling high/low for each window
print("Pre-computing rolling range windows...")
for window_h in RANGE_WINDOWS_H:
    candles = window_h // 4
    ohlcv[f"rolling_high_{window_h}h"] = ohlcv["High"].rolling(candles).max()
    ohlcv[f"rolling_low_{window_h}h"]  = ohlcv["Low"].rolling(candles).min()
print("  Done.")

# ── Load Trades ───────────────────────────────────────────────────────────────
print("Loading trades...")
trades_raw = []
with open(TRADES_CSV, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        trades_raw.append(row)
print(f"  Loaded {len(trades_raw)} trades.")

# ── Helper ────────────────────────────────────────────────────────────────────
def parse_dt(s: str) -> pd.Timestamp:
    return pd.Timestamp(s.replace("+00:00", ""), tz="UTC")

def get_range_position(entry_ts: pd.Timestamp, entry_price: float, window_h: int) -> float | None:
    """Return (price - low) / (high - low) over the rolling window ending at entry_ts."""
    col_high = f"rolling_high_{window_h}h"
    col_low  = f"rolling_low_{window_h}h"
    # Find the OHLCV row at or just before entry_ts
    idx = ohlcv.index.get_indexer([entry_ts], method="ffill")[0]
    if idx < 0:
        return None
    rng_high = ohlcv[col_high].iloc[idx]
    rng_low  = ohlcv[col_low].iloc[idx]
    if pd.isna(rng_high) or pd.isna(rng_low) or (rng_high - rng_low) < 1e-6:
        return None
    return (entry_price - rng_low) / (rng_high - rng_low)

# ── Compute stats helper ──────────────────────────────────────────────────────
def stats(trades: list[dict]) -> dict:
    if not trades:
        return {}
    wins   = [t for t in trades if float(t["pnl_usd"]) > 0]
    losses = [t for t in trades if float(t["pnl_usd"]) <= 0]
    net    = sum(float(t["pnl_usd"]) for t in trades)
    gw     = sum(float(t["pnl_usd"]) for t in wins)
    gl     = abs(sum(float(t["pnl_usd"]) for t in losses))
    aw     = gw / len(wins)   if wins   else 0
    al     = gl / len(losses) if losses else 0
    pf     = gw / gl          if gl > 0 else float("inf")
    rr     = aw / al          if al > 0 else float("inf")
    wr     = len(wins) / len(trades) * 100
    return {
        "n":  len(trades),
        "w":  len(wins),
        "l":  len(losses),
        "wr": round(wr, 2),
        "net": round(net, 2),
        "avg_win":  round(aw, 2),
        "avg_loss": round(-al, 2),
        "rr":  round(rr, 3),
        "pf":  round(pf, 3),
        "net_per_trade": round(net / len(trades), 2),
    }

# ── Baseline ──────────────────────────────────────────────────────────────────
baseline = stats(trades_raw)
print(f"\n{'='*70}")
print(f"BASELINE (all {baseline['n']} trades)")
print(f"  WR: {baseline['wr']}%  |  Net: ${baseline['net']:,.2f}  |  R:R: {baseline['rr']}  |  PF: {baseline['pf']}  |  Net/trade: ${baseline['net_per_trade']}")
print(f"{'='*70}\n")

# ── Tag each trade with range position ───────────────────────────────────────
print("Computing range positions for each trade (this may take a moment)...")
for window_h in RANGE_WINDOWS_H:
    col = f"rp_{window_h}h"
    for t in trades_raw:
        entry_ts    = parse_dt(t["entry_time"])
        entry_price = float(t["entry_price"])
        rp = get_range_position(entry_ts, entry_price, window_h)
        t[col] = rp
print("  Done.\n")

# ── Run all threshold combinations ───────────────────────────────────────────
results = []

for window_h in RANGE_WINDOWS_H:
    col = f"rp_{window_h}h"
    for lower, upper in THRESHOLD_PAIRS:
        # Filter: LONG only if rp < upper, SHORT only if rp > lower
        kept    = []
        skipped = []
        for t in trades_raw:
            rp = t[col]
            if rp is None:
                kept.append(t)  # no data → keep
                continue
            side = t["side"].upper()
            if side == "LONG"  and rp > upper:
                skipped.append(t)
            elif side == "SHORT" and rp < lower:
                skipped.append(t)
            else:
                kept.append(t)

        s_kept    = stats(kept)
        s_skipped = stats(skipped) if skipped else {}

        delta_wr  = round(s_kept["wr"]  - baseline["wr"],  2)
        delta_net = round(s_kept["net"] - baseline["net"],  2)
        delta_rr  = round(s_kept["rr"]  - baseline["rr"],   3)
        delta_pf  = round(s_kept["pf"]  - baseline["pf"],   3)
        delta_npt = round(s_kept["net_per_trade"] - baseline["net_per_trade"], 2)

        results.append({
            "window_h":    window_h,
            "lower":       lower,
            "upper":       upper,
            "kept":        s_kept,
            "skipped_n":   len(skipped),
            "skipped_wr":  s_skipped.get("wr", "-"),
            "delta_wr":    delta_wr,
            "delta_net":   delta_net,
            "delta_rr":    delta_rr,
            "delta_pf":    delta_pf,
            "delta_npt":   delta_npt,
        })

        print(f"[{window_h}h | {lower:.2f}-{upper:.2f}]  "
              f"kept={len(kept):4d}  skip={len(skipped):4d}  "
              f"WR={s_kept['wr']:5.1f}% (Δ{delta_wr:+.1f})  "
              f"Net=${s_kept['net']:,.0f} (Δ${delta_net:+,.0f})  "
              f"R:R={s_kept['rr']:.3f} (Δ{delta_rr:+.3f})  "
              f"PF={s_kept['pf']:.3f} (Δ{delta_pf:+.3f})  "
              f"Net/trade=${s_kept['net_per_trade']:+.2f} (Δ${delta_npt:+.2f})  "
              f"| skipped_wr={s_skipped.get('wr', '-')}")

# ── Best result ───────────────────────────────────────────────────────────────
best = max(results, key=lambda r: r["delta_npt"])
print(f"\n{'='*70}")
print(f"BEST CONFIGURATION (by Net/trade improvement):")
print(f"  Window: {best['window_h']}h  |  Range: [{best['lower']:.2f}, {best['upper']:.2f}]")
print(f"  Kept trades: {best['kept']['n']}  |  Skipped: {best['skipped_n']}")
print(f"  WR:       {best['kept']['wr']}%   (Δ{best['delta_wr']:+.2f}%)")
print(f"  Net PnL:  ${best['kept']['net']:,.2f}  (Δ${best['delta_net']:+,.2f})")
print(f"  R:R:      {best['kept']['rr']}   (Δ{best['delta_rr']:+.3f})")
print(f"  PF:       {best['kept']['pf']}   (Δ{best['delta_pf']:+.3f})")
print(f"  Net/trade: ${best['kept']['net_per_trade']:+.2f}  (Δ${best['delta_npt']:+.2f})")
print(f"  Skipped trades WR: {best['skipped_wr']}%")
print(f"{'='*70}\n")

# ── Save JSON ─────────────────────────────────────────────────────────────────
out = {
    "run_timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
    "baseline": baseline,
    "results":  results,
    "best":     best,
}
out_path = OUT_DIR / "rpf_results.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)
print(f"Results saved to: {out_path}")
