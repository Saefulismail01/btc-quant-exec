import pandas as pd

df = pd.read_csv('data/exports/lighter-trade-export-2026-04-17T06_54_16.134Z-UTC.csv')
closes = df[df['Side'].str.contains('Close')].copy()
closes_with_pnl = closes[closes['Closed PnL'] != '-'].copy()
closes_with_pnl['Closed PnL'] = pd.to_numeric(closes_with_pnl['Closed PnL'])

# Group by timestamp - merge partial fills
by_time = closes_with_pnl.groupby('Date')['Closed PnL'].sum().reset_index()

print('=== PnL PER POSISI (group by timestamp) ===')
for idx, row in by_time.iterrows():
    pnl = row['Closed PnL']
    print(f"{row['Date']:<22} | PnL: {pnl:>10.6f}")

print(f'\nTotal posisi unik: {len(by_time)}')
print(f'Total PnL (grouped): ${by_time["Closed PnL"].sum():.2f}')

# Perbandingan
print('\n=== PERBANDINGAN ===')
raw_total = closes_with_pnl['Closed PnL'].sum()
grouped_total = by_time['Closed PnL'].sum()
print(f'Raw CSV sum (57 rows): ${raw_total:.2f}')
print(f'Grouped by time (29 posisi): ${grouped_total:.2f}')
print(f'Dashboard Lighter: $10.54')
print(f'Selisih dari grouped: ${grouped_total - 10.54:.2f}')
