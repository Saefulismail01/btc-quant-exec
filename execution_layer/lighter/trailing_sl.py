#!/usr/bin/env python3
"""
Trailing Stop Loss Manager for BTC-QUANT

Manages trailing SL logic to lock profits when position moves in favor.
Works with Lighter mainnet execution.

Parameters:
- TRAILING_PROFIT_THRESHOLD: Minimum % profit before trailing starts
- TRAILING_LOCK_PROFIT: Minimum % profit to lock when trailing
"""

import logging
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict
from pathlib import Path

# Import lighter for API calls
import lighter

# ── Configuration ─────────────────────────────────────────────────────────────

# Trailing SL parameters
TRAILING_PROFIT_THRESHOLD = 1.0  # % profit before trailing starts
TRAILING_LOCK_PROFIT = 0.5       # % profit to lock when trailing
TRAILING_STEP = 0.25             # Minimum price movement % before updating SL

# Lighter configuration
BASE_URL = "https://mainnet.zklighter.elliot.ai"
API_SECRET = None  # Will be loaded from env
API_KEY_INDEX = 3
ACCOUNT_INDEX = 718591
BTC_MARKET = 1

# Order IDs state file (same as signal_executor)
ORDER_IDS_FILE = Path(__file__).parent / "order_ids.json"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Order ID tracking helpers ─────────────────────────────────────────────────────

def load_order_ids() -> dict:
    """Load order IDs from disk."""
    try:
        if ORDER_IDS_FILE.exists():
            with open(ORDER_IDS_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"[TrailingSL] Could not load order IDs: {e}")
    return {}


def save_order_ids(order_ids: dict) -> bool:
    """Save order IDs to disk."""
    try:
        with open(ORDER_IDS_FILE, "w") as f:
            json.dump(order_ids, f, indent=2)
        logger.info(f"[TrailingSL] Saved order IDs: {order_ids}")
        return True
    except Exception as e:
        logger.error(f"[TrailingSL] Could not save order IDs: {e}")
        return False


# ── Trailing SL Logic ─────────────────────────────────────────────────────────

class TrailingSLManager:
    """Manages trailing stop loss for open positions."""
    
    def __init__(self, api_secret: str):
        self.api_secret = api_secret
        if self.api_secret.startswith("0x"):
            self.api_secret = self.api_secret[2:]
        
        self.client = None
        self._last_sl_update = {}  # Track last SL update per position
        
    async def initialize(self):
        """Initialize Lighter client."""
        try:
            config = lighter.Configuration(host=BASE_URL)
            self.client = lighter.SignerClient(
                url=BASE_URL,
                account_index=ACCOUNT_INDEX,
                api_private_keys={API_KEY_INDEX: self.api_secret},
            )
            logger.info("[TrailingSL] Client initialized")
        except Exception as e:
            logger.error(f"[TrailingSL] Failed to initialize client: {e}")
            raise
    
    async def close(self):
        """Close Lighter client."""
        if self.client:
            await self.client.close()
    
    async def get_open_position(self) -> Optional[Dict]:
        """Get current open position from Lighter."""
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
                        "sl_price": self._extract_sl_price(acc),
                    }
        except Exception as e:
            logger.error(f"[TrailingSL] Failed to get position: {e}")
        return None
    
    def _extract_sl_price(self, account) -> Optional[float]:
        """Extract SL price from account orders."""
        try:
            if hasattr(account, 'orders'):
                for order in account.orders:
                    # Check if this is a stop loss order
                    if hasattr(order, 'order_type'):
                        order_type = str(order.order_type).lower()
                        if 'stop' in order_type and hasattr(order, 'trigger_price'):
                            return float(order.trigger_price) / 10.0  # Convert from scaled
        except Exception as e:
            logger.warning(f"[TrailingSL] Failed to extract SL price: {e}")
        return None
    
    async def get_current_price(self) -> Optional[float]:
        """Get current BTC price from Lighter orderbook."""
        try:
            config = lighter.Configuration(host=BASE_URL)
            async with lighter.ApiClient(config) as api:
                order_api = lighter.OrderApi(api)
                book = await order_api.order_book_details(market_id=BTC_MARKET)
                return float(book.order_book_details[0].last_trade_price)
        except Exception as e:
            logger.error(f"[TrailingSL] Failed to get price: {e}")
        return None
    
    def should_trail_sl(self, position: Dict, current_price: float) -> bool:
        """
        Check if SL should be trailed based on profit threshold.
        
        Args:
            position: Position dict with entry, side
            current_price: Current market price
            
        Returns:
            True if SL should be trailed
        """
        entry = position["entry"]
        side = position["side"]
        
        if side == "LONG":
            profit_pct = (current_price - entry) / entry * 100
        else:  # SHORT
            profit_pct = (entry - current_price) / entry * 100
        
        should_trail = profit_pct >= TRAILING_PROFIT_THRESHOLD
        
        if should_trail:
            logger.info(
                f"[TrailingSL] Profit {profit_pct:.2f}% >= threshold "
                f"{TRAILING_PROFIT_THRESHOLD}% - should trail"
            )
        
        return should_trail
    
    def calculate_trailing_sl(self, position: Dict, current_price: float) -> float:
        """
        Calculate new trailing SL price.
        
        Args:
            position: Position dict with entry, side
            current_price: Current market price
            
        Returns:
            New SL price
        """
        entry = position["entry"]
        side = position["side"]
        current_sl = position.get("sl_price", entry)
        
        if side == "LONG":
            # Lock profit: SL = entry * (1 + lock_profit%)
            new_sl = entry * (1 + TRAILING_LOCK_PROFIT / 100)
            # Only trail if new SL is higher (more favorable)
            new_sl = max(new_sl, current_sl)
        else:  # SHORT
            # Lock profit: SL = entry * (1 - lock_profit%)
            new_sl = entry * (1 - TRAILING_LOCK_PROFIT / 100)
            # Only trail if new SL is lower (more favorable for short)
            new_sl = min(new_sl, current_sl)
        
        logger.info(
            f"[TrailingSL] Calculated trailing SL: ${new_sl:.2f} "
            f"(current: ${current_sl:.2f}, entry: ${entry:.2f})"
        )
        
        return new_sl
    
    def check_trailing_step(self, new_sl: float, current_sl: float) -> bool:
        """
        Check if movement is significant enough to update SL.
        
        Args:
            new_sl: Proposed new SL price
            current_sl: Current SL price
            
        Returns:
            True if movement >= TRAILING_STEP
        """
        movement_pct = abs(new_sl - current_sl) / current_sl * 100
        return movement_pct >= TRAILING_STEP
    
    async def cancel_order(self, order_id: str, nonce: int) -> bool:
        """
        Cancel an order by its transaction hash.
        
        Args:
            order_id: Transaction hash of the order to cancel
            nonce: Current nonce
            
        Returns:
            True if successful
        """
        try:
            # Cancel order using SignerClient
            _, _, err = await self.client.cancel_order(
                order_id=order_id,
                nonce=nonce,
                api_key_index=API_KEY_INDEX,
            )
            if err:
                logger.error(f"[TrailingSL] Failed to cancel order {order_id}: {err}")
                return False
            logger.info(f"[TrailingSL] Cancelled order {order_id}")
            return True
        except Exception as e:
            logger.error(f"[TrailingSL] Cancel order error: {e}")
            return False
    
    async def update_sl_order(self, position: Dict, new_sl_price: float) -> bool:
        """
        Update SL order to new price using cancel + create pattern.
        
        Args:
            position: Position dict
            new_sl_price: New SL price
            
        Returns:
            True if successful
        """
        try:
            # Load order IDs
            order_ids = load_order_ids()
            sl_order_id = order_ids.get("sl")
            
            if not sl_order_id:
                logger.warning("[TrailingSL] No SL order ID found - cannot update")
                return False
            
            logger.info(f"[TrailingSL] Updating SL from ${position.get('sl_price', 'N/A')} to ${new_sl_price:.2f}")
            
            # Get current nonce
            config = lighter.Configuration(host=BASE_URL)
            async with lighter.ApiClient(config) as api:
                tx_api = lighter.TransactionApi(api)
                resp = await tx_api.next_nonce(
                    account_index=ACCOUNT_INDEX, 
                    api_key_index=API_KEY_INDEX
                )
                nonce = resp.nonce
            
            # Step 1: Cancel existing SL order
            logger.info(f"[TrailingSL] Cancelling existing SL order {sl_order_id}")
            cancel_success = await self.cancel_order(sl_order_id, nonce)
            if not cancel_success:
                logger.error("[TrailingSL] Failed to cancel SL order - aborting update")
                return False
            
            nonce += 1
            time.sleep(3)  # Wait for cancel to settle
            
            # Step 2: Calculate order parameters for new SL
            side = position["side"]
            base_amount = int(position["size"] * 1e5)  # Convert to base_amount
            sl_scaled = int(new_sl_price * 10)
            
            # SL closes position (opposite side)
            is_ask = (side == "LONG")
            
            # Step 3: Create new SL order
            logger.info(f"[TrailingSL] Creating new SL order @ ${new_sl_price:.2f}")
            _, resp_sl, err_sl = await self.client.create_order(
                market_index=BTC_MARKET,
                client_order_index=1,  # Use same index as original
                base_amount=base_amount,
                price=sl_scaled,
                is_ask=is_ask,
                order_type=lighter.SignerClient.ORDER_TYPE_STOP_LOSS_LIMIT,
                time_in_force=lighter.SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
                trigger_price=sl_scaled,
                reduce_only=1,
                nonce=nonce,
                api_key_index=API_KEY_INDEX,
            )
            
            if err_sl:
                logger.error(f"[TrailingSL] Failed to create new SL order: {err_sl}")
                # Try to restore old SL (this is complex, skip for now)
                return False
            
            logger.info(f"[TrailingSL] New SL order created: {getattr(resp_sl, 'tx_hash', 'n/a')}")
            
            # Step 4: Update order IDs
            order_ids["sl"] = getattr(resp_sl, 'tx_hash', None)
            order_ids["updated_at"] = datetime.now(timezone.utc).isoformat()
            save_order_ids(order_ids)
            
            logger.info(f"[TrailingSL] ✅ SL successfully updated to ${new_sl_price:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"[TrailingSL] Failed to update SL: {e}", exc_info=True)
            return False
    
    async def evaluate_and_trail(self) -> bool:
        """
        Main evaluation cycle: check position and trail SL if needed.
        
        Returns:
            True if SL was updated, False otherwise
        """
        try:
            # Get position
            pos = await self.get_open_position()
            if not pos:
                logger.debug("[TrailingSL] No open position")
                return False
            
            # Get current price
            price = await self.get_current_price()
            if not price:
                logger.warning("[TrailingSL] Could not get current price")
                return False
            
            # Check if should trail
            if not self.should_trail_sl(pos, price):
                logger.debug("[TrailingSL] Profit threshold not met")
                return False
            
            # Calculate new SL
            new_sl = self.calculate_trailing_sl(pos, price)
            
            # Check if movement is significant enough (avoid too frequent updates)
            current_sl = pos.get("sl_price", pos["entry"])
            if not self.check_trailing_step(new_sl, current_sl):
                movement_pct = abs(new_sl - current_sl) / current_sl * 100
                logger.debug(
                    f"[TrailingSL] Movement {movement_pct:.2f}% < step {TRAILING_STEP}% - skip"
                )
                return False
            
            # Update SL order
            success = await self.update_sl_order(pos, new_sl)
            
            if success:
                logger.info(f"[TrailingSL] ✅ SL updated to ${new_sl:.2f}")
            
            return success
            
        except Exception as e:
            logger.error(f"[TrailingSL] Evaluation error: {e}", exc_info=True)
            return False


# ── Main for Testing ─────────────────────────────────────────────────────────

async def main():
    """Test trailing SL logic."""
    import os
    from dotenv import load_dotenv
    
    # Load env
    load_dotenv(Path(__file__).parent.parent.parent / ".env")
    
    api_secret = os.getenv("LIGHTER_MAINNET_API_SECRET", "")
    if not api_secret:
        logger.error("LIGHTER_MAINNET_API_SECRET not set")
        return
    
    manager = TrailingSLManager(api_secret)
    
    try:
        await manager.initialize()
        
        # Test evaluation
        result = await manager.evaluate_and_trail()
        logger.info(f"[TrailingSL] Evaluation result: {result}")
        
    finally:
        await manager.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
