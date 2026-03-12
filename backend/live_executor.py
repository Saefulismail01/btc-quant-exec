#!/usr/bin/env python3
"""
BTC-QUANT v4.4 — Live Execution Daemon

Main loop that orchestrates:
1. PositionManager (open, hold, close positions)
2. Risk management checks
3. Signal processing
4. Telegram notifications

Usage:
    python backend/live_executor.py

Environment:
    EXECUTION_MODE=testnet|live
    TRADING_ENABLED=true|false (CRITICAL safety flag)
"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.adapters.gateways.binance_execution_gateway import BinanceExecutionGateway
from app.adapters.repositories.live_trade_repository import LiveTradeRepository
from app.use_cases.position_manager import PositionManager
from app.use_cases.risk_manager import RiskManager
from app.use_cases.signal_service import get_cached_signal as _get_cached_signal

# Load .env from backend directory
load_dotenv(Path(__file__).parent / ".env")

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class LiveExecutor:
    """Main execution daemon."""

    CYCLE_INTERVAL = 60  # seconds
    BALANCE_CHECK_INTERVAL = 3600  # seconds (1 hour)
    MIN_BALANCE_MAINNET = 1200.0  # $1,000 margin + $200 buffer

    def __init__(self):
        self.execution_mode = os.getenv("EXECUTION_MODE", "testnet").lower()
        self.trading_enabled = os.getenv("TRADING_ENABLED", "false").lower() == "true"
        self.running = False
        self.last_balance_check = 0

    async def startup_checks(self) -> bool:
        """Perform startup safety checks."""
        logger.info("="*70)
        logger.info("[LIVE] BTC-QUANT v4.4 Live Execution Daemon")
        logger.info("="*70)

        logger.info(f"[LIVE] Mode: {self.execution_mode.upper()}")
        logger.info(
            f"[LIVE] Trading: {'🟢 ENABLED' if self.trading_enabled else '🔴 DISABLED'}"
        )
        logger.info("[LIVE] Parameters: Margin=$1,000 | Leverage=15x | SL=1.333% | TP=0.71%")
        logger.info("[LIVE] TIME_EXIT: 24 hours (6 × 4h candles)")

        try:
            # Initialize gateway
            gateway = BinanceExecutionGateway()

            # Check account balance
            balance = await gateway.get_account_balance()
            logger.info(f"[LIVE] Account Balance: ${balance:,.2f} USDT")

            if self.execution_mode == "live" and balance < self.MIN_BALANCE_MAINNET:
                logger.error(
                    f"[LIVE] ❌ Insufficient balance for mainnet! "
                    f"Need ${self.MIN_BALANCE_MAINNET:,.2f}, have ${balance:,.2f}"
                )
                await gateway.close()
                return False

            # Check for existing positions
            position = await gateway.get_open_position()
            if position:
                logger.warning(
                    f"[LIVE] ⚠️  Existing position detected at startup! "
                    f"{position.side} {position.quantity:.8f} BTC @ ${position.entry_price:,.2f}"
                )
            else:
                logger.info("[LIVE] No existing positions (clean state)")

            await gateway.close()
            return True

        except Exception as e:
            logger.error(f"[LIVE] Startup check failed: {e}", exc_info=True)
            return False

    async def run(self):
        """Main execution loop."""
        try:
            # Startup checks
            if not await self.startup_checks():
                logger.error("[LIVE] Startup checks failed. Aborting.")
                return

            # Initialize components
            gateway = BinanceExecutionGateway()
            repo = LiveTradeRepository()
            risk_manager = RiskManager()
            position_manager = PositionManager(gateway, repo, risk_manager)


            self.running = True
            cycle_count = 0

            logger.info("[LIVE] Starting main execution loop...")
            logger.info("="*70)

            while self.running:
                cycle_count += 1
                cycle_start = datetime.utcnow()

                try:
                    # 1. Sync position status (detect SL/TP fills)
                    logger.info(f"[LIVE] Cycle {cycle_count} — Syncing position...")
                    await position_manager.sync_position_status()

                    # 2. Get latest cached signal
                    signal = _get_cached_signal()

                    if signal and not signal.is_fallback:
                        logger.info(
                            f"[LIVE] Signal available | "
                            f"Verdict: {signal.confluence.verdict} | "
                            f"Conviction: {signal.confluence.conviction_pct:.1f}%"
                        )
                        # 3. Process signal
                        await position_manager.process_signal(signal)
                    else:
                        logger.info("[LIVE] No valid signal or fallback signal. Waiting...")

                    # 4. Periodic balance check
                    now = datetime.utcnow().timestamp()
                    if now - self.last_balance_check > self.BALANCE_CHECK_INTERVAL:
                        balance = await gateway.get_account_balance()
                        logger.info(f"[LIVE] Balance check: ${balance:,.2f} USDT")
                        self.last_balance_check = now

                    # 5. Log cycle duration
                    cycle_duration = (datetime.utcnow() - cycle_start).total_seconds()
                    logger.info(
                        f"[LIVE] Cycle {cycle_count} complete | "
                        f"Duration: {cycle_duration:.1f}s"
                    )

                except Exception as e:
                    logger.error(f"[LIVE] Cycle {cycle_count} error: {e}", exc_info=True)
                    await asyncio.sleep(10)  # Wait longer on error
                    continue

                # Wait for next cycle
                await asyncio.sleep(self.CYCLE_INTERVAL)

        except KeyboardInterrupt:
            logger.info("[LIVE] Received interrupt signal")
            self.running = False
        except Exception as e:
            logger.error(f"[LIVE] Fatal error: {e}", exc_info=True)
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Graceful shutdown."""
        try:
            logger.info("[LIVE] Shutting down gracefully...")

            gateway = BinanceExecutionGateway()

            # Check if position exists and close it
            position = await gateway.get_open_position()
            if position:
                logger.warning(f"[LIVE] Open position detected during shutdown. Closing...")
                result = await gateway.close_position_market()
                if result.success:
                    logger.info(
                        f"[LIVE] Position closed | "
                        f"Exit: ${result.filled_price:,.2f}"
                    )
                else:
                    logger.error(f"[LIVE] Failed to close position: {result.error_message}")

            # Close gateway
            await gateway.close()
            logger.info("[LIVE] Shutdown complete. Bye!")

        except Exception as e:
            logger.error(f"[LIVE] Error during shutdown: {e}", exc_info=True)


def handle_signal(signum, frame):
    """Handle system signals."""
    if signum == signal.SIGINT:
        logger.info("[LIVE] Received SIGINT, initiating graceful shutdown...")
        executor.running = False


if __name__ == "__main__":
    executor = LiveExecutor()

    # Register signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Run
    try:
        asyncio.run(executor.run())
    except Exception as e:
        logger.error(f"[LIVE] Fatal error: {e}", exc_info=True)
        sys.exit(1)
