import asyncio
import os
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

# Mock class for Lighter API Response
class MockResponse:
    def __init__(self, json_data, status=200):
        self.json_data = json_data
        self.status = status
    async def json(self):
        return self.json_data
    async def text(self):
        return str(self.json_data)
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

async def test_logic():
    print("🧪 [UNIT TEST] Verifying Sync Logic with Mock API")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # 1. Setup Mock Data
    mock_orders = {
        "orders": [
            {
                "order_id": "sl_123",
                "type": "STOP_LOSS_LIMIT",
                "trigger_price": 66500.0,
                "price": 66490.0,
                "status": "OPEN",
                "side": "SELL"
            },
            {
                "order_id": "tp_456",
                "type": "TAKE_PROFIT_LIMIT",
                "trigger_price": 68500.0,
                "price": 68510.0,
                "status": "OPEN",
                "side": "SELL"
            }
        ]
    }

    # 2. Mock _make_request to return mock_orders
    from backend.app.adapters.gateways.lighter_execution_gateway import LighterExecutionGateway
    
    with patch.object(LighterExecutionGateway, '_make_request', new_callable=AsyncMock) as mocked_req:
        mocked_req.return_value = mock_orders
        
        # Instantiate with dummy creds
        os.environ["LIGHTER_TESTNET_API_KEY"] = "mock_key"
        os.environ["LIGHTER_TESTNET_API_SECRET"] = "mock_secret"
        
        gateway = LighterExecutionGateway()
        
        # Test fetch_open_orders
        res_orders = await gateway.fetch_open_orders()
        print(f"✅ fetch_open_orders: Retrieved {len(res_orders)} orders (Expected: 2)")
        
        # Test get_active_sl_tp
        active = await gateway.get_active_sl_tp()
        print(f"✅ get_active_sl_tp: SL=${active['sl_price']}, TP=${active['tp_price']}")
        
        # Assertions
        assert active['sl_price'] == 66500.0
        assert active['tp_price'] == 68500.0
        print("\n🎉 SYNC LOGIC VERIFIED: Exchange codes and categorization are correct.")

if __name__ == "__main__":
    asyncio.run(test_logic())
