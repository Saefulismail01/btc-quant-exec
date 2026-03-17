"""
Scalp V2 - Patience-based scalper.

Strategy: WAIT for price to move significantly, then trade the reversal.
- Collect 5 minutes of price data first (no trading)
- Identify clear support/resistance from actual highs/lows
- Only enter when price hits extreme and starts reversing
- Use tight SL ($0.01) but let TP run ($0.02)

Key difference from V1: PATIENCE. Don't trade immediately.
Wait for a real setup, not noise.
"""
import asyncio
import sys
import os
import time
from pathlib import Path
from datetime import datetime
from collections import deque
from dotenv import load_dotenv

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

# Config
TRADE_SIZE = 0.00021
TP_USD = 0.02  # $0.02 profit target
SL_USD = 0.01  # $0.01 stop loss
WARMUP_SECONDS = 120  # 2 min warmup before trading
POLL_INTERVAL = 3  # seconds


def ts():
    return datetime.now().strftime("%H:%M:%S")


async def get_price():
    config = lighter.Configuration(host=BASE_URL)
    async with lighter.ApiClient(config) as api_client:
        order_api = lighter.OrderApi(api_client)
        book = await order_api.order_book_details(market_id=BTC_MARKET)
        return float(book.order_book_details[0].last_trade_price)


async def get_nonce():
    config = lighter.Configuration(host=BASE_URL)
    async with lighter.ApiClient(config) as api_client:
        tx_api = lighter.TransactionApi(api_client)
        resp = await tx_api.next_nonce(
            account_index=ACCOUNT_INDEX, api_key_index=API_KEY_INDEX
        )
        return resp.nonce


async def check_position():
    config = lighter.Configuration(host=BASE_URL)
    async with lighter.ApiClient(config) as api_client:
        account_api = lighter.AccountApi(api_client)
        account = await account_api.account(by="index", value=str(ACCOUNT_INDEX))
        a = account.accounts[0]
        if a.positions and float(a.positions[0].position) > 0:
            pos = a.positions[0]
            return {
                "side": "LONG" if pos.sign == 1 else "SHORT",
                "size": float(pos.position),
                "entry": float(pos.avg_entry_price),
                "pnl": float(pos.unrealized_pnl),
                "tied_orders": pos.position_tied_order_count,
            }
        return None


async def execute(side, entry_price):
    """Execute entry + SL/TP with proper delays."""
    if side == "LONG":
        tp_price = entry_price + (TP_USD / TRADE_SIZE)
        sl_price = entry_price - (SL_USD / TRADE_SIZE)
    else:
        tp_price = entry_price - (TP_USD / TRADE_SIZE)
        sl_price = entry_price + (SL_USD / TRADE_SIZE)

    print(f"[{ts()}] EXECUTE {side} @ ${entry_price:,.2f}")
    print(f"  TP ${tp_price:,.2f} (+${TP_USD}) | SL ${sl_price:,.2f} (-${SL_USD})")

    nonce = await get_nonce()

    client = lighter.SignerClient(
        url=BASE_URL,
        account_index=ACCOUNT_INDEX,
        api_private_keys={API_KEY_INDEX: API_SECRET},
    )

    # Entry
    base_amount = int(TRADE_SIZE * 1e5)
    avg_price = int(entry_price * 10 * (0.98 if side == "SHORT" else 1.02))

    _, resp, err = await client.create_market_order(
        market_index=BTC_MARKET,
        client_order_index=0,
        base_amount=base_amount,
        avg_execution_price=avg_price,
        is_ask=(side == "SHORT"),
        nonce=nonce,
        api_key_index=API_KEY_INDEX,
    )
    if err:
        print(f"  Entry FAILED: {err}")
        await client.close()
        return False
    print(f"  Entry OK")
    nonce += 1
    time.sleep(3)

    # SL
    sl_scaled = int(sl_price * 10)
    _, _, err_sl = await client.create_order(
        market_index=BTC_MARKET,
        client_order_index=1,
        base_amount=base_amount,
        price=sl_scaled,
        is_ask=(side == "LONG"),
        order_type=lighter.SignerClient.ORDER_TYPE_STOP_LOSS_LIMIT,
        time_in_force=lighter.SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
        trigger_price=sl_scaled,
        reduce_only=1,
        nonce=nonce,
        api_key_index=API_KEY_INDEX,
    )
    if err_sl:
        print(f"  SL FAILED: {err_sl}")
    else:
        print(f"  SL OK")
    nonce += 1
    time.sleep(3)

    # TP
    tp_scaled = int(tp_price * 10)
    _, _, err_tp = await client.create_order(
        market_index=BTC_MARKET,
        client_order_index=2,
        base_amount=base_amount,
        price=tp_scaled,
        is_ask=(side == "LONG"),
        order_type=lighter.SignerClient.ORDER_TYPE_TAKE_PROFIT_LIMIT,
        time_in_force=lighter.SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
        trigger_price=tp_scaled,
        reduce_only=1,
        nonce=nonce,
        api_key_index=API_KEY_INDEX,
    )
    if err_tp:
        print(f"  TP FAILED: {err_tp}")
    else:
        print(f"  TP OK")

    await client.close()

    # Verify
    time.sleep(3)
    pos = await check_position()
    if pos:
        print(f"  VERIFIED: {pos['side']} {pos['size']} @ ${pos['entry']:,.2f}, orders={pos['tied_orders']}")
    else:
        print(f"  WARNING: No position detected")

    return True


async def main():
    print(f"[{ts()}] Scalp V2 - Patience-based")
    print(f"  Size: {TRADE_SIZE} BTC | TP: ${TP_USD} | SL: ${SL_USD}")
    print(f"  R:R = 1:{TP_USD/SL_USD:.0f} (need {SL_USD/TP_USD*100:.0f}% win rate to breakeven)")
    print()

    # Check existing position
    pos = await check_position()
    if pos:
        print(f"[{ts()}] Already in position: {pos['side']} {pos['size']} @ ${pos['entry']:,.2f}")
        print(f"  PnL: ${pos['pnl']:+.6f} | Tied orders: {pos['tied_orders']}")
        print("  Waiting for position to close...")

        while True:
            await asyncio.sleep(5)
            pos = await check_position()
            if not pos:
                print(f"[{ts()}] Position closed!")
                break
            price = await get_price()
            print(f"[{ts()}] BTC ${price:,.2f} | PnL: ${pos['pnl']:+.6f}")

    # Phase 1: WARMUP - collect price data, DO NOT TRADE
    print(f"\n[{ts()}] WARMUP: Collecting {WARMUP_SECONDS}s of price data...")
    prices = deque(maxlen=200)
    warmup_start = time.time()

    while time.time() - warmup_start < WARMUP_SECONDS:
        try:
            price = await get_price()
            prices.append(price)
            elapsed = int(time.time() - warmup_start)
            remaining = WARMUP_SECONDS - elapsed

            if len(prices) >= 3:
                high = max(prices)
                low = min(prices)
                spread = high - low
                print(f"[{ts()}] ${price:,.2f} | Range: ${low:,.2f}-${high:,.2f} (${spread:.1f}) | {remaining}s left")
            else:
                print(f"[{ts()}] ${price:,.2f} | Collecting... {remaining}s left")

            await asyncio.sleep(POLL_INTERVAL)
        except Exception as e:
            print(f"[{ts()}] Error: {e}")
            await asyncio.sleep(POLL_INTERVAL)

    # Phase 2: ANALYZE collected data
    if len(prices) < 10:
        print("Not enough data collected. Exiting.")
        return

    high = max(prices)
    low = min(prices)
    spread = high - low
    avg = sum(prices) / len(prices)
    current = prices[-1]

    print(f"\n[{ts()}] ANALYSIS ({len(prices)} samples)")
    print(f"  High: ${high:,.2f}")
    print(f"  Low:  ${low:,.2f}")
    print(f"  Avg:  ${avg:,.2f}")
    print(f"  Spread: ${spread:.2f}")
    print(f"  Current: ${current:,.2f}")

    # Need minimum spread to have a tradeable range
    # TP needs ~$95 movement (0.02/0.00021), SL needs ~$47 movement
    # If spread < $20, market is too quiet - skip
    if spread < 15:
        print(f"\n  Market too quiet (spread ${spread:.1f} < $15). No trade.")
        print("  Run again when there's more volatility.")
        return

    # Phase 3: WAIT for entry signal
    # Strategy: Price bounces between high and low
    # LONG when price drops near low and starts bouncing
    # SHORT when price rises near high and starts dropping
    print(f"\n[{ts()}] HUNTING: Waiting for price to hit extreme...")

    # Define entry zones
    long_zone = low + spread * 0.2   # bottom 20%
    short_zone = high - spread * 0.2  # top 20%
    print(f"  LONG zone: below ${long_zone:,.2f}")
    print(f"  SHORT zone: above ${short_zone:,.2f}")

    prev_price = current
    consecutive_reversals = 0
    reversal_direction = None

    while True:
        try:
            await asyncio.sleep(POLL_INTERVAL)
            price = await get_price()
            prices.append(price)

            # Update range
            high = max(prices)
            low = min(prices)
            spread = high - low
            long_zone = low + spread * 0.2
            short_zone = high - spread * 0.2

            # Check for reversal pattern
            if price < long_zone:
                if price > prev_price:  # bouncing up from bottom
                    if reversal_direction == "LONG":
                        consecutive_reversals += 1
                    else:
                        reversal_direction = "LONG"
                        consecutive_reversals = 1
                    print(f"[{ts()}] ${price:,.2f} BOUNCE #{consecutive_reversals} (near low ${low:,.2f})")
                else:
                    consecutive_reversals = 0
                    reversal_direction = None
                    print(f"[{ts()}] ${price:,.2f} still dropping...")

            elif price > short_zone:
                if price < prev_price:  # dropping from top
                    if reversal_direction == "SHORT":
                        consecutive_reversals += 1
                    else:
                        reversal_direction = "SHORT"
                        consecutive_reversals = 1
                    print(f"[{ts()}] ${price:,.2f} REJECT #{consecutive_reversals} (near high ${high:,.2f})")
                else:
                    consecutive_reversals = 0
                    reversal_direction = None
                    print(f"[{ts()}] ${price:,.2f} still rising...")
            else:
                consecutive_reversals = 0
                reversal_direction = None
                print(f"[{ts()}] ${price:,.2f} mid-range, waiting...")

            prev_price = price

            # ENTRY: 2 consecutive reversals = confirmed bounce/rejection
            if consecutive_reversals >= 2 and reversal_direction:
                print(f"\n[{ts()}] SIGNAL: {reversal_direction} confirmed with {consecutive_reversals} reversals!")
                success = await execute(reversal_direction, price)
                if success:
                    # Monitor until position closes
                    print(f"\n[{ts()}] Monitoring position...")
                    while True:
                        await asyncio.sleep(5)
                        pos = await check_position()
                        if not pos:
                            print(f"[{ts()}] Position closed!")
                            # Check final balance
                            config = lighter.Configuration(host=BASE_URL)
                            async with lighter.ApiClient(config) as api_client:
                                account_api = lighter.AccountApi(api_client)
                                account = await account_api.account(by="index", value=str(ACCOUNT_INDEX))
                                balance = account.accounts[0].collateral
                                print(f"[{ts()}] Balance: ${balance}")
                            break
                        p = await get_price()
                        print(f"[{ts()}] ${p:,.2f} | PnL: ${pos['pnl']:+.6f}")
                break

        except KeyboardInterrupt:
            print(f"\n[{ts()}] Stopped by user")
            break
        except Exception as e:
            print(f"[{ts()}] Error: {e}")
            await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
