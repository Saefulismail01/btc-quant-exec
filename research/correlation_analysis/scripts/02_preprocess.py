"""
Phase 2: Data Preprocessing
- Load semua CSV dari data/raw/
- Align ke timestamp yang sama (inner join)
- Handle missing values (forward fill, max 2 candle)
- Hitung simple returns & log returns
- Simpan ke data/processed/
"""

import pandas as pd
import numpy as np
from pathlib import Path

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

PAIRS = ["BTCUSDT", "ETHUSDT", "DOGEUSDT", "LINKUSDT", "SOLUSDT", "BNBUSDT"]
TIMEFRAMES = ["4h", "1d"]


def load_csv(pair: str, tf: str) -> pd.DataFrame:
    path = RAW_DIR / f"{pair}_{tf}.csv"
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.set_index("timestamp").sort_index()
    # Keep only close price, rename to pair symbol
    symbol = pair.replace("USDT", "")
    return df[["close"]].rename(columns={"close": symbol})


def preprocess(tf: str):
    print(f"\n=== Timeframe: {tf} ===")

    # Load & align
    frames = [load_csv(p, tf) for p in PAIRS]
    combined = pd.concat(frames, axis=1, join="inner")
    print(f"Aligned shape: {combined.shape}  ({combined.index[0]} to {combined.index[-1]})")

    # Missing value check before fill
    missing = combined.isnull().sum()
    if missing.any():
        print(f"Missing before ffill:\n{missing[missing > 0]}")

    # Forward fill max 2 candles
    combined = combined.ffill(limit=2)

    # Drop rows still NaN after fill
    combined = combined.dropna()
    print(f"Shape after fill+dropna: {combined.shape}")

    # Save aligned close prices
    close_path = PROCESSED_DIR / f"close_{tf}.csv"
    combined.to_csv(close_path)
    print(f"Saved: {close_path}")

    # Simple returns
    returns = combined.pct_change().dropna()
    ret_path = PROCESSED_DIR / f"returns_{tf}.csv"
    returns.to_csv(ret_path)
    print(f"Saved: {ret_path}")

    # Log returns
    log_returns = np.log(combined / combined.shift(1)).dropna()
    logret_path = PROCESSED_DIR / f"log_returns_{tf}.csv"
    log_returns.to_csv(logret_path)
    print(f"Saved: {logret_path}")

    # Basic stats
    print(f"\nReturns stats ({tf}):")
    stats = returns.describe().T[["mean", "std", "min", "max"]]
    stats["skew"] = returns.skew()
    stats["kurt"] = returns.kurt()
    print(stats.to_string())

    return combined, returns, log_returns


if __name__ == "__main__":
    for tf in TIMEFRAMES:
        preprocess(tf)
    print("\nPhase 2 complete. Output in data/processed/")
