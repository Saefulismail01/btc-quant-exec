import os
import sys
import time
import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
from datetime import datetime

# Add backend to path
_BACKEND_DIR = str(Path(__file__).resolve().parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# Import Engines
from engines.layer1_hmm import MarketRegimeModel
from engines.layer1_bcd import BayesianChangepointModel
from data_engine import get_latest_market_data

def run_long_comparison():
    print("\n" + "="*70)
    print(" BTC-QUANT: LONG TIMEFRAME LAYER 1 ENGINE COMPARISON (HMM VS BCD)")
    print("="*70 + "\n")

    # 1. Fetch Data
    print("1. Fetching 1 year of historical data from DuckDB...")
    from data_engine import DuckDBManager, DB_PATH
    db = DuckDBManager(DB_PATH)
    df = db.get_latest_ohlcv(limit=8000)
    
    if df is None or len(df) < 500:
        print(" [!] Insufficient data for comparison. Need at least 500 rows.")
        return

    print(f"    Loaded {len(df)} candles.")
    start_ts = df.index[0]
    end_ts = df.index[-1]
    print(f"    Timeframe: {start_ts} to {end_ts}")

    # 2. Initialize Models
    hmm_model = MarketRegimeModel()
    bcd_model = BayesianChangepointModel()

    # 3. Global Training
    print("\n2. Training Engines (Global Mode)...")
    
    t0 = time.time()
    hmm_success = hmm_model.train_global(df)
    hmm_train_time = time.time() - t0
    
    t0 = time.time()
    bcd_success = bcd_model.train_global(df)
    bcd_train_time = time.time() - t0

    print(f"    HMM Training: {'SUCCESS' if hmm_success else 'FAILED'} ({hmm_train_time:.2f}s)")
    print(f"    BCD Training: {'SUCCESS' if bcd_success else 'FAILED'} ({bcd_train_time:.2f}s)")

    if not hmm_success or not bcd_success:
        print(" [!] One or more engines failed to train.")
        return

    # 4. Comparative Inference
    print("\n3. Running Comparative Inference...")
    
    hmm_states, hmm_idx = hmm_model.get_state_sequence_raw(df)
    bcd_states, bcd_idx = bcd_model.get_state_sequence_raw(df)

    common_idx = hmm_idx.intersection(bcd_idx)
    df_compare = df.loc[common_idx].copy()
    
    df_compare['hmm_raw_state'] = hmm_states[np.searchsorted(hmm_idx, common_idx)]
    df_compare['bcd_raw_state'] = bcd_states[np.searchsorted(bcd_idx, common_idx)]
    
    df_compare['hmm_label'] = df_compare['hmm_raw_state'].map(hmm_model.state_map)
    df_compare['bcd_label'] = df_compare['bcd_raw_state'].map(bcd_model.state_map)

    # 5. Metric Extraction
    def count_switches(labels):
        return (labels != labels.shift(1)).sum() - 1

    hmm_switches = count_switches(df_compare['hmm_label'])
    bcd_switches = count_switches(df_compare['bcd_label'])
    
    # Calculate regime distribution
    hmm_dist = df_compare['hmm_label'].value_counts(normalize=True) * 100
    bcd_dist = df_compare['bcd_label'].value_counts(normalize=True) * 100

    print(f"\n4. Stability & Persistence Metrics:")
    print(f"    {'Metric':30s} | {'HMM (GMM)':15s} | {'BCD (Bayesian)':15s}")
    print(f"    {'-'*30} | {'-'*15} | {'-'*15}")
    print(f"    {'Total Regime Switches':30s} | {hmm_switches:<15d} | {bcd_switches:<15d}")
    print(f"    {'Avg Persistence (candles)':30s} | {len(df_compare)/(hmm_switches+1):<15.1f} | {len(df_compare)/(bcd_switches+1):<15.1f}")
    
    print(f"\n5. Regime Distribution (%):")
    all_labels = sorted(list(set(df_compare['hmm_label'].unique()) | set(df_compare['bcd_label'].unique())))
    for label in all_labels:
        h_val = hmm_dist.get(label, 0.0)
        b_val = bcd_dist.get(label, 0.0)
        print(f"    {label:30s} | {h_val:<14.1f}% | {b_val:<14.1f}%")

    # 6. Returns Analysis
    df_compare['fwd_ret_5c'] = df_compare['Close'].shift(-5) / df_compare['Close'] - 1.0
    eval_df = df_compare.dropna(subset=['fwd_ret_5c'])
    
    print(f"\n6. Predictive Alignment (5-Candle Forward Return):")
    print(f"    {'Regime':30s} | {'HMM Mean (%)':15s} | {'BCD Mean (%)':15s}")
    print(f"    {'-'*30} | {'-'*15} | {'-'*15}")
    for label in ["Bullish Trend", "Bearish Trend", "High Volatility Sideways", "Low Volatility Sideways"]:
        h_mean = eval_df[eval_df['hmm_label'] == label]['fwd_ret_5c'].mean() * 100
        b_mean = eval_df[eval_df['bcd_label'] == label]['fwd_ret_5c'].mean() * 100
        print(f"    {label:30s} | {h_mean:+.4f}%       | {b_mean:+.4f}%")

    # 7. Visualization
    print("\n7. Generating Visual Comparison...")
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(20, 12), sharex=True)
    
    color_map = {
        "Bullish Trend": "green",
        "Bearish Trend": "red",
        "High Volatility Sideways": "orange",
        "Low Volatility Sideways": "blue",
        "Unknown Regime": "gray"
    }

    # Plot HMM
    ax1.plot(df_compare.index, df_compare['Close'], color='black', alpha=0.2)
    ax1.set_title("Layer 1: HMM (Gaussian Mixture) - Long Timeframe")
    for label, color in color_map.items():
        mask = df_compare['hmm_label'] == label
        if mask.any():
            ax1.scatter(df_compare.index[mask], df_compare['Close'][mask], color=color, s=5, label=label)
    ax1.legend(loc='upper left')

    # Plot BCD
    ax2.plot(df_compare.index, df_compare['Close'], color='black', alpha=0.2)
    ax2.set_title("Layer 1: BCD (Bayesian Online Changepoint) - Long Timeframe")
    for label, color in color_map.items():
        mask = df_compare['bcd_label'] == label
        if mask.any():
            ax2.scatter(df_compare.index[mask], df_compare['Close'][mask], color=color, s=5, label=label)
    ax2.legend(loc='upper left')

    plt.tight_layout()
    viz_path = str(Path(_BACKEND_DIR).parent / "docs" / "history" / "long_compare_viz.png")
    os.makedirs(os.path.dirname(viz_path), exist_ok=True)
    plt.savefig(viz_path)
    print(f"    [✓] Visualization saved to {viz_path}")

    # 8. Comparison Summary for Documentation
    print("\n" + "="*70)
    print(" VERDICT SUMMARY:")
    stability_gain = hmm_switches / bcd_switches if bcd_switches > 0 else 1.0
    print(f" * Persistence: BCD is {stability_gain:.1f}x more stable than HMM.")
    
    hmm_bull_signal = eval_df[eval_df['hmm_label'] == "Bullish Trend"]['fwd_ret_5c'].mean() > 0
    bcd_bull_signal = eval_df[eval_df['bcd_label'] == "Bullish Trend"]['fwd_ret_5c'].mean() > 0
    print(f" * Accuracy (Bullish): HMM [{'PASS' if hmm_bull_signal else 'FAIL'}], BCD [{'PASS' if bcd_bull_signal else 'FAIL'}]")
    print("="*70 + "\n")

if __name__ == "__main__":
    run_long_comparison()
