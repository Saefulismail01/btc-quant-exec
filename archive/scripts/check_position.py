#!/usr/bin/env python3
import asyncio
import sys

sys.path.insert(0, "/app/backend")
from app.adapters.gateways.lighter_execution_gateway import LighterExecutionGateway


async def check():
    gateway = LighterExecutionGateway()
    pos = await gateway.get_open_position()
    if pos:
        print(f"Position found: {pos.side} {pos.quantity} @ ${pos.entry_price}")
    else:
        print("No position at exchange")


asyncio.run(check())
