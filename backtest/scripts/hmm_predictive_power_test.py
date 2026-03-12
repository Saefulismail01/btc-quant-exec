import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime

# Allow importing from backend/app and backend/engines
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "engines"))

import duckdb
from backend.engines.layer1_bcd import BayesianChangepointModel as MarketRegimeModel

def load_data() -> pd.DataFrame:
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "btc-quant.db")
    with duckdb.connect(db_path) as con:
        df = con.execute('''
            SELECT 
                o.timestamp, o.open, o.high, o.low, o.close, o.volume,
                m.funding_rate, m.open_interest, m.cvd,
                m.liquidations_buy, m.liquidations_sell
            FROM btc_ohlcv_4h o
            LEFT JOIN market_metrics m ON o.timestamp = m.timestamp
            ORDER BY o.timestamp ASC
        ''').df()
    
    # Standardize column names to match layer1_hmm.py expectations
    df.rename(columns={
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close',
        'volume': 'Volume'
    }, inplace=True)
    return df

def run_predictive_power_test():
    print("═══ BTC-QUANT: Layer 1 HMM Predictive Power Test ═══")
    
    df = load_data()
    if len(df) < 500:
        print(f"Error: Insufficient data ({len(df)} rows). Need >500 rows.")
        return

    print(f"Total History Loaded: {len(df)} candles")
    print("Partitioning data into 3 non-overlapping windows...")
    
    # Split into 3 roughly equal historical windows
    window_pts = np.array_split(df.index, 3)
    windows = [df.loc[idx].copy() for idx in window_pts]
    
    results = []

    for w_idx, w_df in enumerate(windows):
        start_date = datetime.fromtimestamp(w_df['timestamp'].iloc[0]/1000).strftime('%Y-%m-%d')
        end_date = datetime.fromtimestamp(w_df['timestamp'].iloc[-1]/1000).strftime('%Y-%m-%d')
        print(f"\n--- Testing Window {w_idx+1}: {start_date} to {end_date} (n={len(w_df)}) ---")
        
        # 1. Compute Forward Returns
        w_df['fwd_ret_1c'] = w_df['Close'].shift(-1) / w_df['Close'] - 1.0
        w_df['fwd_ret_3c'] = w_df['Close'].shift(-3) / w_df['Close'] - 1.0
        w_df['fwd_ret_5c'] = w_df['Close'].shift(-5) / w_df['Close'] - 1.0
        
        # Drop the NaN rows at the end caused by shifting
        eval_df = w_df.dropna(subset=['fwd_ret_5c']).copy()
        
        # Ensure eval_df features have no NaNs before passing to HMM model
        eval_df = eval_df.ffill().bfill().fillna(0.0)
        
        # 2. Extract features and scale them
        hmm_model = MarketRegimeModel()
        df_feat_train = hmm_model.prepare_features(eval_df)
        cols_train = df_feat_train.columns
        df_feat_train[cols_train] = df_feat_train[cols_train].replace([np.inf, -np.inf], np.nan)
        df_feat_train[cols_train] = df_feat_train[cols_train].ffill().bfill().fillna(0.0)
        
        X_scaled_train = hmm_model.scaler.fit_transform(df_feat_train)
        
        # Train HMM on this specific window to simulate out-of-sample dynamics
        states = hmm_model.train_model(X_scaled_train)
        
        if states is None or len(states) == 0:
            print("  Training failed for this window.")
            continue
            
        n_comp_str = f"{hmm_model.model.n_components} states" if hasattr(hmm_model, "model") else f"{len(set(states))} segments"
        print(f"  Model Selected: {n_comp_str}")
        
        # Generate the state map mappings
        hmm_model.label_states(df_feat_train, states)
        
        # Map state IDs to Regime Labels using the model's mapped dictionary
        eval_df['hmm_state_id'] = states
        eval_df['regime_label'] = eval_df['hmm_state_id'].map(hmm_model.state_map)
        
        # Group by label and calculate expected forward metrics
        groups = eval_df.groupby('regime_label')
        
        for label, group in groups:
            n_samples = len(group)
            
            # Simple metrics
            mean_1c = group['fwd_ret_1c'].mean() * 100
            mean_3c = group['fwd_ret_3c'].mean() * 100
            mean_5c = group['fwd_ret_5c'].mean() * 100
            
            # Win rates (close > 0)
            wr_1c = (group['fwd_ret_1c'] > 0).mean() * 100
            
            # Rough t-stat for 1c return vs 0
            std_1c = group['fwd_ret_1c'].std()
            t_stat = (group['fwd_ret_1c'].mean() / (std_1c / np.sqrt(n_samples))) if std_1c > 0 else 0
            
            print(f"    {label:<25} | n={n_samples:<4} | 1C: {mean_1c:+.2f}% (WR: {wr_1c:.1f}%) | 3C: {mean_3c:+.2f}% | 5C: {mean_5c:+.2f}% | t={t_stat:+.2f}")
            
            results.append({
                "window": w_idx + 1,
                "start_date": start_date,
                "end_date": end_date,
                "regime": label,
                "n_candles": n_samples,
                "mean_ret_1c_pct": mean_1c,
                "mean_ret_3c_pct": mean_3c,
                "mean_ret_5c_pct": mean_5c,
                "win_rate_1c_pct": wr_1c,
                "t_stat_1c": t_stat
            })
            
    # Save Results
    res_df = pd.DataFrame(results)
    out_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(out_dir, exist_ok=True)
    out_csv = os.path.join(out_dir, "hmm_power_test.csv")
    res_df.to_csv(out_csv, index=False)
    
    print("\n" + "="*50)
    print(f"Test complete. Detailed results saved to {out_csv}")
    print("Please review the results against PRD I-00 PASS criteria:")
    print("1) 'Bullish Trend' candles have positive mean return & significant t-stat in 2 of 3 windows.")
    print("2) 'Bearish Trend' candles have negative mean return in 2 of 3 windows.")
    print("3) 'Bullish' win rate > 53%")
    print("Record the PASS/FAIL decision in backtest/results/hmm_power_test_decision.md")
    print("="*50)

if __name__ == "__main__":
    run_predictive_power_test()
