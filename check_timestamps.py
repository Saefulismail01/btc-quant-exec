#!/usr/bin/env python3
import sys

sys.path.insert(0, "/app/backend")
from app.adapters.repositories.live_trade_repository import LiveTradeRepository

repo = LiveTradeRepository()

import duckdb
from datetime import datetime

conn = duckdb.connect(repo.db_path, read_only=True)
result = conn.execute("""
    SELECT id, side, entry_price, exit_price, sl_price, tp_price, status, pnl_usdt, 
           timestamp_open, timestamp_close 
    FROM live_trades 
    ORDER BY timestamp_open DESC 
    LIMIT 5
""").fetchall()

print("=== Recent Trades with Timestamps ===")
for row in result:
    ts_open = datetime.fromtimestamp(row[8] / 1000) if row[8] else "N/A"
    ts_close = datetime.fromtimestamp(row[9] / 1000) if row[9] else "N/A"
    print(f"ID: {row[0][:30]}...")
    print(f"  Entry: {row[2]}, Exit: {row[3]}")
    print(f"  Status: {row[6]}, PnL: {row[7]}")
    print(f"  Opened: {ts_open}, Closed: {ts_close}")
    print()
conn.close()
