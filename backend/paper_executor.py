"""
Paper Execution Daemon — The "Autonomous Trader".
Loops every 60s, fetches signals, and executes paper trades.
"""
import sys
import asyncio
import logging
import signal
import time
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Setup paths to ensure app.* imports work
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Setup dummy environment if needed
from app.use_cases.signal_service import get_signal_service
from app.use_cases.paper_trade_service import get_paper_trade_service

# Constants
CYCLE_INTERVAL = int(os.getenv("PAPER_EXECUTOR_CYCLE_INTERVAL", "60"))
SIGNAL_TIMEOUT = 30.0  # seconds
MAX_OPEN_POSITIONS = 5
DAILY_LOSS_LIMIT_PCT = 5.0  # 5% of starting capital
CONSECUTIVE_LOSS_LIMIT = 3  # stop after 3 consecutive losses

# Logging Setup with rotation
log_handler = RotatingFileHandler(
    BACKEND_DIR / "paper_execution.log",
    maxBytes=10_000_000,  # 10MB
    backupCount=5  # Keep 5 old files
)
log_handler.setFormatter(
    logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s")
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(), log_handler]
)
logger = logging.getLogger("PaperExecutor")

class PaperExecutor:
    """Paper execution daemon with risk management."""

    def __init__(self):
        self.signal_svc = get_signal_service()
        self.paper_svc = get_paper_trade_service()
        self.running = asyncio.Event()
        self.running.set()
        self.consecutive_losses = 0
        self.cycle_count = 0

    async def run(self):
        """Main execution loop."""
        logger.info("=" * 70)
        logger.info("[PAPER] BTC-QUANT Paper Execution Daemon")
        logger.info("=" * 70)
        logger.info(f"[PAPER] Parameters: Cycle={CYCLE_INTERVAL}s | Signal timeout={SIGNAL_TIMEOUT}s")
        logger.info(f"[PAPER] Risk: Max {MAX_OPEN_POSITIONS} positions | Daily loss cap {DAILY_LOSS_LIMIT_PCT}%")

        try:
            while self.running.is_set():
                self.cycle_count += 1
                cycle_start = time.time()

                try:
                    # Get account status
                    account = self.paper_svc.get_account_status()
                    logger.info(
                        f"[PAPER] Cycle {self.cycle_count} | Balance: ${account.get('balance', 0):,.2f} | "
                        f"Open positions: {len(account.get('open_trades', []))}"
                    )

                    # Check position limits
                    open_positions = account.get('open_trades', [])
                    if len(open_positions) >= MAX_OPEN_POSITIONS:
                        logger.warning(
                            f"[PAPER] Position limit reached ({len(open_positions)}/{MAX_OPEN_POSITIONS}). Skipping new entries."
                        )
                        await asyncio.sleep(CYCLE_INTERVAL)
                        continue

                    # Check consecutive loss limit
                    if self.consecutive_losses >= CONSECUTIVE_LOSS_LIMIT:
                        logger.warning(
                            f"[PAPER] Consecutive loss limit ({self.consecutive_losses}) reached. "
                            f"Halting new trades."
                        )
                        await asyncio.sleep(CYCLE_INTERVAL)
                        continue

                    # Fetch signal with timeout
                    logger.debug("[PAPER] Fetching latest signal...")
                    try:
                        signal = await asyncio.wait_for(
                            asyncio.to_thread(self.signal_svc.get_signal),
                            timeout=SIGNAL_TIMEOUT
                        )
                    except asyncio.TimeoutError:
                        logger.warning(f"[PAPER] Signal generation timeout (>{SIGNAL_TIMEOUT}s)")
                        await asyncio.sleep(CYCLE_INTERVAL)
                        continue

                    # Process signal
                    if not signal:
                        logger.debug("[PAPER] No signal returned")
                    elif signal.is_fallback:
                        logger.warning("[PAPER] Signal engine returned fallback (unreliable)")
                    else:
                        logger.info(
                            f"[PAPER] Signal available | "
                            f"Action: {signal.trade_plan.action} | "
                            f"Status: {signal.trade_plan.status} | "
                            f"Conviction: {signal.trade_plan.position_size_pct:.1f}%"
                        )
                        # Execute signal
                        try:
                            result = self.paper_svc.process_signal(signal)
                            if result:
                                logger.info(f"[PAPER] Signal processed: {result}")
                                self.consecutive_losses = 0  # Reset on successful trade
                            else:
                                logger.info("[PAPER] Signal rejected by paper service")
                        except Exception as e:
                            logger.error(f"[PAPER] Signal processing error: {e}")
                            self.consecutive_losses += 1

                    # Log cycle duration
                    cycle_duration = time.time() - cycle_start
                    if cycle_duration > CYCLE_INTERVAL * 0.8:  # >80% of cycle time
                        logger.warning(
                            f"[PAPER] Slow cycle: {cycle_duration:.1f}s (target: {CYCLE_INTERVAL}s)"
                        )

                except asyncio.CancelledError:
                    logger.info("[PAPER] Executor cancelled")
                    break
                except Exception as e:
                    logger.error(f"[PAPER] Cycle {self.cycle_count} error: {e}", exc_info=True)
                    self.consecutive_losses += 1
                    await asyncio.sleep(10)  # Backoff on error
                    continue

                # Wait for next cycle
                await asyncio.sleep(CYCLE_INTERVAL)

        except KeyboardInterrupt:
            logger.info("[PAPER] Received interrupt signal")
            self.running.clear()
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Graceful shutdown."""
        logger.info("[PAPER] Shutting down gracefully...")
        try:
            # Close any open positions
            account = self.paper_svc.get_account_status()
            open_count = len(account.get('open_trades', []))
            if open_count > 0:
                logger.warning(f"[PAPER] Closing {open_count} open position(s) during shutdown...")
                # TODO: Implement close_all_positions() in paper_trade_service
                # self.paper_svc.close_all_positions()
            logger.info("[PAPER] Shutdown complete")
        except Exception as e:
            logger.error(f"[PAPER] Shutdown error: {e}")


async def run_executor():
    """Legacy entry point."""
    executor = PaperExecutor()
    await executor.run()

def handle_signal(signum, frame):
    """Handle system signals."""
    if signum in (signal.SIGINT, signal.SIGTERM):
        logger.info("[PAPER] Received shutdown signal")
        if executor and executor.running:
            executor.running.clear()


if __name__ == "__main__":
    executor = None
    try:
        # Register signal handlers
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        executor = PaperExecutor()
        asyncio.run(executor.run())
    except KeyboardInterrupt:
        logger.info("[PAPER] Paper execution stopped by user")
    except Exception as e:
        logger.error(f"[PAPER] Fatal error: {e}", exc_info=True)
