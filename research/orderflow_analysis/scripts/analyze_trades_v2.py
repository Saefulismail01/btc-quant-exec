"""
Modul untuk analisis trade exit patterns dengan konteks leverage.
Mengidentifikasi Full TP vs Manual Close vs Partial Exit.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Tuple
import warnings
warnings.filterwarnings('ignore')


class TradeAnalyzer:
    """Analyzer untuk memproses dan mengkategorikan trades dengan leverage context."""
    
    def __init__(self, leverage: float = 15.0, tp_pct: float = 10.0, 
                 partial_threshold: float = 0.9):
        """
        Args:
            leverage: Leverage digunakan (default 15x)
            tp_pct: Target PnL % (default 10%)
            partial_threshold: Ratio untuk consider partial exit (default 0.9 = 90%)
        """
        self.leverage = leverage
        self.tp_pct = tp_pct
        self.partial_threshold = partial_threshold
        # Price movement needed for TP = tp_pct / leverage
        self.price_move_for_tp = tp_pct / leverage  # 0.67% for 15x
        
    def load_data(self, filepath: str) -> pd.DataFrame:
        """Load trade data dari CSV."""
        df = pd.read_csv(filepath)
        df['Date'] = pd.to_datetime(df['Date'])
        df['Closed PnL'] = pd.to_numeric(df['Closed PnL'], errors='coerce')
        df = df.sort_values('Date').reset_index(drop=True)
        return df
    
    def pair_trades(self, df: pd.DataFrame) -> pd.DataFrame:
        """Pair open trades dengan close trades menggunakan FIFO."""
        opens = df[df['Side'].str.contains('Open')].copy()
        closes = df[df['Side'].str.contains('Close')].copy()
        
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
            close_pnl = close['Closed PnL'] if pd.notna(close['Closed PnL']) else 0
            
            while remaining_size > 0.000001 and open_idx < len(opens_dir):
                open = opens_dir.iloc[open_idx]
                matched_size = min(remaining_size, open['Size'])
                
                entry_value = matched_size * open['Price']
                
                if entry_value > 0:
                    pnl_pct = (close_pnl * (matched_size / close['Size'])) / entry_value * 100
                else:
                    pnl_pct = 0
                
                # Calculate actual price movement %
                if direction == 'Long':
                    price_move_pct = (close['Price'] - open['Price']) / open['Price'] * 100
                else:  # Short
                    price_move_pct = (open['Price'] - close['Price']) / open['Price'] * 100
                
                matched.append({
                    'Direction': direction,
                    'Open_Time': open['Date'],
                    'Close_Time': close['Date'],
                    'Entry_Price': open['Price'],
                    'Exit_Price': close['Price'],
                    'Open_Size': open['Size'],
                    'Close_Size': matched_size,
                    'PnL': close_pnl * (matched_size / close['Size']),
                    'PnL_Pct': pnl_pct,
                    'Price_Move_Pct': price_move_pct,
                    'Hold_Time_Min': (close['Date'] - open['Date']).total_seconds() / 60,
                    'Close_Ratio': matched_size / open['Size'] if open['Size'] > 0 else 1,
                })
                
                remaining_size -= matched_size
                opens_dir.at[open_idx, 'Size'] -= matched_size
                
                if opens_dir.iloc[open_idx]['Size'] < 0.000001:
                    open_idx += 1
        
        return pd.DataFrame(matched)
    
    def categorize_exits(self, trades_df: pd.DataFrame) -> pd.DataFrame:
        """Kategorikan exit berdasarkan close ratio dan PnL."""
        trades = trades_df.copy()
        
        def categorize(row):
            close_ratio = row['Close_Ratio']
            pnl_pct = row['PnL_Pct']
            price_move = row['Price_Move_Pct']
            hold_time = row['Hold_Time_Min']
            
            # Full close (close_ratio > 90%)
            if close_ratio >= self.partial_threshold:
                # Check if this looks like TP hit
                # With leverage 15x, 10% PnL = 0.67% price move
                # If price moved >= 0.5% (close to TP) and profitable
                if price_move >= (self.price_move_for_tp * 0.7) and pnl_pct > 0 and hold_time < 240:
                    return 'TP_Hit'
                elif price_move >= (self.price_move_for_tp * 0.5) and pnl_pct > 0:
                    return 'Near_TP'
                else:
                    return 'Full_Manual'
            else:
                # Partial close
                return f'Partial_{int(close_ratio*100)}pct'
        
        trades['Exit_Type'] = trades.apply(categorize, axis=1)
        return trades
    
    def analyze_by_period(self, trades_df: pd.DataFrame) -> pd.DataFrame:
        """Analisis periode leverage berbeda."""
        trades = trades_df.copy()
        
        # Define periods
        def get_period(date):
            if date < pd.Timestamp('2026-03-11'):
                return 'Testing'
            elif date < pd.Timestamp('2026-03-16'):
                return '5usd_15x'
            elif date < pd.Timestamp('2026-03-18'):
                return '10usd_15x'
            elif date < pd.Timestamp('2026-03-18 23:59'):
                return 'Bug_Op'
            elif date < pd.Timestamp('2026-03-28'):
                return '5usd_15x_return'
            else:
                return '20usd_7x'
        
        trades['Period'] = trades['Open_Time'].apply(get_period)
        
        # Summary by period
        summary = trades.groupby('Period').agg({
            'PnL_Pct': ['count', 'mean', 'sum'],
            'Hold_Time_Min': ['mean', 'median'],
            'Price_Move_Pct': 'mean',
            'Exit_Type': lambda x: x.value_counts().to_dict()
        }).round(3)
        
        return trades, summary
    
    def summary_stats(self, trades_df: pd.DataFrame) -> Dict:
        """Generate summary statistics."""
        return {
            'total_trades': len(trades_df),
            'tp_hit_rate': (trades_df['Exit_Type'] == 'TP_Hit').mean() * 100,
            'near_tp_rate': (trades_df['Exit_Type'] == 'Near_TP').mean() * 100,
            'full_manual_rate': (trades_df['Exit_Type'] == 'Full_Manual').mean() * 100,
            'partial_exit_rate': (trades_df['Exit_Type'].str.contains('Partial')).mean() * 100,
            'avg_price_move': trades_df['Price_Move_Pct'].mean(),
            'avg_pnl': trades_df['PnL_Pct'].mean(),
            'avg_hold_time': trades_df['Hold_Time_Min'].mean(),
            'exit_type_dist': trades_df['Exit_Type'].value_counts().to_dict(),
        }


def print_report(stats: Dict, period_summary: pd.DataFrame):
    """Print formatted report."""
    print("=" * 70)
    print("TRADE EXIT ANALYSIS REPORT (With Leverage Context)")
    print("=" * 70)
    
    print(f"\n--- LEVERAGE CONFIG ---")
    print(f"Leverage: 15x (most periods)")
    print(f"TP Target: 10% PnL = 0.67% price move")
    
    print(f"\n--- OVERALL STATS ---")
    print(f"Total Trades: {stats['total_trades']:.0f}")
    print(f"TP Hit (auto): {stats['tp_hit_rate']:.1f}%")
    print(f"Near TP: {stats['near_tp_rate']:.1f}%")
    print(f"Full Manual Close: {stats['full_manual_rate']:.1f}%")
    print(f"Partial Exit: {stats['partial_exit_rate']:.1f}%")
    print(f"Avg Price Move: {stats['avg_price_move']:.3f}%")
    print(f"Avg PnL: {stats['avg_pnl']:.3f}%")
    print(f"Avg Hold Time: {stats['avg_hold_time']:.1f} min")
    
    print(f"\n--- EXIT TYPE BREAKDOWN ---")
    for exit_type, count in stats['exit_type_dist'].items():
        pct = count / stats['total_trades'] * 100
        print(f"  {exit_type}: {count} ({pct:.1f}%)")
    
    print(f"\n--- BY PERIOD ---")
    print(period_summary.to_string())
    
    print("\n" + "=" * 70)


if __name__ == '__main__':
    # Paths
    data_path = r'C:\Users\ThinkPad\Documents\Windsurf\btc-scalping-execution_layer\docs\reports\data\trade_export_2026-03-29.csv'
    output_path = r'C:\Users\ThinkPad\Documents\Windsurf\btc-scalping-execution_layer\research\orderflow_analysis\data\processed_trades_v2.csv'
    
    # Initialize analyzer dengan 15x leverage
    analyzer = TradeAnalyzer(leverage=15.0, tp_pct=10.0)
    
    print("Loading data...")
    df = analyzer.load_data(data_path)
    
    # Filter out March 15 and March 18
    df = df[~df['Date'].dt.date.isin([pd.Timestamp('2026-03-15').date(), pd.Timestamp('2026-03-18').date()])]
    print(f"Filtered data: {len(df)} rows (excluded Mar 15 & 18)")
    
    print("Pairing trades...")
    trades = analyzer.pair_trades(df)
    
    print("Categorizing exits...")
    trades = analyzer.categorize_exits(trades)
    
    print("Analyzing by period...")
    trades_with_period, period_summary = analyzer.analyze_by_period(trades)
    
    print("Generating stats...")
    stats = analyzer.summary_stats(trades_with_period)
    
    # Print report
    print_report(stats, period_summary)
    
    # Save
    trades_with_period.to_csv(output_path, index=False)
    print(f"\nProcessed trades saved to: {output_path}")
