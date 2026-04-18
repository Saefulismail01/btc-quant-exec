#!/usr/bin/env python3
"""
Intraday Position Monitor for BTC-QUANT

Monitors open positions every 15 minutes for:
- Trailing SL evaluation
- Early exit detection
- PnL tracking

Schedule: Every 15 minutes (00, 15, 30, 45)
"""

import asyncio
import logging
import os
import sys
import json
import time
import signal as sig_mod
from pathlib import Path
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

# Path setup
root_path = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_path / "backend"))

from dotenv import load_dotenv
load_dotenv(root_path / ".env")

import lighter
import aiohttp

# ── Config ─────────────────────────────────────────────────────────────────────

BASE_URL = os.getenv("LIGHTER_MAINNET_BASE_URL", "https://mainnet.zklighter.elliot.ai")
API_SECRET = os.getenv("LIGHTER_MAINNET_API_SECRET", "")
if API_SECRET.startswith("0x"):
    API_SECRET = API_SECRET[2:]
API_KEY_INDEX = int(os.getenv("LIGHTER_API_KEY_INDEX", "3"))
ACCOUNT_INDEX = int(os.getenv("LIGHTER_ACCOUNT_INDEX", "718591"))
BTC_MARKET = 1

# Monitoring interval (minutes)
CHECK_INTERVAL_MINUTES = 15

# Order IDs state file (same as signal_executor)
ORDER_IDS_FILE = Path(__file__).parent / "order_ids.json"

# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Order ID tracking helpers ─────────────────────────────────────────────────────

def clear_order_ids() -> bool:
    """Clear order IDs when position is closed."""
    try:
        if ORDER_IDS_FILE.exists():
            ORDER_IDS_FILE.unlink()
            logger.info("[Monitor] Order IDs cleared")
        return True
    except Exception as e:
        logger.error(f"[Monitor] Could not clear order IDs: {e}")
        return False

# ── Import trailing SL manager ───────────────────────────────────────────────────

from execution_layer.lighter.trailing_sl import TrailingSLManager

# ── Price & Position fetching (reused from signal_executor) ───────────────────

async def get_current_price() -> float:
    """Fetch current BTC price from Lighter orderbook."""
    try:
        config = lighter.Configuration(host=BASE_URL)
        async with lighter.ApiClient(config) as api:
            order_api = lighter.OrderApi(api)
            book = await order_api.order_book_details(market_id=BTC_MARKET)
            return float(book.order_book_details[0].last_trade_price)
    except Exception as e:
        logger.error(f"[Monitor] Failed to get price: {e}")
        return None

async def get_open_position() -> dict | None:
    """Check if there's an open position."""
    try:
        config = lighter.Configuration(host=BASE_URL)
        async with lighter.ApiClient(config) as api:
            acc_api = lighter.AccountApi(api)
            r = await acc_api.account(by="index", value=str(ACCOUNT_INDEX))
            acc = r.accounts[0]
            if acc.positions and float(acc.positions[0].position) > 0:
                pos = acc.positions[0]
                return {
                    "side": "LONG" if pos.sign == 1 else "SHORT",
                    "size": float(pos.position),
                    "entry": float(pos.avg_entry_price),
                    "pnl": float(pos.unrealized_pnl),
                    "tied_orders": pos.position_tied_order_count,
                }
        return None
    except Exception as e:
        logger.error(f"[Monitor] Failed to get position: {e}")
        return None

# ── Early Exit Detection ─────────────────────────────────────────────────────

def calculate_pnl_pct(position: dict, current_price: float) -> float:
    """Calculate PnL percentage."""
    entry = position["entry"]
    side = position["side"]
    
    if side == "LONG":
        return (current_price - entry) / entry * 100
    else:
        return (entry - current_price) / entry * 100

def should_early_exit(position: dict, current_price: float) -> tuple[bool, str]:
    """
    Check if position should be closed early due to reversal.
    
    Returns:
        (should_exit, reason)
    """
    pnl_pct = calculate_pnl_pct(position, current_price)
    
    # Condition 1: Significant loss with potential reversal
    if pnl_pct < -1.0:
        # For now, simple threshold
        # TODO: Add reversal indicators (RSI, MACD, volume)
        reason = f"PnL {pnl_pct:.2f}% below -1% threshold"
        logger.info(f"[Monitor] {reason}")
        # Don't exit yet - just log for now
        # return True, reason
    
    # Condition 2: Time exit (24 hours)
    # TODO: Add time tracking
    
    return False, ""

async def close_position_market() -> bool:
    """Close position with market order."""
    try:
        config = lighter.Configuration(host=BASE_URL)
        async with lighter.ApiClient(config) as api:
            acc_api = lighter.AccountApi(api)
            r = await acc_api.account(by="index", value=str(ACCOUNT_INDEX))
            acc = r.accounts[0]
            
            if not acc.positions or float(acc.positions[0].position) == 0:
                logger.info("[Monitor] No position to close")
                return True
            
            pos = acc.positions[0]
            side = "sell" if pos.sign == 1 else "buy"
            amount = abs(float(pos.position))
            
            # Get nonce
            tx_api = lighter.TransactionApi(api)
            resp = await tx_api.next_nonce(
                account_index=ACCOUNT_INDEX, 
                api_key_index=API_KEY_INDEX
            )
            nonce = resp.nonce
            
            # Create SignerClient
            client = lighter.SignerClient(
                url=BASE_URL,
                account_index=ACCOUNT_INDEX,
                api_private_keys={API_KEY_INDEX: API_SECRET},
            )
            
            # Close position
            base_amount = int(amount * 1e5)  # Convert to base_amount
            current_price = await get_current_price()
            avg_price = int(current_price * 10 * (0.98 if side == "sell" else 1.02))
            
            _, resp, err = await client.create_market_order(
                market_index=BTC_MARKET,
                client_order_index=99,  # Use high index for exit orders
                base_amount=base_amount,
                avg_execution_price=avg_price,
                is_ask=(side == "sell"),
                nonce=nonce,
                api_key_index=API_KEY_INDEX,
            )
            
            if err:
                logger.error(f"[Monitor] Failed to close position: {err}")
                return False
            
            logger.info(f"[Monitor] ✅ Position closed via market order")
            await client.close()
            # Clear order IDs since position is closed
            clear_order_ids()
            return True
            
    except Exception as e:
        logger.error(f"[Monitor] Error closing position: {e}", exc_info=True)
        return False

# ── Main Monitoring Cycle ─────────────────────────────────────────────────────

_running = True

def handle_shutdown(signum, frame):
    global _running
    logger.info("[Monitor] Shutdown signal received")
    _running = False

async def monitoring_cycle(trailing_manager: TrailingSLManager):
    """Single monitoring cycle."""
    logger.info("=" * 60)
    logger.info(f"[Monitor] Cycle start at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    
    # 1. Check if position exists
    pos = await get_open_position()
    if not pos:
        logger.info("[Monitor] No open position - skipping")
        # Clear order IDs if position was closed
        clear_order_ids()
        return
    
    logger.info(
        f"[Monitor] Position: {pos['side']} {pos['size']:.5f} BTC "
        f"@ ${pos['entry']:,.2f} | PnL=${pos['pnl']:+.4f} | "
        f"tied_orders={pos['tied_orders']}"
    )
    
    # 2. Get current price
    price = await get_current_price()
    if not price:
        logger.warning("[Monitor] Could not get current price")
        return
    
    logger.info(f"[Monitor] Current price: ${price:,.2f}")
    
    # 3. Calculate PnL
    pnl_pct = calculate_pnl_pct(pos, price)
    logger.info(f"[Monitor] PnL: {pnl_pct:+.2f}%")
    
    # 4. Evaluate trailing SL
    logger.info("[Monitor] Evaluating trailing SL...")
    sl_updated = await trailing_manager.evaluate_and_trail()
    if sl_updated:
        logger.info("[Monitor] ✅ Trailing SL updated")
    else:
        logger.info("[Monitor] No trailing SL update needed")
    
    # 5. Check early exit conditions
    should_exit, reason = should_early_exit(pos, price)
    if should_exit:
        logger.warning(f"[Monitor] ⚠️ Early exit triggered: {reason}")
        # For now, just log - don't auto-close yet
        # success = await close_position_market()
        # if success:
        #     logger.info("[Monitor] ✅ Position closed early")
    
    logger.info("[Monitor] Cycle complete")

async def main():
    global _running
    
    logger.info("=" * 60)
    logger.info("[Monitor] BTC-QUANT Intraday Position Monitor")
    logger.info(f"[Monitor] Check interval: {CHECK_INTERVAL_MINUTES} minutes")
    logger.info(f"[Monitor] Account: {ACCOUNT_INDEX} | API Key: {API_KEY_INDEX}")
    logger.info("=" * 60)
    
    # Initialize trailing SL manager
    trailing_manager = TrailingSLManager(API_SECRET)
    try:
        await trailing_manager.initialize()
        logger.info("[Monitor] Trailing SL manager initialized")
    except Exception as e:
        logger.error(f"[Monitor] Failed to initialize trailing manager: {e}")
        return
    
    try:
        while _running:
            try:
                await monitoring_cycle(trailing_manager)
            except Exception as e:
                logger.error(f"[Monitor] Cycle error: {e}", exc_info=True)
            
            if not _running:
                break
            
            # Wait until next 15-minute mark
            now = datetime.now(timezone.utc)
            next_quarter = ((now.minute // CHECK_INTERVAL_MINUTES) + 1) * CHECK_INTERVAL_MINUTES
            if next_quarter >= 60:
                next_check = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            else:
                next_check = now.replace(minute=next_quarter, second=0, microsecond=0)
            wait_seconds = (next_check - now).total_seconds()
            
            logger.info(
                f"[Monitor] Sleeping {int(wait_seconds // 60)}m until next check at "
                f"{next_check.strftime('%Y-%m-%d %H:%M')} UTC "
                f"({(next_check + timedelta(hours=7)).strftime('%H:%M')} WIB)"
            )
            
            # Sleep in 60s intervals
            for _ in range(int(wait_seconds // 60) + 1):
                if not _running:
                    break
                await asyncio.sleep(60)
    
    finally:
        await trailing_manager.close()
        logger.info("[Monitor] Shutdown complete")

if __name__ == "__main__":
    sig_mod.signal(sig_mod.SIGINT, handle_shutdown)
    sig_mod.signal(sig_mod.SIGTERM, handle_shutdown)
    asyncio.run(main())
