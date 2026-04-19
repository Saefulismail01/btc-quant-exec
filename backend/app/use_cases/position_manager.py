"""
PositionManager: Core execution logic for live trading.

Receives SignalResponse and decides whether to open, hold, or close positions.
Manages order placement, risk checks, and position state.
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.schemas.signal import SignalResponse
from app.adapters.gateways.base_execution_gateway import (
    BaseExchangeExecutionGateway,
    OrderResult,
    PositionInfo,
)
from app.adapters.repositories.live_trade_repository import LiveTradeRepository
from app.use_cases.risk_manager import RiskManager
from app.use_cases.execution_notifier_use_case import get_execution_notifier
from app.use_cases.strategies.base_strategy import BaseTradePlanStrategy
from app.use_cases.strategies.fixed_strategy import FixedStrategy
from app.use_cases.shadow_trade_monitor import ShadowTradeMonitor

logger = logging.getLogger(__name__)

WIB = ZoneInfo("Asia/Jakarta")
_FREEZE_STATE_FILE = os.path.join(
    os.path.dirname(__file__), "..", "infrastructure", "sl_freeze_state.json"
)

# Fallback constants — hanya dipakai oleh dry-run log dan legacy code
# Nilai actual SL/TP/Leverage sekarang dikontrol oleh strategy
SL_PERCENT = 1.333
TP_PERCENT = 0.71
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

    Strategy Pattern: SL/TP/leverage dikontrol oleh TradePlanStrategy.
    Default: FixedStrategy (Golden v4.4).
    Swap ke HestonStrategy via constructor argument.
    """

    def __init__(
        self,
        gateway: BaseExchangeExecutionGateway,
        repo: LiveTradeRepository,
        risk_manager: Optional[RiskManager] = None,
        strategy: Optional[BaseTradePlanStrategy] = None,
    ):
        self.gateway = gateway
        self.repo = repo
        self.risk_manager = risk_manager or RiskManager()
        self.strategy = strategy or FixedStrategy()
        self.notifier = get_execution_notifier()
        self.shadow_monitor = ShadowTradeMonitor(repo)
        self._sl_freeze_until: Optional[datetime] = self._load_freeze_state()
        logger.info(f"[PositionManager] Strategy: {self.strategy.__class__.__name__}")
        if self._sl_freeze_until:
            logger.info(
                f"[PositionManager] SL freeze active until {self._sl_freeze_until.isoformat()}"
            )

    async def sync_position_status(self) -> bool:
        """
        Sync position status from exchange.

        Detects if SL or TP were hit since last cycle.
        Updates database and sends notifications if position closed.

        Returns:
            True if a position was JUST closed this cycle (caller should skip open).
            False if no position closed (position still open, or no position at all, or error).
        """
        try:
            # Get open trade from DB
            db_trade = self.repo.get_open_trade()
            if not db_trade:
                return False  # No position to sync

            logger.info(
                f"[PositionManager] Syncing position status: {db_trade.side} "
                f"@ ${db_trade.entry_price:,.2f}"
            )

            # Get position from exchange — retry once to avoid false None on transient errors
            exchange_pos = await self.gateway.get_open_position()
            if exchange_pos is None:
                import asyncio as _asyncio

                logger.warning(
                    "[PositionManager] get_open_position() returned None — retrying in 3s..."
                )
                await _asyncio.sleep(3)
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
                    # Filter by SL/TP prices to get the correct trade
                    # Pass position open time to avoid matching old orders from history
                    last_order = await self.gateway.fetch_last_closed_order(
                        expected_sl_price=db_trade.sl_price,
                        expected_tp_price=db_trade.tp_price,
                        position_open_time=db_trade.timestamp_open,
                        max_order_age_seconds=7200,  # Max 2 hours old
                    )
                    if last_order:
                        exit_price = last_order.get(
                            "filled_price", db_trade.entry_price
                        )
                        # Determine exit type from order_type field (reliable)
                        order_type_str = last_order.get("order_type", "").lower()
                        if "stop" in order_type_str:
                            exit_type = "SL"
                        elif (
                            "take-profit" in order_type_str
                            or "take_profit" in order_type_str
                        ):
                            exit_type = "TP"
                        else:
                            # Fallback: distance comparison
                            if abs(exit_price - db_trade.sl_price) < abs(
                                exit_price - db_trade.tp_price
                            ):
                                exit_type = "SL"
                            else:
                                exit_type = "TP"
                        logger.info(
                            f"[PositionManager] Detected exit from order history: "
                            f"{exit_type} ({order_type_str}) @ ${exit_price:,.2f}"
                        )
                    else:
                        # Fallback: Use heuristic (distance from SL vs TP to CURRENT price)
                        # IMPORTANT: Must use current market price, NOT entry price.
                        # Using entry price always picks TP (TP is closer to entry than SL by design).
                        if db_trade.entry_price > 0:
                            try:
                                current_price = await self.gateway.get_current_price()
                            except Exception:
                                current_price = None

                            if current_price and current_price > 0:
                                sl_dist = abs(current_price - db_trade.sl_price)
                                tp_dist = abs(current_price - db_trade.tp_price)
                                logger.info(
                                    f"[PositionManager] Heuristic using current price ${current_price:,.2f} | SL dist: {sl_dist:.2f} | TP dist: {tp_dist:.2f}"
                                )
                            else:
                                # Last resort: check if entry price moved toward SL or TP
                                # Use SL as default (safer — avoids false TP detection)
                                sl_dist = 1
                                tp_dist = 2
                                logger.warning(
                                    "[PositionManager] Cannot get current price — defaulting to SL heuristic (safe)"
                                )

                            if sl_dist < tp_dist:
                                exit_price = db_trade.sl_price
                                exit_type = "SL"
                                logger.info(f"[PositionManager] Heuristic: SL hit")
                            else:
                                exit_price = db_trade.tp_price
                                exit_type = "TP"
                                logger.info(f"[PositionManager] Heuristic: TP hit")
                        else:
                            exit_price = db_trade.entry_price
                            exit_type = "MANUAL"
                            logger.warning(
                                "[PositionManager] Using entry price as fallback"
                            )
                except Exception as e:
                    logger.error(f"[PositionManager] Error determining exit: {e}")
                    # Fallback to heuristic on error
                    if db_trade.entry_price > 0:
                        sl_dist = abs(db_trade.entry_price - db_trade.sl_price)
                        tp_dist = abs(db_trade.entry_price - db_trade.tp_price)
                        exit_price = (
                            db_trade.sl_price
                            if sl_dist < tp_dist
                            else db_trade.tp_price
                        )
                        exit_type = "SL" if sl_dist < tp_dist else "TP"
                    else:
                        exit_price = db_trade.entry_price
                        exit_type = "ERROR"

                # Hitung PnL dari actual fill Lighter jika tersedia
                exit_filled_quote = (
                    last_order.get("filled_quote", 0) if last_order else 0
                )
                entry_filled_quote = getattr(db_trade, "entry_filled_quote", None) or 0

                if exit_filled_quote > 0 and entry_filled_quote > 0:
                    # Branch 1: kedua fill amount tersedia (market order entry + market order exit)
                    if db_trade.side == "LONG":
                        pnl_usdt = exit_filled_quote - entry_filled_quote
                    else:
                        pnl_usdt = entry_filled_quote - exit_filled_quote
                    logger.info(
                        f"[PositionManager] PnL from Lighter fills: "
                        f"entry_quote=${entry_filled_quote:.4f} exit_quote=${exit_filled_quote:.4f} "
                        f"pnl=${pnl_usdt:+.4f}"
                    )
                elif (
                    entry_filled_quote > 0
                    and exit_price > 0
                    and db_trade.entry_price > 0
                ):
                    # Branch 2: SL/TP trigger order — filled_quote=0 tapi exit_price valid.
                    # Hitung exit_filled_quote dari: entry_base × exit_price
                    # di mana entry_base = entry_filled_quote / entry_price
                    entry_base = entry_filled_quote / db_trade.entry_price
                    exit_filled_quote_computed = entry_base * exit_price
                    if db_trade.side == "LONG":
                        pnl_usdt = exit_filled_quote_computed - entry_filled_quote
                    else:
                        pnl_usdt = entry_filled_quote - exit_filled_quote_computed
                    logger.info(
                        f"[PositionManager] PnL from entry fill + exit price: "
                        f"entry_quote=${entry_filled_quote:.4f} entry_base={entry_base:.6f} "
                        f"exit_price=${exit_price:.2f} exit_quote=${exit_filled_quote_computed:.4f} "
                        f"pnl=${pnl_usdt:+.4f}"
                    )
                else:
                    # Branch 3: fallback ke formula lokal jika tidak ada fill data sama sekali
                    pnl_usdt = self._calculate_pnl(db_trade, exit_price)
                    logger.warning(
                        f"[PositionManager] PnL fallback to local formula "
                        f"(entry_quote={entry_filled_quote}, exit_quote={exit_filled_quote})"
                    )

                pnl_pct = (
                    (pnl_usdt / db_trade.size_usdt * 100)
                    if db_trade.size_usdt > 0
                    else 0
                )

                # TRIPLE-CHECK: Final confirmation position is really closed on exchange
                # before updating DB (prevents false closures)
                final_check = await self.gateway.get_open_position()
                if final_check is not None:
                    logger.warning(
                        f"[PositionManager] Triple-check FAILED: Position still open on exchange! "
                        f"Aborting DB close. Position size: {final_check.size}"
                    )
                    return False

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

                # PR-2: SL hit dengan loss nyata → freeze entry sampai 07:00 WIB besok
                # SL hit tapi breakeven/profit (misal SL dipindah manual) → tidak freeze
                # TP hit → clear freeze yang ada
                # EDGE CASE: "SL" dengan profit = trailing SL yang tereksekusi, treat as positive exit
                if exit_type == "SL":
                    if pnl_usdt < 0:
                        # Real SL hit with loss → freeze
                        self._set_sl_freeze()
                        logger.info(f"[PositionManager] SL freeze activated (PnL: ${pnl_usdt:+.2f})")
                    else:
                        # SL hit tapi profit/breakeven = manual trailing SL
                        # Clear freeze dan treat sebagai positive exit
                        self._clear_sl_freeze()
                        logger.info(f"[PositionManager] SL hit with profit (PnL: ${pnl_usdt:+.2f}) - no freeze, trailing SL executed")
                elif exit_type == "TP":
                    self._clear_sl_freeze()

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
                    logger.warning(
                        f"[PositionManager] Failed to send trade closed notification: {e}"
                    )

                # Start shadow monitoring for manual closes
                if exit_type == "MANUAL":
                    try:
                        db_trade.exit_price = exit_price
                        db_trade.pnl_usdt = pnl_usdt
                        self.shadow_monitor.start_shadow(db_trade)
                    except Exception as e:
                        logger.warning(
                            f"[PositionManager] Failed to start shadow trade: {e}"
                        )

                return True

            if exchange_pos:
                logger.info(
                    f"[PositionManager] ✅ Position still open at exchange | "
                    f"Entry: ${exchange_pos.entry_price:,.2f} | PnL: ${exchange_pos.unrealized_pnl:+.2f}"
                )

                # [NEW] NOTIFY: Position still open from previous session
                # Calculate current PnL and hold time
                try:
                    current_price = await self.gateway.get_current_price()
                    if current_price is None:
                        logger.warning("[PositionManager] Cannot get current price for position status")
                        return False

                    hold_time_hours = self._get_position_hold_time_hours(db_trade)

                    # Calculate unrealized PnL
                    if db_trade.side == "LONG":
                        unrealized_pnl_usdt = (current_price - db_trade.entry_price) * db_trade.size_base
                    else:
                        unrealized_pnl_usdt = (db_trade.entry_price - current_price) * db_trade.size_base
                    unrealized_pnl_pct = (unrealized_pnl_usdt / db_trade.size_usdt * 100) if db_trade.size_usdt > 0 else 0

                    await self.notifier.notify_position_status(
                        trade_id=db_trade.id,
                        side=db_trade.side,
                        entry_price=db_trade.entry_price,
                        current_price=current_price,
                        unrealized_pnl_usdt=unrealized_pnl_usdt,
                        unrealized_pnl_pct=unrealized_pnl_pct,
                        hold_time_hours=hold_time_hours,
                        sl_price=db_trade.sl_price,
                        tp_price=db_trade.tp_price,
                    )
                    logger.info(f"[PositionManager] Sent position status notification")
                except Exception as e:
                    logger.warning(f"[PositionManager] Failed to send position status: {e}")

                # [NEW] SYNC SL/TP FROM EXCHANGE
                try:
                    active_orders = await self.gateway.get_active_sl_tp()
                    synced = False
                    new_sl = active_orders.get("sl_price")
                    new_tp = active_orders.get("tp_price")

                    if new_sl and abs(new_sl - db_trade.sl_price) > 0.01:
                        logger.info(
                            f"[PositionManager] 🔄 Syncing SL from exchange: ${db_trade.sl_price} -> ${new_sl}"
                        )
                        db_trade.sl_price = new_sl
                        synced = True
                    if new_tp and abs(new_tp - db_trade.tp_price) > 0.01:
                        logger.info(
                            f"[PositionManager] 🔄 Syncing TP from exchange: ${db_trade.tp_price} -> ${new_tp}"
                        )
                        db_trade.tp_price = new_tp
                        synced = True

                    if synced:
                        self.repo.update_trade_params(
                            db_trade.id,
                            sl_price=db_trade.sl_price,
                            tp_price=db_trade.tp_price,
                        )
                        logger.info(
                            f"[PositionManager] ✅ Database synced with actual exchange orders"
                        )
                except Exception as e:
                    logger.warning(
                        f"[PositionManager] Failed to sync SL/TP from exchange: {e}"
                    )
            else:
                logger.warning(
                    "[PositionManager] Position disappeared just before logging status"
                )
            return False  # Position still open (or disappeared without close event) — allow normal flow

        except Exception as e:
            logger.error(
                f"[PositionManager] Error syncing position: {e}", exc_info=True
            )
            return False

    async def process_signal(self, signal: SignalResponse) -> bool:
        """
        Process incoming signal and execute trading logic.

        EXCHANGE-FIRST APPROACH:
        Always check exchange state first, DB is secondary (logging only).
        This prevents data inconsistency issues where DB shows wrong state.

        Args:
            signal: SignalResponse from signal pipeline

        Returns:
            True if processed successfully, False otherwise
        """
        try:
            # [FIX] Fallback protection — skip all actions if signal is a fallback (data error)
            if signal.is_fallback:
                logger.warning("[PositionManager] ⚠️ Signal is FALLBACK (data error). Skipping all actions.")
                return True

            logger.info(
                f"[PositionManager] Processing signal | Verdict: {signal.confluence.verdict}"
            )

            # Check trading enabled flag
            if not self._is_trading_enabled():
                entry = signal.price.now
                side = signal.trade_plan.action
                status = signal.trade_plan.status
                verdict = signal.confluence.verdict
                conviction = signal.confluence.conviction_pct
                if status == "ACTIVE":
                    params = self.strategy.calculate(entry, side, signal.dict())
                    logger.info(
                        f"[PositionManager] [DRY-RUN] Would open {side} | "
                        f"Entry: ${entry:,.2f} | SL: ${params.sl_price:,.2f} ({params.sl_pct:.3f}%) | "
                        f"TP: ${params.tp_price:,.2f} ({params.tp_pct:.3f}%) | "
                        f"Strategy: {params.strategy_name} | "
                        f"Verdict: {verdict} | Conviction: {conviction:.1f}%"
                    )
                else:
                    logger.info(
                        f"[PositionManager] [DRY-RUN] No entry (status={status}, verdict={verdict}, conviction={conviction:.1f}%)"
                    )
                return True

            # EXCHANGE-FIRST: Check position directly from exchange
            exchange_pos = await self.gateway.get_open_position()

            if exchange_pos:
                # Position exists at exchange - manage it
                logger.info(
                    f"[PositionManager] Position detected at exchange | "
                    f"{exchange_pos.side} @ ${exchange_pos.entry_price:,.2f} | "
                    f"PnL: ${exchange_pos.unrealized_pnl:+.2f}"
                )

                # Get DB record for additional data (SL/TP, order IDs)
                db_trade = self.repo.get_open_trade()

                if db_trade:
                    # Both exchange and DB have position - normal manage
                    return await self._manage_existing_position(signal, db_trade, exchange_pos)
                else:
                    # Exchange has position but DB empty - possible sync issue
                    # Mark as cannot open new until resolved
                    logger.warning(
                        "[PositionManager] Exchange has position but DB empty - "
                        "cannot manage without SL/TP data. Skipping signal."
                    )
                    # Notify Telegram about blocked entry
                    try:
                        await self.notifier.notify_entry_blocked(
                            block_reason="Position Exists (DB Sync Issue)",
                            signal_verdict=signal.confluence.verdict,
                            signal_status=signal.trade_plan.status,
                            conviction_pct=signal.confluence.conviction_pct,
                            details=f"Exchange has {exchange_pos.side} position @ ${exchange_pos.entry_price:,.2f} but DB empty. Cannot manage without SL/TP data.",
                        )
                    except Exception as e:
                        logger.warning(f"[PositionManager] Failed to send blocked entry notification: {e}")
                    return True

            # No position at exchange - check if we should open
            logger.info("[PositionManager] No position at exchange")

            # Check if DB incorrectly shows open position (sync issue)
            db_trade = self.repo.get_open_trade()
            if db_trade:
                logger.warning(
                    f"[PositionManager] DB shows open trade but exchange empty - "
                    f"position likely closed. Marking DB trade as orphaned."
                )
                # Could optionally mark DB trade as closed here

            # Try to open new position
            return await self._try_open_position(signal)

        except Exception as e:
            logger.error(
                f"[PositionManager] Error processing signal: {e}", exc_info=True
            )
            return False

    async def _manage_existing_position(
        self, signal: SignalResponse, db_trade, exchange_pos=None
    ) -> bool:
        """
        Manage an existing open position.

        Checks:
        1. If position still exists at exchange
        2. If TIME_EXIT triggered (6 candles / 24h)

        Args:
            signal: Current signal
            db_trade: Database trade record
            exchange_pos: Optional PositionInfo from exchange (avoid redundant API call)

        Returns:
            True if processed, False on error
        """
        try:
            # Verify position still exists (use provided exchange_pos if available)
            if exchange_pos is None:
                exchange_pos = await self.gateway.get_open_position()

            if not exchange_pos:
                logger.warning(
                    "[PositionManager] Position no longer exists at exchange"
                )
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
                pnl_pct = (
                    (pnl_usdt / db_trade.size_usdt * 100)
                    if db_trade.size_usdt > 0
                    else 0
                )

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
                    logger.warning(
                        f"[PositionManager] Failed to send trade closed notification: {e}"
                    )

                return True

            logger.info(
                f"[PositionManager] Position held | "
                f"Time: {self._get_position_hold_time(db_trade)} | "
                f"PnL: ${exchange_pos.unrealized_pnl:+.2f}"
            )
            return True

        except Exception as e:
            logger.error(
                f"[PositionManager] Error managing position: {e}", exc_info=True
            )
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
            # REDUNDANT SAFETY GUARD: process_signal already checked exchange-first,
            # but we double-check here to prevent any race conditions
            live_pos = await self.gateway.get_open_position()
            if live_pos is not None:
                logger.warning(
                    f"[PositionManager] ⛔ Entry blocked — position still OPEN at exchange "
                    f"(race condition detected). Entry: ${live_pos.entry_price:,.2f}"
                )
                # Notify Telegram about race condition block
                try:
                    await self.notifier.notify_entry_blocked(
                        block_reason="Position Exists (Race Condition)",
                        signal_verdict=signal.confluence.verdict,
                        signal_status=signal.trade_plan.status,
                        conviction_pct=signal.confluence.conviction_pct,
                        details=f"Position already open @ ${live_pos.entry_price:,.2f}. Cannot open another.",
                    )
                except Exception as e:
                    logger.warning(f"[PositionManager] Failed to send race condition notification: {e}")
                return True

            # PR-2: Block entry if SL freeze is active
            if self._is_sl_frozen():
                freeze_until: Optional[datetime] = self._sl_freeze_until
                freeze_str = freeze_until.strftime('%H:%M') if freeze_until else 'unknown'
                logger.info(
                    f"[PositionManager] ⛔ Entry blocked — SL freeze until "
                    f"{freeze_until.isoformat() if freeze_until else '?'} WIB"
                )
                # Notify Telegram about SL freeze
                try:
                    await self.notifier.notify_entry_blocked(
                        block_reason="SL Freeze Active",
                        signal_verdict=signal.confluence.verdict,
                        signal_status=signal.trade_plan.status,
                        conviction_pct=signal.confluence.conviction_pct,
                        details=f"SL freeze active until {freeze_str} WIB. Entry blocked until next trading window.",
                    )
                except Exception as e:
                    logger.warning(f"[PositionManager] Failed to send SL freeze notification: {e}")
                return True

            # Check signal status
            # MUST be ACTIVE/ADVISORY and NOT NEUTRAL to enter.
            if signal.trade_plan.status not in ("ACTIVE", "ADVISORY") or signal.confluence.verdict == "NEUTRAL":
                block_reason = f"Signal {signal.trade_plan.status}" if signal.confluence.verdict != "NEUTRAL" else "Neutral Verdict"
                logger.info(
                    f"[PositionManager] {block_reason} (status={signal.trade_plan.status}, verdict={signal.confluence.verdict}). "
                    f"Skipping open."
                )
                # Notify Telegram about entry block
                try:
                    await self.notifier.notify_entry_blocked(
                        block_reason=block_reason,
                        signal_verdict=signal.confluence.verdict,
                        signal_status=signal.trade_plan.status,
                        conviction_pct=signal.confluence.conviction_pct,
                        details=f"Entry blocked because verdict is {signal.confluence.verdict} and status is {signal.trade_plan.status}. We only enter on ACTIVE/ADVISORY signals with non-neutral verdicts.",
                    )
                except Exception as e:
                    logger.warning(f"[PositionManager] Failed to send entry block notification: {e}")
                return True

            # Check RiskManager (with actual account balance for proper position sizing)
            if self.risk_manager:
                try:
                    account_balance = await self.gateway.get_account_balance()
                    risk_result = self.risk_manager.evaluate(
                        portfolio_value=account_balance,
                        atr=signal.price.atr14,
                        sl_multiplier=1.333
                        / 100
                        * signal.price.now
                        / max(signal.price.atr14, 1),
                        requested_leverage=15,
                        current_price=signal.price.now,
                    )
                    if not risk_result.can_trade:
                        logger.warning(
                            f"[PositionManager] RiskManager blocked: {risk_result.rejection_reason} "
                            f"(balance: ${account_balance:,.2f})"
                        )
                        # Notify Telegram about risk manager block
                        try:
                            await self.notifier.notify_entry_blocked(
                                block_reason="Risk Manager Block",
                                signal_verdict=signal.confluence.verdict,
                                signal_status=signal.trade_plan.status,
                                conviction_pct=signal.confluence.conviction_pct,
                                details=f"Risk Manager: {risk_result.rejection_reason}. Balance: ${account_balance:,.2f}",
                            )
                        except Exception as e:
                            logger.warning(f"[PositionManager] Failed to send risk block notification: {e}")
                        return True
                except Exception as e:
                    logger.error(f"[PositionManager] Failed to check risk: {e}")
                    # Fail-safe: don't trade if we can't check risk
                    return True

            # Calculate trade parameters via strategy
            entry_price = signal.price.now
            side = signal.trade_plan.action  # "LONG" or "SHORT"

            params = self.strategy.calculate(
                entry_price=entry_price,
                action=side,
                signal_data=signal.dict(),
            )
            sl_price = params.sl_price
            tp_price = params.tp_price
            margin_usd = params.margin_usd
            leverage = params.leverage

            logger.info(
                f"[PositionManager] 🔓 Opening {side} | "
                f"Entry: ${entry_price:,.2f} | SL: ${sl_price:,.2f} ({params.sl_pct:.3f}%) | "
                f"TP: ${tp_price:,.2f} ({params.tp_pct:.3f}%) | "
                f"Strategy: {params.strategy_name}"
            )

            # Place market order
            market_result = await self.gateway.place_market_order(
                side=side,
                size_usdt=margin_usd,
                leverage=leverage,
            )

            if not market_result.success:
                logger.error(
                    f"[PositionManager] Market order failed: {market_result.error_message}"
                )
                return True  # Don't retry, wait for next signal

            entry_price = market_result.filled_price
            quantity = market_result.filled_quantity

            logger.info(
                f"[PositionManager] ✅ Market order filled | "
                f"{side} {quantity:.8f} BTC @ ${entry_price:,.2f}"
            )

            # Ambil filled_quote_amount dari Lighter untuk PnL yang akurat saat close
            entry_filled_quote: Optional[float] = None
            try:
                entry_filled_quote = await self.gateway.fetch_entry_fill_quote(
                    market_result.order_id
                )
                if entry_filled_quote:
                    logger.info(
                        f"[PositionManager] Entry fill quote captured: ${entry_filled_quote:.4f}"
                    )
                else:
                    logger.warning(
                        "[PositionManager] Entry fill quote not found — PnL will use fallback formula"
                    )
            except Exception as e:
                logger.warning(
                    f"[PositionManager] Failed to fetch entry fill quote: {e}"
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
                        size_usdt=margin_usd,
                        leverage=leverage,
                    )
                    pnl_usdt = self._calculate_pnl(
                        trade_mock, close_result.filled_price
                    )
                    pnl_pct = pnl_usdt / margin_usd * 100
                    self.repo.insert_trade(
                        trade_id=market_result.order_id,
                        symbol="BTC/USDT",
                        side=side,
                        entry_price=entry_price,
                        size_usdt=margin_usd,
                        size_base=quantity,
                        leverage=leverage,
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
                            exit_type="EMERGENCY_SL_FAIL",
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to send emergency close notification: {e}"
                        )
                else:
                    logger.error(
                        f"Emergency position close FAILED: {close_result.error_message}"
                    )
                return False

            logger.info(
                f"[PositionManager] ✅ SL order placed | ID: {sl_result.order_id}"
            )

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
                logger.info(
                    f"[PositionManager] ✅ TP order placed | ID: {tp_result.order_id}"
                )

            # Record to DB
            trade_id = market_result.order_id
            self.repo.insert_trade(
                trade_id=trade_id,
                symbol="BTC/USDT",
                side=side,
                entry_price=entry_price,
                size_usdt=margin_usd,
                size_base=quantity,
                leverage=leverage,
                sl_price=sl_price,
                tp_price=tp_price,
                sl_order_id=sl_result.order_id,
                tp_order_id=tp_result.order_id if tp_result.success else None,
                signal_verdict=signal.confluence.verdict,
                signal_conviction=signal.confluence.conviction_pct,
                candle_open_ts=int(time.time() * 1000),
                entry_filled_quote=entry_filled_quote,
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
                    size_usdt=margin_usd,
                    leverage=leverage,
                    sl_price=sl_price,
                    tp_price=tp_price,
                    conviction_pct=signal.confluence.conviction_pct,
                    signal_verdict=signal.confluence.verdict,
                )
            except Exception as e:
                logger.warning(
                    f"[PositionManager] Failed to send trade opened notification: {e}"
                )

            return True

        except Exception as e:
            logger.error(
                f"[PositionManager] Error opening position: {e}", exc_info=True
            )
            return False

    # ─ SL freeze state helpers ────────────────────────────────────────────────

    def _load_freeze_state(self) -> Optional[datetime]:
        """Load SL freeze timestamp from disk (survives restarts)."""
        try:
            if os.path.exists(_FREEZE_STATE_FILE):
                with open(_FREEZE_STATE_FILE, "r") as f:
                    data = json.load(f)
                ts = data.get("sl_freeze_until")
                if ts:
                    return datetime.fromisoformat(ts)
        except Exception as e:
            logger.warning(f"[PositionManager] Could not load freeze state: {e}")
        return None

    def _save_freeze_state(self, until: Optional[datetime]) -> None:
        """Persist SL freeze timestamp to disk."""
        try:
            os.makedirs(os.path.dirname(_FREEZE_STATE_FILE), exist_ok=True)
            with open(_FREEZE_STATE_FILE, "w") as f:
                json.dump({"sl_freeze_until": until.isoformat() if until else None}, f)
        except Exception as e:
            logger.warning(f"[PositionManager] Could not save freeze state: {e}")

    def _set_sl_freeze(self) -> None:
        """Freeze entry until 07:00 WIB next day."""
        now_wib = datetime.now(WIB)
        next_day = (now_wib + timedelta(days=1)).replace(
            hour=7, minute=0, second=0, microsecond=0
        )
        self._sl_freeze_until = next_day
        self._save_freeze_state(next_day)
        logger.info(f"[PositionManager] SL freeze set until {next_day.isoformat()}")

    def _clear_sl_freeze(self) -> None:
        self._sl_freeze_until = None
        self._save_freeze_state(None)

    def _is_sl_frozen(self) -> bool:
        """Return True if new entries are blocked due to recent SL hit."""
        freeze_until: Optional[datetime] = self._sl_freeze_until
        if freeze_until is None:
            return False
        now = datetime.now(WIB)
        if now >= freeze_until:
            self._clear_sl_freeze()
            return False
        return True

    # ─ Helper methods ─────────────────────────────────────────────────────────

    def _is_trading_enabled(self) -> bool:
        """Check if trading is enabled (Lighter-specific flag)."""
        import os

        return os.getenv("LIGHTER_TRADING_ENABLED", "false").lower() == "true"

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
