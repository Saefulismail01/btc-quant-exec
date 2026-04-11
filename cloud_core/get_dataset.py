"""
Get Dataset - Fetch OHLCV from Binance
Standalone script for downloading historical data
"""
import pandas as pd
import ccxt
from datetime import datetime, timedelta


def fetch_ohlcv(
    symbol: str = "BTC/USDT",
    timeframe: str = "4h",
    since_days: int = 365,
    save_csv: bool = True,
) -> pd.DataFrame:
    """
    Fetch OHLCV data from Binance Futures.
    
    Args:
        symbol: Trading pair (default: BTC/USDT)
        timeframe: Candle timeframe (1m, 5m, 15m, 1h, 4h, 1d)
        since_days: How many days of history to fetch
        save_csv: Save to CSV file
    
    Returns:
        DataFrame with OHLCV data
    """
    print(f"[DataFetcher] Fetching {symbol} {timeframe} data...")
    print(f"[DataFetcher] Period: last {since_days} days")
    
    # Initialize exchange
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {'defaultType': 'future'}
    })
    
    # Calculate start time
    since = exchange.milliseconds() - (since_days * 24 * 60 * 60 * 1000)
    
    all_ohlcv = []
    
    while since < exchange.milliseconds():
        try:
            ohlcv = exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=since,
                limit=1000
            )
            
            if not ohlcv:
                break
            
            all_ohlcv.extend(ohlcv)
            
            # Update since to last timestamp + 1 interval
            since = ohlcv[-1][0] + 1
            
            print(f"[DataFetcher] Fetched {len(all_ohlcv)} candles so far...")
            
        except Exception as e:
            print(f"[DataFetcher] Error: {e}")
            break
    
    # Create DataFrame
    df = pd.DataFrame(
        all_ohlcv,
        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
    )
    
    # Convert timestamp
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    
    # Remove duplicates
    df = df[~df.index.duplicated(keep='first')]
    
    print(f"[DataFetcher] Total candles: {len(df)}")
    print(f"[DataFetcher] Date range: {df.index[0]} to {df.index[-1]}")
    
    # Save to CSV
    if save_csv:
        filename = f"{symbol.replace('/', '_')}_{timeframe}_{since_days}d.csv"
        df.to_csv(filename)
        print(f"[DataFetcher] Saved to: {filename}")
    
    return df


# ============ COPY PASTE FROM HERE ============

# Install dependencies (run in Colab/Jupyter cell):
# !pip install ccxt pandas -q

# Import
import ccxt
import pandas as pd

# Fetch data function
def get_data(symbol="BTC/USDT", timeframe="4h", days=180):
    exchange = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})
    since = exchange.milliseconds() - (days * 24 * 60 * 60 * 1000)
    
    ohlcv = []
    while since < exchange.milliseconds():
        batch = exchange.fetch_ohlcv(symbol, timeframe, since, limit=1000)
        if not batch:
            break
        ohlcv.extend(batch)
        since = batch[-1][0] + 1
    
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df

# Get data
df = get_data("BTC/USDT", "4h", days=365)
print(f"Got {len(df)} candles from {df.index[0]} to {df.index[-1]}")

# Save to CSV (optional)
df.to_csv("btc_usdt_4h.csv")
print("Saved to btc_usdt_4h.csv")

# ============ END COPY PASTE ============


if __name__ == "__main__":
    # Example usage
    df = fetch_ohlcv(
        symbol="BTC/USDT",
        timeframe="4h",
        since_days=365,
        save_csv=True
    )
    
    print("\nFirst 5 rows:")
    print(df.head())
    
    print("\nLast 5 rows:")
    print(df.tail())
    
    print("\nData statistics:")
    print(df.describe())
