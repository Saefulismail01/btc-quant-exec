import sys
import pandas as pd
from pathlib import Path

backend_dir = str(Path(__file__).parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from engines.layer1_hmm import MarketRegimeModel

def analyze_year(year: int):
    data_path = Path(__file__).parent / "data" / f"BTC_USDT_4h_{year}.csv"
    if not data_path.exists():
        return
        
    print(f"\n--- Menganalisis Distribusi Regime Tahun {year} ---")
    df = pd.read_csv(data_path, index_col=0, parse_dates=True)
    df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}, inplace=True)
    
    hmm = MarketRegimeModel()
    
    # Analyze the whole year in chunks realistically 
    # (since the model retrains on sliding windows, we'll just evaluate every 50 candles as a sample)
    regimes_detected = []
    
    for i in range(100, len(df), 50):
        df_window = df.iloc[:i+1]
        label, _ = hmm.get_current_regime(df_window)
        # Store just the label
        regimes_detected.append(label)
        
    # Count occurrences
    counts = pd.Series(regimes_detected).value_counts()
    for regime, count in counts.items():
        pct = (count / len(regimes_detected)) * 100
        print(f"[{count:3d} kali] - {pct:^5.1f}% : {regime}")
        
analyze_year(2023)
analyze_year(2025)
