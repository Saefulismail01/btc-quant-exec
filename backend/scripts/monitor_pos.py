import asyncio, os
from dotenv import load_dotenv
from pathlib import Path
import lighter, sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

BASE_URL = os.getenv("LIGHTER_MAINNET_BASE_URL", "https://mainnet.zklighter.elliot.ai")
ACCOUNT_INDEX = 718591

async def monitor():
    for i in range(30):
        config = lighter.Configuration(host=BASE_URL)
        async with lighter.ApiClient(config) as api:
            acc_api = lighter.AccountApi(api)
            r = await acc_api.account(by="index", value=str(ACCOUNT_INDEX))
            acc = r.accounts[0]
            order_api = lighter.OrderApi(api)
            b = await order_api.order_book_details(market_id=1)
            price = float(b.order_book_details[0].last_trade_price)

            if acc.positions and float(acc.positions[0].position) > 0:
                pos = acc.positions[0]
                pnl = float(pos.unrealized_pnl)
                side = "LONG" if pos.sign == 1 else "SHORT"
                print(f"[{i}] BTC ${price:,.2f} | {side} PnL: ${pnl:+.6f} | orders: {pos.position_tied_order_count}")
            else:
                print(f"[{i}] NO POSITION | Balance: ${acc.collateral}")
                break
        await asyncio.sleep(10)

asyncio.run(monitor())
