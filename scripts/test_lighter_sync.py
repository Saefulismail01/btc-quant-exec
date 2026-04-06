import asyncio
import os
import sys
from pathlib import Path

# Add backend and parent directory to path for imports
_BACKEND = str(Path(__file__).resolve().parent.parent / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)
_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from backend.app.adapters.gateways.lighter_execution_gateway import LighterExecutionGateway

async def test_sync():
    print("\n🚀 [TEST] Lighter Exchange Sync Audit")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    try:
        gateway = LighterExecutionGateway()
        
        # 1. Fetch current price
        price = await gateway.get_current_price()
        print(f"✅ Connection: SUCCESS | Current BTC/USDC: ${price:,.2f}")
        
        # 2. Fetch Open Orders
        print("\n📥 Fetching all open orders from Lighter...")
        orders = await gateway.fetch_open_orders()
        print(f"📊 Total Open Orders: {len(orders)}")
        
        # 3. Analyze SL/TP
        print("\n🔍 Analyzing active SL/TP levels...")
        active_params = await gateway.get_active_sl_tp()
        sl = active_params.get("sl_price")
        tp = active_params.get("tp_price")
        
        print(f"🛑 Active SL: ${sl:,.2f}" if sl else "🛑 Active SL: NOT FOUND")
        print(f"🏁 Active TP: ${tp:,.2f}" if tp else "🏁 Active TP: NOT FOUND")
        
        # 4. Fetch Position to correlate
        print("\n🏦 Checking current open position...")
        pos = await gateway.get_open_position()
        if pos:
            print(f"📌 Position Found: {pos.side} {pos.quantity:.8f} BTC @ ${pos.entry_price:,.2f}")
            print(f"💵 Unrealized PnL: ${pos.unrealized_pnl:+.2f}")
        else:
            print("📌 Position Info: NO OPEN POSITION")
            
        await gateway.close()
        print("\n✅ [TEST] Audit complete.")
        
    except Exception as e:
        print(f"\n❌ [ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_sync())
