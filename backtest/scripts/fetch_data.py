import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import ccxt
import pandas as pd

# ════════════════════════════════════════════════════════════
# CONSTANTS
# ════════════════════════════════════════════════════════════
SYMBOL = "BTC/USDT"
TIMEFRAME = "4h"

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# ════════════════════════════════════════════════════════════
# FETCHER (Sync)
# ════════════════════════════════════════════════════════════

def fetch_year(year: int):
    """
    Fetch OHLCV data for a specific year and save to CSV using sync CCXT.
    """
    print(f"\n[FETCH] Starting download for {year}...")
    
    # Define start and end timestamps for the year
    start_date = datetime(year, 1, 1, tzinfo=timezone.utc)
    if year == datetime.now(timezone.utc).year:
        end_date = datetime.now(timezone.utc)
    else:
        end_date = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        
    start_ts = int(start_date.timestamp() * 1000)
    end_ts = int(end_date.timestamp() * 1000)
    
    http_proxy = os.getenv("HTTP_PROXY", "").strip()
    https_proxy = os.getenv("HTTPS_PROXY", "").strip()
    
    proxy_config = {}
    if http_proxy or https_proxy:
        proxy_config["proxies"] = {
            "http": http_proxy or https_proxy,
            "https": https_proxy or http_proxy,
        }
        print(f"[FETCH] Using proxy: {https_proxy or http_proxy}")
    
    exchange = ccxt.binance({
        "enableRateLimit": True,
        "options": {
            "defaultType": "future",
        },
        **proxy_config
    })
    
    all_ohlcv = []
    current_ts = start_ts
    
    try:
        while current_ts < end_ts:
            print(f"  -> Fetching from {datetime.fromtimestamp(current_ts/1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')}")
            
            try:
                ohlcv = exchange.fetch_ohlcv(
                    symbol=SYMBOL,
                    timeframe=TIMEFRAME,
                    since=current_ts,
                    limit=1000
                )
            except Exception as e:
                print(f"  -> Error fetching data: {e}. Retrying in 5 seconds...")
                time.sleep(5)
                continue
            
            if not ohlcv:
                print("  -> No more data returned from exchange.")
                break
                
            filtered_ohlcv = [row for row in ohlcv if row[0] <= end_ts]
            if not filtered_ohlcv:
                break
                
            all_ohlcv.extend(filtered_ohlcv)
            
            last_ts = filtered_ohlcv[-1][0]
            if last_ts == current_ts:
                current_ts += exchange.parse_timeframe(TIMEFRAME) * 1000
            else:
                current_ts = last_ts + 1
                
            time.sleep(0.5)
            
    except Exception as e:
        print(f"\n[ERROR] Failed during fetch: {e}")
        
    if not all_ohlcv:
        print(f"[FETCH] No data found for {year}.")
        return None
        
    df = pd.DataFrame(
        all_ohlcv, 
        columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    
    df = df.drop_duplicates(subset=["timestamp"], keep="last")
    
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("datetime").sort_index()
    
    filename = DATA_DIR / f"BTC_USDT_{TIMEFRAME}_{year}.csv"
    df.to_csv(filename)
    print(f"[FETCH] Saved {len(df)} rows to {filename}")
    
    return filename

def main():
    years_to_fetch = [2023, 2025]
    
    for year in years_to_fetch:
        filename = DATA_DIR / f"BTC_USDT_{TIMEFRAME}_{year}.csv"
        if filename.exists():
            print(f"[FETCH] Data for {year} already exists at {filename}. Skipping...")
            continue
            
        fetch_year(year)

if __name__ == "__main__":
    main()
