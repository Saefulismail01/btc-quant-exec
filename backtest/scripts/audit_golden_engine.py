import csv, statistics
from pathlib import Path
from collections import Counter, defaultdict

f = Path("results/v4_5_comparison_results/v4_5_201901_202603_20260309_102822_golden_trades.csv")
trades = list(csv.DictReader(open(f)))

# Distribusi exit_type
exit_types = Counter(t["exit_type"] for t in trades)
print("Exit types:", dict(exit_types))

# Avg PnL per exit type
pnl_by_exit = defaultdict(list)
for t in trades:
    pnl_by_exit[t["exit_type"]].append(float(t["pnl_usd"]))

for et, pnls in sorted(pnl_by_exit.items()):
    wins = [p for p in pnls if p > 0]
    avg_win = statistics.mean(wins) if wins else 0
    print(f"{et:12s}: n={len(pnls):4d}  avg=${statistics.mean(pnls):+8.2f}  avg_win=${avg_win:+8.2f}  wr={len(wins)/len(pnls)*100:.1f}%")

# Cek actual_move_pct pada TRAIL_TP trades
trail = [t for t in trades if t["exit_type"] == "TRAIL_TP"]
moves = [float(t["actual_move_pct"]) for t in trail]
print(f"\nTRAIL_TP actual_move_pct: min={min(moves):.4f}  max={max(moves):.4f}  mean={statistics.mean(moves):.4f}  median={statistics.median(moves):.4f}")
print(f"TRAIL_TP avg_pnl=${statistics.mean([float(t['pnl_usd']) for t in trail]):+.2f}")

# Reconstruct PnL dari entry/exit/notional/leverage - cek apakah ada fee
print("\nPnL reconstruction check (10 sample trades):")
for t in trades[1:6]:
    notional = float(t["notional"])
    entry    = float(t["entry_price"])
    exit_p   = float(t["exit_price"])
    side     = t["side"]
    pnl_act  = float(t["pnl_usd"])
    move     = (exit_p - entry)/entry if side == "LONG" else (entry - exit_p)/entry
    pnl_nofee = notional * move
    pnl_fee12 = notional * move - 12
    print(f"  {side:5s} entry={entry:.2f} exit={exit_p:.2f} | actual={pnl_act:+8.2f} | no_fee={pnl_nofee:+8.2f} | fee12={pnl_fee12:+8.2f} | diff={pnl_act-pnl_nofee:+.2f}")

# Check holding_candles distribution
holds = [int(t["holding_candles"]) for t in trades]
print(f"\nholding_candles: min={min(holds)}  max={max(holds)}  mean={statistics.mean(holds):.2f}")
for k, v in sorted(Counter(holds).items()):
    print(f"  hold={k}: {v} ({v/len(holds)*100:.1f}%)")
