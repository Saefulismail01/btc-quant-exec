import numpy as np
import pandas as pd
import sys
from pathlib import Path

# Add backend to path
_BACKEND_DIR = str(Path(__file__).resolve().parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from engines.layer1_bcd import BayesianChangepointModel

def test_bcd_isolated():
    print("Generating synthetic crypto-like data...")
    # Generate 1000 rows
    np.random.seed(42)
    
    # We create 3 distinct periods (changepoints at 300, 700)
    # Period 1: Low vol sideways
    # Period 2: High vol bull
    # Period 3: Extreme vol bear
    
    data = []
    
    # Base cols: Open, High, Low, Close, Volume, cvd, open_interest, liquidations_buy, liquidations_sell
    price = 60000.0
    for i in range(1000):
        if i < 300:
            ret = np.random.normal(0, 0.001)
            vol = np.random.uniform(100, 500)
        elif i < 700:
            ret = np.random.normal(0.003, 0.005)  # Bull
            vol = np.random.uniform(500, 2000)
        else:
            ret = np.random.normal(-0.004, 0.008) # Bear
            vol = np.random.uniform(1000, 3000)
            
        price *= (1 + ret)
        
        high = price * (1 + abs(np.random.normal(0, 0.002)))
        low = price * (1 - abs(np.random.normal(0, 0.002)))
        
        data.append({
            "Open": price,
            "High": high,
            "Low": low,
            "Close": price,
            "Volume": vol,
            "cvd": np.random.normal(0, 1000),
            "open_interest": np.random.uniform(1e8, 2e8),
            "liquidations_buy": np.random.exponential(1000),
            "liquidations_sell": np.random.exponential(1000)
        })
        
    df = pd.DataFrame(data)
    
    print("Testing BCD Engine Initialization...")
    model = BayesianChangepointModel()
    
    print("Testing get_current_regime on Window 1...")
    regime1, sid1 = model.get_current_regime(df.iloc[:250])
    print(f"Window 1 Regime Result: {regime1} (ID: {sid1})")
    
    print("Testing train_global on full dataset...")
    success = model.train_global(df)
    print(f"Global Training Success: {success}")
    
    print("Testing get_current_regime on full dataset (should map to last period...)")
    regime3, sid3 = model.get_current_regime(df)
    print(f"End Regime Result: {regime3} (ID: {sid3})")
    
    vote = model.get_directional_vote(df)
    print(f"Directional Vote: {vote}")
    
    print("\nState Map Assigned by BCD Engine:")
    for key, val in model.state_map.items():
        print(f"Segment {key}: {val}")

if __name__ == "__main__":
    test_bcd_isolated()
