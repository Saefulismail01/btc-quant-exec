"""
Modul untuk analisis trade exit patterns.
Mengidentifikasi kapan early exit lebih optimal daripada hold ke TP.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Tuple
import warnings
warnings.filterwarnings('ignore')


class TradeAnalyzer:
    """Analyzer untuk memproses dan mengkategorikan trades."""
    
    def __init__(self, tp_threshold: float = 10.0, manual_threshold: float = 5.0):
        self.tp_threshold = tp_threshold
        self.manual_threshold = manual_threshold
        
    def load_data(self, filepath: str) -> pd.DataFrame:
        """Load trade data dari CSV."""
        df = pd.read_csv(filepath)
        df['Date'] = pd.to_datetime(df['Date'])
        # Convert Closed PnL to numeric, replacing '-' with NaN
        df['Closed PnL'] = pd.to_numeric(df['Closed PnL'], errors='coerce')
        df = df.sort_values('Date').reset_index(drop=True)
        return df
    
    def pair_trades(self, df: pd.DataFrame) -> pd.DataFrame:
        """Pair open trades dengan close trades menggunakan FIFO."""
        # Separate opens and closes
        opens = df[df['Side'].str.contains('Open')].copy()
        closes = df[df['Side'].str.contains('Close')].copy()
        
        # Extract direction
        opens['Direction'] = opens['Side'].str.replace('Open ', '')
        closes['Direction'] = closes['Side'].str.replace('Close ', '')
        
        # Aggregate by direction and timestamp
        open_agg = opens.groupby(['Direction', 'Date']).agg({
            'Trade Value': 'sum',
            'Size': 'sum',
            'Price': 'mean'
        }).reset_index()
        
        close_agg = closes.groupby(['Direction', 'Date']).agg({
            'Trade Value': 'sum',
            'Size': 'sum',
            'Price': 'mean',
            'Closed PnL': 'sum'
        }).reset_index()
        
        # Match by direction
        long_trades = self._match_fifo(open_agg, close_agg, 'Long')
        short_trades = self._match_fifo(open_agg, close_agg, 'Short')
        
        all_trades = pd.concat([long_trades, short_trades], ignore_index=True)
        all_trades = all_trades[all_trades['Hold_Time_Min'] > 0]
        
        return all_trades
    
    def _match_fifo(self, opens_df: pd.DataFrame, closes_df: pd.DataFrame, 
                   direction: str) -> pd.DataFrame:
        """FIFO matching untuk satu direction."""
        opens_dir = opens_df[opens_df['Direction'] == direction].sort_values('Date').reset_index(drop=True)
        closes_dir = closes_df[closes_df['Direction'] == direction].sort_values('Date').reset_index(drop=True)
        
        matched = []
        open_idx = 0
        
        for _, close in closes_dir.iterrows():
            remaining_size = close['Size']
            close_pnl = close['Closed PnL']
            
            while remaining_size > 0.000001 and open_idx < len(opens_dir):
                open = opens_dir.iloc[open_idx]
                matched_size = min(remaining_size, open['Size'])
                
                entry_value = matched_size * open['Price']
                
                if entry_value > 0:
                    pnl_pct = (close_pnl * (matched_size / close['Size'])) / entry_value * 100
                else:
                    pnl_pct = 0
                
                matched.append({
                    'Direction': direction,
                    'Open_Time': open['Date'],
                    'Close_Time': close['Date'],
                    'Entry_Price': open['Price'],
                    'Exit_Price': close['Price'],
                    'Size': matched_size,
                    'PnL': close_pnl * (matched_size / close['Size']),
                    'PnL_Pct': pnl_pct,
                    'Hold_Time_Min': (close['Date'] - open['Date']).total_seconds() / 60,
                })
                
                remaining_size -= matched_size
                opens_dir.at[open_idx, 'Size'] -= matched_size
                
                if opens_dir.iloc[open_idx]['Size'] < 0.000001:
                    open_idx += 1
        
        return pd.DataFrame(matched)
    
    def categorize_exits(self, trades_df: pd.DataFrame) -> pd.DataFrame:
        """Kategorikan exit berdasarkan PnL."""
        trades = trades_df.copy()
        
        def categorize(row):
            pnl = row['PnL_Pct']
            if pd.isna(pnl):
                return 'Unknown'
            elif pnl >= self.tp_threshold:
                return 'TP_Hit'
            elif pnl <= -self.manual_threshold:
                return 'SL_Hit'
            elif abs(pnl) < self.manual_threshold:
                return 'Early_Exit'
            else:
                return 'Runner'
        
        trades['Exit_Type'] = trades.apply(categorize, axis=1)
        return trades
    
    def analyze_early_exits(self, trades_df: pd.DataFrame) -> Dict:
        """Analisis kualitas early exits."""
        early = trades_df[trades_df['Exit_Type'] == 'Early_Exit'].copy()
        
        if len(early) == 0:
            return {'error': 'No early exits found'}
        
        # Calculate opportunity cost
        early['Opportunity_Cost'] = self.tp_threshold - early['PnL_Pct']
        early['Saved_Loss'] = -self.manual_threshold - early['PnL_Pct']
        
        profitable = early[early['PnL_Pct'] > 0]
        losing = early[early['PnL_Pct'] <= 0]
        
        return {
            'count': len(early),
            'profitable_count': len(profitable),
            'losing_count': len(losing),
            'profitable_pct': (len(profitable) / len(early) * 100),
            'avg_pnl': early['PnL_Pct'].mean(),
            'median_hold_time': early['Hold_Time_Min'].median(),
            'profitable_avg_pnl': profitable['PnL_Pct'].mean() if len(profitable) > 0 else 0,
            'profitable_opportunity_cost': profitable['Opportunity_Cost'].mean() if len(profitable) > 0 else 0,
            'losing_avg_pnl': losing['PnL_Pct'].mean() if len(losing) > 0 else 0,
            'losing_saved_loss': losing['Saved_Loss'].mean() if len(losing) > 0 else 0,
        }
    
    def time_analysis(self, trades_df: pd.DataFrame) -> pd.DataFrame:
        """Analisis performance berdasarkan hold time."""
        trades = trades_df.copy()
        trades['Hold_Time_Bin'] = pd.cut(
            trades['Hold_Time_Min'],
            bins=[0, 30, 60, 120, 240, 480, 1440],
            labels=['0-30m', '30-60m', '1-2h', '2-4h', '4-8h', '8h+']
        )
        
        analysis = trades.groupby('Hold_Time_Bin').agg({
            'PnL_Pct': ['count', 'mean', 'sum'],
            'Exit_Type': lambda x: (x == 'TP_Hit').sum() / len(x) * 100 if len(x) > 0 else 0
        }).round(2)
        
        analysis.columns = ['Count', 'Avg_PnL', 'Total_PnL', 'TP_Hit_Rate']
        return analysis
    
    def summary_stats(self, trades_df: pd.DataFrame) -> Dict:
        """Generate summary statistics."""
        return {
            'total_trades': len(trades_df),
            'tp_hit_rate': (trades_df['Exit_Type'] == 'TP_Hit').mean() * 100,
            'early_exit_rate': (trades_df['Exit_Type'] == 'Early_Exit').mean() * 100,
            'sl_hit_rate': (trades_df['Exit_Type'] == 'SL_Hit').mean() * 100,
            'runner_rate': (trades_df['Exit_Type'] == 'Runner').mean() * 100,
            'avg_pnl_by_type': trades_df.groupby('Exit_Type')['PnL_Pct'].mean().to_dict(),
            'total_pnl_by_type': trades_df.groupby('Exit_Type')['PnL_Pct'].sum().to_dict(),
        }


def print_report(stats: Dict, early_analysis: Dict, time_analysis: pd.DataFrame):
    """Print formatted report."""
    print("=" * 60)
    print("TRADE EXIT ANALYSIS REPORT")
    print("=" * 60)
    
    print(f"\n--- OVERALL STATS ---")
    print(f"Total Trades: {stats['total_trades']:.0f}")
    print(f"TP Hit Rate: {stats['tp_hit_rate']:.1f}%")
    print(f"Early Exit Rate: {stats['early_exit_rate']:.1f}%")
    print(f"SL Hit Rate: {stats['sl_hit_rate']:.1f}%")
    print(f"Runner Rate: {stats['runner_rate']:.1f}%")
    
    print(f"\n--- PnL BY EXIT TYPE ---")
    for exit_type, avg_pnl in stats['avg_pnl_by_type'].items():
        total_pnl = stats['total_pnl_by_type'].get(exit_type, 0)
        print(f"{exit_type}: Avg={avg_pnl:.3f}%, Total={total_pnl:.3f}%")
    
    if 'error' not in early_analysis:
        print(f"\n--- EARLY EXIT ANALYSIS ---")
        print(f"Count: {early_analysis['count']}")
        print(f"Profitable: {early_analysis['profitable_count']} ({early_analysis['profitable_pct']:.1f}%)")
        print(f"Avg PnL: {early_analysis['avg_pnl']:.3f}%")
        print(f"Median Hold Time: {early_analysis['median_hold_time']:.1f} min")
        print(f"Opportunity Cost (profitable): {early_analysis['profitable_opportunity_cost']:.3f}%")
        print(f"Saved Loss (losing): {early_analysis['losing_saved_loss']:.3f}%")
    
    print(f"\n--- TIME ANALYSIS ---")
    print(time_analysis.to_string())
    
    print("\n" + "=" * 60)
    print("ORDERFLOW HYPOTHESES TO TEST:")
    print("=" * 60)
    print("1. MOMENTUM DECAY: Delta divergence detection")
    print("2. TIME DECAY: Exit rules based on hold time + PnL threshold")
    print("3. VOLUME CLIMAX: Volume spike + reversal pattern")
    print("4. LIQUIDITY SWEEP: Wick rejection at key levels")
    print("=" * 60)


if __name__ == '__main__':
    # Paths
    data_path = r'C:\Users\ThinkPad\Documents\Windsurf\btc-scalping-execution_layer\docs\reports\data\trade_export_2026-03-29.csv'
    output_path = r'C:\Users\ThinkPad\Documents\Windsurf\btc-scalping-execution_layer\research\orderflow_analysis\data\processed_trades.csv'
    
    # Initialize analyzer
    analyzer = TradeAnalyzer(tp_threshold=10.0, manual_threshold=5.0)
    
    # Run analysis
    print("Loading data...")
    df = analyzer.load_data(data_path)
    
    print("Pairing trades...")
    trades = analyzer.pair_trades(df)
    
    print("Categorizing exits...")
    trades = analyzer.categorize_exits(trades)
    
    print("Analyzing early exits...")
    early_analysis = analyzer.analyze_early_exits(trades)
    
    print("Time analysis...")
    time_analysis_df = analyzer.time_analysis(trades)
    
    print("Generating stats...")
    stats = analyzer.summary_stats(trades)
    
    # Print report
    print_report(stats, early_analysis, time_analysis_df)
    
    # Save results
    trades.to_csv(output_path, index=False)
    print(f"\nProcessed trades saved to: {output_path}")
