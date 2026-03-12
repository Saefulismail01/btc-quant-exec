import os
import sys
import time
import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

# Add backend to path
_BACKEND_DIR = str(Path(__file__).resolve().parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# Import Engines
from engines.layer1_hmm import MarketRegimeModel
from engines.layer1_bcd import BayesianChangepointModel
from data_engine import get_latest_market_data

def run_comparison():
    print("\n" + "="*60)
    print(" BTC-QUANT: LAYER 1 ENGINE COMPARISON (HMM VS BCD)")
    print("="*60 + "\n")

    # 1. Fetch Data
    print("1. Fetching historical data from DuckDB...")
    df, _ = get_latest_market_data()
    
    if df is None or len(df) < 500:
        print(" [!] Insufficient data for comparison. Need at least 500 rows.")
        return

    print(f"    Loaded {len(df)} candles.")

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
    
    # We'll use get_state_sequence_raw to get the aligned states for the whole dataframe
    hmm_states, hmm_idx = hmm_model.get_state_sequence_raw(df)
    bcd_states, bcd_idx = bcd_model.get_state_sequence_raw(df)

    # Use intersection of indices to ensure alignment
    common_idx = hmm_idx.intersection(bcd_idx)
    df_compare = df.loc[common_idx].copy()
    
    # Map internal state IDs to human labels
    df_compare['hmm_raw_state'] = hmm_states[np.searchsorted(hmm_idx, common_idx)]
    df_compare['bcd_raw_state'] = bcd_states[np.searchsorted(bcd_idx, common_idx)]
    
    df_compare['hmm_label'] = df_compare['hmm_raw_state'].map(hmm_model.state_map)
    df_compare['bcd_label'] = df_compare['bcd_raw_state'].map(bcd_model.state_map)

    # 5. Metric Extraction: Flickering (Regime Switches)
    def count_switches(labels):
        return (labels != labels.shift(1)).sum() - 1

    hmm_switches = count_switches(df_compare['hmm_label'])
    bcd_switches = count_switches(df_compare['bcd_label'])

    print(f"\n4. Metrics (Stability/Persistence):")
    print(f"    {'Metric':25s} | {'HMM (GMM)':15s} | {'BCD (Bayesian)':15s}")
    print(f"    {'-'*25} | {'-'*15} | {'-'*15}")
    print(f"    {'Total Switches':25s} | {hmm_switches:<15d} | {bcd_switches:<15d}")
    print(f"    {'Avg Persistence (candles)':25s} | {len(df_compare)/(hmm_switches+1):<15.1f} | {len(df_compare)/(bcd_switches+1):<15.1f}")
    
    # 6. Visualization
    print("\n5. Generating Visual Comparison (bcd_vs_hmm.png)...")
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10), sharex=True)
    
    # Color Maps
    color_map = {
        "Bullish Trend": "green",
        "Bearish Trend": "red",
        "High Volatility Sideways": "orange",
        "Low Volatility Sideways": "blue",
        "Unknown Regime": "gray"
    }

    # Plot HMM
    ax1.plot(df_compare.index, df_compare['Close'], color='black', alpha=0.3)
    ax1.set_title("Layer 1: HMM (Gaussian Mixture) Regimes")
    for label, color in color_map.items():
        mask = df_compare['hmm_label'] == label
        if mask.any():
            ax1.scatter(df_compare.index[mask], df_compare['Close'][mask], color=color, s=10, label=label)
    ax1.legend(loc='upper left')

    # Plot BCD
    ax2.plot(df_compare.index, df_compare['Close'], color='black', alpha=0.3)
    ax2.set_title("Layer 1: BCD (Bayesian Online Changepoint) Regimes")
    for label, color in color_map.items():
        mask = df_compare['bcd_label'] == label
        if mask.any():
            ax2.scatter(df_compare.index[mask], df_compare['Close'][mask], color=color, s=10, label=label)
    ax2.legend(loc='upper left')

    plt.tight_layout()
    plt.savefig("bcd_vs_hmm.png")
    print("    [✓] Visualization saved to bcd_vs_hmm.png")

    # 7. Final Verdict
    print("\n" + "="*60)
    print(" VERDICT:")
    if bcd_switches < hmm_switches:
        print(f" BCD is {hmm_switches/bcd_switches:.1f}x MORE PERSISTENT than HMM.")
        print(" This confirms the 'Anti-Flickering' property of the Bayesian approach.")
    else:
        print(" HMM appears more stable in this dataset, check hyper-parameters.")
    print("="*60 + "\n")

if __name__ == "__main__":
    run_comparison()
