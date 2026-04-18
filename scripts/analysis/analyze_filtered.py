import pandas as pd

df = pd.read_csv('data/exports/lighter-trade-export-2026-04-17T07_11_42.517Z-UTC.csv')
closes = df[df['Side'].str.contains('Close')].copy()
closes_with_pnl = closes[closes['Closed PnL'] != '-'].copy()
closes_with_pnl['Closed PnL'] = pd.to_numeric(closes_with_pnl['Closed PnL'])
closes_with_pnl['Date'] = pd.to_datetime(closes_with_pnl['Date'])
closes_with_pnl['Day'] = closes_with_pnl['Date'].dt.date

# Exclude tanggal 15 dan 18 Maret 2026
exclude_dates = [pd.to_datetime('2026-03-15').date(), pd.to_datetime('2026-03-18').date()]
filtered = closes_with_pnl[~closes_with_pnl['Day'].isin(exclude_dates)].copy()

print('=== FILTERED ANALYSIS (Exclude 15 Mar & 18 Mar) ===')
print(f'Excluded dates: March 15, March 18')
print(f'Rows excluded: {len(closes_with_pnl) - len(filtered)}')

# Group by timestamp (merge partial fills)
by_time = filtered.groupby('Date')['Closed PnL'].sum()
positions = len(by_time)
by_time_wins = len(by_time[by_time > 0])
by_time_losses = len(by_time[by_time < 0])
win_rate = by_time_wins / positions * 100 if positions > 0 else 0

print(f'\n=== STATISTIK FILTERED ===')
print(f"Periode: {filtered['Date'].min()} - {filtered['Date'].max()}")
print(f'Unique Positions: {positions}')
print(f'Win: {by_time_wins} | Loss: {by_time_losses}')
print(f'Win Rate: {win_rate:.1f}%')
print(f'Total PnL: ${by_time.sum():.2f}')
print(f'Avg Win: ${by_time[by_time > 0].mean():.2f}')
print(f'Avg Loss: ${by_time[by_time < 0].mean():.2f}')

# By Side (grouped)
print('\n=== BY SIDE ===')
for side in ['Close Long', 'Close Short']:
    side_data = filtered[filtered['Side'] == side]
    if len(side_data) > 0:
        side_by_time = side_data.groupby('Date')['Closed PnL'].sum()
        side_wins = len(side_by_time[side_by_time > 0])
        side_losses = len(side_by_time[side_by_time < 0])
        side_pnl = side_by_time.sum()
        print(f'{side}: {side_wins}W/{side_losses}L | WR: {side_wins/(side_wins+side_losses)*100:.1f}% | PnL: ${side_pnl:.2f}')

# By month
filtered['Month'] = filtered['Date'].dt.strftime('%Y-%m')
monthly_data = filtered.groupby(['Month', 'Date'])['Closed PnL'].sum().groupby('Month')
print('\n=== BY MONTH ===')
for month, pnl_series in monthly_data:
    trades = len(pnl_series)
    pnl = pnl_series.sum()
    print(f'{month}: ${pnl:.2f} ({trades} posisi)')

# By day (for verification)
print('\n=== DAILY BREAKDOWN (selected) ===')
daily = filtered.groupby('Day')['Closed PnL'].sum()
for day, pnl in daily.items():
    trades = filtered[filtered['Day'] == day]['Date'].nunique()
    print(f'{day}: ${pnl:.2f} ({trades} posisi)')

# Dashboard comparison
print(f'\n=== PERBANDINGAN DASHBOARD ===')
print(f'CSV Filtered PnL: ${by_time.sum():.2f}')
print(f'Dashboard Lighter: $14.11')
print(f'Selisih: ${by_time.sum() - 14.11:.2f}')

# Show what was excluded
print('\n=== EXCLUDED DATA ===')
excluded = closes_with_pnl[closes_with_pnl['Day'].isin(exclude_dates)]
for date in exclude_dates:
    date_data = excluded[excluded['Day'] == date]
    if len(date_data) > 0:
        date_grouped = date_data.groupby('Date')['Closed PnL'].sum()
        print(f'{date}: {len(date_grouped)} posisi, PnL: ${date_grouped.sum():.2f}')
        for ts, pnl in date_grouped.items():
            print(f'  {ts}: ${pnl:.2f}')
