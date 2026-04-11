#!/usr/bin/env python3
import sys

sys.path.insert(0, "/app/backend")
from app.adapters.repositories.live_trade_repository import LiveTradeRepository

repo = LiveTradeRepository()

# Get all trades
import duckdb

conn = duckdb.connect(repo.db_path, read_only=True)
result = conn.execute(
    "SELECT id, side, entry_price, exit_price, sl_price, tp_price, status, pnl_usdt FROM live_trades ORDER BY timestamp_open DESC LIMIT 10"
).fetchall()
print("=== Recent Trades ===")
for row in result:
    print(f"ID: {row[0][:20]}...")
    print(f"  Side: {row[1]}, Entry: {row[2]}, Exit: {row[3]}")
    print(f"  SL: {row[4]}, TP: {row[5]}, Status: {row[6]}, PnL: {row[7]}")
    print()
conn.close()
