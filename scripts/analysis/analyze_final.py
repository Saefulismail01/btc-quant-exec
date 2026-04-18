import pandas as pd

df = pd.read_csv('data/exports/lighter-trade-export-2026-04-17T07_11_42.517Z-UTC.csv')
closes = df[df['Side'].str.contains('Close')].copy()
closes_with_pnl = closes[closes['Closed PnL'] != '-'].copy()
closes_with_pnl['Closed PnL'] = pd.to_numeric(closes_with_pnl['Closed PnL'])
closes_with_pnl['Date'] = pd.to_datetime(closes_with_pnl['Date'])

# Stats total
total_trades = len(closes_with_pnl)
wins = len(closes_with_pnl[closes_with_pnl['Closed PnL'] > 0])
losses = len(closes_with_pnl[closes_with_pnl['Closed PnL'] < 0])
total_pnl = closes_with_pnl['Closed PnL'].sum()

# Group by timestamp (merge partial fills)
by_time = closes_with_pnl.groupby('Date')['Closed PnL'].sum()
positions = len(by_time)
by_time_wins = len(by_time[by_time > 0])
by_time_losses = len(by_time[by_time < 0])
win_rate = by_time_wins / positions * 100 if positions > 0 else 0

print('=== STATISTIK FINAL (10 Mar - 14 Apr 2026) ===')
print(f"Periode: {closes_with_pnl['Date'].min()} - {closes_with_pnl['Date'].max()}")
print(f'Total Rows: {total_trades}')
print(f'Unique Positions: {positions}')
print(f'Win: {by_time_wins} | Loss: {by_time_losses}')
print(f'Win Rate: {win_rate:.1f}%')
print(f'Total PnL: ${by_time.sum():.2f}')
print(f'Avg Win: ${by_time[by_time > 0].mean():.2f}')
print(f'Avg Loss: ${by_time[by_time < 0].mean():.2f}')

# By Side (grouped)
print('\n=== BY SIDE ===')
for side in ['Close Long', 'Close Short']:
    side_data = closes_with_pnl[closes_with_pnl['Side'] == side]
    if len(side_data) > 0:
        side_by_time = side_data.groupby('Date')['Closed PnL'].sum()
        side_wins = len(side_by_time[side_by_time > 0])
        side_losses = len(side_by_time[side_by_time < 0])
        side_pnl = side_by_time.sum()
        print(f'{side}: {side_wins}W/{side_losses}L | WR: {side_wins/(side_wins+side_losses)*100:.1f}% | PnL: ${side_pnl:.2f}')

# By month
closes_with_pnl['Month'] = closes_with_pnl['Date'].dt.strftime('%Y-%m')
monthly = closes_with_pnl.groupby(['Month', 'Date'])['Closed PnL'].sum().groupby('Month').sum()
print('\n=== BY MONTH ===')
for month, pnl in monthly.items():
    trades = closes_with_pnl[closes_with_pnl['Month'] == month]['Date'].nunique()
    print(f'{month}: ${pnl:.2f} ({trades} posisi)')

# Dashboard comparison
print(f'\n=== PERBANDINGAN DASHBOARD ===')
print(f'CSV Total PnL: ${by_time.sum():.2f}')
print(f'Dashboard Lighter: $14.11')
print(f'Selisih: ${by_time.sum() - 14.11:.2f}')
