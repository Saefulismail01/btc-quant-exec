import pandas as pd

# Load the data
file_path = r'C:\Users\ThinkPad\Documents\Windsurf\btc-scalping-quant\backtest\results\walkforward_trades_202211_202603_20260303_161852.csv'
df = pd.read_csv(file_path)

# Calculate raw price return for each trade
def calculate_raw_return(row):
    try:
        if row['side'] == 'LONG':
            return (row['exit_price'] - row['entry_price']) / row['entry_price']
        else: # SHORT
            return (row['entry_price'] - row['exit_price']) / row['entry_price']
    except:
        return 0

df['raw_return'] = df.apply(calculate_raw_return, axis=1)

# Leverage 5x
leverage = 5
df['leveraged_return'] = df['raw_return'] * leverage

# Initial equity
initial_equity = 10000.0
current_equity = initial_equity

# List to keep track of equity
equity_path = []

for ret in df['leveraged_return']:
    current_equity *= (1 + ret)
    equity_path.append(current_equity)

# Current value and total return
final_equity = current_equity
total_return_pct = (final_equity - initial_equity) / initial_equity * 100

print(f"Initial Equity: {initial_equity}")
print(f"Final Equity (5x Leverage): {final_equity:,.2f}")
print(f"Total Return (5x Leverage): {total_return_pct:,.2f}%")

# Compare with current results in CSV
current_backtest_final_equity = df['equity'].iloc[-1]
current_backtest_return_pct = (current_backtest_final_equity - initial_equity) / initial_equity * 100
print(f"\nCurrent Backtest Final Equity (at variable risk): {current_backtest_final_equity:,.2f}")
print(f"Current Backtest Total Return: {current_backtest_return_pct:,.2f}%")
