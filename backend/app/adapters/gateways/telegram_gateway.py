import asyncio
import httpx
import logging
import re
from typing import Optional

class TelegramGateway:
    """
    Adapter for Telegram Bot API.
    Sends formatted messages to a specific Chat ID.
    Supports MarkdownV2 with auto-escaping for safe delivery.
    """
    
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.logger = logging.getLogger("telegram_gateway")

    def _escape_markdown(self, text: str) -> str:
        """
        Escapes special characters for Telegram MarkdownV2.
        Characters to escape: _ * [ ] ( ) ~ ` > # + - = | { } . !
        Note: We don't escape characters if they are part of the intended formatting.
        This is a simplified version.
        """
        # Telegram MarkdownV2 requires escaping of many characters
        escape_chars = r'_*[]()~`>#+-=|{}.!'
        return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

    async def _post_message(self, payload: dict, retries: int = 3, backoff: float = 5.0) -> tuple[bool, Optional[httpx.Response]]:
        """Low-level POST with retry on transient connection errors."""
        url = f"{self.base_url}/sendMessage"
        last_exc: Optional[Exception] = None

        for attempt in range(1, retries + 1):
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    response = await client.post(url, json=payload)
                    return response.status_code == 200, response
            except httpx.ConnectError as e:
                last_exc = e
                detail = f"ConnectError — DNS/TCP gagal ke api.telegram.org: {e}"
            except httpx.TimeoutException as e:
                last_exc = e
                detail = f"TimeoutException — tidak ada respons dalam 20s: {e}"
            except httpx.RemoteProtocolError as e:
                last_exc = e
                detail = f"RemoteProtocolError — SSL/HTTP handshake gagal: {e}"
            except Exception as e:
                self.logger.error(f"[Telegram] POST Exception tak terduga ({type(e).__name__}): {e}")
                return False, None

            if attempt < retries:
                wait = backoff * attempt
                self.logger.warning(
                    f"[Telegram] Attempt {attempt}/{retries} gagal — {detail}. "
                    f"Retry dalam {wait:.0f}s..."
                )
                await asyncio.sleep(wait)

        self.logger.error(
            f"[Telegram] Gagal kirim setelah {retries} attempts. "
            f"Error terakhir: {type(last_exc).__name__}: {last_exc}"
        )
        return False, None

    async def send_message(self, text: str, parse_mode: str = "MarkdownV2") -> bool:
        """Sends a text message to the configured channel."""
        if not self.token or not self.chat_id:
            self.logger.warning("Telegram Bot Token or Chat ID not configured. Skipping notification.")
            return False

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        try:
            ok, response = await self._post_message(payload)
            if ok:
                return True

            # MarkdownV2 parse failures are common when one special character slips through.
            # Retry once with full escaping, then fall back to plain text.
            resp_text = response.text if response is not None else ""
            status_code = response.status_code if response is not None else None

            if parse_mode == "MarkdownV2" and status_code == 400 and "can't parse entities" in resp_text:
                escaped_payload = {
                    "chat_id": self.chat_id,
                    "text": self._escape_markdown(text),
                    "parse_mode": "MarkdownV2",
                }
                ok_escaped, response_escaped = await self._post_message(escaped_payload)
                if ok_escaped:
                    self.logger.warning("Telegram MarkdownV2 parse error recovered via full escaping.")
                    return True

                plain_payload = {
                    "chat_id": self.chat_id,
                    "text": text,
                }
                ok_plain, response_plain = await self._post_message(plain_payload)
                if ok_plain:
                    self.logger.warning("Telegram MarkdownV2 parse error recovered via plain-text fallback.")
                    return True

                if response_plain is not None:
                    self.logger.error(
                        f"Telegram API Error (fallback plain text failed): "
                        f"{response_plain.status_code} - {response_plain.text}"
                    )
                elif response_escaped is not None:
                    self.logger.error(
                        f"Telegram API Error (escaped retry failed): "
                        f"{response_escaped.status_code} - {response_escaped.text}"
                    )
                return False

            self.logger.error(f"Telegram API Error: {status_code} - {resp_text}")
            return False
        except Exception as e:
            self.logger.error(f"Telegram Connection Error: {str(e)}")
            return False

    def send_message_sync(self, text: str, parse_mode: str = "MarkdownV2") -> bool:
        """Synchronous version for non-async environments."""
        if not self.token or not self.chat_id:
            return False

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(url, json=payload)
                return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Telegram Sync Error: {str(e)}")
            return False
