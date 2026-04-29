import csv

def analyze_csv(file_path):
    with open(file_path, 'r') as f:
        reader = csv.DictReader(f)
        trades = list(reader)
        
    closes = [t for t in trades if 'Close' in t['Side'] and t['Closed PnL'] != '-']
    for t in closes:
        t['PnL'] = float(t['Closed PnL'])
        
    wins = [t for t in closes if t['PnL'] > 0]
    losses = [t for t in closes if t['PnL'] < 0]
    
    total = len(closes)
    win_count = len(wins)
    loss_count = len(losses)
    total_pnl = sum(t['PnL'] for t in closes)
    
    print(f"Total Closed Trades: {total}")
    print(f"Wins: {win_count} ({win_count/total*100:.1f}%)")
    print(f"Losses: {loss_count} ({loss_count/total*100:.1f}%)")
    print(f"Total PnL: {total_pnl:.2f}")
    
    # By Side
    for side in ['Close Long', 'Close Short']:
        side_trades = [t for t in closes if t['Side'] == side]
        if not side_trades: continue
        s_wins = [t for t in side_trades if t['PnL'] > 0]
        s_loss = [t for t in side_trades if t['PnL'] < 0]
        swr = len(s_wins)/len(side_trades)*100
        spnl = sum(t['PnL'] for t in side_trades)
        print(f"\n--- {side} ---")
        print(f"Trades: {len(side_trades)}")
        print(f"Win Rate: {swr:.1f}%")
        print(f"PnL: {spnl:.2f}")

if __name__ == "__main__":
    analyze_csv('data/exports/lighter-trade-export-2026-04-17T07_11_42.517Z-UTC.csv')
