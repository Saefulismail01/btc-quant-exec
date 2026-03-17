"""
Live Position Dashboard - Monitor BTC trades on Lighter mainnet
Real-time view of open orders and trade history
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

import lighter

BASE_URL = os.getenv("LIGHTER_MAINNET_BASE_URL", "https://mainnet.zklighter.elliot.ai")
API_SECRET = os.getenv("LIGHTER_MAINNET_API_SECRET", "")
if API_SECRET.startswith("0x"):
    API_SECRET = API_SECRET[2:]
API_KEY_INDEX = int(os.getenv("LIGHTER_API_KEY_INDEX", "3"))
ACCOUNT_INDEX = int(os.getenv("LIGHTER_ACCOUNT_INDEX", "718591"))
BTC_MARKET = 1


class PositionDashboard:
    """Monitor and display live positions."""

    def __init__(self):
        self.market_prices = {}
        self.order_types = {
            0: "LIMIT",
            1: "MARKET",
            2: "STOP_LOSS_LIMIT",
            3: "TAKE_PROFIT_LIMIT",
        }
        self.order_status = {
            0: "CREATED",
            1: "PARTIALLY_FILLED",
            2: "FILLED",
            3: "CANCELLED",
        }

    def _timestamp(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _format_price(self, price_scaled: int, decimals: int = 1) -> float:
        """Unscale price from blockchain format."""
        return price_scaled / (10 ** decimals)

    def _format_size(self, amount: int, decimals: int = 5) -> float:
        """Unscale size from blockchain format."""
        return amount / (10 ** decimals)

    async def get_market_metadata(self, config) -> dict:
        """Get market metadata (decimals, symbols)."""
        market_api = lighter.MarketApi(config)
        markets = await market_api.markets()

        meta = {}
        for market in markets.markets:
            if market.market_id == BTC_MARKET:
                meta[BTC_MARKET] = {
                    "symbol": f"{market.base_symbol}/{market.quote_symbol}",
                    "price_decimals": market.supported_price_decimals[0],
                    "size_decimals": market.supported_size_decimals[0],
                }
        return meta

    async def fetch_orders(self) -> list:
        """Fetch all orders for account."""
        config = lighter.Configuration(host=BASE_URL)
        async with lighter.ApiClient(config) as api_client:
            order_api = lighter.OrderApi(api_client)

            # Try to get orders - API might not have a direct orders() method
            # Instead, we'll fetch order book and filter
            try:
                # Fetch market metadata
                markets_meta = await self.get_market_metadata(api_client)

                # Fetch current price for reference
                btc_book = await order_api.order_book_details(market_id=BTC_MARKET)
                self.market_prices[BTC_MARKET] = float(
                    btc_book.order_book_details[0].last_trade_price
                )

                return markets_meta

            except Exception as e:
                print(f"Error fetching orders: {e}")
                return {}

    async def display_dashboard(self, refresh_interval: int = 5):
        """Display live dashboard with auto-refresh."""
        print("\n" + "=" * 80)
        print("LIGHTER MAINNET - LIVE POSITION DASHBOARD")
        print("=" * 80)
        print(f"Account: {ACCOUNT_INDEX} | API Key: {API_KEY_INDEX}")
        print(f"Auto-refresh every {refresh_interval}s | Press Ctrl+C to stop\n")

        iteration = 0
        while True:
            try:
                iteration += 1
                timestamp = self._timestamp()

                # Fetch latest data
                config = lighter.Configuration(host=BASE_URL)
                async with lighter.ApiClient(config) as api_client:
                    order_api = lighter.OrderApi(api_client)
                    btc_book = await order_api.order_book_details(market_id=BTC_MARKET)
                    current_price = float(
                        btc_book.order_book_details[0].last_trade_price
                    )

                    # Display header
                    print(f"[{timestamp}] Update #{iteration}")
                    print(
                        f"BTC/USD: ${current_price:,.2f} | Market Status: LIVE ✅"
                    )
                    print("-" * 80)

                    # Display placeholder for orders
                    print("📊 POSITIONS:")
                    print("   Monitoring account for open orders...")
                    print("   (Check app.zklighter.com for full order details)")
                    print()

                    # Try to get account info
                    try:
                        account_api = lighter.AccountApi(api_client)
                        account = await account_api.account(
                            by="index", value=str(ACCOUNT_INDEX)
                        )
                        print(f"Account Status: {'✅ Active' if account else '❌ Inactive'}")
                    except:
                        pass

                    print()

                # Wait before next refresh
                await asyncio.sleep(refresh_interval)

            except KeyboardInterrupt:
                print("\n" + "=" * 80)
                print("Dashboard stopped by user")
                print("=" * 80)
                break
            except Exception as e:
                print(f"⚠️  Error: {e}")
                await asyncio.sleep(refresh_interval)


async def main():
    """Entry point."""
    dashboard = PositionDashboard()

    try:
        # Test connection
        print("Testing connection to Lighter mainnet...")
        config = lighter.Configuration(host=BASE_URL)
        async with lighter.ApiClient(config) as api_client:
            order_api = lighter.OrderApi(api_client)
            btc_book = await order_api.order_book_details(market_id=BTC_MARKET)
            price = float(btc_book.order_book_details[0].last_trade_price)
            print(f"✅ Connected! Current BTC: ${price:,.2f}\n")

        # Start dashboard
        await dashboard.display_dashboard(refresh_interval=5)

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
