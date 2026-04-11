#!/usr/bin/env python3
import sqlite3
import sys

conn = sqlite3.connect(sys.argv[1])
cur = conn.cursor()
cur.execute(
    "SELECT id, side, entry_price, status, timestamp_open FROM live_trades ORDER BY timestamp_open DESC LIMIT 5"
)
for row in cur.fetchall():
    print(row)
conn.close()
