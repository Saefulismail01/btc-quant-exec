import asyncio
import os
import sys
import pandas as pd
from datetime import datetime
import ccxt.async_support as ccxt
import time

# Ensure we can import from backend root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_engine import DuckDBManager, _log

SYMBOL = "BTCUSDT"
PERP_SYMBOL = "BTC/USDT:USDT"
INTERVAL = "4h"
DAYS_TO_FETCH = 1200 
KLINES_LIMIT = 1500  # Max per Binance fapi getKlines
OI_LIMIT = 500       # Max per Binance fapi openInterestHist

async def fetch_klines_chunk(exchange, start_time, end_time=None):
    """Fetch 4H chunk via implicit API (fapiPublicGetKlines) for precise CVD"""
    params = {
        'symbol': SYMBOL,
        'interval': INTERVAL,
        'limit': KLINES_LIMIT,
        'startTime': start_time
    }
    if end_time:
        params['endTime'] = end_time
    return await exchange.fapiPublicGetKlines(params)

async def fetch_oi_chunk(exchange, start_time, end_time=None):
    """Fetch OI history via fapiDataGetOpenInterestHist"""
    params = {
        'symbol': SYMBOL,
        'period': INTERVAL,
        'limit': OI_LIMIT,
        'startTime': start_time
    }
    if end_time:
        params['endTime'] = end_time
    return await exchange.fapiDataGetOpenInterestHist(params)

async def fetch_fgi_history(limit=1000):
    """Fetch historical Fear & Greed Index from Alternative.me"""
    import httpx
    url = f"https://api.alternative.me/fng/?limit={limit}&format=json"
    _log("BACKFILL", f"Fetching FGI history (limit={limit})...")
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        if resp.status_code == 200:
            data = resp.json()
            # FGI is daily. We'll map it by timestamp (it provides daily reset timestamp)
            fgi_map = {}
            for item in data['data']:
                ts = int(item['timestamp']) * 1000 # Convert to ms
                fgi_map[ts] = float(item['value'])
            _log("BACKFILL", f"  Got {len(fgi_map)} FGI records.")
            return fgi_map
    return {}

async def run_backfill():
    _log("BACKFILL", f"Starting 1-Year Historical Data Expansion for {SYMBOL}")
    
    db = DuckDBManager()
    exchange = ccxt.binance({
        "enableRateLimit": True,
        "options": {"defaultType": "future"}
    })
    
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (DAYS_TO_FETCH * 24 * 60 * 60 * 1000)
    
    # ── 1. Fetch Klines (OHLCV + CVD) ──
    _log("BACKFILL", f"Fetching Klines from {datetime.fromtimestamp(start_ms/1000).strftime('%Y-%m-%d')}...")
    all_klines = []
    current_start = start_ms
    
    while current_start < now_ms:
        try:
            klines = await fetch_klines_chunk(exchange, current_start)
            if not klines:
                break
                
            all_klines.extend(klines)
            _log("BACKFILL", f"  Got {len(klines)} candles. Latest: {datetime.fromtimestamp(klines[-1][0]/1000).strftime('%Y-%m-%d')}")
            
            # Next start time = last candle open time + 1ms to avoid overlap
            next_start = klines[-1][0] + 1
            if next_start <= current_start or len(klines) < KLINES_LIMIT:
                break
            current_start = next_start
            await asyncio.sleep(1.0) # Rate limit safety
        except Exception as e:
            _log("BACKFILL", f"Kline fetch error: {e}")
            await asyncio.sleep(5.0)
            
    # Remove duplicates if any
    all_klines = {k[0]: k for k in all_klines}.values()
    all_klines = sorted(all_klines, key=lambda x: x[0])
    
    _log("BACKFILL", f"Total distinct 4H candles fetched: {len(all_klines)}")
    
    # ── 2. Fetch Open Interest History ──
    _log("BACKFILL", "Fetching Open Interest History (Backwards)...")
    all_oi = {}
    current_end = now_ms
    
    while current_end > start_ms:
        try:
            oi_chunk = await fetch_oi_chunk(exchange, None, current_end)
            if not oi_chunk:
                break
                
            for row in oi_chunk:
                all_oi[int(row["timestamp"])] = float(row["sumOpenInterestValue"])
                
            oldest_record_in_chunk = int(oi_chunk[0]["timestamp"])
            _log("BACKFILL", f"  Got {len(oi_chunk)} OI records. Oldest in this chunk: {datetime.fromtimestamp(oldest_record_in_chunk/1000).strftime('%Y-%m-%d')}")
            
            next_end = oldest_record_in_chunk - 1
            if next_end >= current_end or len(oi_chunk) < OI_LIMIT:
                # We reached the end of history possible or a glitch
                break
            current_end = next_end
            await asyncio.sleep(1.5)
        except Exception as e:
            _log("BACKFILL", f"OI fetch limit reached or error: {e}. Stopping OI fetch here.")
            break

    # ── 3. Fetch FGI History ──
    fgi_history = await fetch_fgi_history(limit=DAYS_TO_FETCH + 10)

    # ── 3. Assemble and Insert ──
    _log("BACKFILL", "Assembling tables...")
    
    ohlcv_data = []
    metrics_data = []
    
    for k in all_klines:
        ts = int(k[0])
        # [timestamp, open, high, low, close, volume, close_time, quote_vol, trades, taker_buy_base, taker_buy_quote, ignore]
        open_p, high_p, low_p, close_p, vol = float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])
        
        # Calculate exactly per-candle CVD
        taker_buy_vol = float(k[9])
        taker_sell_vol = vol - taker_buy_vol
        cvd = taker_buy_vol - taker_sell_vol
        
        # Find closest OI (within 4H = 14400000ms)
        oi_val = 0.0
        # Check an exact match first
        if ts in all_oi:
            oi_val = all_oi[ts]
        else:
            # Finding closest preceding OI
            candidates = [v for t, v in all_oi.items() if t <= ts + 14400000]
            if candidates:
                oi_val = candidates[-1]

        # Find closest FGI (FGI is daily, so we look for the most recent one <= current ts)
        fgi_val = 50.0 # Neutral fallback
        # Filter FGI entries that are on or before the current candle's timestamp
        # Then find the one with the largest timestamp (most recent)
        fgi_candidates = [(t, v) for t, v in fgi_history.items() if t <= ts]
        if fgi_candidates:
            # Sort by timestamp in descending order to get the most recent first
            fgi_candidates.sort(key=lambda x: x[0], reverse=True)
            fgi_val = fgi_candidates[0][1] # Get the value of the most recent FGI

        ohlcv_data.append((ts, open_p, high_p, low_p, close_p, vol, cvd))
        metrics_data.append({
            "timestamp": ts,
            "funding_rate": 0.0,  # difficult to batch backfill reliably, defaulting 0
            "open_interest": oi_val,
            "global_mcap_change": 0.0,
            "order_book_imbalance": 0.0,
            "cvd": cvd,
            "liquidations_buy": 0.0,
            "liquidations_sell": 0.0,
            "fgi_value": fgi_val
        })

    # Prepare DataFrame for OHLCV
    df_ohlcv = pd.DataFrame(ohlcv_data, columns=["timestamp", "open", "high", "low", "close", "volume", "cvd"])
    
    _log("BACKFILL", f"Upserting {len(df_ohlcv)} OHLCV rows to DuckDB...")
    db.upsert_ohlcv(df_ohlcv)
    
    _log("BACKFILL", f"Inserting {len(metrics_data)} Metrics rows to DuckDB...")
    # metrics_data is list of dicts suitable for DuckDBManager.insert_metrics? No, that inserts single.
    # We will bulk insert to avoid 2000 disk I/O ops.
    import duckdb
    con = duckdb.connect(db.db_path)
    tuples = [
        (
            m["timestamp"], m["funding_rate"], m["open_interest"], 
            m["global_mcap_change"], m["order_book_imbalance"], 
            m["cvd"], m["liquidations_buy"], m["liquidations_sell"],
            m["fgi_value"]
        ) for m in metrics_data
    ]
    con.executemany('''
        INSERT OR REPLACE INTO market_metrics 
        (timestamp, funding_rate, open_interest, global_mcap_change, order_book_imbalance, cvd, liquidations_buy, liquidations_sell, fgi_value)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', tuples)
    con.close()

    _log("BACKFILL", "✅ Historical Data Expansion Complete. Database is ready with >2000 periods.")
    await exchange.close()

if __name__ == "__main__":
    asyncio.run(run_backfill())
