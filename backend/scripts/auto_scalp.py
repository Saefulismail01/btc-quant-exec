"""
Automated BTC scalp bot with SL/TP orders.
Usage: python auto_scalp.py LONG/SHORT entry_price quantity
"""

import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

import lighter

BASE_URL = os.getenv("LIGHTER_MAINNET_BASE_URL", "https://mainnet.zklighter.elliot.ai")
API_SECRET = os.getenv("LIGHTER_MAINNET_API_SECRET", "")
# Strip 0x prefix if present
if API_SECRET.startswith("0x"):
    API_SECRET = API_SECRET[2:]
API_KEY_INDEX = int(os.getenv("LIGHTER_API_KEY_INDEX", "3"))
ACCOUNT_INDEX = int(os.getenv("LIGHTER_ACCOUNT_INDEX", "718591"))
BTC_MARKET = 1


async def place_entry_and_hedges(side: str, entry_price: float, quantity: float, tp_profit: float, sl_loss: float):
    """
    Place entry market order + SL/TP limit orders atomically.

    Args:
        side: "LONG" or "SHORT"
        entry_price: Entry price in USD
        quantity: Size in BTC
        tp_profit: Take profit in USD (e.g., 0.01)
        sl_loss: Stop loss in USD (e.g., 0.01)
    """

    # TP/SL prices
    if side == "LONG":
        tp_price = entry_price + (tp_profit / quantity)
        sl_price = entry_price - (sl_loss / quantity)
        print(f"LONG {quantity:.5f} BTC @ ${entry_price:,.2f}")
        print(f"  SL @ ${sl_price:,.2f} (-${sl_loss})")
        print(f"  TP @ ${tp_price:,.2f} (+${tp_profit})")
    else:  # SHORT
        tp_price = entry_price - (tp_profit / quantity)
        sl_price = entry_price + (sl_loss / quantity)
        print(f"SHORT {quantity:.5f} BTC @ ${entry_price:,.2f}")
        print(f"  SL @ ${sl_price:,.2f} (-${sl_loss})")
        print(f"  TP @ ${tp_price:,.2f} (+${tp_profit})")

    client = lighter.SignerClient(
        url=BASE_URL,
        account_index=ACCOUNT_INDEX,
        api_private_keys={API_KEY_INDEX: API_SECRET},
    )

    # Get current price & nonce
    config = lighter.Configuration(host=BASE_URL)
    async with lighter.ApiClient(config) as api_client:
        order_api = lighter.OrderApi(api_client)
        btc_book = await order_api.order_book_details(market_id=BTC_MARKET)
        mid_price = float(btc_book.order_book_details[0].last_trade_price)
        print(f"\nCurrent BTC: ${mid_price:,.2f}")

        tx_api = lighter.TransactionApi(api_client)
        nonce_resp = await tx_api.next_nonce(account_index=ACCOUNT_INDEX, api_key_index=API_KEY_INDEX)
        nonce = nonce_resp.nonce

    # 1. Place entry market order
    print(f"\n[1] Placing {side} entry...")
    base_amount = int(quantity * 1e5)  # size_decimals=5
    avg_price = int(entry_price * 10 * (0.98 if side == "SHORT" else 1.02))  # price_decimals=1, slippage tolerance

    created_order, resp, err = await client.create_market_order(
        market_index=BTC_MARKET,
        client_order_index=0,
        base_amount=base_amount,
        avg_execution_price=avg_price,
        is_ask=(side == "SHORT"),
        nonce=nonce,
        api_key_index=API_KEY_INDEX,
    )

    if err:
        print(f"    ❌ Entry failed: {err}")
        await client.close()
        return

    print(f"    ✅ Entry TX: {resp.tx_hash if resp else 'pending'}")
    nonce += 1

    # 2. Place SL order (use STOP_LOSS order type, not trigger_price)
    print(f"[2] Placing SL @ ${sl_price:,.2f}...")
    sl_base = base_amount
    sl_price_scaled = int(sl_price * 10)

    _, resp_sl, err_sl = await client.create_order(
        market_index=BTC_MARKET,
        client_order_index=1,
        base_amount=sl_base,
        price=sl_price_scaled,
        is_ask=(side == "LONG"),  # SL closes position: LONG=SELL, SHORT=BUY
        order_type=lighter.SignerClient.ORDER_TYPE_STOP_LOSS_LIMIT,
        time_in_force=lighter.SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
        trigger_price=sl_price_scaled,
        reduce_only=1,
        nonce=nonce,
        api_key_index=API_KEY_INDEX,
    )

    if err_sl:
        print(f"    ⚠️  SL failed: {err_sl}")
    else:
        print(f"    ✅ SL TX: {resp_sl.tx_hash if resp_sl else 'pending'}")
        await asyncio.sleep(0.5)  # Wait for nonce update
    nonce += 1

    # 3. Place TP order (use TAKE_PROFIT order type)
    print(f"[3] Placing TP @ ${tp_price:,.2f}...")
    tp_base = base_amount
    tp_price_scaled = int(tp_price * 10)

    _, resp_tp, err_tp = await client.create_order(
        market_index=BTC_MARKET,
        client_order_index=2,
        base_amount=tp_base,
        price=tp_price_scaled,
        is_ask=(side == "LONG"),  # TP closes: LONG=SELL, SHORT=BUY
        order_type=lighter.SignerClient.ORDER_TYPE_TAKE_PROFIT_LIMIT,
        time_in_force=lighter.SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
        trigger_price=tp_price_scaled,
        reduce_only=1,
        nonce=nonce,
        api_key_index=API_KEY_INDEX,
    )

    if err_tp:
        print(f"    ⚠️  TP failed: {err_tp}")
    else:
        print(f"    ✅ TP TX: {resp_tp.tx_hash if resp_tp else 'pending'}")

    print(f"\n✅ Setup complete! Waiting for SL/TP to fill...\n")
    await client.close()


async def main():
    if len(sys.argv) < 4:
        print("Usage: python auto_scalp.py LONG/SHORT entry_price quantity [tp_profit] [sl_loss]")
        print("  Example: python auto_scalp.py LONG 71500 0.00021 0.01 0.01")
        sys.exit(1)

    side = sys.argv[1].upper()
    entry_price = float(sys.argv[2])
    quantity = float(sys.argv[3])
    tp_profit = float(sys.argv[4]) if len(sys.argv) > 4 else 0.01
    sl_loss = float(sys.argv[5]) if len(sys.argv) > 5 else 0.01

    if side not in ["LONG", "SHORT"]:
        print("Side must be LONG or SHORT")
        sys.exit(1)

    await place_entry_and_hedges(side, entry_price, quantity, tp_profit, sl_loss)


if __name__ == "__main__":
    asyncio.run(main())
