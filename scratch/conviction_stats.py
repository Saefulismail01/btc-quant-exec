import re
from datetime import datetime

def analyze_conviction_stats(html_path, conviction_threshold=15.0):
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Regex to find all messages with their text and timestamp
    messages = re.findall(r'<div class="message.*?id="(message\d+)".*?<div class="pull_right date details" title="(.*?)">.*?<div class="text">(.*?)</div>', content, re.DOTALL)
    
    signals = {} # ID -> details
    current_signal_id = None
    
    # First pass: map trade IDs (from open/close messages) to their conviction scores
    # Also track which signal ID belongs to which trade ID
    
    trade_id_to_conviction = {}
    
    for mid, mdate, mtext in messages:
        mtext_clean = mtext.replace('<br>', '\n').replace('<strong>', '').replace('</strong>', '')
        
        # 1. Catch SIGNAL ALERT to get conviction
        if "SIGNAL ALERT" in mtext_clean:
            conv_match = re.search(r'CONVICTION\s*:\s*([\d.]+)%', mtext_clean)
            if conv_match:
                # We need to correlate this signal with the "LIVE TRADE OPENED" that follows it
                # Usually they are sent together or close
                current_conviction = float(conv_match.group(1))
            else:
                current_conviction = 0.0
                
        # 2. Catch LIVE TRADE OPENED to link conviction to trade ID
        if "LIVE TRADE OPENED" in mtext_clean:
            tid_match = re.search(r'ID:\s*([a-f0-9]+)', mtext_clean)
            if tid_match:
                tid = tid_match.group(1)
                trade_id_to_conviction[tid] = current_conviction

    # Second pass: count wins/losses for closed trades based on their trade ID conviction
    stats = {
        'below_threshold': {'win': 0, 'loss': 0, 'pnl_sum': 0.0, 'trades': []},
        'above_threshold': {'win': 0, 'loss': 0, 'pnl_sum': 0.0, 'trades': []}
    }
    
    # To avoid double counting (sometimes history commands show the same thing)
    processed_closed_ids = set()

    for mid, mdate, mtext in messages:
        mtext_clean = mtext.replace('<br>', '\n').replace('<strong>', '').replace('</strong>', '')
        
        if "LIVE TRADE CLOSED" in mtext_clean:
            tid_match = re.search(r'ID:\s*([a-f0-9]+)', mtext_clean)
            if not tid_match: continue
            
            tid = tid_match.group(1)
            if tid in processed_closed_ids: continue
            processed_closed_ids.add(tid)
            
            conv = trade_id_to_conviction.get(tid, 0.0)
            
            is_win = "— TP" in mtext_clean or "PnL    : +" in mtext_clean
            is_loss = "— SL" in mtext_clean or "PnL    : -" in mtext_clean
            
            pnl_match = re.search(r'PnL\s*:\s*([+-]?[\d.]+)', mtext_clean)
            pnl_val = float(pnl_match.group(1)) if pnl_match else 0.0
            
            key = 'below_threshold' if conv < conviction_threshold else 'above_threshold'
            
            if is_win: stats[key]['win'] += 1
            elif is_loss: stats[key]['loss'] += 1
            
            stats[key]['pnl_sum'] += pnl_val
            stats[key]['trades'].append({'id': tid, 'conv': conv, 'pnl': pnl_val, 'win': is_win})

    return stats, conviction_threshold

if __name__ == "__main__":
    html_file = r"C:\Users\ThinkPad\Downloads\Telegram Desktop\ChatExport_2026-04-19\messages.html"
    stats, threshold = analyze_conviction_stats(html_file)
    
    low = stats['below_threshold']
    high = stats['above_threshold']
    
    print(f"=== ANALISIS CONVICTION (Threshold {threshold}%) ===")
    print(f"\n[Low Conviction < {threshold}%]")
    print(f"Total Trades: {low['win'] + low['loss']}")
    print(f"Wins  : {low['win']}")
    print(f"Losses: {low['loss']}")
    wr = (low['win'] / (low['win'] + low['loss']) * 100) if (low['win'] + low['loss']) > 0 else 0
    print(f"Win Rate: {wr:.1f}%")
    print(f"Total PnL: {low['pnl_sum']:.2f} USDT")

    print(f"\n[High Conviction >= {threshold}%]")
    print(f"Total Trades: {high['win'] + high['loss']}")
    print(f"Wins  : {high['win']}")
    print(f"Losses: {high['loss']}")
    wr_h = (high['win'] / (high['win'] + high['loss']) * 100) if (high['win'] + high['loss']) > 0 else 0
    print(f"Win Rate: {wr_h:.1f}%")
    print(f"Total PnL: {high['pnl_sum']:.2f} USDT")
