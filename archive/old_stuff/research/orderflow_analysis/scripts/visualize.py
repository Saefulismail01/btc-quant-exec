"""
Visualization utilities untuk trade analysis.
"""

import os
import matplotlib.pyplot as plt
import pandas as pd
from typing import Dict

RESULTS_DIR = r'C:\Users\ThinkPad\Documents\Windsurf\btc-scalping-execution_layer\research\orderflow_analysis\results'


def plot_exit_analysis(trades_df: pd.DataFrame, save_path: str = None):
    """Generate 4-panel visualization dari exit analysis."""
    if save_path is None:
        save_path = os.path.join(RESULTS_DIR, 'exit_analysis.png')
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    colors = {'TP_Hit': 'green', 'Early_Exit': 'orange', 'SL_Hit': 'red', 'Runner': 'blue'}
    tp_threshold = 10.0
    manual_threshold = 5.0
    
    # 1. PnL Distribution
    ax1 = axes[0, 0]
    for exit_type in trades_df['Exit_Type'].unique():
        data = trades_df[trades_df['Exit_Type'] == exit_type]['PnL_Pct']
        ax1.hist(data, bins=20, alpha=0.6, label=exit_type)
    ax1.axvline(tp_threshold, color='green', linestyle='--', label=f'TP ({tp_threshold}%)')
    ax1.axvline(-manual_threshold, color='red', linestyle='--', label=f'SL (-{manual_threshold}%)')
    ax1.set_xlabel('PnL %')
    ax1.set_ylabel('Count')
    ax1.set_title('PnL Distribution by Exit Type')
    ax1.legend()
    
    # 2. Hold Time vs PnL
    ax2 = axes[0, 1]
    for exit_type in trades_df['Exit_Type'].unique():
        data = trades_df[trades_df['Exit_Type'] == exit_type]
        ax2.scatter(data['Hold_Time_Min'], data['PnL_Pct'],
                   c=colors.get(exit_type, 'gray'), alpha=0.6, label=exit_type, s=30)
    ax2.set_xlabel('Hold Time (minutes)')
    ax2.set_ylabel('PnL %')
    ax2.set_title('Hold Time vs PnL')
    ax2.legend()
    
    # 3. Exit Type Count
    ax3 = axes[1, 0]
    exit_counts = trades_df['Exit_Type'].value_counts()
    ax3.bar(exit_counts.index, exit_counts.values,
           color=[colors.get(x, 'gray') for x in exit_counts.index])
    ax3.set_ylabel('Count')
    ax3.set_title('Exit Type Count')
    
    # 4. Cumulative PnL
    ax4 = axes[1, 1]
    cumulative = trades_df.groupby('Exit_Type')['PnL_Pct'].sum().sort_values(ascending=False)
    ax4.barh(cumulative.index, cumulative.values,
            color=[colors.get(x, 'gray') for x in cumulative.index])
    ax4.set_xlabel('Total PnL %')
    ax4.set_title('Cumulative PnL by Exit Type')
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()
    print(f"Exit analysis chart saved to: {save_path}")


def plot_time_analysis(time_df: pd.DataFrame, save_path: str = None):
    """Generate time-based analysis charts."""
    if save_path is None:
        save_path = os.path.join(RESULTS_DIR, 'time_analysis.png')
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
    
    # Avg PnL by time
    ax1.bar(time_df.index.astype(str), time_df['Avg_PnL'], color='steelblue')
    ax1.set_ylabel('Avg PnL %')
    ax1.set_title('Average PnL by Hold Time')
    ax1.tick_params(axis='x', rotation=45)
    
    # TP Hit Rate by time
    ax2.bar(time_df.index.astype(str), time_df['TP_Hit_Rate'], color='green', alpha=0.7)
    ax2.set_ylabel('TP Hit Rate %')
    ax2.set_title('TP Hit Rate by Hold Time')
    ax2.tick_params(axis='x', rotation=45)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close()
    print(f"Time analysis chart saved to: {save_path}")


if __name__ == '__main__':
    # Load processed data dan generate charts
    import pandas as pd
    
    trades = pd.read_csv('../data/processed_trades.csv')
    
    print("Generating exit analysis chart...")
    plot_exit_analysis(trades)
    
    print("Done!")
