#!/usr/bin/env python3
import sys

sys.path.insert(0, "/app/backend")
from app.adapters.repositories.live_trade_repository import LiveTradeRepository

repo = LiveTradeRepository()
trade = repo.get_open_trade()
if trade:
    print(f"ID: {trade.id}")
    print(f"Side: {trade.side}")
    print(f"Entry: {trade.entry_price}")
    print(f"Status: {trade.status}")
    print(f"SL: {trade.sl_price}")
    print(f"TP: {trade.tp_price}")
else:
    print("No open trade in DB")
