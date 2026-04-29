"""
Debug: cari kenapa engine rebuild tidak match CSV golden.
Print 20 trades yang punya error besar.
"""
import csv, statistics
from pathlib import Path
import pandas as pd

BASE_DIR   = Path(__file__).parent.parent
TRADES_CSV = BASE_DIR / "results/v4_5_comparison_results/v4_5_201901_202603_20260309_102822_golden_trades.csv"
OHLCV_CSV  = BASE_DIR / "data/BTC_USDT_4h_2020_2026_with_bcd.csv"

NOTIONAL = 15_000.0
FEE_USD  = 12.0
SL_PCT   = 0.01333
TP_PCT   = 0.0071
MAX_HOLD = 6

ohlcv = pd.read_csv(OHLCV_CSV, index_col=0, parse_dates=True)
ohlcv.index = pd.to_datetime(ohlcv.index, utc=True)
ohlcv.columns = [c.capitalize() for c in ohlcv.columns]
if "High" not in ohlcv.columns:
    ohlcv.rename(columns={"high":"High","low":"Low","open":"Open","close":"Close"}, inplace=True)
ohlcv = ohlcv[["Open","High","Low","Close"]].copy()
N = len(ohlcv)
ohlcv_start = pd.Timestamp(ohlcv.index[0])
ohlcv_end   = pd.Timestamp(ohlcv.index[-1])

trades_raw = list(csv.DictReader(open(TRADES_CSV)))
in_range = [t for t in trades_raw
            if ohlcv_start <= pd.Timestamp(t["entry_time"].replace("+00:00",""), tz="UTC") <= ohlcv_end]

def check_exit(side, sl, tp, c_high, c_low, c_close):
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

def calc_pnl(side, entry, exit_price):
    move = (exit_price - entry)/entry if side == "LONG" else (entry - exit_price)/entry
    return round(NOTIONAL * move - FEE_USD, 2)

def run_trade(side, entry_px, entry_ci):
    sl = entry_px * (1.0 - SL_PCT) if side == "LONG" else entry_px * (1.0 + SL_PCT)
    tp = entry_px * (1.0 + TP_PCT) if side == "LONG" else entry_px * (1.0 - TP_PCT)
    for hold in range(1, MAX_HOLD + 1):
        ci = entry_ci + hold
        if ci >= N:
            return calc_pnl(side, entry_px, float(ohlcv.iloc[N-1]["Close"])), "TIME_EXIT", hold, float(ohlcv.iloc[N-1]["Close"])
        c = ohlcv.iloc[ci]
        ep, et = check_exit(side, sl, tp, float(c["High"]), float(c["Low"]), float(c["Close"]))
        if ep is not None:
            return calc_pnl(side, entry_px, ep), et, hold, ep
    last = float(ohlcv.iloc[min(entry_ci+MAX_HOLD, N-1)]["Close"])
    return calc_pnl(side, entry_px, last), "TIME_EXIT", MAX_HOLD, last

# ── Sample mismatch analysis ──────────────────────────────────────────────────
big_errors = []
exit_type_match = {"match": 0, "mismatch": 0}

for t in in_range[:500]:
    side     = t["side"].upper()
    entry_ts = pd.Timestamp(t["entry_time"].replace("+00:00",""), tz="UTC")
    entry_px = float(t["entry_price"])
    csv_pnl  = float(t["pnl_usd"])
    csv_exit = t["exit_type"]
    csv_hold = int(t["holding_candles"])
    csv_exit_px = float(t["exit_price"])

    ci = int(ohlcv.index.get_indexer([entry_ts], method="nearest")[0])
    sim_pnl, sim_exit, sim_hold, sim_exit_px = run_trade(side, entry_px, ci)

    err = abs(sim_pnl - csv_pnl)
    if csv_exit == sim_exit:
        exit_type_match["match"] += 1
    else:
        exit_type_match["mismatch"] += 1

    if err > 5.0:
        big_errors.append({
            "side": side, "entry_px": entry_px, "entry_ts": str(entry_ts)[:16],
            "csv_exit": csv_exit, "sim_exit": sim_exit,
            "csv_hold": csv_hold, "sim_hold": sim_hold,
            "csv_exit_px": csv_exit_px, "sim_exit_px": round(sim_exit_px, 2),
            "csv_pnl": csv_pnl, "sim_pnl": sim_pnl, "err": round(err, 2),
            "ci": ci,
        })

print(f"Exit type match: {exit_type_match}")
print(f"Big errors (err>$5): {len(big_errors)} / 500\n")

# Print 20 worst
for e in sorted(big_errors, key=lambda x: -x["err"])[:20]:
    print(f"{e['entry_ts']} {e['side']:5s} entry={e['entry_px']:.2f}  "
          f"csv=({e['csv_exit']:8s} hold={e['csv_hold']} exit={e['csv_exit_px']:.2f} pnl={e['csv_pnl']:+.2f})  "
          f"sim=({e['sim_exit']:8s} hold={e['sim_hold']} exit={e['sim_exit_px']:.2f} pnl={e['sim_pnl']:+.2f})  "
          f"err=${e['err']:.2f}  ci={e['ci']}")

# ── Kasus hold mismatch ───────────────────────────────────────────────────────
hold_mismatches = [e for e in big_errors if e["csv_hold"] != e["sim_hold"]]
print(f"\nHold mismatch cases: {len(hold_mismatches)}")
hold_diffs = [e["sim_hold"] - e["csv_hold"] for e in hold_mismatches]
if hold_diffs:
    from collections import Counter
    print("  sim_hold - csv_hold distribution:", dict(Counter(hold_diffs)))

# ── Spot check: apakah entry_time = candle open setelah signal? ───────────────
print("\n--- Entry time vs OHLCV candle check (10 in-range) ---")
for t in in_range[10:20]:
    entry_ts = pd.Timestamp(t["entry_time"].replace("+00:00",""), tz="UTC")
    ci = int(ohlcv.index.get_indexer([entry_ts], method="nearest")[0])
    candle_ts = ohlcv.index[ci]
    delta_min = abs((entry_ts - candle_ts).total_seconds()) / 60
    print(f"  entry_time={str(entry_ts)[:16]}  nearest_candle={str(candle_ts)[:16]}  delta={delta_min:.0f}min  "
          f"open={ohlcv.iloc[ci]['Open']:.2f}  entry_px={t['entry_price']}")
