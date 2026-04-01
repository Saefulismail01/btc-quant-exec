"""
Script runner untuk full analysis pipeline.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from analyze_trades import TradeAnalyzer, print_report
from visualize import plot_exit_analysis, plot_time_analysis
import pandas as pd


def main():
    # Configuration
    DATA_PATH = r'C:\Users\ThinkPad\Documents\Windsurf\btc-scalping-execution_layer\docs\reports\data\trade_export_2026-03-29.csv'
    OUTPUT_PATH = r'C:\Users\ThinkPad\Documents\Windsurf\btc-scalping-execution_layer\research\orderflow_analysis\data\processed_trades.csv'
    
    TP_THRESHOLD = 10.0
    MANUAL_THRESHOLD = 5.0
    
    print("=" * 60)
    print("TRADE EXIT ANALYSIS PIPELINE")
    print("=" * 60)
    
    # Step 1: Initialize analyzer
    print("\n[1/4] Initializing analyzer...")
    analyzer = TradeAnalyzer(tp_threshold=TP_THRESHOLD, manual_threshold=MANUAL_THRESHOLD)
    
    # Step 2: Load and process data
    print(f"[2/4] Loading data from {DATA_PATH}...")
    df = analyzer.load_data(DATA_PATH)
    print(f"      Loaded {len(df)} rows")
    
    print("      Pairing open/close trades...")
    trades = analyzer.pair_trades(df)
    print(f"      Matched {len(trades)} complete trades")
    
    print("      Categorizing exits...")
    trades = analyzer.categorize_exits(trades)
    
    # Step 3: Analysis
    print("\n[3/4] Running analysis...")
    early_analysis = analyzer.analyze_early_exits(trades)
    time_analysis_df = analyzer.time_analysis(trades)
    stats = analyzer.summary_stats(trades)
    
    # Step 4: Report and save
    print("\n[4/4] Generating report...")
    print_report(stats, early_analysis, time_analysis_df)
    
    # Save data
    trades.to_csv(OUTPUT_PATH, index=False)
    print(f"\n      Saved processed trades to: {OUTPUT_PATH}")
    
    # Generate visualizations
    print("\n      Generating visualizations...")
    plot_exit_analysis(trades)
    plot_time_analysis(time_analysis_df)
    
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)


if __name__ == '__main__':
    main()
