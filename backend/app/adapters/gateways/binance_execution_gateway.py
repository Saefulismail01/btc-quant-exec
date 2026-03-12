"""
Binance Futures execution gateway for placing and managing live orders.

Supports both testnet and mainnet via EXECUTION_MODE environment variable.
"""

import asyncio
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
import aiohttp
import ccxt.async_support as ccxt_async

from .base_execution_gateway import (
    BaseExchangeExecutionGateway,
    OrderResult,
    PositionInfo,
)

# Load .env
load_dotenv(Path(__file__).resolve().parent.parent.parent.parent / ".env")

logger = logging.getLogger(__name__)


class BinanceExecutionGateway(BaseExchangeExecutionGateway):
    """
    Concrete implementation for Binance Futures (testnet or mainnet).

    Handles:
    - Market order placement
    - Stop-loss and take-profit order placement
    - Position monitoring
    - Order cancellation
    """

    SYMBOL = "BTC/USDT"
    PERP_SYMBOL = "BTC/USDT:USDT"
    RETRY_ATTEMPTS = 3
    RETRY_DELAY = 1.0  # seconds

    def __init__(self):
        """Initialize Binance execution gateway."""
        self.execution_mode = os.getenv("EXECUTION_MODE", "testnet").lower()
        self.trading_enabled = os.getenv("TRADING_ENABLED", "false").lower() == "true"

        if self.execution_mode == "testnet":
            api_key = os.getenv("BINANCE_TESTNET_API_KEY", "").strip()
            secret = os.getenv("BINANCE_TESTNET_SECRET", "").strip()
            use_testnet = True
        else:
            api_key = os.getenv("BINANCE_LIVE_API_KEY", "").strip()
            secret = os.getenv("BINANCE_LIVE_SECRET", "").strip()
            use_testnet = False

        if not api_key or not secret:
            raise ValueError(
                f"Missing credentials for {self.execution_mode} mode. "
                f"Set BINANCE_{'TESTNET' if use_testnet else 'LIVE'}_API_KEY and SECRET."
            )

        # Proxy config (from existing BinanceGateway pattern)
        http_proxy = os.getenv("HTTP_PROXY", "").strip()
        https_proxy = os.getenv("HTTPS_PROXY", "").strip()
        proxy_config = {}
        if http_proxy or https_proxy:
            proxy_config["proxies"] = {
                "http": http_proxy or https_proxy,
                "https": https_proxy or http_proxy,
            }
            proxy_config["aiohttp_proxy"] = https_proxy or http_proxy

        # Initialize CCXT exchange
        # Testnet uses demo-fapi.binance.com (old testnet.binancefuture.com deprecated)
        exchange_config = {
            "apiKey": api_key,
            "secret": secret,
            "enableRateLimit": True,
            "options": {
                "defaultType": "future",
            },
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            **proxy_config,
        }

        if use_testnet:
            exchange_config["urls"] = {
                "api": {
                    "public": "https://demo-fapi.binance.com",
                    "private": "https://demo-fapi.binance.com",
                    "fapiPublic": "https://demo-fapi.binance.com/fapi/v1",
                    "fapiPrivate": "https://demo-fapi.binance.com/fapi/v1",
                    "fapiPublicV2": "https://demo-fapi.binance.com/fapi/v2",
                    "fapiPrivateV2": "https://demo-fapi.binance.com/fapi/v2",
                    "fapiPublicV3": "https://demo-fapi.binance.com/fapi/v3",
                    "fapiPrivateV3": "https://demo-fapi.binance.com/fapi/v3",
                }
            }

        self.exchange = ccxt_async.binance(exchange_config)

        self.exchange.timeout = 20000  # 20 seconds

        # Use ThreadedResolver for DNS (Docker compatibility)
        connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver(), ssl=False)
        self.exchange.session = aiohttp.ClientSession(
            connector=connector,
            trust_env=True,
        )

        logger.info(
            f"[BinanceExecution] Initialized in {self.execution_mode} mode. "
            f"Trading: {'ENABLED' if self.trading_enabled else 'DISABLED'}"
        )

    async def close(self):
        """Close the exchange session."""
        await self.exchange.close()

    async def _retry_call(self, coro, operation_name: str):
        """
        Retry a coroutine with exponential backoff.

        Args:
            coro: Coroutine to execute
            operation_name: For logging

        Returns:
            Result of coro or raises exception
        """
        for attempt in range(self.RETRY_ATTEMPTS):
            try:
                return await coro()
            except Exception as e:
                if attempt < self.RETRY_ATTEMPTS - 1:
                    wait_time = self.RETRY_DELAY * (2 ** attempt)
                    logger.warning(
                        f"[BinanceExecution] {operation_name} attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"[BinanceExecution] {operation_name} failed after {self.RETRY_ATTEMPTS} attempts: {e}")
                    raise

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
            size_usdt: Margin in USDT (e.g., 1000)
            leverage: Leverage (e.g., 15)

        Returns:
            OrderResult
        """
        try:
            # Prevent actual order if trading disabled
            if not self.trading_enabled:
                logger.warning("[BinanceExecution] Trading disabled. Order NOT placed.")
                return OrderResult(
                    success=False,
                    error_message="Trading is disabled (TRADING_ENABLED=false)"
                )

            # 1. Set leverage
            ccxt_side = "long" if side == "LONG" else "short"
            try:
                await self._retry_call(
                    lambda: self.exchange.privatePostSetLeverage({
                        "symbol": "BTCUSDT",
                        "leverage": leverage,
                    }),
                    f"Set leverage {leverage}x"
                )
            except Exception as e:
                logger.warning(f"[BinanceExecution] Failed to set leverage: {e}")

            # 2. Fetch current price
            ticker = await self._retry_call(
                lambda: self.exchange.fetch_ticker(self.PERP_SYMBOL),
                "Fetch ticker"
            )
            current_price = ticker["last"]
            logger.info(f"[BinanceExecution] Current {self.SYMBOL} price: ${current_price:,.2f}")

            # 3. Calculate quantity
            notional = size_usdt * leverage
            quantity = notional / current_price
            logger.info(
                f"[BinanceExecution] Calculated quantity: {quantity:.8f} BTC "
                f"(${size_usdt} × {leverage}x / ${current_price:,.2f})"
            )

            # 4. Round to Binance precision (typically 0.001 BTC)
            # Fetch market info to get exact precision
            market = self.exchange.market(self.PERP_SYMBOL)
            amount_precision = market.get("precision", {}).get("amount", 0.001)
            quantity = round(quantity / amount_precision) * amount_precision

            # 5. Place market order
            order_params = {
                "stopPrice": None,
                "postOnly": False,
            }

            order = await self._retry_call(
                lambda: self.exchange.create_order(
                    self.PERP_SYMBOL,
                    "market",
                    side.lower(),
                    quantity,
                    params=order_params,
                ),
                f"Place {side} market order"
            )

            order_id = order.get("id")
            filled_price = order.get("average", current_price)
            filled_quantity = order.get("amount", quantity)

            logger.info(
                f"[BinanceExecution] ✅ Order placed: {order_id} "
                f"| {side} {filled_quantity:.8f} BTC @ ${filled_price:,.2f}"
            )

            return OrderResult(
                success=True,
                order_id=order_id,
                filled_price=filled_price,
                filled_quantity=filled_quantity,
            )

        except Exception as e:
            logger.error(f"[BinanceExecution] Market order placement failed: {e}", exc_info=True)
            return OrderResult(
                success=False,
                error_message=str(e)
            )

    async def place_sl_order(
        self,
        side: str,
        trigger_price: float,
        quantity: float
    ) -> OrderResult:
        """
        Place a stop-loss order (STOP_MARKET).

        Args:
            side: Direction ("LONG" or "SHORT")
            trigger_price: Trigger price for SL
            quantity: Quantity to close

        Returns:
            OrderResult
        """
        try:
            if not self.trading_enabled:
                return OrderResult(
                    success=False,
                    error_message="Trading is disabled"
                )

            # SL closes position in opposite direction
            ccxt_side = "sell" if side == "LONG" else "buy"

            order_params = {
                "stopPrice": trigger_price,
                "closePosition": True,
                "type": "STOP_MARKET",
            }

            order = await self._retry_call(
                lambda: self.exchange.create_order(
                    self.PERP_SYMBOL,
                    "market",
                    ccxt_side,
                    quantity,
                    params=order_params,
                ),
                f"Place SL order for {side}"
            )

            order_id = order.get("id")
            logger.info(
                f"[BinanceExecution] ✅ SL order placed: {order_id} | {side} SL @ ${trigger_price:,.2f}"
            )

            return OrderResult(
                success=True,
                order_id=order_id,
                filled_price=trigger_price,
                filled_quantity=quantity,
            )

        except Exception as e:
            logger.error(f"[BinanceExecution] SL order placement failed: {e}", exc_info=True)
            return OrderResult(
                success=False,
                error_message=str(e)
            )

    async def place_tp_order(
        self,
        side: str,
        trigger_price: float,
        quantity: float
    ) -> OrderResult:
        """
        Place a take-profit order (TAKE_PROFIT_MARKET).

        Args:
            side: Direction ("LONG" or "SHORT")
            trigger_price: Trigger price for TP
            quantity: Quantity to close

        Returns:
            OrderResult
        """
        try:
            if not self.trading_enabled:
                return OrderResult(
                    success=False,
                    error_message="Trading is disabled"
                )

            # TP closes position in opposite direction
            ccxt_side = "sell" if side == "LONG" else "buy"

            order_params = {
                "stopPrice": trigger_price,
                "closePosition": True,
                "type": "TAKE_PROFIT_MARKET",
            }

            order = await self._retry_call(
                lambda: self.exchange.create_order(
                    self.PERP_SYMBOL,
                    "market",
                    ccxt_side,
                    quantity,
                    params=order_params,
                ),
                f"Place TP order for {side}"
            )

            order_id = order.get("id")
            logger.info(
                f"[BinanceExecution] ✅ TP order placed: {order_id} | {side} TP @ ${trigger_price:,.2f}"
            )

            return OrderResult(
                success=True,
                order_id=order_id,
                filled_price=trigger_price,
                filled_quantity=quantity,
            )

        except Exception as e:
            logger.error(f"[BinanceExecution] TP order placement failed: {e}", exc_info=True)
            return OrderResult(
                success=False,
                error_message=str(e)
            )

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order.

        Args:
            order_id: Order ID to cancel

        Returns:
            True if cancelled, False otherwise
        """
        try:
            await self._retry_call(
                lambda: self.exchange.cancel_order(order_id, self.PERP_SYMBOL),
                f"Cancel order {order_id}"
            )
            logger.info(f"[BinanceExecution] ✅ Order cancelled: {order_id}")
            return True
        except Exception as e:
            logger.warning(f"[BinanceExecution] Failed to cancel order {order_id}: {e}")
            return False

    async def get_open_position(self) -> PositionInfo | None:
        """
        Get the current open BTC/USDT position.

        Returns:
            PositionInfo if position exists, None otherwise
        """
        try:
            positions = await self._retry_call(
                lambda: self.exchange.fetch_positions(),
                "Fetch positions"
            )

            # Find BTC/USDT position
            btc_pos = next((p for p in positions if p["symbol"] == self.PERP_SYMBOL), None)

            if not btc_pos or btc_pos.get("contracts", 0) == 0:
                return None

            info = btc_pos.get("info", {})
            side = btc_pos.get("side", "").upper()
            if side not in ["LONG", "SHORT"]:
                return None

            return PositionInfo(
                symbol=self.SYMBOL,
                side=side,
                entry_price=float(btc_pos.get("entryPrice", 0)),
                quantity=float(btc_pos.get("contracts", 0)),
                unrealized_pnl=float(btc_pos.get("unrealizedPnl", 0)),
                leverage=int(info.get("leverage", 15)),
                sl_order_id=info.get("stopOrderId"),
                tp_order_id=info.get("profitOrderId"),
                opened_at_ts=int(info.get("time", 0)),
            )

        except Exception as e:
            logger.error(f"[BinanceExecution] Failed to fetch position: {e}")
            return None

    async def close_position_market(self) -> OrderResult:
        """
        Close the current position with a market order.

        Returns:
            OrderResult with exit price
        """
        try:
            position = await self.get_open_position()
            if not position:
                return OrderResult(
                    success=False,
                    error_message="No open position to close"
                )

            # Close in opposite direction
            ccxt_side = "sell" if position.side == "LONG" else "buy"

            order = await self._retry_call(
                lambda: self.exchange.create_order(
                    self.PERP_SYMBOL,
                    "market",
                    ccxt_side,
                    position.quantity,
                ),
                f"Close {position.side} position"
            )

            order_id = order.get("id")
            exit_price = order.get("average", 0)

            logger.info(
                f"[BinanceExecution] ✅ Position closed: {order_id} | {position.side} "
                f"{position.quantity:.8f} BTC @ ${exit_price:,.2f}"
            )

            return OrderResult(
                success=True,
                order_id=order_id,
                filled_price=exit_price,
                filled_quantity=position.quantity,
            )

        except Exception as e:
            logger.error(f"[BinanceExecution] Failed to close position: {e}", exc_info=True)
            return OrderResult(
                success=False,
                error_message=str(e)
            )

    async def get_account_balance(self) -> float:
        """
        Get account USDT balance.

        Returns:
            USDT balance as float
        """
        try:
            balance = await self._retry_call(
                lambda: self.exchange.fetch_balance(),
                "Fetch balance"
            )

            usdt_balance = balance.get("USDT", {})
            free = float(usdt_balance.get("free", 0))

            logger.info(f"[BinanceExecution] Account balance: ${free:,.2f} USDT")
            return free

        except Exception as e:
            logger.error(f"[BinanceExecution] Failed to fetch balance: {e}")
            return 0.0
