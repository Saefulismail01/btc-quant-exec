import os, sys, time
import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
from datetime import datetime

_BACKEND_DIR = str(Path(__file__).resolve().parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from engines.layer1_hmm import MarketRegimeModel
from engines.layer1_bcd import BayesianChangepointModel
from data_engine import DuckDBManager, DB_PATH

def run_2023_test():
    print("\n" + "="*70)
    print(" BTC-QUANT: 2023 WINDOW TEST")
    print("="*70 + "\n")

    # 1. Fetch & Filter
    print("1. Fetching data...")
    db = DuckDBManager(DB_PATH)
    total_df = db.get_latest_ohlcv(limit=8000)
    
    start_ts = int(datetime(2023, 1, 1).timestamp() * 1000)
    end_ts   = int(datetime(2024, 1, 1).timestamp() * 1000)
    df = total_df[(total_df['timestamp'] >= start_ts) & (total_df['timestamp'] < end_ts)].copy()
    
    if len(df) < 200:
        print(f" [!] Insufficient data ({len(df)} rows).")
        return

    print(f"    Loaded {len(df)} candles for 2023.")
    print(f"    Timeframe: {df.index[0]} to {df.index[-1]}")
    print(f"    Price range: ${df['Close'].min():,.0f} — ${df['Close'].max():,.0f}")

    # 2. Train
    print("\n2. Training Engines...")
    hmm = MarketRegimeModel()
    bcd = BayesianChangepointModel()
    hmm.train_global(df)
    bcd.train_global(df)

    # 3. Inference
    hmm_states, hmm_idx = hmm.get_state_sequence_raw(df)
    bcd_states, bcd_idx = bcd.get_state_sequence_raw(df)

    common_idx = hmm_idx.intersection(bcd_idx)
    dc = df.loc[common_idx].copy()
    dc['hmm_label'] = hmm_states[np.searchsorted(hmm_idx, common_idx)]
    dc['hmm_label'] = dc['hmm_label'].map(hmm.state_map)
    dc['bcd_label'] = bcd_states[np.searchsorted(bcd_idx, common_idx)]
    dc['bcd_label'] = dc['bcd_label'].map(bcd.state_map)

    # 4. Metrics
    target_per_candle = (1.03**(1/6) - 1)
    dc['fwd_ret'] = dc['Close'].shift(-1) / dc['Close'] - 1.0
    dc['abs_ret'] = dc['fwd_ret'].abs()

    def analyze(label_col):
        results = []
        for label in ["Bullish Trend", "Bearish Trend", "High Volatility Sideways", "Low Volatility Sideways"]:
            sub = dc[dc[label_col] == label].dropna(subset=['fwd_ret'])
            if sub.empty: continue
            mr = sub['fwd_ret'].mean()
            wr = (sub['fwd_ret'] > 0).mean() if "Bull" in label else (sub['fwd_ret'] < 0).mean()
            vol = sub['fwd_ret'].std()
            if "Bull" in label:
                opp = (sub['fwd_ret'] >= target_per_candle).mean()
            elif "Bear" in label:
                opp = (sub['fwd_ret'] <= -target_per_candle).mean()
            else:
                opp = (sub['abs_ret'] >= target_per_candle).mean()
            results.append({"Regime": label, "Avg Ret": f"{mr*100:+.3f}%", "Volatility": f"{vol*100:.3f}%",
                            "WR": f"{wr*100:.1f}%", "Profit Opp Freq": f"{opp*100:.1f}%"})
        return pd.DataFrame(results)

    print("\n3. Profit Feasibility (Target: 0.493%/candle = 3%/day):\n")
    print("--- HMM ---")
    print(analyze('hmm_label'))
    print("\n--- BCD ---")
    print(analyze('bcd_label'))

    # Daily potential
    bcd_bull = dc[dc['bcd_label'] == "Bullish Trend"]
    if not bcd_bull.empty:
        pot = (bcd_bull['fwd_ret'].abs().mean() * 6) * 100
        print(f"\nDaily Gross Potential (BCD Bullish): {pot:.2f}%/day")

    # 2-directional
    bcd_bear = dc[dc['bcd_label'] == "Bearish Trend"]
    if not bcd_bull.empty and not bcd_bear.empty:
        bull_avg = bcd_bull['fwd_ret'].mean()
        bear_avg = abs(bcd_bear['fwd_ret'].mean())
        combined = (bull_avg * len(bcd_bull) + bear_avg * len(bcd_bear)) / (len(bcd_bull) + len(bcd_bear))
        print(f"2-Directional Avg Profit: {combined*100:+.3f}%/candle = {combined*600:.2f}%/day")

    # 5. Distribution
    print("\nRegime Distribution (BCD):")
    dist = dc['bcd_label'].value_counts(normalize=True) * 100
    for label, pct in dist.items():
        print(f"  {label:30s} {pct:6.1f}%")

    # 6. Visualization (NEW file)
    colors = {"Bullish Trend": "#2196F3", "Bearish Trend": "#FF5722",
              "High Volatility Sideways": "#4CAF50", "Low Volatility Sideways": "#9E9E9E"}
    plt.figure(figsize=(16, 7))
    plt.plot(dc.index, dc['Close'], color='#E0E0E0', alpha=0.5, linewidth=0.8)
    for label, color in colors.items():
        mask = dc['bcd_label'] == label
        if mask.sum() > 0:
            plt.scatter(dc.index[mask], dc['Close'][mask], s=12, label=label, color=color, alpha=0.8)
    plt.title("BCD Regimes (2023 Window)", fontsize=13)
    plt.ylabel("BTC Price (USD)")
    plt.legend(loc='upper left')
    plt.tight_layout()
    viz_path = str(Path(_BACKEND_DIR).parent / "docs" / "history" / "viz_2023_v3.png")
    plt.savefig(viz_path, dpi=150)
    print(f"\n[✓] Visualization saved to {viz_path}")

if __name__ == "__main__":
    run_2023_test()
