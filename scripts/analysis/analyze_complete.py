import pandas as pd

df = pd.read_csv('data/exports/lighter-trade-export-2026-04-17T07_06_34.871Z-UTC.csv')
closes = df[df['Side'].str.contains('Close')].copy()
closes_with_pnl = closes[closes['Closed PnL'] != '-'].copy()
closes_with_pnl['Closed PnL'] = pd.to_numeric(closes_with_pnl['Closed PnL'])
closes_with_pnl['Date'] = pd.to_datetime(closes_with_pnl['Date'])

# Stats
total_trades = len(closes_with_pnl)
wins = len(closes_with_pnl[closes_with_pnl['Closed PnL'] > 0])
losses = len(closes_with_pnl[closes_with_pnl['Closed PnL'] < 0])
win_rate = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0
total_pnl = closes_with_pnl['Closed PnL'].sum()
avg_win = closes_with_pnl[closes_with_pnl['Closed PnL'] > 0]['Closed PnL'].mean() if wins > 0 else 0
avg_loss = closes_with_pnl[closes_with_pnl['Closed PnL'] < 0]['Closed PnL'].mean() if losses > 0 else 0
profit_factor = abs(closes_with_pnl[closes_with_pnl['Closed PnL'] > 0]['Closed PnL'].sum() / closes_with_pnl[closes_with_pnl['Closed PnL'] < 0]['Closed PnL'].sum()) if losses > 0 else float('inf')

print('=== STATISTIK LENGKAP (16 Mar - 14 Apr 2026) ===')
print(f"Periode: {closes_with_pnl['Date'].min()} - {closes_with_pnl['Date'].max()}")
print(f'Total Trade (rows): {total_trades}')
print(f'Win: {wins} | Loss: {losses}')
print(f'Win Rate: {win_rate:.1f}%')
print(f'Total PnL: ${total_pnl:.2f}')
print(f'Avg Win: ${avg_win:.2f}')
print(f'Avg Loss: ${avg_loss:.2f}')
print(f'Profit Factor: {profit_factor:.2f}')

# Group by timestamp (merge partial fills)
by_time = closes_with_pnl.groupby('Date')['Closed PnL'].sum().reset_index()
by_time_wins = len(by_time[by_time['Closed PnL'] > 0])
by_time_losses = len(by_time[by_time['Closed PnL'] < 0])

print(f'\n=== GROUPED BY POSITION (unique timestamps) ===')
print(f'Unique positions: {len(by_time)}')
print(f'Win: {by_time_wins} | Loss: {by_time_losses}')
print(f'Win Rate: {by_time_wins/(by_time_wins+by_time_losses)*100:.1f}%')
print(f'Total PnL (grouped): ${by_time["Closed PnL"].sum():.2f}')

# Per side
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
    print(f'{month}: ${pnl:.2f}')

# By day (April only)
april = closes_with_pnl[closes_with_pnl['Month'] == '2026-04']
if len(april) > 0:
    april_by_day = april.groupby(april['Date'].dt.date)['Closed PnL'].sum()
    print('\n=== APRIL DAILY ===')
    for day, pnl in april_by_day.items():
        print(f'{day}: ${pnl:.2f}')

print(f'\n=== DASHBOARD COMPARISON ===')
print(f'CSV Total PnL: ${total_pnl:.2f}')
print(f'Dashboard PnL: $10.54')
print(f'Difference: ${total_pnl - 10.54:.2f}')
