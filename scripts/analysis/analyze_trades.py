import pandas as pd

# Read CSV
df = pd.read_csv('data/exports/lighter-trade-export-2026-04-17T06_54_16.134Z-UTC.csv')

# Separate open and close trades
opens = df[df['Side'].str.contains('Open')].copy()
closes = df[df['Side'].str.contains('Close')].copy()

# Calculate closed trade statistics
closes_with_pnl = closes[closes['Closed PnL'] != '-'].copy()
closes_with_pnl['Closed PnL'] = pd.to_numeric(closes_with_pnl['Closed PnL'])

# Stats
total_trades = len(closes_with_pnl)
wins = len(closes_with_pnl[closes_with_pnl['Closed PnL'] > 0])
losses = len(closes_with_pnl[closes_with_pnl['Closed PnL'] < 0])
win_rate = wins / total_trades * 100 if total_trades > 0 else 0
total_pnl = closes_with_pnl['Closed PnL'].sum()
avg_win = closes_with_pnl[closes_with_pnl['Closed PnL'] > 0]['Closed PnL'].mean() if wins > 0 else 0
avg_loss = closes_with_pnl[closes_with_pnl['Closed PnL'] < 0]['Closed PnL'].mean() if losses > 0 else 0
profit_factor = abs(closes_with_pnl[closes_with_pnl['Closed PnL'] > 0]['Closed PnL'].sum() / closes_with_pnl[closes_with_pnl['Closed PnL'] < 0]['Closed PnL'].sum()) if losses > 0 else float('inf')

print('=== STATISTIK TRADING ===')
print(f"Periode: {df['Date'].min()} - {df['Date'].max()}")
print(f'Total Trade: {total_trades}')
print(f'Win: {wins} | Loss: {losses}')
print(f'Win Rate: {win_rate:.1f}%')
print(f'Total PnL: ${total_pnl:.2f}')
print(f'Avg Win: ${avg_win:.2f}')
print(f'Avg Loss: ${avg_loss:.2f}')
print(f'Profit Factor: {profit_factor:.2f}')

# By Side
print('\n=== BY SIDE ===')
for side in ['Close Long', 'Close Short']:
    side_data = closes_with_pnl[closes_with_pnl['Side'] == side]
    if len(side_data) > 0:
        side_wins = len(side_data[side_data['Closed PnL'] > 0])
        side_losses = len(side_data[side_data['Closed PnL'] < 0])
        side_pnl = side_data['Closed PnL'].sum()
        print(f'{side}: {side_wins}W/{side_losses}L | WR: {side_wins/(side_wins+side_losses)*100:.1f}% | PnL: ${side_pnl:.2f}')

# Recent 10 trades
print('\n=== 10 TRADE TERAKHIR ===')
print(closes_with_pnl[['Date', 'Side', 'Closed PnL']].tail(10).to_string(index=False))
