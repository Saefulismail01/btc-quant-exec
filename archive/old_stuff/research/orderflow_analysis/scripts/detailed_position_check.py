"""
Detailed position tracking analysis.
Identifikasi unmatched positions dan complete trade cycles.
"""

import pandas as pd
import numpy as np
from datetime import datetime

# Load data
df = pd.read_csv(r'C:\Users\ThinkPad\Documents\Windsurf\btc-scalping-execution_layer\docs\reports\data\trade_export_2026-03-29.csv')
df['Date'] = pd.to_datetime(df['Date'])
df['Closed PnL'] = pd.to_numeric(df['Closed PnL'], errors='coerce')
df = df.sort_values('Date').reset_index(drop=True)

# Filter out March 15 and 18
df = df[~df['Date'].dt.date.isin([pd.Timestamp('2026-03-15').date(), pd.Timestamp('2026-03-18').date()])]

print("=" * 70)
print("RAW DATA BREAKDOWN")
print("=" * 70)
print(f"Total rows (after filter): {len(df)}")
print(f"\nBy Side:")
print(df['Side'].value_counts())

print(f"\nBy Date:")
date_counts = df.groupby([df['Date'].dt.date, 'Side']).size().unstack(fill_value=0)
print(date_counts.to_string())

# Calculate total open and close sizes per direction
print("\n" + "=" * 70)
print("POSITION BALANCE CHECK")
print("=" * 70)

for direction in ['Long', 'Short']:
    opens = df[df['Side'] == f'Open {direction}']
    closes = df[df['Side'] == f'Close {direction}']
    
    total_open_size = opens['Size'].sum()
    total_close_size = closes['Size'].sum()
    
    print(f"\n{direction}:")
    print(f"  Total Open Size: {total_open_size:.6f}")
    print(f"  Total Close Size: {total_close_size:.6f}")
    print(f"  Net Position: {total_open_size - total_close_size:.6f}")
    print(f"  Open Count: {len(opens)}, Close Count: {len(closes)}")

# Detailed position tracking with cumulative
print("\n" + "=" * 70)
print("POSITION TRACKING (First 20 events)")
print("=" * 70)

position_tracker = {'Long': 0, 'Short': 0}
events = []

for idx, row in df.head(20).iterrows():
    direction = row['Side'].replace('Open ', '').replace('Close ', '')
    size = row['Size']
    
    if 'Open' in row['Side']:
        position_tracker[direction] += size
        action = 'OPEN'
    else:
        position_tracker[direction] -= size
        action = 'CLOSE'
    
    events.append({
        'Time': row['Date'].strftime('%m-%d %H:%M'),
        'Action': action,
        'Direction': direction,
        'Size': size,
        'Price': row['Price'],
        'PnL': row['Closed PnL'],
        'Long_Pos': position_tracker['Long'],
        'Short_Pos': position_tracker['Short']
    })

events_df = pd.DataFrame(events)
print(events_df.to_string(index=False))

# Full position tracking
print("\n" + "=" * 70)
print("COMPLETE POSITION TRACKING")
print("=" * 70)

position_tracker = {'Long': 0, 'Short': 0}
cycle_count = 0
open_events = []

for idx, row in df.iterrows():
    direction = row['Side'].replace('Open ', '').replace('Close ', '')
    size = row['Size']
    
    if 'Open' in row['Side']:
        # This is a new position open
        position_tracker[direction] += size
        open_events.append({
            'idx': idx,
            'date': row['Date'],
            'direction': direction,
            'size': size,
            'price': row['Price'],
            'closed': False
        })
    else:
        # This is a close - match to earliest open
        position_tracker[direction] -= size
        
        # Find matching opens
        remaining = size
        for open_evt in open_events:
            if open_evt['direction'] == direction and not open_evt['closed'] and remaining > 0:
                matched = min(remaining, open_evt['size'])
                remaining -= matched
                open_evt['size'] -= matched
                if open_evt['size'] <= 0.000001:
                    open_evt['closed'] = True
                    cycle_count += 1

print(f"Complete Trade Cycles Identified: {cycle_count}")
print(f"Final Position - Long: {position_tracker['Long']:.6f}, Short: {position_tracker['Short']:.6f}")

# Count unclosed positions
unclosed = [e for e in open_events if not e['closed']]
print(f"Unclosed Positions: {len(unclosed)}")
for pos in unclosed[:5]:
    print(f"  {pos['direction']} opened {pos['date'].strftime('%m-%d %H:%M')}, size: {pos['size']:.6f}")

# Estimate actual trade count
print("\n" + "=" * 70)
print("TRADE COUNT ESTIMATION")
print("=" * 70)

# A simpler approach: group by approximate time windows
print("\nGrouping closes by timestamp (same minute = likely same exit):")
closes = df[df['Side'].str.contains('Close')].copy()
closes['Minute'] = closes['Date'].dt.floor('min')
exit_groups = closes.groupby('Minute').agg({
    'Size': 'sum',
    'Closed PnL': 'sum',
    'Side': 'first'
}).reset_index()

print(f"Number of distinct exit events: {len(exit_groups)}")
print(f"\nExit events breakdown:")
print(exit_groups.groupby('Side').size())
