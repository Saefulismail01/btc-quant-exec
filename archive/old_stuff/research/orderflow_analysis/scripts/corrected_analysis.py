"""
Analisis koreksi: Memisahkan full manual vs auto dengan intervensi TP/SL.
"""

import pandas as pd
import numpy as np

print("=" * 70)
print("KOREKSI: MANUAL vs AUTO + INTERVENSI TP/SL")
print("=" * 70)

# Data dari documented log dengan koreksi konteks
trades_data = [
    # === MANUAL PHASE (10-13 Mar) ===
    # Full manual: entry manual, TP/SL manual
    {"date": "10 Mar", "pnl": -0.12, "exit_type": "manual_full"},
    {"date": "11 Mar 04:48", "pnl": 0.52, "exit_type": "manual_full"},
    {"date": "11 Mar 13:14", "pnl": 0.34, "exit_type": "manual_full"},
    {"date": "11-12 Mar", "pnl": -0.89, "exit_type": "manual_full"},
    {"date": "12 Mar 09:45", "pnl": 1.00, "exit_type": "manual_full"},
    {"date": "12 Mar 13:46", "pnl": -1.03, "exit_type": "manual_full"},
    {"date": "12-13 Mar", "pnl": 0.57, "exit_type": "manual_full"},
    {"date": "13 Mar 05:33", "pnl": 0.17, "exit_type": "manual_full"},
    {"date": "13 Mar 08:37", "pnl": 0.58, "exit_type": "manual_full"},
    {"date": "13 Mar 14:23", "pnl": 0.52, "exit_type": "manual_full"},
    {"date": "13 Mar 16:18", "pnl": -1.00, "exit_type": "manual_full"},
    
    # === AUTO PHASE (16-27 Mar, excl 18 Mar bug) ===
    # Entry otomatis, TP/SL otomatis tapi kadang di-intervensi manual
    
    # Pure auto (hit TP atau SL, tidak ada intervensi)
    {"date": "16 Mar 13:32", "pnl": 0.96, "exit_type": "auto_pure", "hold_time_min": 318},
    {"date": "16 Mar 16:32", "pnl": 0.69, "exit_type": "auto_pure", "hold_time_min": 31},
    {"date": "17 Mar 01:10", "pnl": 0.99, "exit_type": "auto_pure", "hold_time_min": 19},
    {"date": "17 Mar 04:39", "pnl": -1.01, "exit_type": "auto_pure", "hold_time_min": 37},
    {"date": "17 Mar 14:44", "pnl": 0.55, "exit_type": "auto_pure", "hold_time_min": 28},
    {"date": "22 Mar 00:02", "pnl": 0.56, "exit_type": "auto_pure", "hold_time_min": 2},
    {"date": "22 Mar 14:19", "pnl": -0.54, "exit_type": "auto_pure", "hold_time_min": 139},
    {"date": "26 Mar 15:14", "pnl": 0.52, "exit_type": "auto_pure", "hold_time_min": 90},
    
    # Auto dengan intervensi manual TP/SL (close sebelum TP atau geser TP/SL)
    {"date": "17 Mar 02:44", "pnl": 0.12, "exit_type": "auto_intervene", "hold_time_min": 37, "note": "Close dini, TP normal ~0.45"},
    {"date": "17 Mar 07:39", "pnl": 0.03, "exit_type": "auto_intervene", "hold_time_min": 18, "note": "Very early exit"},
    {"date": "17 Mar 14:40", "pnl": 0.62, "exit_type": "auto_intervene", "hold_time_min": 400, "note": "Hold lama, mungkin geser TP"},
    {"date": "22 Mar 09:18", "pnl": 0.26, "exit_type": "auto_intervene", "hold_time_min": 78, "note": "Close manual, belum TP"},
    {"date": "23 Mar 07:01", "pnl": 0.26, "exit_type": "auto_intervene", "hold_time_min": 421, "note": "Hold lama, close manual"},
    {"date": "26 Mar 13:42", "pnl": -0.10, "exit_type": "auto_intervene", "hold_time_min": 102, "note": "SL atau close manual sebelum SL"},
    {"date": "27 Mar 05:33", "pnl": 0.26, "exit_type": "auto_intervene", "hold_time_min": 93, "note": "Close manual, belum TP"},
]

# Group analysis
manual_full = [t for t in trades_data if t['exit_type'] == 'manual_full']
auto_pure = [t for t in trades_data if t['exit_type'] == 'auto_pure']
auto_intervene = [t for t in trades_data if t['exit_type'] == 'auto_intervene']

print(f"\n{'='*70}")
print("BREAKDOWN")
print(f"{'='*70}")
print(f"Manual Phase (full manual): {len(manual_full)} trades")
print(f"Auto Phase - Pure: {len(auto_pure)} trades")
print(f"Auto Phase - With Intervention: {len(auto_intervene)} trades")
print(f"Total: {len(trades_data)} trades")

print(f"\n{'='*70}")
print("PERFORMA PER KATEGORI")
print(f"{'='*70}")

for label, trades in [
    ("Manual Full", manual_full),
    ("Auto Pure", auto_pure),
    ("Auto + Intervention", auto_intervene)
]:
    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] <= 0]
    total_pnl = sum(t['pnl'] for t in trades)
    avg_pnl = total_pnl / len(trades)
    
    print(f"\n{label}:")
    print(f"  Trades: {len(trades)}")
    print(f"  Win: {len(wins)} ({len(wins)/len(trades)*100:.0f}%) | Loss: {len(losses)} ({len(losses)/len(trades)*100:.0f}%)")
    print(f"  Total PnL: ${total_pnl:.2f}")
    print(f"  Avg PnL: ${avg_pnl:.2f}")
    if wins:
        print(f"  Avg Win: ${sum(t['pnl'] for t in wins)/len(wins):.2f}")
    if losses:
        print(f"  Avg Loss: ${sum(t['pnl'] for t in losses)/len(losses):.2f}")

print(f"\n{'='*70}")
print("TRADES DENGAN INTERVENSI MANUAL (YANG PERLU DIOTOMASI)")
print(f"{'='*70}")

for t in auto_intervene:
    print(f"\n{t['date']}: ${t['pnl']:+.2f} ({t['hold_time_min']} min hold)")
    print(f"  Note: {t.get('note', 'N/A')}")

print(f"\n{'='*70}")
print("HYPOTHESIS: KAPAN INTERVENSI TERJADI?")
print(f"{'='*70}")

print("""
Dari 7 trades dengan intervensi:

1. SHORT HOLD TIME (< 40 min) + small profit
   - 17 Mar 02:44: 37 min, $0.12
   - 17 Mar 07:39: 18 min, $0.03
   → Close terlalu cepat, FOMO?

2. LONG HOLD TIME (> 90 min) + small profit
   - 17 Mar 14:40: 400 min, $0.62 (actually good)
   - 23 Mar 07:01: 421 min, $0.26
   → Hold lama tapi TP geser atau close manual

3. MODERATE HOLD (70-100 min) + small profit
   - 22 Mar 09:18: 78 min, $0.26
   - 26 Mar 13:42: 102 min, -$0.10
   - 27 Mar 05:33: 93 min, $0.26
   → Momentum decay, manual close sebelum TP

PATTERN UNTUK ORDERFLOW AUTOMATION:
- Time-based: Setelah 60-90 min, cek momentum
- Momentum decay: Delta divergence detection
- Partial TP: Auto-close 50% di 50% TP, runner ke TP
""")
