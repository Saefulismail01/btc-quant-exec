#!/usr/bin/env python3
import sys

sys.path.insert(0, "/app/backend")
import duckdb

db_path = "/app/backend/app/infrastructure/database/btc-quant.db"
conn = duckdb.connect(db_path, read_only=True)

# Check all trades with OPEN status
open_trades = conn.execute(
    "SELECT id, side, entry_price, status FROM live_trades WHERE status = 'OPEN'"
).fetchall()
print(f"=== OPEN Status Trades: {len(open_trades)} ===")
for t in open_trades:
    print(f"  ID: {t[0][:40]}...")
    print(f"  Side: {t[1]}, Entry: {t[2]}, Status: {t[3]}")
    print()

# Check all statuses
statuses = conn.execute(
    "SELECT status, COUNT(*) FROM live_trades GROUP BY status"
).fetchall()
print("=== Status Summary ===")
for s in statuses:
    print(f"  {s[0]}: {s[1]}")

conn.close()
