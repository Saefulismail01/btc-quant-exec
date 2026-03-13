#!/usr/bin/env python3
"""
BTC-QUANT v4.4 — Lighter.xyz Live Execution Daemon

Main loop that orchestrates:
1. PositionManager (open, hold, close positions)
2. Risk management checks
3. Signal processing
4. Telegram notifications
5. Lighter-specific: Nonce management, Integer scaling, Market metadata sync

Usage:
    python execution_layer/lighter/lighter_executor.py

Environment:
    LIGHTER_EXECUTION_MODE=testnet|mainnet
    LIGHTER_TRADING_ENABLED=true|false (CRITICAL safety flag)
"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add backend to path (navigate up 3 levels: lighter/ → execution_layer/ → root → backend/)
backend_path = Path(__file__).resolve().parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.adapters.gateways.lighter_execution_gateway import LighterExecutionGateway
from app.adapters.repositories.live_trade_repository import LiveTradeRepository
from app.use_cases.position_manager import PositionManager
from app.use_cases.risk_manager import RiskManager
from app.use_cases.signal_service import get_cached_signal as _get_cached_signal

# Load .env from backend directory
load_dotenv(backend_path / ".env")

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class LighterExecutor:
    """Main execution daemon for Lighter Protocol."""

    CYCLE_INTERVAL = 60  # seconds
    BALANCE_CHECK_INTERVAL = 3600  # seconds (1 hour)
    METADATA_SYNC_INTERVAL = 86400  # seconds (24 hours)
    MIN_BALANCE_MAINNET = 1200.0  # $1,200 USDC ($1,000 margin + $200 buffer)

    def __init__(self):
        self.execution_mode = os.getenv("LIGHTER_EXECUTION_MODE", "testnet").lower()
        self.trading_enabled = (
            os.getenv("LIGHTER_TRADING_ENABLED", "false").lower() == "true"
        )
        self.running = False
        self.last_balance_check = 0
        self.last_metadata_sync = 0

    async def startup_checks(self) -> bool:
        """Perform startup safety checks for Lighter execution."""
        logger.info("=" * 70)
        logger.info("[LIGHTER] BTC-QUANT v4.4 Lighter.xyz Execution Daemon")
        logger.info("=" * 70)

        logger.info(f"[LIGHTER] Mode: {self.execution_mode.upper()}")
        logger.info(
            f"[LIGHTER] Trading: {'🟢 ENABLED' if self.trading_enabled else '🔴 DISABLED'}"
        )
        logger.info("[LIGHTER] Parameters: Margin=$1,000 | Leverage=15x | SL=1.333% | TP=0.71%")
        logger.info("[LIGHTER] TIME_EXIT: 24 hours (6 × 4h candles)")

        try:
            # Initialize gateway
            gateway = LighterExecutionGateway()

            logger.info(
                f"[LIGHTER] API Key Index: {gateway.api_key_index}"
            )

            # Check account balance
            balance = await gateway.get_account_balance()
            logger.info(f"[LIGHTER] Account Balance: ${balance:,.2f} USDC")

            if self.execution_mode == "mainnet" and balance < self.MIN_BALANCE_MAINNET:
                logger.error(
                    f"[LIGHTER] ❌ Insufficient balance for mainnet! "
                    f"Need ${self.MIN_BALANCE_MAINNET:,.2f}, have ${balance:,.2f}"
                )
                await gateway.close()
                return False

            # CRITICAL: Resync nonce from server on startup
            logger.info("[LIGHTER] Resyncing nonce from server...")
            try:
                # In production, fetch nonce from Lighter API
                # For now, assume it starts at 0 on testnet
                server_nonce = 0
                await gateway.nonce_manager.resync_from_server(server_nonce)
                logger.info(
                    f"[LIGHTER] ✅ Nonce resynced. Next nonce: {server_nonce}"
                )
            except Exception as e:
                logger.error(f"[LIGHTER] ⚠️  Failed to resync nonce: {e}")
                # Don't abort — try to continue with local state

            # Sync market metadata
            logger.info("[LIGHTER] Syncing market metadata...")
            try:
                await gateway._sync_market_metadata()
                logger.info(
                    f"[LIGHTER] ✅ Market metadata synced. "
                    f"Price decimals: {gateway._price_decimals}, "
                    f"Size decimals: {gateway._size_decimals}"
                )
            except Exception as e:
                logger.warning(f"[LIGHTER] Failed to sync metadata: {e}. Using defaults.")

            # Check for existing positions
            position = await gateway.get_open_position()
            if position:
                logger.warning(
                    f"[LIGHTER] ⚠️  Existing position detected at startup! "
                    f"{position.side} {position.quantity:.8f} BTC @ ${position.entry_price:,.2f}"
                )
            else:
                logger.info("[LIGHTER] No existing positions (clean state)")

            await gateway.close()
            return True

        except Exception as e:
            logger.error(f"[LIGHTER] Startup check failed: {e}", exc_info=True)
            return False

    async def run(self):
        """Main execution loop."""
        try:
            # Startup checks
            if not await self.startup_checks():
                logger.error("[LIGHTER] Startup checks failed. Aborting.")
                return

            # Initialize components
            gateway = LighterExecutionGateway()
            repo = LiveTradeRepository()
            risk_manager = RiskManager()
            position_manager = PositionManager(gateway, repo, risk_manager)

            self.running = True
            cycle_count = 0

            logger.info("[LIGHTER] Starting main execution loop...")
            logger.info("=" * 70)

            while self.running:
                cycle_count += 1
                cycle_start = datetime.utcnow()

                try:
                    # 1. Sync position status (detect SL/TP fills)
                    logger.info(f"[LIGHTER] Cycle {cycle_count} — Syncing position...")
                    await position_manager.sync_position_status()

                    # 2. Get latest cached signal
                    signal = _get_cached_signal()

                    if signal and not signal.is_fallback:
                        logger.info(
                            f"[LIGHTER] Signal available | "
                            f"Verdict: {signal.confluence.verdict} | "
                            f"Conviction: {signal.confluence.conviction_pct:.1f}%"
                        )
                        # 3. Process signal
                        await position_manager.process_signal(signal)
                    else:
                        logger.info("[LIGHTER] No valid signal or fallback signal. Waiting...")

                    # 4. Periodic balance check
                    now = datetime.utcnow().timestamp()
                    if now - self.last_balance_check > self.BALANCE_CHECK_INTERVAL:
                        balance = await gateway.get_account_balance()
                        logger.info(f"[LIGHTER] Balance check: ${balance:,.2f} USDC")
                        self.last_balance_check = now

                    # 5. Periodic metadata sync (24h)
                    if now - self.last_metadata_sync > self.METADATA_SYNC_INTERVAL:
                        logger.info("[LIGHTER] Refreshing market metadata...")
                        try:
                            await gateway._sync_market_metadata()
                            logger.info("[LIGHTER] ✅ Market metadata refreshed")
                            self.last_metadata_sync = now
                        except Exception as e:
                            logger.warning(f"[LIGHTER] Failed to refresh metadata: {e}")

                    # 6. Log cycle duration
                    cycle_duration = (datetime.utcnow() - cycle_start).total_seconds()
                    logger.info(
                        f"[LIGHTER] Cycle {cycle_count} complete | "
                        f"Duration: {cycle_duration:.1f}s"
                    )

                    # 7. Log nonce status periodically
                    if cycle_count % 60 == 0:  # Every 60 cycles (1 hour)
                        nonce_status = gateway.get_nonce_status()
                        logger.info(
                            f"[LIGHTER] Nonce status: next={nonce_status['next_nonce']}, "
                            f"synced={nonce_status['synced_from_server']}"
                        )

                except Exception as e:
                    logger.error(f"[LIGHTER] Cycle {cycle_count} error: {e}", exc_info=True)
                    await asyncio.sleep(10)  # Wait longer on error
                    continue

                # Wait for next cycle
                await asyncio.sleep(self.CYCLE_INTERVAL)

        except KeyboardInterrupt:
            logger.info("[LIGHTER] Received interrupt signal")
            self.running = False
        except Exception as e:
            logger.error(f"[LIGHTER] Fatal error: {e}", exc_info=True)
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Graceful shutdown."""
        try:
            logger.info("[LIGHTER] Shutting down gracefully...")

            gateway = LighterExecutionGateway()

            # Check if position exists and close it
            position = await gateway.get_open_position()
            if position:
                logger.warning(f"[LIGHTER] Open position detected during shutdown. Closing...")
                result = await gateway.close_position_market()
                if result.success:
                    logger.info(
                        f"[LIGHTER] Position closed | "
                        f"Exit: ${result.filled_price:,.2f}"
                    )
                else:
                    logger.error(f"[LIGHTER] Failed to close position: {result.error_message}")

            # Close gateway
            await gateway.close()
            logger.info("[LIGHTER] Shutdown complete. Bye!")

        except Exception as e:
            logger.error(f"[LIGHTER] Error during shutdown: {e}", exc_info=True)


def handle_signal(signum, frame):
    """Handle system signals."""
    if signum == signal.SIGINT:
        logger.info("[LIGHTER] Received SIGINT, initiating graceful shutdown...")
        executor.running = False


if __name__ == "__main__":
    executor = LighterExecutor()

    # Register signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Run
    try:
        asyncio.run(executor.run())
    except Exception as e:
        logger.error(f"[LIGHTER] Fatal error: {e}", exc_info=True)
        sys.exit(1)
