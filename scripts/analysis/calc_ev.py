import pandas as pd

df = pd.read_csv('data/exports/lighter-trade-export-2026-04-17T07_11_42.517Z-UTC.csv')
closes = df[df['Side'].str.contains('Close')].copy()
closes_with_pnl = closes[closes['Closed PnL'] != '-'].copy()
closes_with_pnl['Closed PnL'] = pd.to_numeric(closes_with_pnl['Closed PnL'])
closes_with_pnl['Date'] = pd.to_datetime(closes_with_pnl['Date'])

# Group by timestamp (merge partial fills)
by_time = closes_with_pnl.groupby('Date')['Closed PnL'].sum()
positions = len(by_time)
by_time_wins = by_time[by_time > 0]
by_time_losses = by_time[by_time < 0]

win_rate = len(by_time_wins) / positions
loss_rate = len(by_time_losses) / positions

avg_win = by_time_wins.mean()
avg_loss = abs(by_time_losses.mean())  # absolute value for loss

# EV calculation
ev = (win_rate * avg_win) - (loss_rate * avg_loss)

print(f'Total Positions: {positions}')
print(f'Wins: {len(by_time_wins)} | Losses: {len(by_time_losses)}')
print(f'Win Rate: {win_rate:.1%}')
print(f'Avg Win: ${avg_win:.2f}')
print(f'Avg Loss: ${avg_loss:.2f}')
print(f'EV per trade: ${ev:.2f}')
print()
print('=== BREAKDOWN BY SIDE ===')

# Add side info by looking at the original Side column (most recent per timestamp)
by_time_side = closes_with_pnl.groupby('Date')['Side'].first()

for side_name, side_code in [('Long', 'Close Long'), ('Short', 'Close Short')]:
    side_dates = by_time_side[by_time_side == side_code].index
    side_pnl = by_time[by_time.index.isin(side_dates)]
    
    if len(side_pnl) == 0:
        continue
        
    side_wins = side_pnl[side_pnl > 0]
    side_losses = side_pnl[side_pnl < 0]
    
    side_wr = len(side_wins) / len(side_pnl) if len(side_pnl) > 0 else 0
    side_lr = len(side_losses) / len(side_pnl) if len(side_pnl) > 0 else 0
    side_avg_win = side_wins.mean() if len(side_wins) > 0 else 0
    side_avg_loss = abs(side_losses.mean()) if len(side_losses) > 0 else 0
    side_ev = (side_wr * side_avg_win) - (side_lr * side_avg_loss)
    side_total_pnl = side_pnl.sum()
    
    print(f'{side_name}: {len(side_wins)}W/{len(side_losses)}L | WR: {side_wr:.1%}')
    print(f'  Avg Win: ${side_avg_win:.2f} | Avg Loss: ${side_avg_loss:.2f}')
    print(f'  Total PnL: ${side_total_pnl:.2f} | EV: ${side_ev:.2f}')
    print()
