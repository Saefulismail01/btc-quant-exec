"""
Analisis dengan notional-based thresholds untuk manual intervention.
Notional: 16-17 Mar = $150, 22-27 Mar = $75
"""

import pandas as pd

print("=" * 70)
print("ANALISIS DENGAN NOTIONAL-BASED THRESHOLDS")
print("=" * 70)

# Data trades dengan notional info
trades_with_notional = [
    # === AUTO PHASE 16-17 Mar: $10 × 15x = $150 notional ===
    # Threshold manual: ~$0.50 profit
    {"date": "16 Mar 13:32", "pnl": 0.96, "notional": 150, "manual_threshold": 0.50},
    {"date": "16 Mar 16:32", "pnl": 0.69, "notional": 150, "manual_threshold": 0.50},
    {"date": "17 Mar 01:10", "pnl": 0.99, "notional": 150, "manual_threshold": 0.50},
    {"date": "17 Mar 02:44", "pnl": 0.12, "notional": 150, "manual_threshold": 0.50},  # < 0.50
    {"date": "17 Mar 04:39", "pnl": -1.01, "notional": 150, "manual_threshold": 0.50},  # Loss
    {"date": "17 Mar 07:39", "pnl": 0.03, "notional": 150, "manual_threshold": 0.50},  # < 0.50
    {"date": "17 Mar 14:40", "pnl": 0.62, "notional": 150, "manual_threshold": 0.50},  # > 0.50 tapi < TP
    {"date": "17 Mar 14:44", "pnl": 0.55, "notional": 150, "manual_threshold": 0.50},  # > 0.50 tapi < TP
    
    # === AUTO PHASE 22-27 Mar: $5 × 15x = $75 notional ===
    # Threshold manual: ~$0.25 profit
    {"date": "22 Mar 00:02", "pnl": 0.56, "notional": 75, "manual_threshold": 0.25},
    {"date": "22 Mar 09:18", "pnl": 0.26, "notional": 75, "manual_threshold": 0.25},  # ~ threshold
    {"date": "22 Mar 14:19", "pnl": -0.54, "notional": 75, "manual_threshold": 0.25},  # Loss
    {"date": "23 Mar 07:01", "pnl": 0.26, "notional": 75, "manual_threshold": 0.25},  # ~ threshold
    {"date": "26 Mar 13:42", "pnl": -0.10, "notional": 75, "manual_threshold": 0.25},  # Loss
    {"date": "26 Mar 15:14", "pnl": 0.52, "notional": 75, "manual_threshold": 0.25},
    {"date": "27 Mar 05:33", "pnl": 0.26, "notional": 75, "manual_threshold": 0.25},  # ~ threshold
]

def classify_exit(trade):
    """Classify exit type based on PnL vs notional-based threshold."""
    pnl = trade['pnl']
    threshold = trade['manual_threshold']
    notional = trade['notional']
    
    if pnl < 0:
        return "SL_Hit"
    elif pnl >= threshold * 1.3:  # Clearly hit TP (30% above manual threshold)
        return "TP_Hit"
    else:
        return "Manual_Close"  # Suspicious - close near manual threshold

print("\nCLASSIFIKASI PER TRADE:")
print("-" * 70)

for t in trades_with_notional:
    exit_type = classify_exit(t)
    suspicious = "👀" if exit_type == "Manual_Close" else ""
    print(f"{t['date']}: ${t['pnl']:+.2f} (notional ${t['notional']}, threshold ${t['manual_threshold']}) → {exit_type} {suspicious}")

# Summary
print("\n" + "=" * 70)
print("SUMMARY BERDASARKAN NOTIONAL THRESHOLDS")
print("=" * 70)

from collections import Counter
exit_types = [classify_exit(t) for t in trades_with_notional]
counts = Counter(exit_types)

print(f"\nTotal Auto Phase Trades: {len(trades_with_notional)}")
print(f"TP Hit (otomatis): {counts.get('TP_Hit', 0)} trades")
print(f"SL Hit: {counts.get('SL_Hit', 0)} trades")
print(f"Suspected Manual Close: {counts.get('Manual_Close', 0)} trades")

manual_closes = [t for t in trades_with_notional if classify_exit(t) == "Manual_Close"]

print(f"\n" + "=" * 70)
print("SUSPECTED MANUAL INTERVENTION TRADES:")
print("=" * 70)
for t in manual_closes:
    print(f"  {t['date']}: ${t['pnl']:+.2f} (notional ${t['notional']}, manual threshold ~${t['manual_threshold']})")

print(f"\n" + "=" * 70)
print("NOTIONAL PHASE BREAKDOWN")
print("=" * 70)

# Phase $150 (16-17 Mar)
trades_150 = [t for t in trades_with_notional if t['notional'] == 150]
exits_150 = [classify_exit(t) for t in trades_150]
counts_150 = Counter(exits_150)

print(f"\n$150 Notional (16-17 Mar) - {len(trades_150)} trades:")
print(f"  TP Hit: {counts_150.get('TP_Hit', 0)}")
print(f"  SL Hit: {counts_150.get('SL_Hit', 0)}")
print(f"  Manual Close: {counts_150.get('Manual_Close', 0)}")

# Phase $75 (22-27 Mar)
trades_75 = [t for t in trades_with_notional if t['notional'] == 75]
exits_75 = [classify_exit(t) for t in trades_75]
counts_75 = Counter(exits_75)

print(f"\n$75 Notional (22-27 Mar) - {len(trades_75)} trades:")
print(f"  TP Hit: {counts_75.get('TP_Hit', 0)}")
print(f"  SL Hit: {counts_75.get('SL_Hit', 0)}")
print(f"  Manual Close: {counts_75.get('Manual_Close', 0)}")

print(f"\n" + "=" * 70)
print("KEY INSIGHT")
print("=" * 70)
print(f"""
Dari {len(trades_with_notional)} trades auto phase:
- {counts.get('TP_Hit', 0)} pure TP hits (otomatis tanpa intervensi)
- {counts.get('SL_Hit', 0)} SL hits (otomatis)
- {counts.get('Manual_Close', 0)} suspected manual intervention ({counts.get('Manual_Close', 0)/len(trades_with_notional)*100:.0f}%)

Pattern Manual Intervention:
- $150 phase: Close di $0.55-0.62 (belum sampai TP penuh ~$0.96-1.50)
- $75 phase: Close di $0.26 (dekat threshold $0.25)

Ini mendukung hipotesis: Kamu close manual saat profit "cukup" 
berdasarkan feeling visual, bukan aturan sistematis.
""")
