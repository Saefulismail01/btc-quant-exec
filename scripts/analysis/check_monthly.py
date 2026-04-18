import pandas as pd

df = pd.read_csv('data/exports/lighter-trade-export-2026-04-17T06_54_16.134Z-UTC.csv')
closes = df[df['Side'].str.contains('Close')].copy()
closes_with_pnl = closes[closes['Closed PnL'] != '-'].copy()
closes_with_pnl['Closed PnL'] = pd.to_numeric(closes_with_pnl['Closed PnL'])

# Parse date
closes_with_pnl['Date'] = pd.to_datetime(closes_with_pnl['Date'])
closes_with_pnl['Month'] = closes_with_pnl['Date'].dt.strftime('%Y-%m')

# Group by month
monthly = closes_with_pnl.groupby('Month')['Closed PnL'].sum()

print('=== PnL PER BULAN ===')
for month, pnl in monthly.items():
    trades = len(closes_with_pnl[closes_with_pnl['Month'] == month])
    print(f'{month}: ${pnl:.2f} ({trades} trades)')

print(f'\n=== TOTAL: ${monthly.sum():.2f} ===')

# Check if dashboard only shows April
april_pnl = monthly.get('2026-04', 0)
print(f'\n=== APRIL ONLY: ${april_pnl:.2f} ===')
print(f'Selisih dengan dashboard $10.54: ${april_pnl - 10.54:.2f}')

# Show April trades
print('\n=== APRIL TRADES ===')
april_trades = closes_with_pnl[closes_with_pnl['Month'] == '2026-04']
by_day = april_trades.groupby(april_trades['Date'].dt.date)['Closed PnL'].sum()
for day, pnl in by_day.items():
    print(f'{day}: ${pnl:.2f}')
