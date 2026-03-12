"""
Base abstract class for exchange execution gateways.

Defines the contract that all exchange implementations must follow.
Allows swapping between Binance, Lighter, and other exchanges without
changing PositionManager logic.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class OrderResult:
    """Result of an order placement attempt."""
    success: bool
    order_id: Optional[str] = None
    filled_price: float = 0.0
    filled_quantity: float = 0.0
    error_message: str = ""


@dataclass
class PositionInfo:
    """Information about an open position."""
    symbol: str                    # "BTC/USDT"
    side: str                      # "LONG" | "SHORT"
    entry_price: float
    quantity: float                # Base currency quantity (BTC)
    unrealized_pnl: float
    leverage: int
    sl_order_id: Optional[str] = None
    tp_order_id: Optional[str] = None
    opened_at_ts: int = 0          # Unix timestamp (ms)


class BaseExchangeExecutionGateway(ABC):
    """
    Abstract base class for exchange execution gateways.

    All exchange implementations must provide:
    - Market order placement
    - Stop-loss and take-profit order placement
    - Position monitoring and closure
    - Account balance tracking
    """

    @abstractmethod
    async def place_market_order(
        self,
        side: str,
        size_usdt: float,
        leverage: int
    ) -> OrderResult:
        """
        Place a market order.

        Args:
            side: "LONG" or "SHORT"
            size_usdt: Margin in USD (e.g., 1000)
            leverage: Leverage multiplier (e.g., 15)

        Returns:
            OrderResult with order_id and filled_price
        """
        ...

    @abstractmethod
    async def place_sl_order(
        self,
        side: str,
        trigger_price: float,
        quantity: float
    ) -> OrderResult:
        """
        Place a stop-loss order.

        Args:
            side: "LONG" or "SHORT" (direction of SL)
            trigger_price: Price at which SL triggers
            quantity: Base currency quantity

        Returns:
            OrderResult with order_id
        """
        ...

    @abstractmethod
    async def place_tp_order(
        self,
        side: str,
        trigger_price: float,
        quantity: float
    ) -> OrderResult:
        """
        Place a take-profit order.

        Args:
            side: "LONG" or "SHORT" (direction of TP)
            trigger_price: Price at which TP triggers
            quantity: Base currency quantity

        Returns:
            OrderResult with order_id
        """
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order.

        Args:
            order_id: Order ID to cancel

        Returns:
            True if cancelled, False otherwise
        """
        ...

    @abstractmethod
    async def get_open_position(self) -> Optional[PositionInfo]:
        """
        Get the current open position.

        Returns:
            PositionInfo if position exists, None otherwise
        """
        ...

    @abstractmethod
    async def close_position_market(self) -> OrderResult:
        """
        Close the current position with a market order.

        Returns:
            OrderResult with exit_price
        """
        ...

    @abstractmethod
    async def get_account_balance(self) -> float:
        """
        Get the account's USDT balance.

        Returns:
            USDT balance as float
        """
        ...
