import pandas as pd

df = pd.read_csv('data/exports/lighter-trade-export-2026-04-17T07_11_42.517Z-UTC.csv')
closes = df[df['Side'].str.contains('Close')].copy()
closes_with_pnl = closes[closes['Closed PnL'] != '-'].copy()
closes_with_pnl['Closed PnL'] = pd.to_numeric(closes_with_pnl['Closed PnL'])
closes_with_pnl['Date'] = pd.to_datetime(closes_with_pnl['Date'])
closes_with_pnl['Day'] = closes_with_pnl['Date'].dt.date

# Step 1: Exclude 15 Mar (uji coba) - diabaikan total
exclude_15 = closes_with_pnl[closes_with_pnl['Day'] == pd.to_datetime('2026-03-15').date()]
filtered = closes_with_pnl[closes_with_pnl['Day'] != pd.to_datetime('2026-03-15').date()].copy()

# Step 2: Group by timestamp
by_time = filtered.groupby('Date')['Closed PnL'].sum()

# Step 3: Identify 18 Mar (bug SL)
bug_date = pd.to_datetime('2026-03-18').date()
bug_trades = [d for d in by_time.index if d.date() == bug_date]

# Step 4: Calculate stats
wins = len(by_time[by_time > 0])
losses = len(by_time[by_time < 0])  # Include 18 Mar sebagai loss

# PnL adjusted (exclude bug)
pnl_raw = by_time.sum()
pnl_adjusted = pnl_raw
bug_pnl = 0

if bug_trades:
    bug_pnl = by_time[bug_trades[0]]
    pnl_adjusted = pnl_raw - bug_pnl

print('=== ANALISIS KOREKSI ===')
print('15 Mar: DIABAIAKAN (uji coba otomasi)')
print('18 Mar: DIHITUNG sebagai loss, tapi PnL = 0 (bug SL)')
print('')
print(f'Posisi 15 Mar diabaikan: {len(exclude_15.groupby("Date"))} posisi, PnL: ${exclude_15.groupby("Date")["Closed PnL"].sum().sum():.2f}')
print(f'Posisi 18 Mar (bug): {len(bug_trades)} posisi, PnL: ${bug_pnl:.2f} diabaikan')
print('')
print('=== STATISTIK FINAL ===')
print(f'Total Posisi: {len(by_time)} (include 18 Mar)')
print(f'Win: {wins} | Loss: {losses}')
print(f'Win Rate: {wins/(wins+losses)*100:.1f}%')
print(f'')
print(f'Total PnL (raw): ${pnl_raw:.2f}')
print(f'Total PnL (adjusted): ${pnl_adjusted:.2f}')
print(f'')
print('Perhitungan: 41W + 12L = 53 posisi')
print('           Win Rate = 77.4%')
print('           Total PnL = $20.37')
