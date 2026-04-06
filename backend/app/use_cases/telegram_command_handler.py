"""
TelegramCommandHandler: Polling-based Telegram bot command handler.

Commands:
- /pnl    — lihat unrealized PnL posisi sekarang
- /status — status bot (trading enabled, mode, daily PnL)
"""

import asyncio
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv

from app.adapters.repositories.live_trade_repository import LiveTradeRepository
from app.adapters.repositories.market_repository import MarketRepository
from app.adapters.gateways.lighter_execution_gateway import LighterExecutionGateway
from app.use_cases.signal_service import get_cached_signal

logger = logging.getLogger(__name__)

_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

POLL_INTERVAL = 3.0  # seconds between getUpdates polls


class TelegramCommandHandler:
    """
    Polls Telegram getUpdates and responds to /pnl and /status commands.
    Runs as a background asyncio task alongside the data daemon.
    """

    def __init__(self):
        token = os.getenv("EXECUTION_TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}" if token else ""
        self.offset = 0
        self._running = False

        self.live_repo = LiveTradeRepository()
        self.market_repo = MarketRepository(read_only=True)
        self.gateway = LighterExecutionGateway()

        if not token:
            logger.warning("[TelegramCommandHandler] No token configured — commands disabled.")

    # ─ Main loop ──────────────────────────────────────────────────────────────

    async def run(self):
        """Main polling loop. Run as asyncio task."""
        if not self.token:
            return

        self._running = True
        logger.info("[TelegramCommandHandler] Started polling for commands.")

        while self._running:
            try:
                updates = await self._get_updates()
                for update in updates:
                    await self._handle_update(update)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[TelegramCommandHandler] Poll error: {e}")

            await asyncio.sleep(POLL_INTERVAL)

        logger.info("[TelegramCommandHandler] Stopped.")

    def stop(self):
        self._running = False

    # ─ Telegram API ───────────────────────────────────────────────────────────

    async def _get_updates(self) -> list[dict]:
        """Fetch pending updates from Telegram."""
        params = {"timeout": 2, "offset": self.offset}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.base_url}/getUpdates", params=params)
                if resp.status_code != 200:
                    return []
                data = resp.json()
                updates = data.get("result", [])
                if updates:
                    self.offset = updates[-1]["update_id"] + 1
                return updates
        except Exception as e:
            logger.debug(f"[TelegramCommandHandler] getUpdates failed: {e}")
            return []

    async def _send(self, chat_id: int, text: str):
        """Send a message back to user."""
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(f"{self.base_url}/sendMessage", json=payload)
        except Exception as e:
            logger.error(f"[TelegramCommandHandler] Send failed: {e}")

    # ─ Update handler ─────────────────────────────────────────────────────────

    async def _handle_update(self, update: dict):
        """Dispatch update to correct command handler."""
        message = update.get("message") or update.get("edited_message")
        if not message:
            return

        chat_id = message["chat"]["id"]
        text = message.get("text", "").strip().lower()

        if text.startswith("/pnl"):
            await self._cmd_pnl(chat_id)
        elif text.startswith("/status"):
            await self._cmd_status(chat_id)
        elif text.startswith("/signal"):
            await self._cmd_signal(chat_id)
        elif text.startswith("/balance"):
            await self._cmd_balance(chat_id)
        elif text.startswith("/help"):
            await self._cmd_help(chat_id)

    # ─ Commands ───────────────────────────────────────────────────────────────

    async def _cmd_pnl(self, chat_id: int):
        """Return current open position PnL."""
        trade = self.live_repo.get_open_trade()

        if not trade:
            await self._send(chat_id, "📭 <b>Tidak ada posisi terbuka.</b>")
            return

        current_price = self._get_latest_price()
        if current_price is None:
            await self._send(chat_id, "⚠️ Gagal ambil harga terbaru dari DB.")
            return

        # Hitung unrealized PnL
        if trade.side == "LONG":
            price_diff_pct = (current_price - trade.entry_price) / trade.entry_price
        else:
            price_diff_pct = (trade.entry_price - current_price) / trade.entry_price

        unrealized_pnl_usdt = price_diff_pct * trade.size_usdt * trade.leverage
        unrealized_pnl_pct = price_diff_pct * trade.leverage * 100

        # Status vs SL/TP
        if trade.side == "LONG":
            distance_to_sl_pct = (current_price - trade.sl_price) / trade.entry_price * 100
            distance_to_tp_pct = (trade.tp_price - current_price) / trade.entry_price * 100
        else:
            distance_to_sl_pct = (trade.sl_price - current_price) / trade.entry_price * 100
            distance_to_tp_pct = (current_price - trade.tp_price) / trade.entry_price * 100

        pnl_emoji = "📈" if unrealized_pnl_usdt >= 0 else "📉"
        direction_emoji = "📈" if trade.side == "LONG" else "📉"

        hold_hours = (time.time() * 1000 - trade.timestamp_open) / 3600000

        msg = (
            f"📊 <b>OPEN POSITION — Live PnL</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{direction_emoji} <b>{trade.side}</b> BTC/USDT\n"
            f"💰 Entry     : <b>${trade.entry_price:,.2f}</b>\n"
            f"📡 Now       : <b>${current_price:,.2f}</b>\n"
            f"{pnl_emoji} Unreal PnL : <b>{unrealized_pnl_usdt:+.3f} USDT ({unrealized_pnl_pct:+.2f}%)</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🛑 SL        : ${trade.sl_price:,.2f}  (jarak {distance_to_sl_pct:+.3f}%)\n"
            f"🎯 TP        : ${trade.tp_price:,.2f}  (jarak {distance_to_tp_pct:+.3f}%)\n"
            f"📏 Margin    : ${trade.size_usdt:,.0f} × {trade.leverage}x\n"
            f"⏱️  Hold      : {hold_hours:.1f} jam\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🤖 BTC-QUANT LIVE v4.4"
        )
        await self._send(chat_id, msg)

    async def _cmd_status(self, chat_id: int):
        """Return bot status and daily PnL."""
        trading_enabled = os.getenv("LIGHTER_TRADING_ENABLED", "false").lower() == "true"
        mode = os.getenv("LIGHTER_EXECUTION_MODE", "unknown").upper()
        daily_pnl_usdt, daily_pnl_pct = self.live_repo.get_daily_pnl()
        trade = self.live_repo.get_open_trade()
        current_price = self._get_latest_price()

        trading_status = "🟢 ENABLED" if trading_enabled else "🔴 DISABLED"
        position_text = f"Ada posisi {trade.side} @ ${trade.entry_price:,.2f}" if trade else "Tidak ada posisi"
        price_text = f"${current_price:,.2f}" if current_price else "N/A"
        pnl_emoji = "📈" if daily_pnl_usdt >= 0 else "📉"

        msg = (
            f"🤖 <b>BTC-QUANT STATUS</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⚙️  Mode      : <b>{mode}</b>\n"
            f"🔧 Trading   : <b>{trading_status}</b>\n"
            f"📡 BTC Price : <b>{price_text}</b>\n"
            f"📂 Posisi    : {position_text}\n"
            f"{pnl_emoji} Daily PnL  : <b>{daily_pnl_usdt:+.3f} USDT ({daily_pnl_pct:+.2f}%)</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Ketik /pnl untuk detail posisi\n"
            f"Ketik /signal untuk sinyal terbaru\n"
            f"Ketik /balance untuk saldo exchange"
        )
        await self._send(chat_id, msg)

    async def _cmd_signal(self, chat_id: int):
        """Return the latest cached quantitative signal."""
        signal = get_cached_signal()
        if not signal:
            await self._send(chat_id, "📭 <b>Belum ada sinyal yang terhitung.</b>\nHarap tunggu candle 4H berikutnya.")
            return

        c = signal.confluence
        l = c.layers
        
        status_emoji = "🟢" if signal.trade_plan.status == "ACTIVE" else "🟡" if signal.trade_plan.status == "ADVISORY" else "⚪"
        
        msg = (
            f"📡 <b>LATEST QUANT SIGNAL</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🚦 Status    : {status_emoji} <b>{signal.trade_plan.status}</b>\n"
            f"🎯 Action    : <b>{signal.trend.action}</b> ({signal.confluence.verdict})\n"
            f"📊 Conviction: <b>{c.conviction_pct:.1f}%</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>Layer Breakdown:</b>\n"
            f"{'✅' if l.l1.aligned else '❌'} L1 BCD : {l.l1.label}\n"
            f"{'✅' if l.l2.aligned else '❌'} L2 EMA : {l.l2.label}\n"
            f"{'✅' if l.l3.aligned else '❌'} L3 MLP : {l.l3.label}\n"
            f"{'✅' if l.l4.aligned else '❌'} L4 Vol : {signal.volatility.label}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🛑 SL: ${signal.trade_plan.sl_price:,.2f}\n"
            f"🎯 TP: ${signal.trade_plan.tp_price:,.2f}\n"
            f"📏 Lev: {signal.trade_plan.leverage}x\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🕒 <i>{datetime.now().strftime('%H:%M:%S')} WIB</i>"
        )
        await self._send(chat_id, msg)

    async def _cmd_balance(self, chat_id: int):
        """Return account balance from exchange."""
        try:
            balance = await self.gateway.get_account_balance()
            
            msg = (
                f"💰 <b>EXCHANGE BALANCE</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🏦 Unified : <b>{balance:,.2f} USDC</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🤖 Mode: {self.gateway.execution_mode.upper()}"
            )
            await self._send(chat_id, msg)
        except Exception as e:
            await self._send(chat_id, f"❌ Gagal ambil saldo: {str(e)}")

    async def _cmd_help(self, chat_id: int):
        msg = (
            f"🤖 <b>BTC-QUANT Commands</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"/pnl     — PnL posisi saat ini\n"
            f"/status  — Status bot & daily PnL\n"
            f"/signal  — Detail sinyal terbaru\n"
            f"/balance — Saldo exchange rill\n"
            f"/help    — Daftar command\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🤖 BTC-QUANT LIVE v4.6"
        )
        await self._send(chat_id, msg)

    # ─ Helpers ────────────────────────────────────────────────────────────────

    def _get_latest_price(self) -> Optional[float]:
        """Ambil harga BTC terbaru dari DB OHLCV."""
        try:
            import duckdb
            with duckdb.connect(self.market_repo.db_path, read_only=True) as con:
                row = con.execute(
                    "SELECT close FROM btc_ohlcv_4h ORDER BY timestamp DESC LIMIT 1"
                ).fetchone()
                return float(row[0]) if row else None
        except Exception as e:
            logger.error(f"[TelegramCommandHandler] Failed to get latest price: {e}")
            return None


# Singleton
_handler: Optional[TelegramCommandHandler] = None


def get_telegram_command_handler() -> TelegramCommandHandler:
    global _handler
    if _handler is None:
        _handler = TelegramCommandHandler()
    return _handler
