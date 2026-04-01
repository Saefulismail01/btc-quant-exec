"""
01_fetch_data.py
Fetch 15m and 1h klines from Binance for each of the 26 trades.
Saves per-trade JSON to ./data/ directory.
"""

import json
import time
import os
from datetime import datetime, timezone
import urllib.request
import urllib.parse

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TRADES = [
    {"id": 1,  "date": "2026-03-10 16:05", "side": "LONG",  "entry": 71198},
    {"id": 2,  "date": "2026-03-11 04:08", "side": "LONG",  "entry": 69498},
    {"id": 3,  "date": "2026-03-11 08:06", "side": "LONG",  "entry": 69620},
    {"id": 4,  "date": "2026-03-12 08:05", "side": "LONG",  "entry": 69846},
    {"id": 5,  "date": "2026-03-12 12:15", "side": "LONG",  "entry": 70309},
    {"id": 6,  "date": "2026-03-12 20:09", "side": "LONG",  "entry": 70401},
    {"id": 7,  "date": "2026-03-13 04:03", "side": "LONG",  "entry": 71347},
    {"id": 8,  "date": "2026-03-13 08:02", "side": "LONG",  "entry": 71520},
    {"id": 9,  "date": "2026-03-13 14:13", "side": "LONG",  "entry": 73500},
    {"id": 10, "date": "2026-03-13 16:02", "side": "LONG",  "entry": 71891},
    {"id": 11, "date": "2026-03-16 08:14", "side": "LONG",  "entry": 73545},
    {"id": 12, "date": "2026-03-16 16:01", "side": "LONG",  "entry": 73172},
    {"id": 13, "date": "2026-03-17 00:51", "side": "LONG",  "entry": 74930},
    {"id": 14, "date": "2026-03-17 02:07", "side": "LONG",  "entry": 75287},
    {"id": 15, "date": "2026-03-17 04:02", "side": "LONG",  "entry": 74562},
    {"id": 16, "date": "2026-03-17 07:21", "side": "LONG",  "entry": 74319},
    {"id": 17, "date": "2026-03-17 12:00", "side": "LONG",  "entry": 74013},
    {"id": 18, "date": "2026-03-22 00:00", "side": "SHORT", "entry": 68744},
    {"id": 19, "date": "2026-03-22 08:00", "side": "SHORT", "entry": 68860},
    {"id": 20, "date": "2026-03-22 12:00", "side": "SHORT", "entry": 68217},
    {"id": 21, "date": "2026-03-23 00:00", "side": "SHORT", "entry": 67975},
    {"id": 22, "date": "2026-03-26 12:00", "side": "SHORT", "entry": 69215},
    {"id": 23, "date": "2026-03-26 13:44", "side": "SHORT", "entry": 69385},
    {"id": 24, "date": "2026-03-27 04:00", "side": "SHORT", "entry": 68702},
    {"id": 25, "date": "2026-03-28 08:00", "side": "SHORT", "entry": 66460},
    {"id": 26, "date": "2026-03-28 16:00", "side": "SHORT", "entry": 66998},
]

BASE_URL = "https://api.binance.com/api/v3/klines"


def date_to_ms(date_str: str) -> int:
    """Convert 'YYYY-MM-DD HH:MM' UTC string to milliseconds timestamp."""
    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def fetch_klines(symbol: str, interval: str, start_ms: int, limit: int) -> list:
    params = urllib.parse.urlencode({
        "symbol": symbol,
        "interval": interval,
        "startTime": start_ms,
        "limit": limit,
    })
    url = f"{BASE_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def kline_to_dict(k: list) -> dict:
    """Convert raw Binance kline list to named dict."""
    return {
        "open_time": k[0],
        "open":  float(k[1]),
        "high":  float(k[2]),
        "low":   float(k[3]),
        "close": float(k[4]),
        "volume": float(k[5]),
        "close_time": k[6],
        "quote_volume": float(k[7]),
        "num_trades": int(k[8]),
        "taker_buy_volume": float(k[9]),
        "taker_buy_quote_volume": float(k[10]),
    }


def fetch_trade(trade: dict) -> dict:
    tid = trade["id"]
    start_ms = date_to_ms(trade["date"])

    print(f"  Trade {tid:2d} | {trade['date']} | {trade['side']:5s} | entry={trade['entry']}")

    # 15m candles: 100 candles = ~25h (enough for 24h sim with buffer)
    raw_15m = fetch_klines("BTCUSDT", "15m", start_ms, 100)
    candles_15m = [kline_to_dict(k) for k in raw_15m]
    time.sleep(0.25)

    # 1h candles: 30 candles = 30h
    raw_1h = fetch_klines("BTCUSDT", "1h", start_ms, 30)
    candles_1h = [kline_to_dict(k) for k in raw_1h]
    time.sleep(0.25)

    return {
        "trade": trade,
        "start_ms": start_ms,
        "candles_15m": candles_15m,
        "candles_1h": candles_1h,
    }


def main():
    print(f"Fetching data for {len(TRADES)} trades from Binance...\n")
    results = []
    for trade in TRADES:
        try:
            data = fetch_trade(trade)
            results.append(data)
            out_path = os.path.join(OUTPUT_DIR, f"trade_{trade['id']:02d}.json")
            with open(out_path, "w") as f:
                json.dump(data, f, indent=2)
            print(f"    -> Saved {len(data['candles_15m'])} x 15m, {len(data['candles_1h'])} x 1h candles")
        except Exception as e:
            print(f"    -> ERROR: {e}")

    # Save combined file
    combined_path = os.path.join(OUTPUT_DIR, "all_trades.json")
    with open(combined_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nAll data saved to {OUTPUT_DIR}")
    print(f"Combined file: {combined_path}")


if __name__ == "__main__":
    main()
