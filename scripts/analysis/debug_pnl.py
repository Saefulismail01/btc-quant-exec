import pandas as pd

df = pd.read_csv('data/exports/lighter-trade-export-2026-04-17T06_54_16.134Z-UTC.csv')
closes = df[df['Side'].str.contains('Close')].copy()
closes_with_pnl = closes[closes['Closed PnL'] != '-'].copy()
closes_with_pnl['Closed PnL'] = pd.to_numeric(closes_with_pnl['Closed PnL'])

# Debug: print semua PnL
print('=== SEMUA CLOSED PnL ===')
for idx, row in closes_with_pnl.iterrows():
    print(f"{row['Date']:<22} | {row['Side']:<11} | PnL: {row['Closed PnL']:>8.6f}")

print(f'\n=== TOTAL PnL: {closes_with_pnl["Closed PnL"].sum():.6f} ===')

# Cek apakah ada trade yang sama waktu (partial fills)
print('\n=== POTENSI PARTIAL FILLS (waktu sama) ===')
dups = closes_with_pnl[closes_with_pnl.duplicated(subset=['Date'], keep=False)]
if len(dups) > 0:
    print(dups[['Date', 'Side', 'Closed PnL', 'Size', 'Price']].to_string(index=False))
    print(f"\nTotal PnL dari partial fills: {dups['Closed PnL'].sum():.6f}")
else:
    print('Tidak ada partial fills')

# Unique timestamps count
print(f"\nUnique close timestamps: {closes_with_pnl['Date'].nunique()}")
print(f"Total close rows: {len(closes_with_pnl)}")
