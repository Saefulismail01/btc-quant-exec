"""
Proposal D — Pullback Limit Entry: REBUILT ENGINE (v2)
=======================================================
Engine ini dibangun dari reverse-engineering golden_trades.csv.

Temuan dari audit:
  - PnL = notional * price_return - FEE_USD ($12 round-trip) ✓ verified
  - SL selalu kena di harga SL exact (pnl = -$211.95 = SL hit) ✓
  - TP exact = $94.50 (pnl flat) → exit di tp price ✓
  - TRAIL_TP = move > tp, exit di close (avg move 1.90%, min 0.71%)
    → TRAIL_TP aktif ketika harga HIGH melewati TP tapi close LEBIH BESAR dari TP
    → exit = close candle tersebut
  - MAX_HOLD = 6 candles (holding 2-6, min=2 artinya hold 1 candle setelah entry)
  - holding_candles minimum = 2 → entry candle + 1 candle = exit on hold=1

TRAIL_TP Logic yang BENAR (dari data):
  - Cek candle berikutnya setelah entry (hold=1..6)
  - Jika High (LONG) atau Low (SHORT) melewati TP:
      - Jika close juga melewati TP → exit di CLOSE (TRAIL_TP, lebih besar dari TP)
      - Jika close tidak melewati TP → exit di TP (TP fixed)
  - Ini persis sama dengan walkforward_v4_4_trade_plan.py check_sl_tp()

Jadi perbedaan baseline re-run vs CSV bukan di trail logic, tapi di:
  1. holding_candles minimum = 2 (hold dimulai dari candle ke-1 setelah signal)
     → hold range = 1..MAX_HOLD_CANDLES → holding_candles di CSV = 2..6
  2. Signal di CSV: entry_time = candle SETELAH signal (sudah open price berikutnya)
     → di OHLCV, entry candle = candle yang tepat pada entry_time
     → exit scan mulai dari candle ke-1 SETELAH entry candle

Approach:
  - Untuk setiap trade di CSV, entry_time → cari di OHLCV
  - Jalankan exit scan dari candle+1 s/d candle+6
  - Bandingkan PnL hasil vs PnL CSV → kalibrate dulu
  - Jika match: jalankan pullback simulation
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

# ── Constants (dari audit) ────────────────────────────────────────────────────
NOTIONAL         = 15_000.0
FEE_USD          = 12.0        # $12 round-trip (0.04% × 2 × $15k)
SL_PCT           = 0.01333
TP_PCT           = 0.0071
MAX_HOLD         = 6           # candle ke-1 s/d ke-6 setelah entry
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
N = len(ohlcv)
print(f"  {N} rows  ({str(ohlcv_start)[:10]} — {str(ohlcv_end)[:10]})")

# ── Load Trades ───────────────────────────────────────────────────────────────
print("Loading trades...")
trades_raw = []
with open(TRADES_CSV, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        trades_raw.append(row)

in_range  = [t for t in trades_raw
             if ohlcv_start <= pd.Timestamp(t["entry_time"].replace("+00:00",""), tz="UTC") <= ohlcv_end]
out_range = [t for t in trades_raw if t not in in_range]
print(f"  Total={len(trades_raw)} | In-range={len(in_range)} | Out-range={len(out_range)} ({len(out_range)/len(trades_raw)*100:.1f}%)\n")


# ══════════════════════════════════════════════════════════════════════════════
#  CORE ENGINE — rebuilt from audit
# ══════════════════════════════════════════════════════════════════════════════

def check_exit(
    side: str, sl: float, tp: float,
    c_high: float, c_low: float, c_close: float
) -> Tuple[Optional[float], Optional[str]]:
    """
    Exit logic dari golden engine (verified via audit).
    SL priority > TP.
    TRAIL_TP: if high/low crosses TP AND close also beyond TP → exit at close.
    TP: if high/low crosses TP but close pulls back → exit at TP.
    """
    if side == "LONG":
        if c_low <= sl:
            return sl, "SL"
        if c_high >= tp:
            return (c_close, "TRAIL_TP") if c_close >= tp else (tp, "TP")
    else:  # SHORT
        if c_high >= sl:
            return sl, "SL"
        if c_low <= tp:
            return (c_close, "TRAIL_TP") if c_close <= tp else (tp, "TP")
    return None, None


def calc_pnl(side: str, entry: float, exit_price: float) -> float:
    if side == "LONG":
        move = (exit_price - entry) / entry
    else:
        move = (entry - exit_price) / entry
    return round(NOTIONAL * move - FEE_USD, 2)


def run_trade_exit(side: str, entry_px: float, entry_ci: int) -> Tuple[float, str]:
    """
    Run exit from entry_ci+1 to entry_ci+MAX_HOLD.
    Returns (pnl, exit_type).
    """
    if side == "LONG":
        sl = entry_px * (1.0 - SL_PCT)
        tp = entry_px * (1.0 + TP_PCT)
    else:
        sl = entry_px * (1.0 + SL_PCT)
        tp = entry_px * (1.0 - TP_PCT)

    for hold in range(1, MAX_HOLD + 1):
        ci = entry_ci + hold
        if ci >= N:
            exit_px = float(ohlcv.iloc[N - 1]["Close"])
            return calc_pnl(side, entry_px, exit_px), "TIME_EXIT"

        c      = ohlcv.iloc[ci]
        c_high = float(c["High"])
        c_low  = float(c["Low"])
        c_close= float(c["Close"])

        exit_px, exit_type = check_exit(side, sl, tp, c_high, c_low, c_close)
        if exit_px is not None:
            return calc_pnl(side, entry_px, exit_px), exit_type

    # TIME_EXIT at hold=MAX_HOLD close
    exit_px = float(ohlcv.iloc[min(entry_ci + MAX_HOLD, N - 1)]["Close"])
    return calc_pnl(side, entry_px, exit_px), "TIME_EXIT"


# ══════════════════════════════════════════════════════════════════════════════
#  CALIBRATION — engine re-run vs CSV pnl
# ══════════════════════════════════════════════════════════════════════════════

print("Calibrating engine against CSV (in-range trades)...")
match_count = 0
total_err   = 0.0
abs_errs    = []

for t in in_range[:500]:  # sample 500
    side     = t["side"].upper()
    entry_ts = pd.Timestamp(t["entry_time"].replace("+00:00",""), tz="UTC")
    entry_px = float(t["entry_price"])
    csv_pnl  = float(t["pnl_usd"])

    # entry_time di CSV = candle di mana trade aktif
    # exit scan dimulai dari entry_ci+1 (hold=1..6)
    entry_ci = int(ohlcv.index.get_indexer([entry_ts], method="nearest")[0])
    pnl, _ = run_trade_exit(side, entry_px, entry_ci)

    err = abs(pnl - csv_pnl)
    abs_errs.append(err)
    if err < 1.0:
        match_count += 1
    total_err += err

import statistics
print(f"  Sample: 500 trades | Match (<$1 diff): {match_count} ({match_count/5:.1f}%)")
print(f"  Avg abs error: ${statistics.mean(abs_errs):.2f} | Median: ${statistics.median(abs_errs):.2f} | Max: ${max(abs_errs):.2f}")
print()


# ══════════════════════════════════════════════════════════════════════════════
#  BASELINE — engine re-run all in-range
# ══════════════════════════════════════════════════════════════════════════════

print("Running baseline (engine re-run)...")
baseline_pnls = []
for t in in_range:
    side     = t["side"].upper()
    entry_ts = pd.Timestamp(t["entry_time"].replace("+00:00",""), tz="UTC")
    entry_px = float(t["entry_price"])
    entry_ci = int(ohlcv.index.get_indexer([entry_ts], method="nearest")[0])
    pnl, _   = run_trade_exit(side, entry_px, entry_ci)
    baseline_pnls.append(pnl)

out_range_pnls = [float(t["pnl_usd"]) for t in out_range]


def calc_stats(pnls: list) -> dict:
    if not pnls:
        return {"n":0,"wr":0,"net":0,"avg_win":0,"avg_loss":0,"rr":0,"pf":0,"npt":0}
    wins   = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gw     = sum(wins)
    gl     = abs(sum(losses))
    aw     = gw / len(wins)   if wins   else 0
    al     = gl / len(losses) if losses else 0
    return {
        "n":   len(pnls),
        "wr":  round(len(wins) / len(pnls) * 100, 2),
        "net": round(sum(pnls), 2),
        "avg_win":  round(aw, 2),
        "avg_loss": round(-al, 2),
        "rr":  round(aw / al if al > 0 else 0, 3),
        "pf":  round(gw / gl if gl > 0 else 0, 3),
        "npt": round(sum(pnls) / len(pnls), 2),
    }

bl_csv   = calc_stats([float(t["pnl_usd"]) for t in trades_raw])
bl_rerun = calc_stats(baseline_pnls)        # in-range only
bl_full  = calc_stats(baseline_pnls + out_range_pnls)  # all

print(f"{'='*76}")
print(f"BASELINE — CSV original (3866 trades, ground truth):")
print(f"  WR={bl_csv['wr']}%  Net=${bl_csv['net']:,.0f}  R:R={bl_csv['rr']}  PF={bl_csv['pf']}  Net/trade=${bl_csv['npt']}")
print(f"\nBASELINE — Engine rerun in-range ({len(in_range)} trades):")
print(f"  WR={bl_rerun['wr']}%  Net=${bl_rerun['net']:,.0f}  R:R={bl_rerun['rr']}  PF={bl_rerun['pf']}  Net/trade=${bl_rerun['npt']}")
print(f"\nBASELINE — Engine rerun all ({len(trades_raw)} trades, out-range at CSV PnL):")
print(f"  WR={bl_full['wr']}%  Net=${bl_full['net']:,.0f}  R:R={bl_full['rr']}  PF={bl_full['pf']}  Net/trade=${bl_full['npt']}")
print(f"{'='*76}\n")

# Use in-range baseline as comparison anchor
bl = bl_rerun


# ══════════════════════════════════════════════════════════════════════════════
#  PULLBACK SIMULATION
# ══════════════════════════════════════════════════════════════════════════════

print("Running pullback simulations (in-range trades only)...\n")
all_results = []

for pb in PULLBACK_PCTS:
    for max_wait in MAX_WAIT_CANDLES:
        filled_pnls = []
        missed_pnls = []

        for t in in_range:
            side     = t["side"].upper()
            entry_ts = pd.Timestamp(t["entry_time"].replace("+00:00",""), tz="UTC")
            orig_px  = float(t["entry_price"])

            limit_px = orig_px * (1.0 - pb) if side == "LONG" else orig_px * (1.0 + pb)

            # entry_time = candle di mana trade aktif
            entry_ci = int(ohlcv.index.get_indexer([entry_ts], method="nearest")[0])

            # Phase 1: find limit fill within entry_ci .. entry_ci+max_wait
            fill_ci = None
            for ci in range(entry_ci, min(entry_ci + max_wait + 1, N)):
                c = ohlcv.iloc[ci]
                if side == "LONG"  and float(c["Low"])  <= limit_px:
                    fill_ci = ci
                    break
                if side == "SHORT" and float(c["High"]) >= limit_px:
                    fill_ci = ci
                    break

            if fill_ci is None:
                # miss — baseline PnL jika masuk market
                pnl, _ = run_trade_exit(side, orig_px, entry_ci)
                missed_pnls.append(pnl)
                continue

            # Phase 2: run exit from fill candle
            pnl, _ = run_trade_exit(side, limit_px, fill_ci)
            filled_pnls.append(pnl)

        s         = calc_stats(filled_pnls)
        n_in      = len(in_range)
        fill_rate = len(filled_pnls) / n_in * 100

        dwr  = round(s["wr"]  - bl["wr"],  2)
        dnet = round(s["net"] - bl["net"],  2)
        drr  = round(s["rr"]  - bl["rr"],   3)
        dpf  = round(s["pf"]  - bl["pf"],   3)
        dnpt = round(s["npt"] - bl["npt"],   2)
        miss_opp = round(sum(missed_pnls), 2)

        row = {
            "pb_pct": pb, "max_wait": max_wait,
            "n_filled": len(filled_pnls), "n_missed": len(missed_pnls),
            "fill_rate": round(fill_rate, 1),
            "missed_opp_pnl": miss_opp,
            "stats": s,
            "delta_wr": dwr, "delta_net": dnet,
            "delta_rr": drr, "delta_pf": dpf, "delta_npt": dnpt,
        }
        all_results.append(row)

        print(f"pb={pb:.3f} wait={max_wait}c  "
              f"fill={fill_rate:5.1f}% ({len(filled_pnls):4d}/{len(missed_pnls):3d}miss)  "
              f"WR={s['wr']:5.1f}% (Δ{dwr:+.1f})  "
              f"Net=${s['net']:>10,.0f} (Δ${dnet:>+9,.0f})  "
              f"R:R={s['rr']:.3f} (Δ{drr:+.3f})  "
              f"PF={s['pf']:.3f} (Δ{dpf:+.3f})  "
              f"Net/trade=${s['npt']:+.2f} (Δ${dnpt:+.2f})  "
              f"| miss=${miss_opp:+,.0f}")


# ── Best ──────────────────────────────────────────────────────────────────────
def print_best(r: dict, label: str):
    s = r["stats"]
    print(f"\n{'='*76}")
    print(f"BEST ({label}):")
    print(f"  Pullback   : {r['pb_pct']*100:.2f}%  |  Max wait: {r['max_wait']} candle(s)")
    print(f"  Fill rate  : {r['fill_rate']}%  ({r['n_filled']} filled | {r['n_missed']} missed)")
    print(f"  Missed opp : ${r['missed_opp_pnl']:+,.2f}  (jika ambil market entry)")
    print(f"  WR         : {s['wr']}%   (Δ{r['delta_wr']:+.2f}%)")
    print(f"  Net PnL    : ${s['net']:,.2f}  (Δ${r['delta_net']:+,.2f})")
    print(f"  R:R        : {s['rr']}   (Δ{r['delta_rr']:+.3f})")
    print(f"  PF         : {s['pf']}   (Δ{r['delta_pf']:+.3f})")
    print(f"  Net/trade  : ${s['npt']:+.2f}  (Δ${r['delta_npt']:+.2f})")
    print(f"{'='*76}")

best_npt = max(all_results, key=lambda r: r["delta_npt"])
best_net = max(all_results, key=lambda r: r["delta_net"])
print_best(best_npt, "Net/trade")
print_best(best_net, "Absolute Net PnL")

# ── Save ──────────────────────────────────────────────────────────────────────
out = {
    "run_timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
    "engine_version": "v2_rebuilt_from_audit",
    "calibration_notes": "TRAIL_TP=close if close>=tp, SL=exact, FEE=$12, MAX_HOLD=6",
    "baseline_csv":    bl_csv,
    "baseline_rerun":  bl_rerun,
    "baseline_full":   bl_full,
    "results":         all_results,
    "best_npt":        best_npt,
    "best_net":        best_net,
}
out_path = OUT_DIR / "pullback_v2_results.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)
print(f"\nSaved: {out_path}")
