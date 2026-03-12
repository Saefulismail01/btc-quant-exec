import sys
import os
from pathlib import Path

# Add backend and engines to path
_ROOT = Path("C:/Users/ThinkPad/Documents/Windsurf/btc-scalping-quant/backend")
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "engines"))

import pandas as pd
from app.services.signal_service import get_signal_service
from app.services.paper_trade_service import get_paper_trade_service

def debug_crash():
    print("--- Debugging API Crash ---")
    
    # Set LAYER1_ENGINE if not set, for consistency
    if "LAYER1_ENGINE" not in os.environ:
        os.environ["LAYER1_ENGINE"] = "BCD"

    print("1. Testing PaperTradeService.get_account()...")
    try:
        from app.services.paper_trade_service import get_paper_trade_service
        paper_svc = get_paper_trade_service()
        acc = paper_svc.get_account()
        print(f"   Success: {acc}")
    except Exception as e:
        print(f"   FAILED: {e}")
        import traceback
        traceback.print_exc()

    print("\n2. Testing PaperTradeService.get_open_position()...")
    try:
        pos = paper_svc.get_open_position()
        print(f"   Success: {pos}")
    except Exception as e:
        print(f"   FAILED: {e}")
        import traceback
        traceback.print_exc()

    print("\n3. Testing SignalService.get_signal()...")
    try:
        from app.services.signal_service import get_signal_service
        sig_svc = get_signal_service()
        sig = sig_svc.get_signal()
        print(f"   Success: Signal generated for {sig.price.now if sig and sig.price else 'N/A'}")
    except Exception as e:
        print(f"   FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_crash()
