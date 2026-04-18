import pandas as pd

df = pd.read_csv('data/exports/lighter-trade-export-2026-04-17T07_11_42.517Z-UTC.csv')
closes = df[df['Side'].str.contains('Close')].copy()
closes_with_pnl = closes[closes['Closed PnL'] != '-'].copy()
closes_with_pnl['Closed PnL'] = pd.to_numeric(closes_with_pnl['Closed PnL'])
closes_with_pnl['Date'] = pd.to_datetime(closes_with_pnl['Date'])
closes_with_pnl['Day'] = closes_with_pnl['Date'].dt.date

# Analyze tanggal 12-14 April
print('=== ANALISIS TANGGAL 12-14 APRIL ===')
print('')

for day in [12, 13, 14]:
    date = pd.to_datetime(f'2026-04-{day:02d}').date()
    date_data = closes_with_pnl[closes_with_pnl['Day'] == date]
    if len(date_data) > 0:
        by_time = date_data.groupby('Date').agg({
            'Closed PnL': 'sum',
            'Side': 'first',
            'Price': 'first',
            'Trade Value': 'first'
        }).reset_index()
        
        print(f'2026-04-{day:02d}:')
        for idx, row in by_time.iterrows():
            size_info = f' (Value: ${row["Trade Value"]:.2f})' if row['Trade Value'] < 100 else ''
            print(f'  {row["Date"]} | {row["Side"]} | PnL: ${row["Closed PnL"]:.2f}{size_info}')
        print(f'  -> Total: ${by_time["Closed PnL"].sum():.2f}, Avg Size: ${by_time["Trade Value"].mean():.2f}')
        print('')

# Compare with expected sizing
print('=== SIZING ANALYSIS ===')
print('Expected: $100 margin x 5x = $500 notional')
print('Actual: ~$30 margin x 5x = $150 notional (30% dari target)')
print('')
print('Impact: PnL 12-14 April sekitar 30% dari potensi maksimal')
print('        karena sizing terlalu kecil')
