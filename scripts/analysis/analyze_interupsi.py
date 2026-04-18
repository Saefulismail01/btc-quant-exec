import pandas as pd

df = pd.read_csv('data/exports/lighter-trade-export-2026-04-17T07_11_42.517Z-UTC.csv')
closes = df[df['Side'].str.contains('Close')].copy()
closes_with_pnl = closes[closes['Closed PnL'] != '-'].copy()
closes_with_pnl['Closed PnL'] = pd.to_numeric(closes_with_pnl['Closed PnL'])
closes_with_pnl['Date'] = pd.to_datetime(closes_with_pnl['Date'])
closes_with_pnl['Day'] = closes_with_pnl['Date'].dt.date

# Filter tanggal interupsi manual
interupsi_dates = [
    pd.to_datetime('2026-04-03').date(),
    pd.to_datetime('2026-04-05').date(),
    pd.to_datetime('2026-04-07').date(),
    pd.to_datetime('2026-04-10').date()
]

print('=== ANALISIS INTERUPSI MANUAL ===')
print('Tanggal: 3, 5, 7, 10 April 2026')
print('Kondisi: Signal lama tidak close → manual close')
print('Ekspektasi: Harusnya kena TP')
print('')

total_interupsi_pnl = 0
for date in interupsi_dates:
    date_data = closes_with_pnl[closes_with_pnl['Day'] == date]
    if len(date_data) > 0:
        # Group by timestamp
        by_time = date_data.groupby('Date').agg({
            'Closed PnL': 'sum',
            'Side': 'first',
            'Price': 'first'
        }).reset_index()
        
        print(f'{date}:')
        for idx, row in by_time.iterrows():
            print(f'  {row["Date"]} | {row["Side"]} | PnL: ${row["Closed PnL"]:.2f}')
            total_interupsi_pnl += row['Closed PnL']
        print(f'  → Total hari ini: ${by_time["Closed PnL"].sum():.2f}')
        print('')

print('=== RINGKASAN INTERUPSI ===')
print(f'Total PnL dari 4 interupsi: ${total_interupsi_pnl:.2f}')
print('')
print('Catatan user:')
print('- Semua interupsi ini seharusnya kena TP')
print('- Interupsi mengurangi profit (karena TP < 5% atau malah loss)')
print('- Potensi profit yang hilang perlu dihitung dari target TP yang seharusnya')
