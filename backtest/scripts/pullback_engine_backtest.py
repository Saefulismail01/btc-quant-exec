"""
Proposal D — Pullback Limit Entry: ENGINE-ACCURATE BACKTEST
============================================================
Menggunakan exit logic IDENTIK dengan walkforward_v4_4_trade_plan.py:
  - check_sl_tp():  SL/TP/TRAIL_TP (persis sama, termasuk trail logic)
  - calc_pnl():     Notional × price_return − fee
  - MAX_HOLD = 6 candles
  - FEE_RATE = 0.04% per leg

Signal source: Golden v4.4 trades CSV (entry_time, side sudah valid)
Entry mode:
  - Baseline: entry di candle berikutnya setelah signal (pakai orig entry_price)
  - Pullback: set limit = entry_price ± pb%, cari fill dalam max_wait candles

Jika limit tidak fill → trade MISS (tidak ambil).
Jika fill → jalankan exit_logic dari fill candle+1 persis seperti engine asli.
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.parent
TRADES_CSV = BASE_DIR / "results/v4_5_comparison_results/v4_5_201901_202603_20260309_102822_golden_trades.csv"
OHLCV_CSV  = BASE_DIR / "data/BTC_USDT_4h_2020_2026_with_bcd.csv"
OUT_DIR    = BASE_DIR / "results/rpf_analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Engine Constants (IDENTIK dengan walkforward_v4_4_trade_plan.py) ──────────
NOTIONAL         = 15_000.0   # posisi backtest golden: $1k × 15x
FEE_RATE         = 0.0004
FEE_USD          = NOTIONAL * FEE_RATE * 2   # $12 round-trip
SL_PCT           = 0.01333
TP_MIN_PCT       = 0.0071
MAX_HOLD_CANDLES = 6

# ── Parameters pullback yang diuji ────────────────────────────────────────────
PULLBACK_PCTS    = [0.0010, 0.0015, 0.0020, 0.0030, 0.0050]
MAX_WAIT_CANDLES = [1, 2, 3]

# ── Load OHLCV ────────────────────────────────────────────────────────────────
print("Loading OHLCV...")
ohlcv = pd.read_csv(OHLCV_CSV, index_col=0, parse_dates=True)
ohlcv.index = pd.to_datetime(ohlcv.index, utc=True)
ohlcv.columns = [c.capitalize() for c in ohlcv.columns]
if "High" not in ohlcv.columns:
    ohlcv.rename(columns={"high":"High","low":"Low","open":"Open","close":"Close"}, inplace=True)
ohlcv = ohlcv[["Open","High","Low","Close"]].copy()
ohlcv_start = pd.Timestamp(ohlcv.index[0])
ohlcv_end   = pd.Timestamp(ohlcv.index[-1])
print(f"  {len(ohlcv)} rows  ({str(ohlcv_start)[:10]} — {str(ohlcv_end)[:10]})")

# ── Load Trades ───────────────────────────────────────────────────────────────
print("Loading trades...")
trades_raw = []
with open(TRADES_CSV, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        trades_raw.append(row)

in_range  = [t for t in trades_raw if ohlcv_start <= pd.Timestamp(t["entry_time"].replace("+00:00",""), tz="UTC") <= ohlcv_end]
out_range = [t for t in trades_raw if t not in in_range]
print(f"  Total: {len(trades_raw)} | In OHLCV range: {len(in_range)} | Out-of-range: {len(out_range)} ({len(out_range)/len(trades_raw)*100:.1f}%)\n")


# ══════════════════════════════════════════════════════════════════════════════
#  ENGINE FUNCTIONS — identik dengan walkforward_v4_4_trade_plan.py
# ══════════════════════════════════════════════════════════════════════════════

def check_sl_tp(
    side: str, sl: float, tp: float,
    c_high: float, c_low: float, c_close: float
) -> Tuple[Optional[float], Optional[str]]:
    """
    Persis sama dengan walkforward_v4_4_trade_plan.py.
    Priority: SL > TP.
    TRAIL_TP: jika close melewati TP → exit di close (bukan TP fixed).
    """
    if side == "LONG":
        if c_low <= sl:
            return sl, "SL"
        if c_high >= tp:
            return (c_close, "TRAIL_TP") if c_close >= tp else (tp, "TP")
    else:
        if c_high >= sl:
            return sl, "SL"
        if c_low <= tp:
            return (c_close, "TRAIL_TP") if c_close <= tp else (tp, "TP")
    return None, None


def calc_pnl(side: str, entry: float, exit_price: float) -> float:
    """Identik dengan walkforward_v4_4_trade_plan.py."""
    if side == "LONG":
        price_return = (exit_price - entry) / entry
    else:
        price_return = (entry - exit_price) / entry
    return round(NOTIONAL * price_return - FEE_USD, 2)


def execute_from_fill(
    side: str,
    fill_px: float,
    fill_ci: int,   # candle index di ohlcv
) -> float:
    """
    Jalankan exit logic dari fill_ci+1 sampai max hold.
    Return PnL USD.
    """
    if side == "LONG":
        sl = fill_px * (1.0 - SL_PCT)
        tp = fill_px * (1.0 + TP_MIN_PCT)
    else:
        sl = fill_px * (1.0 + SL_PCT)
        tp = fill_px * (1.0 - TP_MIN_PCT)

    n = len(ohlcv)
    for hold in range(1, MAX_HOLD_CANDLES + 1):
        ci = fill_ci + hold
        if ci >= n:
            # out of data
            exit_px = float(ohlcv.iloc[n - 1]["Close"])
            return calc_pnl(side, fill_px, exit_px)

        c = ohlcv.iloc[ci]
        c_high  = float(c["High"])
        c_low   = float(c["Low"])
        c_close = float(c["Close"])

        exit_px, exit_type = check_sl_tp(side, sl, tp, c_high, c_low, c_close)
        if exit_px is not None:
            return calc_pnl(side, fill_px, exit_px)

    # TIME_EXIT setelah MAX_HOLD_CANDLES
    last_ci  = min(fill_ci + MAX_HOLD_CANDLES, n - 1)
    exit_px  = float(ohlcv.iloc[last_ci]["Close"])
    return calc_pnl(side, fill_px, exit_px)


# ══════════════════════════════════════════════════════════════════════════════
#  BASELINE — Re-run engine pada in-range trades dengan entry_price asli
# ══════════════════════════════════════════════════════════════════════════════

print("Computing baseline (engine re-run on in-range trades)...")
baseline_pnls_inrange = []
for t in in_range:
    side       = t["side"].upper()
    entry_ts   = pd.Timestamp(t["entry_time"].replace("+00:00",""), tz="UTC")
    orig_entry = float(t["entry_price"])

    sig_idx = int(ohlcv.index.get_indexer([entry_ts], method="nearest")[0])
    # entry_price di golden = candle open setelah signal → execute_from_fill dari sig_idx
    pnl = execute_from_fill(side, orig_entry, sig_idx)
    baseline_pnls_inrange.append(pnl)

# Tambah out-of-range trades (pakai PnL asli dari CSV)
out_range_pnls = [float(t["pnl_usd"]) for t in out_range]

def calc_stats(pnls: list) -> dict:
    if not pnls:
        return {"n":0,"wr":0,"net":0,"avg_win":0,"avg_loss":0,"rr":0,"pf":0,"npt":0}
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
        "n":   len(pnls),
        "wr":  round(wr, 2),
        "net": round(net, 2),
        "avg_win":  round(aw, 2),
        "avg_loss": round(-al, 2),
        "rr":  round(rr, 3),
        "pf":  round(pf, 3),
        "npt": round(net / len(pnls), 2),
    }

bl_all   = calc_stats(baseline_pnls_inrange + out_range_pnls)
bl_inrng = calc_stats(baseline_pnls_inrange)

print(f"{'='*76}")
print(f"BASELINE (original CSV PnL, all 3866 trades):")
orig_pnls = [float(t["pnl_usd"]) for t in trades_raw]
bl_orig   = calc_stats(orig_pnls)
print(f"  n={bl_orig['n']}  WR={bl_orig['wr']}%  Net=${bl_orig['net']:,.0f}  R:R={bl_orig['rr']}  PF={bl_orig['pf']}  Net/trade=${bl_orig['npt']}")
print(f"\nBASELINE (engine re-run, in-range {len(in_range)} + out-range {len(out_range)} at CSV PnL):")
print(f"  n={bl_all['n']}  WR={bl_all['wr']}%  Net=${bl_all['net']:,.0f}  R:R={bl_all['rr']}  PF={bl_all['pf']}  Net/trade=${bl_all['npt']}")
print(f"\nBASELINE (engine re-run, in-range {len(in_range)} trades only):")
print(f"  n={bl_inrng['n']}  WR={bl_inrng['wr']}%  Net=${bl_inrng['net']:,.0f}  R:R={bl_inrng['rr']}  PF={bl_inrng['pf']}  Net/trade=${bl_inrng['npt']}")
print(f"{'='*76}\n")

# Gunakan baseline in-range untuk delta comparison (apples-to-apples)
bl = bl_inrng


# ══════════════════════════════════════════════════════════════════════════════
#  PULLBACK SIMULATION
# ══════════════════════════════════════════════════════════════════════════════

print("Running pullback simulations...")
all_results = []

for pb in PULLBACK_PCTS:
    for max_wait in MAX_WAIT_CANDLES:
        pnls_filled = []
        missed_pnls = []

        for t in in_range:
            side       = t["side"].upper()
            entry_ts   = pd.Timestamp(t["entry_time"].replace("+00:00",""), tz="UTC")
            orig_entry = float(t["entry_price"])

            # Limit price
            limit_px = orig_entry * (1.0 - pb) if side == "LONG" else orig_entry * (1.0 + pb)

            sig_idx = int(ohlcv.index.get_indexer([entry_ts], method="nearest")[0])
            n       = len(ohlcv)

            # Phase 1: cari fill dalam sig_idx .. sig_idx + max_wait
            fill_ci = None
            for ci in range(sig_idx, min(sig_idx + max_wait + 1, n)):
                c = ohlcv.iloc[ci]
                if side == "LONG"  and float(c["Low"])  <= limit_px:
                    fill_ci = ci
                    break
                if side == "SHORT" and float(c["High"]) >= limit_px:
                    fill_ci = ci
                    break

            if fill_ci is None:
                # Miss — catat baseline PnL sebagai opportunity cost
                missed_pnls.append(execute_from_fill(side, orig_entry, sig_idx))
                continue

            # Phase 2: exit dari engine logic
            pnl = execute_from_fill(side, limit_px, fill_ci)
            pnls_filled.append(pnl)

        # Hitung stats (in-range only untuk delta yang clean)
        s          = calc_stats(pnls_filled)
        n_inrange  = len(in_range)
        fill_rate  = len(pnls_filled) / n_inrange * 100
        missed_sum = round(sum(missed_pnls), 2)

        delta_wr   = round(s["wr"]  - bl["wr"],  2)
        delta_net  = round(s["net"] - bl["net"],  2)
        delta_rr   = round(s["rr"]  - bl["rr"],   3)
        delta_pf   = round(s["pf"]  - bl["pf"],   3)
        delta_npt  = round(s["npt"] - bl["npt"],   2)

        row = {
            "pb_pct": pb, "max_wait": max_wait,
            "n_filled": len(pnls_filled), "n_missed": len(missed_pnls),
            "fill_rate": round(fill_rate, 1),
            "missed_opportunity_pnl": missed_sum,
            "stats": s,
            "delta_wr": delta_wr, "delta_net": delta_net,
            "delta_rr": delta_rr, "delta_pf": delta_pf,
            "delta_npt": delta_npt,
        }
        all_results.append(row)

        print(f"pb={pb:.3f} wait={max_wait}c  "
              f"fill={fill_rate:5.1f}% ({len(pnls_filled):4d}/{len(missed_pnls):3d} miss)  "
              f"WR={s['wr']:5.1f}% (Δ{delta_wr:+.1f})  "
              f"Net=${s['net']:>10,.0f} (Δ${delta_net:>+9,.0f})  "
              f"R:R={s['rr']:.3f} (Δ{delta_rr:+.3f})  "
              f"PF={s['pf']:.3f} (Δ{delta_pf:+.3f})  "
              f"Net/trade=${s['npt']:+.2f} (Δ${delta_npt:+.2f})  "
              f"| miss opp=${missed_sum:+,.0f}")


# ── Best ──────────────────────────────────────────────────────────────────────
def print_best(r: dict, label: str):
    s = r["stats"]
    print(f"\n{'='*76}")
    print(f"BEST ({label}):")
    print(f"  Pullback  : {r['pb_pct']*100:.2f}%  |  Max wait: {r['max_wait']} candle(s)")
    print(f"  Fill rate : {r['fill_rate']}%  ({r['n_filled']} filled | {r['n_missed']} missed)")
    print(f"  Missed opp: ${r['missed_opportunity_pnl']:+,.2f}  (jika ambil di market)")
    print(f"  WR        : {s['wr']}%   (Δ{r['delta_wr']:+.2f}%)")
    print(f"  Net PnL   : ${s['net']:,.2f}  (Δ${r['delta_net']:+,.2f})")
    print(f"  R:R       : {s['rr']}   (Δ{r['delta_rr']:+.3f})")
    print(f"  PF        : {s['pf']}   (Δ{r['delta_pf']:+.3f})")
    print(f"  Net/trade : ${s['npt']:+.2f}  (Δ${r['delta_npt']:+.2f})")
    print(f"{'='*76}")

best_npt = max(all_results, key=lambda r: r["delta_npt"])
best_net = max(all_results, key=lambda r: r["delta_net"])
print_best(best_npt, "Net/trade")
print_best(best_net, "Absolute Net PnL")

# ── Save ──────────────────────────────────────────────────────────────────────
out = {
    "run_timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
    "engine": "walkforward_v4_4_trade_plan identical logic",
    "baseline_orig_csv": bl_orig,
    "baseline_engine_rerun_all": bl_all,
    "baseline_engine_rerun_inrange": bl_inrng,
    "results":  all_results,
    "best_npt": best_npt,
    "best_net": best_net,
}
out_path = OUT_DIR / "pullback_engine_results.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)
print(f"\nSaved: {out_path}")
