"""
PositionManager: Core execution logic for live trading.

Receives SignalResponse and decides whether to open, hold, or close positions.
Manages order placement, risk checks, and position state.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional
from types import SimpleNamespace

from app.schemas.signal import SignalResponse
from app.adapters.gateways.base_execution_gateway import (
    BaseExchangeExecutionGateway,
    OrderResult,
    PositionInfo,
)
from app.adapters.repositories.live_trade_repository import LiveTradeRepository
from app.use_cases.risk_manager import RiskManager
from app.use_cases.execution_notifier_use_case import get_execution_notifier

logger = logging.getLogger(__name__)

# Golden v4.4 Parameters (FIXED — do not change without backtest validation)
MARGIN_USDT = 1000.0  # Fixed margin per trade
LEVERAGE = 15  # Fixed leverage
SL_PERCENT = 1.333  # Stop loss percentage
TP_PERCENT = 0.71  # Take profit percentage
TIME_EXIT_CANDLES = 6  # 6 × 4h = 24 hours
CANDLE_DURATION_MS = 4 * 60 * 60 * 1000  # 4 hours in ms


class PositionManager:
    """
    Manages position lifecycle: open, hold, close.

    Decision flow:
    1. Check TRADING_ENABLED flag
    2. Sync position status (detect SL/TP fills)
    3. If open position exists: manage existing
    4. If no position: try to open new one
    """

    def __init__(
        self,
        gateway: BaseExchangeExecutionGateway,
        repo: LiveTradeRepository,
        risk_manager: Optional[RiskManager] = None,
    ):
        self.gateway = gateway
        self.repo = repo
        self.risk_manager = risk_manager or RiskManager()
        self.notifier = get_execution_notifier()

    async def sync_position_status(self) -> bool:
        """
        Sync position status from exchange.

        Detects if SL or TP were hit since last cycle.
        Updates database and sends notifications if position closed.

        Returns:
            True if position still open or no position, False if error
        """
        try:
            # Get open trade from DB
            db_trade = self.repo.get_open_trade()
            if not db_trade:
                return True  # No position to sync

            logger.info(
                f"[PositionManager] Syncing position status: {db_trade.side} "
                f"@ ${db_trade.entry_price:,.2f}"
            )

            # Get position from exchange
            exchange_pos = await self.gateway.get_open_position()

            if exchange_pos is None:
                # Position closed (SL or TP hit)
                logger.warning(
                    f"[PositionManager] Position closed at exchange (SL/TP hit). "
                    f"DB still shows OPEN."
                )

                # Try to get actual order fills from gateway
                exit_price = None
                exit_type = "UNKNOWN"
                try:
                    # First, try to fetch actual filled order from exchange
                    last_order = await self.gateway.fetch_last_closed_order()
                    if last_order:
                        exit_price = last_order.get("filled_price", db_trade.entry_price)
                        # Determine exit type by comparing exit price to SL/TP
                        if abs(exit_price - db_trade.sl_price) < abs(exit_price - db_trade.tp_price):
                            exit_type = "SL"
                        else:
                            exit_type = "TP"
                        logger.info(
                            f"[PositionManager] Detected exit from order history: "
                            f"{exit_type} @ ${exit_price:,.2f}"
                        )
                    else:
                        # Fallback: Use heuristic (distance to SL vs TP)
                        if db_trade.entry_price > 0:
                            sl_dist = abs(db_trade.entry_price - db_trade.sl_price)
                            tp_dist = abs(db_trade.entry_price - db_trade.tp_price)
                            if sl_dist < tp_dist:
                                exit_price = db_trade.sl_price
                                exit_type = "SL"
                                logger.info(f"[PositionManager] Heuristic: SL hit (distance: {sl_dist:.2f} vs {tp_dist:.2f})")
                            else:
                                exit_price = db_trade.tp_price
                                exit_type = "TP"
                                logger.info(f"[PositionManager] Heuristic: TP hit (distance: {tp_dist:.2f} vs {sl_dist:.2f})")
                        else:
                            exit_price = db_trade.entry_price
                            exit_type = "MANUAL"
                            logger.warning("[PositionManager] Using entry price as fallback")
                except Exception as e:
                    logger.error(f"[PositionManager] Error determining exit: {e}")
                    # Fallback to heuristic on error
                    if db_trade.entry_price > 0:
                        sl_dist = abs(db_trade.entry_price - db_trade.sl_price)
                        tp_dist = abs(db_trade.entry_price - db_trade.tp_price)
                        exit_price = db_trade.sl_price if sl_dist < tp_dist else db_trade.tp_price
                        exit_type = "SL" if sl_dist < tp_dist else "TP"
                    else:
                        exit_price = db_trade.entry_price
                        exit_type = "ERROR"

                # Calculate PnL
                pnl_usdt = self._calculate_pnl(db_trade, exit_price)
                pnl_pct = (pnl_usdt / db_trade.size_usdt * 100) if db_trade.size_usdt > 0 else 0

                # Update DB
                self.repo.update_trade_on_close(
                    db_trade.id,
                    exit_price=exit_price,
                    exit_type=exit_type,
                    pnl_usdt=pnl_usdt,
                    pnl_pct=pnl_pct,
                )

                # Record result for risk manager
                if self.risk_manager:
                    self.risk_manager.record_trade_result(pnl_pct)

                logger.info(
                    f"[PositionManager] ✅ Position closed via {exit_type} | "
                    f"PnL: ${pnl_usdt:+.2f} ({pnl_pct:+.2f}%)"
                )

                # Send Telegram notification
                hold_time_hours = self._get_position_hold_time_hours(db_trade)
                try:
                    await self.notifier.notify_trade_closed(
                        trade_id=db_trade.id,
                        side=db_trade.side,
                        entry_price=db_trade.entry_price,
                        exit_price=exit_price,
                        exit_type=exit_type,
                        pnl_usdt=pnl_usdt,
                        pnl_pct=pnl_pct,
                        hold_time_hours=hold_time_hours,
                        size_usdt=db_trade.size_usdt,
                        leverage=db_trade.leverage,
                    )
                except Exception as e:
                    logger.warning(f"[PositionManager] Failed to send trade closed notification: {e}")

                return True

            logger.info(
                f"[PositionManager] ✅ Position still open at exchange | "
                f"Entry: ${exchange_pos.entry_price:,.2f} | PnL: ${exchange_pos.unrealized_pnl:+.2f}"
            )
            return True

        except Exception as e:
            logger.error(f"[PositionManager] Error syncing position: {e}", exc_info=True)
            return False

    async def process_signal(self, signal: SignalResponse) -> bool:
        """
        Process incoming signal and execute trading logic.

        Args:
            signal: SignalResponse from signal pipeline

        Returns:
            True if processed successfully, False otherwise
        """
        try:
            logger.info(f"[PositionManager] Processing signal | Verdict: {signal.confluence.verdict}")

            # Check trading enabled flag
            if not self._is_trading_enabled():
                logger.info("[PositionManager] Trading disabled (TRADING_ENABLED=false)")
                return True

            # Get or manage existing position
            db_trade = self.repo.get_open_trade()

            if db_trade:
                logger.info(f"[PositionManager] Open position exists | Managing...")
                return await self._manage_existing_position(signal, db_trade)
            else:
                logger.info("[PositionManager] No open position | Trying to open new...")
                return await self._try_open_position(signal)

        except Exception as e:
            logger.error(f"[PositionManager] Error processing signal: {e}", exc_info=True)
            return False

    async def _manage_existing_position(self, signal: SignalResponse, db_trade) -> bool:
        """
        Manage an existing open position.

        Checks:
        1. If position still exists at exchange
        2. If TIME_EXIT triggered (6 candles / 24h)

        Args:
            signal: Current signal
            db_trade: Database trade record

        Returns:
            True if processed, False on error
        """
        try:
            # Verify position still exists
            exchange_pos = await self.gateway.get_open_position()
            if not exchange_pos:
                logger.warning("[PositionManager] Position no longer exists at exchange")
                # Already handled by sync_position_status, don't double-update
                return True

            # Check TIME_EXIT trigger
            if self._should_time_exit(db_trade):
                logger.warning(
                    f"[PositionManager] ⏰ TIME_EXIT triggered after 6 candle (24h). "
                    f"Closing position..."
                )

                # Cancel SL and TP orders
                if db_trade.sl_order_id:
                    await self.gateway.cancel_order(db_trade.sl_order_id)
                if db_trade.tp_order_id:
                    await self.gateway.cancel_order(db_trade.tp_order_id)

                # Close with market order
                close_result = await self.gateway.close_position_market()
                if not close_result.success:
                    logger.error(
                        f"[PositionManager] Failed to close position: {close_result.error_message}"
                    )
                    return False

                # Update DB
                exit_price = close_result.filled_price
                pnl_usdt = self._calculate_pnl(db_trade, exit_price)
                pnl_pct = (pnl_usdt / db_trade.size_usdt * 100) if db_trade.size_usdt > 0 else 0

                self.repo.update_trade_on_close(
                    db_trade.id,
                    exit_price=exit_price,
                    exit_type="TIME_EXIT",
                    pnl_usdt=pnl_usdt,
                    pnl_pct=pnl_pct,
                )

                if self.risk_manager:
                    self.risk_manager.record_trade_result(pnl_pct)

                logger.info(
                    f"[PositionManager] ✅ TIME_EXIT closed | "
                    f"Exit: ${exit_price:,.2f} | PnL: ${pnl_usdt:+.2f} ({pnl_pct:+.2f}%)"
                )

                # Send Telegram notification
                hold_time_hours = self._get_position_hold_time_hours(db_trade)
                try:
                    await self.notifier.notify_trade_closed(
                        trade_id=db_trade.id,
                        side=db_trade.side,
                        entry_price=db_trade.entry_price,
                        exit_price=exit_price,
                        exit_type="TIME_EXIT",
                        pnl_usdt=pnl_usdt,
                        pnl_pct=pnl_pct,
                        hold_time_hours=hold_time_hours,
                        size_usdt=db_trade.size_usdt,
                        leverage=db_trade.leverage,
                    )
                except Exception as e:
                    logger.warning(f"[PositionManager] Failed to send trade closed notification: {e}")

                return True

            logger.info(
                f"[PositionManager] Position held | "
                f"Time: {self._get_position_hold_time(db_trade)} | "
                f"PnL: ${exchange_pos.unrealized_pnl:+.2f}"
            )
            return True

        except Exception as e:
            logger.error(f"[PositionManager] Error managing position: {e}", exc_info=True)
            return False

    async def _try_open_position(self, signal: SignalResponse) -> bool:
        """
        Try to open a new position.

        Checks:
        1. Signal is ACTIVE
        2. Risk manager approval
        3. Place market order
        4. Place SL/TP orders
        5. Record to DB

        Args:
            signal: Current signal

        Returns:
            True if processed (success or declined), False on error
        """
        try:
            # Check signal status
            if signal.trade_plan.status != "ACTIVE":
                logger.info(
                    f"[PositionManager] Signal not ACTIVE (status={signal.trade_plan.status}). "
                    f"Skipping open."
                )
                return True

            # Check RiskManager (with actual account balance for proper position sizing)
            if self.risk_manager:
                try:
                    account_balance = await self.gateway.get_account_balance()
                    risk_result = self.risk_manager.evaluate(portfolio_value=account_balance)
                    if not risk_result.allowed:
                        logger.warning(
                            f"[PositionManager] RiskManager blocked: {risk_result.reason} "
                            f"(balance: ${account_balance:,.2f})"
                        )
                        return True
                except Exception as e:
                    logger.error(f"[PositionManager] Failed to check risk: {e}")
                    # Fail-safe: don't trade if we can't check risk
                    return True

            # Calculate trade parameters
            entry_price = signal.price.now
            side = signal.trade_plan.action  # "LONG" or "SHORT"

            # Calculate SL and TP
            if side == "LONG":
                sl_price = entry_price * (1 - SL_PERCENT / 100)
                tp_price = entry_price * (1 + TP_PERCENT / 100)
            else:  # SHORT
                sl_price = entry_price * (1 + SL_PERCENT / 100)
                tp_price = entry_price * (1 - TP_PERCENT / 100)

            logger.info(
                f"[PositionManager] 🔓 Opening {side} | "
                f"Entry: ${entry_price:,.2f} | SL: ${sl_price:,.2f} | TP: ${tp_price:,.2f}"
            )

            # Place market order
            market_result = await self.gateway.place_market_order(
                side=side,
                size_usdt=MARGIN_USDT,
                leverage=LEVERAGE,
            )

            if not market_result.success:
                logger.error(f"[PositionManager] Market order failed: {market_result.error_message}")
                return True  # Don't retry, wait for next signal

            entry_price = market_result.filled_price
            quantity = market_result.filled_quantity

            logger.info(
                f"[PositionManager] ✅ Market order filled | "
                f"{side} {quantity:.8f} BTC @ ${entry_price:,.2f}"
            )

            # Place SL order (CRITICAL)
            sl_result = await self.gateway.place_sl_order(
                side=side,
                trigger_price=sl_price,
                quantity=quantity,
            )

            if not sl_result.success:
                logger.error(
                    f"[PositionManager] CRITICAL: SL order failed! "
                    f"Immediately closing position. Error: {sl_result.error_message}"
                )
                # Close position immediately — cannot have position without SL
                close_result = await self.gateway.close_position_market()
                if close_result.success:
                    logger.info(
                        f"[PositionManager] Emergency position close successful | "
                        f"Exit: ${close_result.filled_price:,.2f}"
                    )
                    # Record this emergency close to DB
                    trade_mock = SimpleNamespace(
                        side=side,
                        entry_price=entry_price,
                        size_usdt=MARGIN_USDT,
                        leverage=LEVERAGE
                    )
                    pnl_usdt = self._calculate_pnl(trade_mock, close_result.filled_price)
                    pnl_pct = (pnl_usdt / MARGIN_USDT * 100)
                    self.repo.insert_trade(
                        trade_id=market_result.order_id,
                        symbol="BTC/USDT",
                        side=side,
                        entry_price=entry_price,
                        size_usdt=MARGIN_USDT,
                        size_base=quantity,
                        leverage=LEVERAGE,
                        sl_price=sl_price,
                        tp_price=tp_price,
                        status="CLOSED",
                        exit_price=close_result.filled_price,
                        exit_type="EMERGENCY_SL_FAIL",
                        pnl_usdt=pnl_usdt,
                        pnl_pct=pnl_pct,
                    )
                    try:
                        await self.notifier.notify_trade_closed(
                            trade_id=market_result.order_id,
                            symbol="BTC/USDT",
                            side=side,
                            entry=entry_price,
                            exit=close_result.filled_price,
                            pnl_usdt=pnl_usdt,
                            pnl_pct=pnl_pct,
                            exit_type="EMERGENCY_SL_FAIL"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send emergency close notification: {e}")
                else:
                    logger.error(f"Emergency position close FAILED: {close_result.error_message}")
                return False

            logger.info(f"[PositionManager] ✅ SL order placed | ID: {sl_result.order_id}")

            # Place TP order (non-critical)
            tp_result = await self.gateway.place_tp_order(
                side=side,
                trigger_price=tp_price,
                quantity=quantity,
            )

            if not tp_result.success:
                logger.warning(
                    f"[PositionManager] ⚠️  TP order failed (SL still active): "
                    f"{tp_result.error_message}"
                )
            else:
                logger.info(f"[PositionManager] ✅ TP order placed | ID: {tp_result.order_id}")

            # Record to DB
            trade_id = market_result.order_id
            self.repo.insert_trade(
                trade_id=trade_id,
                symbol="BTC/USDT",
                side=side,
                entry_price=entry_price,
                size_usdt=MARGIN_USDT,
                size_base=quantity,
                leverage=LEVERAGE,
                sl_price=sl_price,
                tp_price=tp_price,
                sl_order_id=sl_result.order_id,
                tp_order_id=tp_result.order_id if tp_result.success else None,
                signal_verdict=signal.confluence.verdict,
                signal_conviction=signal.confluence.conviction_pct,
                candle_open_ts=int(time.time() * 1000),  # Current timestamp
            )

            logger.info(
                f"[PositionManager] ✅ Trade recorded to DB | "
                f"ID: {trade_id} | Conviction: {signal.confluence.conviction_pct:.1f}%"
            )

            # Send Telegram notification
            try:
                await self.notifier.notify_trade_opened(
                    trade_id=trade_id,
                    side=side,
                    entry_price=entry_price,
                    size_usdt=MARGIN_USDT,
                    leverage=LEVERAGE,
                    sl_price=sl_price,
                    tp_price=tp_price,
                    conviction_pct=signal.confluence.conviction_pct,
                    signal_verdict=signal.confluence.verdict,
                )
            except Exception as e:
                logger.warning(f"[PositionManager] Failed to send trade opened notification: {e}")

            return True

        except Exception as e:
            logger.error(f"[PositionManager] Error opening position: {e}", exc_info=True)
            return False

    # ─ Helper methods ─────────────────────────────────────────────────────────

    def _is_trading_enabled(self) -> bool:
        """Check if trading is enabled."""
        import os

        return os.getenv("TRADING_ENABLED", "false").lower() == "true"

    def _should_time_exit(self, db_trade) -> bool:
        """Check if TIME_EXIT should trigger (6 candles / 24h)."""
        if not db_trade.timestamp_open:
            return False

        elapsed_ms = int(time.time() * 1000) - db_trade.timestamp_open
        elapsed_candles = elapsed_ms / CANDLE_DURATION_MS
        return elapsed_candles >= TIME_EXIT_CANDLES

    def _get_position_hold_time(self, db_trade) -> str:
        """Get human-readable hold time."""
        if not db_trade.timestamp_open:
            return "?"

        elapsed_ms = int(time.time() * 1000) - db_trade.timestamp_open
        elapsed_minutes = elapsed_ms // 60000
        hours = elapsed_minutes // 60
        minutes = elapsed_minutes % 60
        return f"{hours}h {minutes}m"

    def _get_position_hold_time_hours(self, db_trade) -> float:
        """Get hold time in hours (float)."""
        if not db_trade.timestamp_open:
            return 0.0

        elapsed_ms = int(time.time() * 1000) - db_trade.timestamp_open
        return elapsed_ms / (3600 * 1000)

    def _calculate_pnl(self, db_trade, exit_price: float) -> float:
        """
        Calculate PnL in USDT, deducting exchange fees.

        Formula:
        - Raw PnL = (price_diff / entry_price) × margin × leverage
        - Trading fees = 2 × (margin × leverage) × taker_fee_rate (entry + exit)
        - Net PnL = Raw PnL - Trading fees
        """
        # Exchange taker fee (typical: 0.02%)
        TAKER_FEE_RATE = 0.0002

        if db_trade.side == "LONG":
            price_diff = exit_price - db_trade.entry_price
        else:  # SHORT
            price_diff = db_trade.entry_price - exit_price

        # Raw PnL = (% change) × (margin × leverage)
        nominal_position = db_trade.size_usdt * db_trade.leverage
        price_change_pct = price_diff / db_trade.entry_price
        raw_pnl = price_change_pct * nominal_position

        # Deduct trading fees (entry + exit)
        trading_fees = 2 * nominal_position * TAKER_FEE_RATE

        # Net PnL after fees
        net_pnl = raw_pnl - trading_fees

        logger.debug(
            f"[PositionManager] PnL calc: raw={raw_pnl:.2f} - fees={trading_fees:.2f} = net={net_pnl:.2f}"
        )

        return net_pnl
