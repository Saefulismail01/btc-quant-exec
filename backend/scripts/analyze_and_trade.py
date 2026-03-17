"""
Analyze BTC market and execute one profitable trade.
Uses recent trades data for momentum + mean reversion analysis.
"""
import asyncio
import sys
import os
import time
from pathlib import Path
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
TRADE_SIZE = 0.00021


async def get_market_data():
    """Get recent trades and orderbook for analysis."""
    config = lighter.Configuration(host=BASE_URL)
    async with lighter.ApiClient(config) as api_client:
        order_api = lighter.OrderApi(api_client)

        # Recent trades - price already in USD from API
        recent = await order_api.recent_trades(market_id=BTC_MARKET, limit=50)
        prices = [float(t.price) for t in recent.trades]

        # Current orderbook
        book = await order_api.order_book_details(market_id=BTC_MARKET)
        current = float(book.order_book_details[0].last_trade_price)

        return current, prices


def analyze(current, prices):
    """Analyze market data and decide direction."""
    if len(prices) < 10:
        return None, "Not enough data"

    high = max(prices)
    low = min(prices)
    spread = high - low
    avg = sum(prices) / len(prices)

    # Split into halves for trend
    first_half = prices[len(prices)//2:]  # older
    second_half = prices[:len(prices)//2]  # newer
    avg_old = sum(first_half) / len(first_half)
    avg_new = sum(second_half) / len(second_half)

    # Momentum (newer vs older)
    momentum = avg_new - avg_old

    # Position in range (0=bottom, 100=top)
    pos_pct = ((current - low) / spread * 100) if spread > 0 else 50

    # Recent 5 trades direction
    recent_5 = prices[:5]
    recent_trend = recent_5[0] - recent_5[-1]  # positive = going up

    print(f"  Current: ${current:,.2f}")
    print(f"  Range: ${low:,.2f} - ${high:,.2f} (${spread:.1f})")
    print(f"  Average: ${avg:,.2f}")
    print(f"  Momentum: ${momentum:+.1f}")
    print(f"  Position in range: {pos_pct:.0f}%")
    print(f"  Recent 5 trend: ${recent_trend:+.1f}")

    # STRATEGY: Mean reversion + momentum confirmation
    #
    # LONG when:
    #   - Price near bottom of range (< 30%)
    #   - Recent trend turning up (buyers stepping in)
    #
    # SHORT when:
    #   - Price near top of range (> 70%)
    #   - Recent trend turning down (sellers stepping in)
    #
    # SKIP when:
    #   - Price in middle (30-70%) = no edge
    #   - Spread too tight (< $5) = no room for profit

    # TP needs price to move ~$47.62 (0.01 / 0.00021)
    # Strategy: trade WITH the short-term momentum, not against it
    # Mean reversion doesn't work on 50-trade window (too short)
    # Instead: momentum continuation + confirmation

    # Strong momentum down = SHORT (price likely to continue)
    if momentum < -1.0 and recent_trend < 0:
        return "SHORT", f"Strong downtrend: momentum ${momentum:+.1f}, recent ${recent_trend:+.1f}"

    # Strong momentum up = LONG
    if momentum > 1.0 and recent_trend > 0:
        return "LONG", f"Strong uptrend: momentum ${momentum:+.1f}, recent ${recent_trend:+.1f}"

    # Moderate momentum with confirmation
    if momentum < -0.3 and recent_trend < -1.0:
        return "SHORT", f"Downtrend confirmed: momentum ${momentum:+.1f}, recent ${recent_trend:+.1f}"

    if momentum > 0.3 and recent_trend > 1.0:
        return "LONG", f"Uptrend confirmed: momentum ${momentum:+.1f}, recent ${recent_trend:+.1f}"

    return None, f"No clear signal (momentum ${momentum:+.1f}, recent ${recent_trend:+.1f})"


async def execute_trade(side, entry_price):
    """Execute entry + SL/TP with proper delays."""
    if side == "LONG":
        tp_price = entry_price + (0.01 / TRADE_SIZE)
        sl_price = entry_price - (0.01 / TRADE_SIZE)
    else:
        tp_price = entry_price - (0.01 / TRADE_SIZE)
        sl_price = entry_price + (0.01 / TRADE_SIZE)

    print(f"\n  EXECUTING {side} {TRADE_SIZE} BTC @ ${entry_price:,.2f}")
    print(f"  TP: ${tp_price:,.2f} | SL: ${sl_price:,.2f}")

    # Get nonce
    config = lighter.Configuration(host=BASE_URL)
    async with lighter.ApiClient(config) as api_client:
        tx_api = lighter.TransactionApi(api_client)
        nonce_resp = await tx_api.next_nonce(
            account_index=ACCOUNT_INDEX, api_key_index=API_KEY_INDEX
        )
        nonce = nonce_resp.nonce

    client = lighter.SignerClient(
        url=BASE_URL,
        account_index=ACCOUNT_INDEX,
        api_private_keys={API_KEY_INDEX: API_SECRET},
    )

    # 1. Entry
    base_amount = int(TRADE_SIZE * 1e5)
    # BUY: willing to pay UP TO 2% above market (slippage up)
    # SELL: willing to accept DOWN TO 2% below market (slippage down)
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
    print(f"  Entry OK: {resp.tx_hash[:16]}...")
    nonce += 1

    # CRITICAL: Wait for chain to process
    time.sleep(3)

    # 2. SL
    sl_scaled = int(sl_price * 10)
    _, resp_sl, err_sl = await client.create_order(
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
        print(f"  SL OK: {resp_sl.tx_hash[:16]}...")
    nonce += 1

    # Wait again
    time.sleep(3)

    # 3. TP
    tp_scaled = int(tp_price * 10)
    _, resp_tp, err_tp = await client.create_order(
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
        print(f"  TP OK: {resp_tp.tx_hash[:16]}...")

    await client.close()

    # Verify position
    time.sleep(3)
    async with lighter.ApiClient(config) as api_client:
        account_api = lighter.AccountApi(api_client)
        account = await account_api.account(by="index", value=str(ACCOUNT_INDEX))
        a = account.accounts[0]
        if a.positions:
            pos = a.positions[0]
            print(f"\n  VERIFIED: {pos.position} BTC, entry ${pos.avg_entry_price}")
            print(f"  Tied orders: {pos.position_tied_order_count}")
            print(f"  Unrealized PnL: ${pos.unrealized_pnl}")
        else:
            print("\n  WARNING: No position found")

    return True


async def main():
    print("=" * 50)
    print("BTC SCALP ANALYSIS")
    print("=" * 50)

    # Check if already in position
    config = lighter.Configuration(host=BASE_URL)
    async with lighter.ApiClient(config) as api_client:
        account_api = lighter.AccountApi(api_client)
        account = await account_api.account(by="index", value=str(ACCOUNT_INDEX))
        a = account.accounts[0]
        if a.positions and float(a.positions[0].position) > 0:
            pos = a.positions[0]
            side = "LONG" if pos.sign == 1 else "SHORT"
            print(f"Already in position: {side} {pos.position} @ ${pos.avg_entry_price}")
            print(f"PnL: ${pos.unrealized_pnl} | Tied orders: {pos.position_tied_order_count}")
            return

    # Get market data
    print("\nAnalyzing market...")
    current, prices = await get_market_data()

    # Analyze
    decision, reason = analyze(current, prices)

    if decision is None:
        print(f"\n  SKIP: {reason}")
        print("  Retrying in 10s...")
        await asyncio.sleep(10)
        # Retry up to 6 times (1 minute total)
        for attempt in range(6):
            print(f"\n--- Attempt {attempt+2}/7 ---")
            current, prices = await get_market_data()
            decision, reason = analyze(current, prices)
            if decision:
                print(f"\n  DECISION: {decision} - {reason}")
                await execute_trade(decision, current)
                print("\nDone. Monitor position at app.zklighter.com")
                return
            print(f"  SKIP: {reason}")
            await asyncio.sleep(10)
        print("\nNo trade opportunity found after 7 attempts. Try again later.")
        return

    print(f"\n  DECISION: {decision} - {reason}")

    # Execute
    await execute_trade(decision, current)
    print("\nDone. Monitor position at app.zklighter.com")


if __name__ == "__main__":
    asyncio.run(main())
