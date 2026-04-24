"""Adapter from LighterExecutionGateway to LighterGatewayProtocol (Tier 0b)."""
from __future__ import annotations
import logging
from typing import Any, Optional
from backend.app.adapters.repositories.reconciliation.models import LighterClosedOrder, LighterPosition
from backend.app.adapters.repositories.reconciliation.lighter_reconciliation_worker import LighterGatewayProtocol

logger = logging.getLogger(__name__)


class LighterGatewayAdapter(LighterGatewayProtocol):
    """
    Adapter that wraps LighterExecutionGateway to satisfy LighterGatewayProtocol.
    
    This bridges the existing gateway implementation with the reconciliation worker
    without modifying the original gateway code.
    """

    def __init__(self, gateway: Any) -> None:
        """
        Args:
            gateway: LighterExecutionGateway instance
        """
        self._gateway = gateway

    async def get_open_position_ids(self) -> set[str]:
        """Fetch open positions and return set of order_ids."""
        try:
            account = await self._gateway.get_account()
            positions = account.get("positions", [])
            # Filter for BTC market (market_id=1 typically)
            order_ids = set()
            for pos in positions:
                if pos.get("size", 0) != 0:
                    order_id = pos.get("order_id") or pos.get("id")
                    if order_id:
                        order_ids.add(str(order_id))
            return order_ids
        except Exception as exc:
            logger.error("[LighterGatewayAdapter] get_open_position_ids failed", extra={"error": str(exc)})
            raise

    async def get_open_position_details(self, order_id: str) -> LighterPosition:
        """Fetch details for a specific open position."""
        try:
            account = await self._gateway.get_account()
            positions = account.get("positions", [])
            for pos in positions:
                pos_order_id = pos.get("order_id") or pos.get("id")
                if str(pos_order_id) == order_id:
                    return LighterPosition(
                        order_id=str(order_id),
                        symbol="BTC/USDC",  # From market_id mapping
                        side="LONG" if pos.get("size", 0) > 0 else "SHORT",
                        entry_price=float(pos.get("entry_price", 0)),
                        size_base=float(abs(pos.get("size", 0))),
                        ts_open_ms=int(pos.get("opened_at", 0)),
                    )
            raise ValueError(f"Position {order_id} not found")
        except Exception as exc:
            logger.error("[LighterGatewayAdapter] get_open_position_details failed", extra={"order_id": order_id, "error": str(exc)})
            raise

    async def fetch_inactive_orders_page(
        self, limit: int = 100, cursor: str | None = None,
        between_timestamps: tuple[int, int] | None = None,
    ) -> tuple[list[LighterClosedOrder], str | None]:
        """Fetch page of inactive/closed orders."""
        try:
            # Use existing fetch_last_closed_order or similar from gateway
            # This is a placeholder - actual implementation depends on gateway capabilities
            orders: list[LighterClosedOrder] = []
            next_cursor: Optional[str] = None
            
            # TODO: Implement using gateway's fetch methods
            # For now, return empty to allow compilation
            logger.warning("[LighterGatewayAdapter] fetch_inactive_orders_page not fully implemented")
            return orders, next_cursor
        except Exception as exc:
            logger.error("[LighterGatewayAdapter] fetch_inactive_orders_page failed", extra={"error": str(exc)})
            raise

    async def get_closed_order_by_id(self, order_id: str) -> LighterClosedOrder | None:
        """Fetch a specific closed order by ID."""
        try:
            # Use gateway's fetch_entry_fill_quote or similar
            # This is a placeholder - actual implementation depends on gateway capabilities
            logger.warning("[LighterGatewayAdapter] get_closed_order_by_id not fully implemented")
            return None
        except Exception as exc:
            logger.error("[LighterGatewayAdapter] get_closed_order_by_id failed", extra={"order_id": order_id, "error": str(exc)})
            return None
