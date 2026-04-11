import os, sys, asyncio

sys.path.insert(0, "/app/backend")
os.environ["LIGHTER_EXECUTION_MODE"] = "mainnet"
os.environ["LIGHTER_TRADING_ENABLED"] = "true"

from app.adapters.gateways.lighter_execution_gateway import LighterExecutionGateway


async def main():
    gw = LighterExecutionGateway()
    await gw._init_session()
    bal = await gw.get_account_balance()
    print(f"Balance: ${bal:,.2f} USDC")
    pos = await gw.get_open_position()
    if pos:
        print(
            f"Open Position: {pos.side} @ ${pos.entry_price:,.2f} | PnL: ${pos.unrealized_pnl:+,.2f}"
        )
    else:
        print("No open position")
    await gw.close()


asyncio.run(main())
