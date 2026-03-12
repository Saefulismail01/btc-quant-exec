#!/usr/bin/env python3
"""
Test Binance Futures Demo Trading connection.
Usage: python test_testnet_connection.py
"""

import os
import sys
import hmac
import hashlib
import time
import json
import urllib.request
from pathlib import Path
from dotenv import load_dotenv

# Fix Unicode/emoji support on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# Load .env from backend directory
load_dotenv(Path(__file__).parent / ".env")

BASE_URL = "https://demo-fapi.binance.com"


def sign_request(secret: str, params: str) -> str:
    return hmac.new(secret.encode(), params.encode(), hashlib.sha256).hexdigest()


def get(path: str, api_key: str, secret: str, params: dict = None) -> dict:
    ts = int(time.time() * 1000)
    query = f"timestamp={ts}"
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items()) + f"&timestamp={ts}"
    sig = sign_request(secret, query)
    url = f"{BASE_URL}{path}?{query}&signature={sig}"
    req = urllib.request.Request(url, headers={"X-MBX-APIKEY": api_key})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def main():
    api_key = os.getenv("BINANCE_TESTNET_API_KEY", "").strip()
    secret = os.getenv("BINANCE_TESTNET_SECRET", "").strip()

    if not api_key or not secret:
        print("ERROR: BINANCE_TESTNET_API_KEY or BINANCE_TESTNET_SECRET not set in .env")
        sys.exit(1)

    print("Connecting to Binance Futures Demo Trading (demo-fapi.binance.com)...")

    # Test 1: Account balance
    print("\n1. Fetching account balance...")
    try:
        data = get("/fapi/v2/balance", api_key, secret)
        usdt = next((x for x in data if x["asset"] == "USDT"), None)
        if usdt:
            print(f"   OK - Balance (USDT):")
            print(f"      Free:  ${float(usdt['availableBalance']):,.2f}")
            print(f"      Total: ${float(usdt['balance']):,.2f}")
        else:
            print(f"   OK - No USDT balance found (assets: {[x['asset'] for x in data[:5]]})")
    except Exception as e:
        print(f"   FAIL: {e}")
        sys.exit(1)

    # Test 2: Current BTC price
    print("\n2. Fetching BTC/USDT price...")
    try:
        url = f"{BASE_URL}/fapi/v1/ticker/price?symbol=BTCUSDT"
        with urllib.request.urlopen(url, timeout=10) as r:
            ticker = json.loads(r.read().decode())
        print(f"   OK - Price: ${float(ticker['price']):,.2f}")
    except Exception as e:
        print(f"   FAIL: {e}")

    # Test 3: Open positions
    print("\n3. Checking open positions...")
    try:
        data = get("/fapi/v2/positionRisk", api_key, secret, {"symbol": "BTCUSDT"})
        pos = next((p for p in data if float(p.get("positionAmt", 0)) != 0), None)
        if pos:
            print(f"   WARNING - Open position detected:")
            print(f"      Side: {'LONG' if float(pos['positionAmt']) > 0 else 'SHORT'}")
            print(f"      Amt:  {pos['positionAmt']} BTC")
            print(f"      Entry: ${float(pos['entryPrice']):,.2f}")
        else:
            print("   OK - No open positions (clean state)")
    except Exception as e:
        print(f"   FAIL: {e}")

    print("\n" + "="*60)
    print("DEMO TRADING CONNECTION SUCCESSFUL")
    print("="*60)
    print("\nNext steps:")
    print("  1. Start API: python -m uvicorn app.main:app --reload")
    print("  2. Start daemon: python live_executor.py")
    print("  3. Check status: curl http://localhost:8000/api/execution/status")


if __name__ == "__main__":
    main()
