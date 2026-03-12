"""
ExecutionNotifier: Send Telegram notifications for live execution events.

Handles:
- Trade opened
- Trade closed (TP, SL, TIME_EXIT, MANUAL)
- Emergency stop
"""

import logging
import os
from datetime import datetime
from typing import Optional

from app.adapters.gateways.telegram_gateway import TelegramGateway
from app.adapters.repositories.live_trade_repository import LiveTradeRecord

logger = logging.getLogger(__name__)


class ExecutionNotifier:
    """Sends notifications for live execution events."""

    def __init__(self):
        """Initialize with Telegram credentials (execution layer specific)."""
        # First try: use dedicated execution telegram (NEW)
        token = os.getenv("EXECUTION_TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.getenv("EXECUTION_TELEGRAM_CHAT_ID", "").strip()

        # Fallback: use existing signal telegram (OLD)
        if not token or not chat_id:
            token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
            chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

        if not token or not chat_id:
            logger.warning("[ExecutionNotifier] Telegram not configured. Notifications disabled.")
            self.gateway = None
        else:
            self.gateway = TelegramGateway(token, chat_id)
            logger.info("[ExecutionNotifier] ✅ Telegram configured (execution layer)")

    async def notify_trade_opened(
        self,
        trade_id: str,
        side: str,
        entry_price: float,
        size_usdt: float,
        leverage: int,
        sl_price: float,
        tp_price: float,
        conviction_pct: float,
        signal_verdict: str,
    ) -> bool:
        """
        Notify when a trade is opened.

        Args:
            trade_id: Trade ID
            side: "LONG" or "SHORT"
            entry_price: Entry price
            size_usdt: Margin in USDT
            leverage: Leverage
            sl_price: Stop-loss price
            tp_price: Take-profit price
            conviction_pct: Signal conviction percentage
            signal_verdict: Signal verdict (e.g., "STRONG BUY")

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.gateway:
            return False

        try:
            notional = size_usdt * leverage
            direction_emoji = "📈" if side == "LONG" else "📉"
            expire_hours = 24
            conviction_bar = self._make_conviction_bar(conviction_pct)

            message = f"""🟢 LIVE TRADE OPENED
━━━━━━━━━━━━━━━━━━
{direction_emoji} BTC/USDT Perpetual | {side}
💰 Entry  : ${entry_price:,.2f}
📏 Size   : ${size_usdt:,.0f} ({leverage}x) = ${notional:,.0f} notional
🛑 SL     : ${sl_price:,.2f} ({self._pct_diff(entry_price, sl_price):+.3f}%)
🎯 TP     : ${tp_price:,.2f} ({self._pct_diff(entry_price, tp_price):+.3f}%)
⏳ Expire : {expire_hours} hours (6 candle)
🎯 Verdict: {signal_verdict}
🔥 Conviction: {conviction_bar} {conviction_pct:.1f}%
━━━━━━━━━━━━━━━━━━
🤖 BTC-QUANT LIVE v4.4
ID: {trade_id}"""

            success = await self.gateway.send_message(message, parse_mode="HTML")

            if success:
                logger.info(f"[ExecutionNotifier] ✅ Trade opened notification sent: {trade_id}")
            else:
                logger.warning(f"[ExecutionNotifier] Failed to send trade opened notification")

            return success

        except Exception as e:
            logger.error(f"[ExecutionNotifier] Error notifying trade opened: {e}", exc_info=True)
            return False

    async def notify_trade_closed(
        self,
        trade_id: str,
        side: str,
        entry_price: float,
        exit_price: float,
        exit_type: str,
        pnl_usdt: float,
        pnl_pct: float,
        hold_time_hours: float,
        size_usdt: float,
        leverage: int,
    ) -> bool:
        """
        Notify when a trade is closed.

        Args:
            trade_id: Trade ID
            side: "LONG" or "SHORT"
            entry_price: Entry price
            exit_price: Exit price
            exit_type: "SL", "TP", "TIME_EXIT", or "MANUAL"
            pnl_usdt: PnL in USDT
            pnl_pct: PnL percentage
            hold_time_hours: How long position was held (hours)
            size_usdt: Margin in USDT
            leverage: Leverage

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.gateway:
            return False

        try:
            # Emoji based on exit type and PnL
            if exit_type == "TP":
                status_emoji = "✅"
                exit_emoji = "🎯"
            elif exit_type == "SL":
                status_emoji = "❌"
                exit_emoji = "🛑"
            elif exit_type == "TIME_EXIT":
                status_emoji = "⏰"
                exit_emoji = "⏳"
            else:
                status_emoji = "🔴"
                exit_emoji = "⚠️"

            pnl_emoji = "📈" if pnl_usdt >= 0 else "📉"
            direction_emoji = "📈" if side == "LONG" else "📉"

            # Daily PnL (would need to fetch from repo)
            daily_pnl_text = "Pending calculation"

            message = f"""{status_emoji} LIVE TRADE CLOSED — {exit_type}
━━━━━━━━━━━━━━━━━━
{direction_emoji} BTC/USDT | {side}
💰 Entry  : ${entry_price:,.2f}
💰 Exit   : ${exit_price:,.2f}
{pnl_emoji} PnL    : {pnl_usdt:+,.2f} USDT ({pnl_pct:+.2f}%)
⏱️  Hold   : {hold_time_hours:.1f} hours
{exit_emoji} Exit   : {exit_type}
━━━━━━━━━━━━━━━━━━
🤖 BTC-QUANT LIVE v4.4
ID: {trade_id}"""

            success = await self.gateway.send_message(message, parse_mode="HTML")

            if success:
                logger.info(
                    f"[ExecutionNotifier] ✅ Trade closed notification sent: {trade_id} | "
                    f"Exit: {exit_type} | PnL: {pnl_usdt:+,.2f}"
                )
            else:
                logger.warning(f"[ExecutionNotifier] Failed to send trade closed notification")

            return success

        except Exception as e:
            logger.error(f"[ExecutionNotifier] Error notifying trade closed: {e}", exc_info=True)
            return False

    async def notify_emergency_stop(
        self,
        position_closed: bool,
        exit_price: Optional[float] = None,
        exit_pnl_usdt: Optional[float] = None,
    ) -> bool:
        """
        Notify when emergency stop is triggered.

        Args:
            position_closed: Whether position was closed
            exit_price: Exit price if closed
            exit_pnl_usdt: Exit PnL if closed

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.gateway:
            return False

        try:
            if position_closed:
                exit_text = f"Position closed @ ${exit_price:,.2f}\nPnL: {exit_pnl_usdt:+,.2f} USDT"
            else:
                exit_text = "No open position"

            message = f"""🚨 EMERGENCY STOP TRIGGERED
━━━━━━━━━━━━━━━━━━
{exit_text}
Trading HALTED.
Resume via API.
━━━━━━━━━━━━━━━━━━
🤖 BTC-QUANT LIVE v4.4"""

            success = await self.gateway.send_message(message, parse_mode="HTML")

            if success:
                logger.info("[ExecutionNotifier] ✅ Emergency stop notification sent")
            else:
                logger.warning("[ExecutionNotifier] Failed to send emergency stop notification")

            return success

        except Exception as e:
            logger.error(f"[ExecutionNotifier] Error notifying emergency stop: {e}", exc_info=True)
            return False

    async def notify_error(self, error_title: str, error_details: str) -> bool:
        """
        Notify about errors.

        Args:
            error_title: Error title/summary
            error_details: Detailed error message

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.gateway:
            return False

        try:
            message = f"""⚠️  EXECUTION ERROR
━━━━━━━━━━━━━━━━━━
{error_title}

{error_details}
━━━━━━━━━━━━━━━━━━
🤖 BTC-QUANT LIVE v4.4"""

            success = await self.gateway.send_message(message, parse_mode="HTML")

            if success:
                logger.info(f"[ExecutionNotifier] ✅ Error notification sent: {error_title}")
            else:
                logger.warning("[ExecutionNotifier] Failed to send error notification")

            return success

        except Exception as e:
            logger.error(f"[ExecutionNotifier] Error sending notification: {e}", exc_info=True)
            return False

    # ─ Helper methods ─────────────────────────────────────────────────────────

    def _pct_diff(self, entry: float, target: float) -> float:
        """Calculate percentage difference."""
        if entry == 0:
            return 0.0
        return ((target - entry) / entry) * 100

    def _make_conviction_bar(self, conviction_pct: float) -> str:
        """Make a visual bar for conviction level."""
        bars = int(conviction_pct / 10)
        empty = 10 - bars
        return "🟩" * bars + "⬜" * empty


# Singleton instance
_notifier: Optional[ExecutionNotifier] = None


def get_execution_notifier() -> ExecutionNotifier:
    """Get or create singleton ExecutionNotifier."""
    global _notifier
    if _notifier is None:
        _notifier = ExecutionNotifier()
    return _notifier
