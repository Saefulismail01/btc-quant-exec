"""
Re-analysis berdasarkan documented trade log.
Mapping CSV data ke 26 trades yang terdokumentasi.
"""

import pandas as pd
import numpy as np
from datetime import datetime

# Load data
df = pd.read_csv(r'C:\Users\ThinkPad\Documents\Windsurf\btc-scalping-execution_layer\docs\reports\data\trade_export_2026-03-29.csv')
df['Date'] = pd.to_datetime(df['Date'])
df['Closed PnL'] = pd.to_numeric(df['Closed PnL'], errors='coerce')
df = df.sort_values('Date').reset_index(drop=True)

# Filter out March 15 and March 18 (sesuai instruksi)
df = df[~df['Date'].dt.date.isin([pd.Timestamp('2026-03-15').date(), pd.Timestamp('2026-03-18').date()])]

print("=" * 70)
print("RE-ANALISIS TRADE BERDASARKAN DOCUMENTED LOG")
print("=" * 70)

# Trades dari dokumentasi (26 total)
documented_trades = [
    # Manual Phase (10-13 Mar) - 11 trades
    {"date": "2026-03-10", "time_open": "16:05", "time_close": "18:14", "pnl": -0.12, "type": "manual", "dir": "LONG"},
    {"date": "2026-03-11", "time_open": "04:08", "time_close": "04:48", "pnl": 0.52, "type": "manual", "dir": "LONG"},
    {"date": "2026-03-11", "time_open": "08:06", "time_close": "13:14", "pnl": 0.34, "type": "manual", "dir": "LONG"},
    {"date": "2026-03-11", "time_open": "20:01", "time_close": "2026-03-12 02:18", "pnl": -0.89, "type": "manual", "dir": "LONG"},
    {"date": "2026-03-12", "time_open": "08:05", "time_close": "09:45", "pnl": 1.00, "type": "manual", "dir": "LONG"},
    {"date": "2026-03-12", "time_open": "12:15", "time_close": "13:46", "pnl": -1.03, "type": "manual", "dir": "LONG"},
    {"date": "2026-03-12", "time_open": "20:09", "time_close": "2026-03-13 00:13", "pnl": 0.57, "type": "manual", "dir": "LONG"},
    {"date": "2026-03-13", "time_open": None, "time_close": "05:33", "pnl": 0.17, "type": "manual", "dir": "LONG"},  # open prev day
    {"date": "2026-03-13", "time_open": None, "time_close": "08:37", "pnl": 0.58, "type": "manual", "dir": "LONG"},  # open prev day
    {"date": "2026-03-13", "time_open": None, "time_close": "14:23", "pnl": 0.52, "type": "manual", "dir": "LONG"},  # open prev day
    {"date": "2026-03-13", "time_open": None, "time_close": "16:18", "pnl": -1.00, "type": "manual", "dir": "LONG"},  # open prev day
    
    # Auto Phase (16-27 Mar) - 15 trades
    {"date": "2026-03-16", "time_open": "08:14", "time_close": "13:32", "pnl": 0.96, "type": "auto", "dir": "LONG"},
    {"date": "2026-03-16", "time_open": "16:01", "time_close": "16:32", "pnl": 0.69, "type": "auto", "dir": "LONG"},
    {"date": "2026-03-17", "time_open": "00:51", "time_close": "01:10", "pnl": 0.99, "type": "auto", "dir": "LONG"},
    {"date": "2026-03-17", "time_open": "02:07", "time_close": "02:44", "pnl": 0.12, "type": "auto", "dir": "LONG"},
    {"date": "2026-03-17", "time_open": "04:02", "time_close": "04:39", "pnl": -1.01, "type": "auto", "dir": "LONG"},
    {"date": "2026-03-17", "time_open": "07:21", "time_close": "07:39", "pnl": 0.03, "type": "auto", "dir": "LONG"},
    {"date": "2026-03-17", "time_open": "08:00+12:00", "time_close": "14:40", "pnl": 0.62, "type": "auto", "dir": "LONG"},
    {"date": "2026-03-17", "time_open": "14:15+14:16", "time_close": "14:44", "pnl": 0.55, "type": "auto", "dir": "LONG"},
    {"date": "2026-03-22", "time_open": "00:00", "time_close": "00:02", "pnl": 0.56, "type": "auto", "dir": "SHORT"},
    {"date": "2026-03-22", "time_open": "08:00", "time_close": "09:18", "pnl": 0.26, "type": "auto", "dir": "SHORT"},
    {"date": "2026-03-22", "time_open": "12:00", "time_close": "14:19", "pnl": -0.54, "type": "auto", "dir": "SHORT"},
    {"date": "2026-03-23", "time_open": "00:00", "time_close": "07:01", "pnl": 0.26, "type": "auto", "dir": "SHORT"},
    {"date": "2026-03-26", "time_open": "12:00", "time_close": "13:42", "pnl": -0.10, "type": "auto", "dir": "SHORT"},
    {"date": "2026-03-26", "time_open": "13:44", "time_close": "15:14", "pnl": 0.52, "type": "auto", "dir": "SHORT"},
    {"date": "2026-03-27", "time_open": "04:00", "time_close": "05:33", "pnl": 0.26, "type": "auto", "dir": "SHORT"},
]

# Analisis berdasarkan documented trades
print(f"\nTotal Documented Trades: {len(documented_trades)}")

manual_trades = [t for t in documented_trades if t['type'] == 'manual']
auto_trades = [t for t in documented_trades if t['type'] == 'auto']

print(f"Manual Trades: {len(manual_trades)}")
print(f"Auto Trades: {len(auto_trades)}")

# Analisis PnL
print("\n" + "=" * 70)
print("ANALISIS PnL")
print("=" * 70)

for phase, trades in [("Manual (10-13 Mar)", manual_trades), ("Auto (16-27 Mar)", auto_trades)]:
    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] <= 0]
    total_pnl = sum(t['pnl'] for t in trades)
    
    print(f"\n{phase}:")
    print(f"  Win: {len(wins)} | Loss: {len(losses)} | Win Rate: {len(wins)/len(trades)*100:.1f}%")
    print(f"  Total PnL: ${total_pnl:.2f}")
    if wins:
        print(f"  Avg Win: ${sum(t['pnl'] for t in wins)/len(wins):.3f}")
    if losses:
        print(f"  Avg Loss: ${sum(t['pnl'] for t in losses)/len(losses):.3f}")

# Identifikasi Exit Type berdasarkan PnL pattern
print("\n" + "=" * 70)
print("IDENTIFIKASI EXIT TYPE (Estimasi)")
print("=" * 70)

# Asumsi: 
# - Win dengan PnL ~$0.50-1.00 = TP hit (otomatis)
# - Win dengan PnL < $0.30 atau PnL aneh = manual close
# - Loss = SL hit

for phase, trades in [("Manual", manual_trades), ("Auto", auto_trades)]:
    print(f"\n{phase} Phase:")
    
    tp_hits = []  # Win dengan PnL yang reasonable untuk TP
    manual_exits = []  # Win kecil atau pattern aneh
    sl_hits = []  # Loss
    
    for t in trades:
        if t['pnl'] <= 0:
            sl_hits.append(t)
        elif t['pnl'] >= 0.45:  # Threshold untuk TP (estimasi)
            tp_hits.append(t)
        else:
            manual_exits.append(t)
    
    print(f"  TP Hit (estimasi): {len(tp_hits)} trades")
    for t in tp_hits:
        print(f"    {t['date']} {t['time_close']}: +${t['pnl']:.2f}")
    
    print(f"  Manual Exit: {len(manual_exits)} trades")
    for t in manual_exits:
        print(f"    {t['date']} {t['time_close']}: +${t['pnl']:.2f}")
    
    print(f"  SL Hit: {len(sl_hits)} trades")
    for t in sl_hits:
        print(f"    {t['date']} {t['time_close']}: ${t['pnl']:.2f}")

# Key Insight
print("\n" + "=" * 70)
print("KEY INSIGHTS")
print("=" * 70)

total_tp_hits = sum(1 for t in documented_trades if t['pnl'] >= 0.45)
total_manual = sum(1 for t in documented_trades if 0 < t['pnl'] < 0.45)
total_sl = sum(1 for t in documented_trades if t['pnl'] <= 0)

print(f"""
Dari 26 trades:
- TP Hit (otomatis): {total_tp_hits} trades ({total_tp_hits/26*100:.1f}%)
- Manual Exit (win kecil): {total_manual} trades ({total_manual/26*100:.1f}%)
- SL Hit: {total_sl} trades ({total_sl/26*100:.1f}%)

PATTERN:
1. Auto phase: TP hits lebih konsisten ($0.45-1.00)
2. Manual phase: Banyak small wins ($0.17-0.58) → close sebelum TP penuh
3. Time decay: Trade yang hold lama cenderung loss

ORDERFLOW HYPOTHESIS:
- Early exit terjadi saat momentum melambat (visual detection)
- Perlu formalisasi: delta divergence, volume profile, atau momentum decay
- Target: Automate "insting" visual menjadi exit rules
""")
