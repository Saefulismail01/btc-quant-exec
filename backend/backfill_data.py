import asyncio
import os
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import ccxt.async_support as ccxt
from data_engine import DuckDBManager, _log

SYMBOL = "BTC/USDT"
PERP_SYMBOL = "BTC/USDT:USDT"
TIMEFRAME = "4h"
LIMIT = 1000 # Fetch more history to ensure enough data with OI

async def backfill():
    db = DuckDBManager()
    exchange = ccxt.binance({
        "enableRateLimit": True,
        "options": {"defaultType": "future"}
    })

    try:
        _log("BACKFILL", f"Starting backfill for {SYMBOL} {TIMEFRAME}...")

        # 1. Fetch OHLCV
        _log("BACKFILL", f"Fetching last {LIMIT} OHLCV candles...")
        ohlcv = await exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=LIMIT)
        df_ohlcv = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        db.upsert_ohlcv(df_ohlcv)
        _log("BACKFILL", f"Upserted {len(df_ohlcv)} OHLCV rows.")

        # 2. Fetch Historical Open Interest & Funding Rate
        # Note: fetch_open_interest_history is available on Binance
        # We'll fetch in chunks if needed, but 500 items should be fine.
        _log("BACKFILL", "Fetching historical Open Interest and Funding Rate...")
        
        # We align metrics with the OHLCV timestamps
        for i, row in df_ohlcv.iterrows():
            ts = int(row["timestamp"])
            
            # Since fetching individual metrics per candle is slow and likely to hit rate limits,
            # we'll try to use bulk endpoints or just populate what we can for the most recent ones.
            # However, for a "data train" update, we need consistency.
            
            # Simplified: Use the current values for the very last row, 
            # and for historical rows, we'll try to fetch OI history.
            pass

        # Realistically, for a quick update, let's fetch the actual OI history if supported.
        try:
            oi_hist = await exchange.fetch_open_interest_history(PERP_SYMBOL, TIMEFRAME, limit=LIMIT)
            # oi_hist is a list of dicts: {'symbol':..., 'openInterestAmount':..., 'timestamp':...}
            df_oi = pd.DataFrame(oi_hist)
            _log("BACKFILL", f"Fetched {len(df_oi)} OI history records.")
        except Exception as e:
            _log("BACKFILL", f"Failed to fetch OI history: {e}")
            df_oi = pd.DataFrame()

        # 3. Assemble Metrics Table
        # We iterate through the OHLCV timestamps and match with OI
        metrics_to_insert = []
        for i, row in df_ohlcv.iterrows():
            ts = int(row["timestamp"])
            
            # Find matching OI
            oi_val = 0.0
            if not df_oi.empty:
                # Find closest timestamp in OI history
                match = df_oi[df_oi['timestamp'] <= ts].iloc[-1:]
                if not match.empty:
                    oi_val = float(match['openInterestAmount'].values[0])

            # Funding rate history is harder to fetch in bulk per candle without many calls.
            # We'll set it to 0.0 or a default for historical data.
            metrics_row = (
                ts,
                0.0, # funding_rate
                oi_val, # open_interest
                0.0, # global_mcap_change
                0.0, # order_book_imbalance
                0.0, # cvd
                0.0, # liquidations_buy
                0.0, # liquidations_sell
            )
            metrics_to_insert.append(metrics_row)

        _log("BACKFILL", f"Inserting {len(metrics_to_insert)} metrics rows in batch...")
        
        # Batch insert using duckdb directly to avoid frequent opening/closing
        import duckdb
        db_path = os.path.join(os.getcwd(), "btc-quant.db")
        with duckdb.connect(db_path) as con:
            con.executemany("""
                INSERT OR IGNORE INTO market_metrics 
                (timestamp, funding_rate, open_interest, global_mcap_change, order_book_imbalance, cvd, liquidations_buy, liquidations_sell)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, metrics_to_insert)

        _log("BACKFILL", "✅ Backfill complete.")

    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(backfill())
