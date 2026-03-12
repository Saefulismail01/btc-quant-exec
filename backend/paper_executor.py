"""
Paper Execution Daemon — The "Autonomous Trader".
Loops every 60s, fetches signals, and executes paper trades.
"""
import sys
import asyncio
import logging
import time
from pathlib import Path

# Setup paths to ensure app.* imports work
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Setup dummy environment if needed
from app.services.signal_service import get_signal_service
from app.services.paper_trade_service import get_paper_trade_service

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)7s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BACKEND_DIR / "paper_execution.log")
    ]
)
logger = logging.getLogger("PaperExecutor")

async def run_executor():
    logger.info(" [BOOT] Starting Paper Execution Daemon...")
    
    signal_svc = get_signal_service()
    paper_svc = get_paper_trade_service()
    
    # Optional: Reset account on fresh start (comment out if you want persistence)
    # paper_svc.reset_account()

    while True:
        try:
            logger.info(" [CYCLE] Fetching latest signal...")
            # Generating a signal triggers the full L1-L5 engine
            signal = signal_svc.get_signal()
            
            if signal.is_fallback:
                logger.warning(" [CYCLE] Signal engine returned fallback. Skipping execution.")
            else:
                logger.info(f" [CYCLE] Signal: {signal.trade_plan.action} | Status: {signal.trade_plan.status} | Conviction: {signal.trade_plan.position_size_pct:.1f}%")
                # Pass to paper trade logic
                paper_svc.process_signal(signal)
                
            # Wait for next cycle (match FETCH_INTERVAL from data_engine)
            await asyncio.sleep(60)
            
        except Exception as e:
            logger.error(f" [CRITICAL] Loop error: {e}", exc_info=True)
            await asyncio.sleep(10) # Quick retry backoff

if __name__ == "__main__":
    try:
        asyncio.run(run_executor())
    except KeyboardInterrupt:
        logger.info(" [EXIT] Paper execution stopped by user.")
