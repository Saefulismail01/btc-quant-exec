import re
import os

def analyze_losses(html_path):
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Find all "LIVE TRADE CLOSED — SL" messages
    # Each message is in a div with text
    loss_blocks = re.findall(r'<div class="text">(.*?)LIVE TRADE CLOSED — SL.*?</div>', content, re.DOTALL)
    
    # Actually it's easier to find the SL messages and then look BACK for the signal that opened it
    # Or find all messages and process them in order
    
    messages = re.findall(r'<div class="message.*?id="(message\d+)".*?<div class="pull_right date details" title="(.*?)">.*?<div class="text">(.*?)</div>', content, re.DOTALL)
    
    current_signal = None
    loss_analysis = []
    
    for mid, mdate, mtext in messages:
        mtext = mtext.replace('<br>', '\n').replace('<strong>', '').replace('</strong>', '')
        
        if "SIGNAL ALERT" in mtext:
            # Parse signal details
            sig = {
                'id': mid,
                'date': mdate,
                'action': 'LONG' if 'LONG' in mtext else 'SHORT',
                'conviction': 0.0,
                'regime': '',
                'trend': '',
                'rationale': ''
            }
            conv = re.search(r'CONVICTION\s*:\s*([\d.]+)%', mtext)
            if conv: sig['conviction'] = float(conv.group(1))
            
            reg = re.search(r'REGIME\s*:\s*(.*?)\n', mtext)
            if reg: sig['regime'] = reg.group(1).strip()
            
            trend = re.search(r'TREND\s*:\s*(.*?)\n', mtext)
            if trend: sig['trend'] = trend.group(1).strip()
            
            rat = re.search(r'RATIONALE\s*:\s*(.*?)━━━━━━━━', mtext, re.DOTALL)
            if rat: sig['rationale'] = rat.group(1).strip()
            
            current_signal = sig
            
        elif "LIVE TRADE CLOSED — SL" in mtext:
            if current_signal:
                loss_info = {
                    'signal': current_signal,
                    'close_date': mdate,
                    'pnl': re.search(r'PnL\s*:\s*(.*?)\n', mtext).group(1).strip() if re.search(r'PnL\s*:\s*(.*?)\n', mtext) else "N/A"
                }
                loss_analysis.append(loss_info)
                
    return loss_analysis

if __name__ == "__main__":
    html_file = r"C:\Users\ThinkPad\Downloads\Telegram Desktop\ChatExport_2026-04-19\messages.html"
    losses = analyze_losses(html_file)
    
    print(f"Ditemukan {len(losses)} kejadian SL (Loss) dengan data signal penyerta.\n")
    
    # Pattern counts
    trend_counts = {}
    conviction_sum = 0
    
    for i, loss in enumerate(losses):
        sig = loss['signal']
        trend = sig['trend']
        trend_counts[trend] = trend_counts.get(trend, 0) + 1
        conviction_sum += sig['conviction']
        
        if i < 10: # Print first 10 for sample inspection
            print(f"[{i+1}] Action: {sig['action']} | PnL: {loss['pnl']}")
            print(f"    Trend: {sig['trend']} | Conviction: {sig['conviction']}%")
            print(f"    Rationale: {sig['rationale'][:100]}...")
            print("-" * 30)
            
    print("\n=== RINGKASAN DATA LOSS ===")
    print(f"Average Conviction on Losses: {conviction_sum/len(losses):.2f}%" if losses else "N/A")
    print("Trend Breakdowns on Losses:")
    for t, count in trend_counts.items():
        print(f" - {t}: {count} kali ({count/len(losses)*100:.1f}%)")
