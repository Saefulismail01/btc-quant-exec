"""
Professional HFT Bot for BTC Scalping on Lighter.xyz
- Real-time price monitoring
- Technical analysis (momentum, trend)
- Autonomous trade execution with risk management
- Position tracking and PnL monitoring
"""

import asyncio
import sys
import os
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from collections import deque

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

import lighter

BASE_URL = os.getenv("LIGHTER_MAINNET_BASE_URL", "https://mainnet.zklighter.elliot.ai")
API_SECRET = os.getenv("LIGHTER_MAINNET_API_SECRET", "")
# Try with 0x prefix first (SDK may need it)
if not API_SECRET.startswith("0x"):
    API_SECRET = "0x" + API_SECRET
API_KEY_INDEX = int(os.getenv("LIGHTER_API_KEY_INDEX", "3"))
ACCOUNT_INDEX = int(os.getenv("LIGHTER_ACCOUNT_INDEX", "718591"))
BTC_MARKET = 1

# Debug
print(f"[DEBUG] Account: {ACCOUNT_INDEX}, Key Index: {API_KEY_INDEX}, Secret: {API_SECRET[:20]}...", file=sys.stderr)

# === CONFIGURATION ===
TRADE_SIZE = 0.00021  # BTC
TP_PROFIT = 0.01  # USD
SL_LOSS = 0.01  # USD
MOMENTUM_WINDOW = 10  # candles for momentum calc
PRICE_THRESHOLD = 0.50  # min price change USD to trigger trade
MAX_OPEN_TRADES = 1  # safety limit
POLL_INTERVAL = 2  # seconds between price checks


class PriceHistory:
    """Track price history for technical analysis."""
    def __init__(self, window_size=20):
        self.prices = deque(maxlen=window_size)
        self.timestamps = deque(maxlen=window_size)

    def add(self, price: float, timestamp: float = None):
        if timestamp is None:
            timestamp = time.time()
        self.prices.append(price)
        self.timestamps.append(timestamp)

    def get_momentum(self):
        """Calculate price momentum (change from oldest to newest)."""
        if len(self.prices) < 2:
            return 0
        return float(self.prices[-1]) - float(self.prices[0])

    def get_volatility(self):
        """Calculate price volatility (std dev)."""
        if len(self.prices) < 2:
            return 0
        prices = [float(p) for p in self.prices]
        mean = sum(prices) / len(prices)
        variance = sum((p - mean) ** 2 for p in prices) / len(prices)
        return variance ** 0.5

    def get_trend(self):
        """Determine trend: 'UP', 'DOWN', or 'FLAT'."""
        momentum = self.get_momentum()
        if momentum > PRICE_THRESHOLD:
            return "UP"
        elif momentum < -PRICE_THRESHOLD:
            return "DOWN"
        return "FLAT"


class TradePosition:
    """Track an open position."""
    def __init__(self, side: str, entry_price: float, quantity: float, timestamp: float):
        self.side = side
        self.entry_price = entry_price
        self.quantity = quantity
        self.timestamp = timestamp
        self.status = "OPEN"
        self.exit_price = None
        self.pnl = 0.0

    def mark_closed(self, exit_price: float):
        self.exit_price = exit_price
        self.status = "CLOSED"
        if self.side == "LONG":
            self.pnl = (exit_price - self.entry_price) * self.quantity
        else:  # SHORT
            self.pnl = (self.entry_price - exit_price) * self.quantity


class HFTBot:
    """Autonomous HFT Bot for BTC scalping."""

    def __init__(self):
        self.price_history = PriceHistory(window_size=MOMENTUM_WINDOW)
        self.positions = []
        self.last_trade_time = 0
        self.min_trade_interval = 5  # seconds
        self.running = False

    async def get_current_price(self) -> float:
        """Fetch current BTC price from Lighter."""
        config = lighter.Configuration(host=BASE_URL)
        async with lighter.ApiClient(config) as api_client:
            order_api = lighter.OrderApi(api_client)
            btc_book = await order_api.order_book_details(market_id=BTC_MARKET)
            price = float(btc_book.order_book_details[0].last_trade_price)
            return price

    async def get_nonce(self) -> int:
        """Get next nonce for order submission."""
        config = lighter.Configuration(host=BASE_URL)
        async with lighter.ApiClient(config) as api_client:
            tx_api = lighter.TransactionApi(api_client)
            nonce_resp = await tx_api.next_nonce(account_index=ACCOUNT_INDEX, api_key_index=API_KEY_INDEX)
            return nonce_resp.nonce

    async def place_trade(self, side: str, entry_price: float, nonce: int) -> bool:
        """Place entry + SL/TP orders."""
        try:
            client = lighter.SignerClient(
                url=BASE_URL,
                account_index=ACCOUNT_INDEX,
                api_private_keys={API_KEY_INDEX: API_SECRET},
            )
        except Exception as e:
            print(f"  ❌ SignerClient init failed: {e}")
            return False

        # Calculate TP/SL prices
        if side == "LONG":
            tp_price = entry_price + (TP_PROFIT / TRADE_SIZE)
            sl_price = entry_price - (SL_LOSS / TRADE_SIZE)
        else:  # SHORT
            tp_price = entry_price - (TP_PROFIT / TRADE_SIZE)
            sl_price = entry_price + (SL_LOSS / TRADE_SIZE)

        print(f"\n[{self._timestamp()}] 📊 NEW TRADE: {side} {TRADE_SIZE:.5f} BTC @ ${entry_price:,.2f}")
        print(f"  TP: ${tp_price:,.2f} (+${TP_PROFIT})")
        print(f"  SL: ${sl_price:,.2f} (-${SL_LOSS})")

        # 1. Entry market order
        base_amount = int(TRADE_SIZE * 1e5)
        avg_price = int(entry_price * 10 * (1.02 if side == "SHORT" else 0.98))

        try:
            created_order, resp, err = await client.create_market_order(
                market_index=BTC_MARKET,
                client_order_index=0,
                base_amount=base_amount,
                avg_execution_price=avg_price,
                is_ask=(side == "SHORT"),
                nonce=nonce,
                api_key_index=API_KEY_INDEX,
            )
        except Exception as e:
            print(f"  ❌ Entry submission error: {e}")
            await client.close()
            return False

        if err:
            print(f"  ❌ Entry failed: {err}")
            await client.close()
            return False

        print(f"  ✅ Entry TX: {resp.tx_hash if resp else 'pending'}")
        nonce += 1

        # 2. SL order
        sl_base = base_amount
        sl_price_scaled = int(sl_price * 10)

        _, resp_sl, err_sl = await client.create_order(
            market_index=BTC_MARKET,
            client_order_index=1,
            base_amount=sl_base,
            price=sl_price_scaled,
            is_ask=(side == "LONG"),
            order_type=lighter.SignerClient.ORDER_TYPE_STOP_LOSS_LIMIT,
            time_in_force=lighter.SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
            trigger_price=sl_price_scaled,
            reduce_only=1,
            nonce=nonce,
            api_key_index=API_KEY_INDEX,
        )

        if err_sl:
            print(f"  ⚠️  SL failed: {err_sl}")
        else:
            print(f"  ✅ SL TX: {resp_sl.tx_hash if resp_sl else 'pending'}")
            await asyncio.sleep(0.5)
        nonce += 1

        # 3. TP order
        tp_base = base_amount
        tp_price_scaled = int(tp_price * 10)

        _, resp_tp, err_tp = await client.create_order(
            market_index=BTC_MARKET,
            client_order_index=2,
            base_amount=tp_base,
            price=tp_price_scaled,
            is_ask=(side == "LONG"),
            order_type=lighter.SignerClient.ORDER_TYPE_TAKE_PROFIT_LIMIT,
            time_in_force=lighter.SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
            trigger_price=tp_price_scaled,
            reduce_only=1,
            nonce=nonce,
            api_key_index=API_KEY_INDEX,
        )

        if err_tp:
            print(f"  ⚠️  TP failed: {err_tp}")
        else:
            print(f"  ✅ TP TX: {resp_tp.tx_hash if resp_tp else 'pending'}")

        await client.close()

        # Track position
        self.positions.append(TradePosition(side, entry_price, TRADE_SIZE, time.time()))
        self.last_trade_time = time.time()
        return True

    def _timestamp(self) -> str:
        """Return formatted timestamp."""
        return datetime.now().strftime("%H:%M:%S")

    async def analyze_and_trade(self, current_price: float):
        """Analyze momentum and place trade if conditions met."""
        self.price_history.add(current_price)

        # Need minimum history
        if len(self.price_history.prices) < 3:
            return

        # Rate limiting: don't trade too frequently
        if time.time() - self.last_trade_time < self.min_trade_interval:
            return

        # Don't exceed max open trades
        open_count = sum(1 for p in self.positions if p.status == "OPEN")
        if open_count >= MAX_OPEN_TRADES:
            return

        trend = self.price_history.get_trend()
        momentum = self.price_history.get_momentum()
        volatility = self.price_history.get_volatility()

        decision = None

        # LONG: strong uptrend, positive momentum
        if trend == "UP" and momentum > 0.3:
            decision = "LONG"

        # SHORT: strong downtrend, negative momentum
        elif trend == "DOWN" and momentum < -0.3:
            decision = "SHORT"

        if decision:
            nonce = await self.get_nonce()
            success = await self.place_trade(decision, current_price, nonce)
            if not success:
                self.last_trade_time = time.time() - self.min_trade_interval  # allow retry sooner

    async def monitor_loop(self):
        """Main monitoring loop."""
        self.running = True
        print(f"\n[{self._timestamp()}] 🚀 HFT Bot started (monitoring BTC {TRADE_SIZE:.5f} BTC trades)")
        print(f"   TP: ${TP_PROFIT}, SL: ${SL_LOSS}, Max open: {MAX_OPEN_TRADES}")
        print(f"   Poll interval: {POLL_INTERVAL}s, Min trade interval: {self.min_trade_interval}s\n")

        try:
            while self.running:
                try:
                    price = await self.get_current_price()

                    # Print price and position status
                    open_count = sum(1 for p in self.positions if p.status == "OPEN")
                    total_pnl = sum(p.pnl for p in self.positions)

                    status = f"${price:,.2f}"
                    if open_count > 0:
                        status += f" | Open: {open_count} | PnL: ${total_pnl:+.4f}"

                    print(f"[{self._timestamp()}] BTC {status}")

                    # Analyze and potentially trade
                    await self.analyze_and_trade(price)

                    await asyncio.sleep(POLL_INTERVAL)

                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"[{self._timestamp()}] ⚠️  Error: {e}")
                    await asyncio.sleep(POLL_INTERVAL)

        finally:
            self.running = False
            print(f"\n[{self._timestamp()}] 🛑 Bot stopped")

            # Print summary
            if self.positions:
                print("\n=== Trade Summary ===")
                for i, pos in enumerate(self.positions, 1):
                    status = pos.status
                    pnl_str = f"${pos.pnl:+.4f}" if pos.exit_price else "OPEN"
                    print(f"{i}. {pos.side} {pos.quantity:.5f} @ ${pos.entry_price:,.2f} | {status} | PnL: {pnl_str}")

                total_pnl = sum(p.pnl for p in self.positions)
                print(f"\nTotal PnL: ${total_pnl:+.4f}")


async def main():
    """Entry point."""
    bot = HFTBot()

    try:
        # Test connection first
        print("Testing connection to Lighter mainnet...")
        price = await bot.get_current_price()
        print(f"✅ Connected! Current BTC: ${price:,.2f}\n")

        # Start monitoring
        await bot.monitor_loop()

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
