"""
Script untuk test koneksi dan order ke Lighter mainnet.

Tahapan:
1. Cek koneksi REST API (GET /markets, GET /account)
2. Cek balance USDC
3. Fetch harga BTC saat ini
4. (Opsional) Place real market order kecil $1

Jalankan dari folder backend/:
    python scripts/test_lighter_connection.py
    python scripts/test_lighter_connection.py --place-order
"""

import asyncio
import sys
import os
import argparse
from pathlib import Path

# Add backend/ to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

import aiohttp

# lighter SDK hanya bisa dijalankan di Linux (butuh libc)
# REST-only mode bisa dijalankan di Windows
try:
    import lighter  # type: ignore[import]
    LIGHTER_SDK_AVAILABLE = True
except (RuntimeError, ImportError) as e:
    LIGHTER_SDK_AVAILABLE = False
    print(f"⚠️  lighter SDK tidak tersedia ({e})")
    print("   REST-only mode: test koneksi API tanpa SDK (order tidak bisa ditest)")
    print("   Untuk test order, jalankan di VPS Linux.\n")

BASE_URL = os.getenv("LIGHTER_MAINNET_BASE_URL", "https://mainnet.zklighter.elliot.ai")
API_KEY   = os.getenv("LIGHTER_MAINNET_API_KEY", "")
API_SECRET = os.getenv("LIGHTER_MAINNET_API_SECRET", "")
API_KEY_INDEX  = int(os.getenv("LIGHTER_API_KEY_INDEX", "3"))
ACCOUNT_INDEX  = int(os.getenv("LIGHTER_ACCOUNT_INDEX", "3"))

BTC_MARKET_INDEX = 1  # BTC/USDC di Lighter


def sep(title: str):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print('='*50)


async def test_rest_api():
    """Test 1: Cek REST API bisa diakses."""
    sep("TEST 1: REST API Connection")
    config = lighter.Configuration(host=BASE_URL)
    async with lighter.ApiClient(config) as api_client:
        order_api = lighter.OrderApi(api_client)

        # Fetch semua order books
        order_books = await order_api.order_books()
        print(f"✅ Connected! Markets tersedia: {len(order_books.order_books)}")
        for book in order_books.order_books[:5]:
            print(f"   Market {book.market_id}: {book}")

        # Fetch BTC order book detail
        btc_book = await order_api.order_book_details(market_id=BTC_MARKET_INDEX)
        details = btc_book.order_book_details[0]
        mid_price = float(details.last_trade_price)
        print(f"\n✅ BTC/USDC Last Trade Price: ${mid_price:,.2f}")
        return mid_price


async def test_account(mid_price: float):
    """Test 2: Cek account balance."""
    sep("TEST 2: Account Balance")
    config = lighter.Configuration(host=BASE_URL)
    async with lighter.ApiClient(config) as api_client:
        account_api = lighter.AccountApi(api_client)

        account = await account_api.account(by="index", value=str(ACCOUNT_INDEX))
        print(f"✅ Account index: {ACCOUNT_INDEX}")
        print(f"\n   Raw account data: {account}")
        return account


async def test_nonce():
    """Test 3: Fetch nonce dari server."""
    sep("TEST 3: Account Nonce")
    config = lighter.Configuration(host=BASE_URL)
    async with lighter.ApiClient(config) as api_client:
        tx_api = lighter.TransactionApi(api_client)

        nonce_resp = await tx_api.next_nonce(
            account_index=ACCOUNT_INDEX,
            api_key_index=API_KEY_INDEX
        )
        print(f"✅ Current nonce: {nonce_resp.nonce}")
        return nonce_resp.nonce


async def test_place_order(mid_price: float, server_nonce: int):
    """Test 4: Place market order $1 (BUY LONG)."""
    sep("TEST 4: Place Market Order ($1 LONG)")

    # BTC minimum: 0.00020 BTC, size_decimals=5 (scaled by 1e5)
    # Pakai 0.00021 BTC (sedikit di atas minimum)
    quantity_btc = 0.00021
    base_amount = 21  # 0.00021 * 1e5
    notional_usd = quantity_btc * mid_price

    print(f"   Entry price: ${mid_price:,.2f}")
    print(f"   Notional: ${notional_usd}")
    print(f"   BTC qty: {quantity_btc:.8f} BTC")
    print(f"   base_amount (scaled): {base_amount}")
    print(f"   Nonce: {server_nonce}")

    # Slippage 2% untuk market order, price_decimals=1 untuk BTC
    avg_exec_price = int(mid_price * 10 * 1.02)  # price_decimals=1, +2% slippage untuk BUY

    print(f"   avg_execution_price (scaled): {avg_exec_price}")
    print(f"\n⚡ Submitting order...")

    client = lighter.SignerClient(
        url=BASE_URL,
        account_index=ACCOUNT_INDEX,
        api_private_keys={API_KEY_INDEX: API_SECRET},
    )

    tx = await client.create_market_order(
        market_index=BTC_MARKET_INDEX,
        client_order_index=0,
        base_amount=base_amount,
        avg_execution_price=avg_exec_price,
        is_ask=False,  # False = BUY
    )

    await client.close()

    print(f"\n✅ ORDER SUBMITTED!")
    print(f"   TX: {tx}")
    return tx


async def main(place_order: bool = False):
    print("\n🚀 Lighter Mainnet Connection Test")
    print(f"   URL: {BASE_URL}")
    print(f"   Account Index: {ACCOUNT_INDEX}")
    print(f"   API Key Index: {API_KEY_INDEX}")
    print(f"   API Key: {API_KEY[:12]}...")

    try:
        mid_price = await test_rest_api()
        await test_account(mid_price)
        server_nonce = await test_nonce()

        if place_order:
            confirm = input(f"\n⚠️  AKAN PLACE REAL ORDER $1 di MAINNET. Lanjut? (yes/no): ")
            if confirm.strip().lower() == "yes":
                await test_place_order(mid_price, server_nonce)
            else:
                print("❌ Order dibatalkan.")
        else:
            print(f"\n{'='*50}")
            print("✅ Semua test koneksi PASSED!")
            print("   Untuk test place order: python scripts/test_lighter_connection.py --place-order")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--place-order", action="store_true", help="Place real $1 market order")
    args = parser.parse_args()

    asyncio.run(main(place_order=args.place_order))
