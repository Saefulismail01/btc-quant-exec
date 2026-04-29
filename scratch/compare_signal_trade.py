import pandas as pd
import re
from bs4 import BeautifulSoup
import os

def parse_signals(html_path):
    signals = []
    if not os.path.exists(html_path):
        return signals
        
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
        
    messages = soup.find_all('div', class_='message')
    for msg in messages:
        text_div = msg.find('div', class_='text')
        if not text_div:
            continue
            
        text = text_div.get_text(separator=' ')
        
        # Look for SIGNAL ALERT
        if "SIGNAL ALERT" in text:
            signal_data = {}
            # Extract date from message
            date_div = msg.find('div', class_='date')
            msg_date = date_div.get('title') if date_div else ""
            
            # Extract Candle CL
            candle_match = re.search(r'CANDLE CL\s*:\s*([\d\-\s:]+)', text)
            signal_data['candle_cl'] = candle_match.group(1).strip() if candle_match else ""
            
            # Extract Action
            action_match = re.search(r'PRIMARY ACTION\s*:\s*(\w+)', text)
            signal_data['action'] = action_match.group(1).strip() if action_match else ""
            
            # Extract Entry Zone
            entry_match = re.search(r'ENTRY ZONE\s*:\s*([\d,\-\s.]+)', text)
            signal_data['entry_zone'] = entry_match.group(1).strip() if entry_match else ""
            
            # Extract SL and TP
            sl_match = re.search(r'STOP LOSS\s*:\s*([\d,.]+)', text)
            signal_data['sl'] = sl_match.group(1).strip() if sl_match else ""
            
            tp_match = re.search(r'TARGET TP\s*:\s*([\d,.]+)', text)
            signal_data['tp'] = tp_match.group(1).strip() if tp_match else ""
            
            # Extract Conviction
            conv_match = re.search(r'CONVICTION\s*:\s*([\d.]+)%', text)
            signal_data['conviction'] = float(conv_match.group(1)) if conv_match else 0.0
            
            # Extract Rationale
            rationale_match = re.search(r'RATIONALE\s*:\s*(.*?)━━━━━━━━', text, re.DOTALL)
            signal_data['rationale'] = rationale_match.group(1).strip() if rationale_match else ""
            
            signals.append(signal_data)
            
        # Look for NO SIGNAL / SUSPENDED
        elif "NO SIGNAL" in text or "MONITORING" in text:
            # We can skip these for now or log them for "missed opportunities"
            pass
            
    return signals

def analyze_matching(signals, trade_csv):
    df = pd.read_csv(trade_csv)
    df = df[df['Side'].str.contains('Open')].copy()
    df['Date'] = pd.to_datetime(df['Date'])
    
    # Map signals to trades
    # Signals use UTC, trades use the same? Let's assume they match up roughly in time.
    matches = []
    
    # Simple matching logic: find trade close to signal time and same direction
    for sig in signals:
        if not sig['candle_cl'] or not sig['action']:
            continue
            
        sig_time = pd.to_datetime(sig['candle_cl'])
        sig_action = sig['action'].upper()
        
        # Find trades within 1 hour of signal candle close
        mask = (df['Date'] >= sig_time) & (df['Date'] <= sig_time + pd.Timedelta(hours=4))
        potential_trades = df[mask]
        
        for _, trade in potential_trades.iterrows():
            trade_action = "LONG" if "Long" in trade['Side'] else "SHORT"
            if trade_action == sig_action:
                # Match found. Now look for the corresponding Close trade for PnL
                # Usually the close trade comes after the open trade.
                # In the CSV, it looks like rows are ordered by time (descending or ascending?)
                # Looking at view_file, they seem to be grouped or mixed.
                pass # Logic to find PnL is better handled by analyzing the CSV fully
                
    # Direct analysis of CSV is better for win rate
    closes = pd.read_csv(trade_csv)
    closes = closes[closes['Side'].str.contains('Close')].copy()
    closes = closes[closes['Closed PnL'] != '-'].copy()
    closes['Closed PnL'] = pd.to_numeric(closes['Closed PnL'])
    
    wins = closes[closes['Closed PnL'] > 0]
    losses = closes[closes['Closed PnL'] < 0]
    
    print(f"Total Closed Trades: {len(closes)}")
    print(f"Wins: {len(wins)} ({len(wins)/len(closes)*100:.1f}%)")
    print(f"Losses: {len(losses)} ({len(losses)/len(closes)*100:.1f}%)")
    print(f"Total PnL: {closes['Closed PnL'].sum():.2f}")
    
    # Analyze win/loss patterns by side
    for side in ['Close Long', 'Close Short']:
        side_data = closes[closes['Side'] == side]
        if len(side_data) == 0: continue
        s_wins = side_data[side_data['Closed PnL'] > 0]
        s_losses = side_data[side_data['Closed PnL'] < 0]
        print(f"\n--- {side} ---")
        print(f"Win Rate: {len(s_wins)/len(side_data)*100:.1f}%")
        print(f"Avg PnL: {side_data['Closed PnL'].mean():.2f}")

if __name__ == "__main__":
    html_file = r"C:\Users\ThinkPad\Downloads\Telegram Desktop\ChatExport_2026-04-19\messages.html"
    csv_file = r"c:\Users\ThinkPad\Documents\Windsurf\btc-scalping-execution_layer\data\exports\lighter-trade-export-2026-04-17T07_11_42.517Z-UTC.csv"
    
    # signals = parse_signals(html_file)
    # print(f"Parsed {len(signals)} signals from Telegram.")
    
    analyze_matching([], csv_file)
