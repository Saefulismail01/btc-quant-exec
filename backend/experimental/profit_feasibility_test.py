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
from data_engine import DuckDBManager, DB_PATH

def run_2025_2026_test():
    print("\n" + "="*70)
    print(" BTC-QUANT: 2025-2026 WINDOW TEST (PROFIT FEASIBILITY)")
    print("="*70 + "\n")

    # 1. Fetch Data
    print("1. Fetching data from January 1, 2025...")
    db = DuckDBManager(DB_PATH)
    total_df = db.get_latest_ohlcv(limit=8000)
    
    # Filter for 2025
    start_2025 = int(datetime(2025, 1, 1).timestamp() * 1000)
    df = total_df[total_df['timestamp'] >= start_2025].copy()
    
    if len(df) < 200:
        print(f" [!] Insufficient data for 2025 window ({len(df)} rows).")
        return

    print(f"    Loaded {len(df)} candles for 2025-2026 window.")
    print(f"    Timeframe: {df.index[0]} to {df.index[-1]}")

    # 2. Initialize Models
    hmm_model = MarketRegimeModel()
    bcd_model = BayesianChangepointModel()

    # 3. Global Training
    print("\n2. Training Engines on 2025-2026 Context...")
    hmm_model.train_global(df)
    bcd_model.train_global(df)

    # 4. Inference & Comparison
    hmm_states, hmm_idx = hmm_model.get_state_sequence_raw(df)
    bcd_states, bcd_idx = bcd_model.get_state_sequence_raw(df)

    common_idx = hmm_idx.intersection(bcd_idx)
    df_compare = df.loc[common_idx].copy()
    
    df_compare['hmm_label'] = hmm_states[np.searchsorted(hmm_idx, common_idx)]
    df_compare['hmm_label'] = df_compare['hmm_label'].map(hmm_model.state_map)
    df_compare['bcd_label'] = bcd_states[np.searchsorted(bcd_idx, common_idx)]
    df_compare['bcd_label'] = df_compare['bcd_label'].map(bcd_model.state_map)

    # 5. Profit Feasibility Calculation (3%/day target)
    # 3% per day = approx 0.5% per 4h candle (compounded is higher, but linear is safer for target)
    # Actually 1.03^(1/6) - 1 = ~0.493% per 4h candle.
    target_per_candle = (1.03**(1/6) - 1)
    
    df_compare['fwd_ret_1c'] = df_compare['Close'].shift(-1) / df_compare['Close'] - 1.0
    df_compare['abs_ret_1c'] = df_compare['fwd_ret_1c'].abs() # Scalping potential in either side if high vol
    
    def analyze_feasibility(label_col):
        results = []
        for label in ["Bullish Trend", "Bearish Trend", "High Volatility Sideways", "Low Volatility Sideways"]:
            subset = df_compare[df_compare[label_col] == label].dropna(subset=['fwd_ret_1c'])
            if subset.empty: continue
            
            mean_ret = subset['fwd_ret_1c'].mean()
            win_rate = (subset['fwd_ret_1c'] > 0).mean() if "Bull" in label else (subset['fwd_ret_1c'] < 0).mean()
            volatility = subset['fwd_ret_1c'].std()
            
            # Opportunity Score: How many candles meet the profit threshold purely by direction?
            if "Bull" in label:
                opp_freq = (subset['fwd_ret_1c'] >= target_per_candle).mean()
            elif "Bear" in label:
                opp_freq = (subset['fwd_ret_1c'] <= -target_per_candle).mean()
            else:
                # Sideways: use abs volatility (scalping both ways)
                opp_freq = (subset['abs_ret_1c'] >= target_per_candle).mean()

            results.append({
                "Regime": label,
                "Avg Ret": f"{mean_ret*100:+.3f}%",
                "Volatility": f"{volatility*100:.3f}%",
                "WR": f"{win_rate*100:.1f}%",
                "Profit Opp Freq": f"{opp_freq*100:.1f}%"
            })
        return pd.DataFrame(results)

    print("\n3. Profit Feasibility Audit (Target: 0.493%/candle = 3%/day):")
    print("\n--- HMM (GMM) Analysis ---")
    print(analyze_feasibility('hmm_label'))
    print("\n--- BCD (Bayesian) Analysis ---")
    print(analyze_feasibility('bcd_label'))

    # Final Verdict Summary
    bcd_bull = df_compare[df_compare['bcd_label'] == "Bullish Trend"]
    if not bcd_bull.empty:
        max_daily_potential = (bcd_bull['fwd_ret_1c'].abs().mean() * 6) * 100
        print(f"\nFinal Scalping Potential (BCD Bullish): Approx {max_daily_potential:.2f}% gross per day")

    # Save visualization for 2025-2026 (NEW FILE — preserve old)
    colors = {"Bullish Trend": "#2196F3", "Bearish Trend": "#FF5722", 
              "High Volatility Sideways": "#4CAF50", "Low Volatility Sideways": "#9E9E9E"}
    plt.figure(figsize=(16, 7))
    plt.plot(df_compare.index, df_compare['Close'], color='#E0E0E0', alpha=0.5, linewidth=0.8)
    for label, color in colors.items():
        mask = df_compare['bcd_label'] == label
        if mask.sum() > 0:
            plt.scatter(df_compare.index[mask], df_compare['Close'][mask], s=12, label=label, color=color, alpha=0.8)
    plt.title("BCD Regimes v2 — MAX_SEGMENT_LEN Split (2025-2026)", fontsize=13)
    plt.ylabel("BTC Price (USD)")
    plt.legend(loc='upper right')
    plt.tight_layout()
    viz_path = str(Path(_BACKEND_DIR).parent / "docs" / "history" / "viz_2025_2026_v3.png")
    plt.savefig(viz_path, dpi=150)
    print(f"\n[✓] Window visualization saved to {viz_path}")

if __name__ == "__main__":
    run_2025_2026_test()
