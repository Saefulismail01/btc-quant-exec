"""
Lighter Protocol Nonce Manager — Persistent Transaction Sequencing.

Manages the sequential nonce requirement for Lighter transactions.
Nonce must increment by 1 for each transaction on the same API Key.
This manager persists nonce state to disk for recovery after restarts.

Architecture:
- Local nonce tracking (in-memory + JSON persistence)
- Server resync on startup (mandatory safety check)
- Auto-resync on nonce mismatch detection
- Thread-safe via asyncio.Lock()
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class LighterNonceManager:
    """
    Manages persistent nonce state for Lighter API transactions.

    Lighter requires that each transaction includes a sequential nonce
    that increments by 1 for each API key. If nonce is wrong, the transaction fails.

    This manager:
    1. Tracks the next expected nonce locally
    2. Persists state to JSON after each transaction
    3. Resyncs from server on startup and after errors
    4. Provides atomic get/mark operations
    """

    STATE_FILE = Path(__file__).resolve().parent.parent / "infrastructure" / "lighter_nonce_state.json"

    def __init__(self, api_key_index: int):
        """
        Initialize Nonce Manager.

        Args:
            api_key_index: API Key index in Lighter (0-254, but 0-1 reserved)
        """
        self.api_key_index = api_key_index
        self.lock = asyncio.Lock()
        self._next_nonce = 0
        self._last_synced_at = 0
        self._synced_from_server = False

        # Ensure state directory exists
        self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Load state from disk if exists
        self._load_state()

    def _load_state(self) -> None:
        """Load nonce state from JSON file if it exists."""
        if self.STATE_FILE.exists():
            try:
                with open(self.STATE_FILE, "r") as f:
                    state = json.load(f)

                # Verify state is for the same API key
                if state.get("api_key_index") != self.api_key_index:
                    logger.warning(
                        f"[LIGHTER_NONCE] State file is for API key {state.get('api_key_index')}, "
                        f"but we are using key {self.api_key_index}. Resetting nonce."
                    )
                    return

                self._next_nonce = state.get("next_nonce", 0)
                self._last_synced_at = state.get("last_synced_at", 0)

                logger.info(
                    f"[LIGHTER_NONCE] Loaded state from disk: "
                    f"next_nonce={self._next_nonce}, api_key_index={self.api_key_index}"
                )
            except Exception as e:
                logger.error(f"[LIGHTER_NONCE] Failed to load state file: {e}. Starting fresh.")
        else:
            logger.info(f"[LIGHTER_NONCE] No state file found. Starting with nonce=0.")

    def _save_state(self) -> None:
        """Persist current nonce state to JSON file."""
        try:
            state = {
                "api_key_index": self.api_key_index,
                "next_nonce": self._next_nonce,
                "last_synced_at": self._last_synced_at,
                "updated_at": datetime.utcnow().isoformat(),
            }

            with open(self.STATE_FILE, "w") as f:
                json.dump(state, f, indent=2)

            logger.debug(f"[LIGHTER_NONCE] Persisted state: next_nonce={self._next_nonce}")
        except Exception as e:
            logger.error(f"[LIGHTER_NONCE] Failed to save state: {e}")

    async def get_next_nonce(self) -> int:
        """
        Get the next nonce for a transaction (without incrementing).

        This method is called before sending a transaction to determine
        what nonce to use. Does not increment — caller must call mark_used()
        after transaction succeeds.

        Returns:
            Next available nonce
        """
        async with self.lock:
            nonce = self._next_nonce
            logger.debug(f"[LIGHTER_NONCE] get_next_nonce() → {nonce}")
            return nonce

    async def mark_used(self, nonce: int) -> None:
        """
        Mark a nonce as consumed and increment the counter.

        Should be called after a transaction is confirmed submitted
        (not necessarily filled, just that Lighter accepted it).

        Args:
            nonce: Nonce that was used
        """
        async with self.lock:
            if nonce != self._next_nonce:
                logger.warning(
                    f"[LIGHTER_NONCE] mark_used() called with nonce={nonce}, "
                    f"but expected {self._next_nonce}. Syncing..."
                )
                # Don't throw — just correct it
                self._next_nonce = nonce + 1
            else:
                self._next_nonce = nonce + 1

            self._save_state()
            logger.info(f"[LIGHTER_NONCE] Marked nonce {nonce} used. Next: {self._next_nonce}")

    async def resync_from_server(self, server_nonce: int) -> int:
        """
        Resync the local nonce state with the server's current nonce.

        Call this at startup and whenever a nonce mismatch error occurs.

        Args:
            server_nonce: The nonce the server reports as next expected

        Returns:
            The next nonce after resync
        """
        async with self.lock:
            old_nonce = self._next_nonce
            self._next_nonce = server_nonce
            self._last_synced_at = int(datetime.utcnow().timestamp())
            self._synced_from_server = True

            self._save_state()

            logger.warning(
                f"[LIGHTER_NONCE] Resynced from server: "
                f"local={old_nonce} → server={server_nonce}"
            )
            return self._next_nonce

    async def handle_nonce_mismatch(self, server_nonce: int) -> int:
        """
        Handle a nonce mismatch error detected by the server.

        This method:
        1. Resyncs the nonce from the server value
        2. Logs the incident (for debugging)
        3. Triggers a Telegram alert (if notifier available)

        Args:
            server_nonce: The nonce the server expected

        Returns:
            The corrected next nonce
        """
        await self.resync_from_server(server_nonce)

        logger.error(
            f"[LIGHTER_NONCE] ⚠️  Nonce mismatch detected and corrected. "
            f"Next nonce: {self._next_nonce}"
        )

        # Trigger Telegram alert asynchronously (non-blocking)
        # This is done by returning to the caller who will notify
        return self._next_nonce

    def is_synced_from_server(self) -> bool:
        """
        Check if this manager has synced with server at least once.

        Returns:
            True if resync_from_server() was called successfully
        """
        return self._synced_from_server

    def get_status(self) -> dict:
        """
        Get current nonce manager status.

        Returns:
            Dict with status info
        """
        return {
            "api_key_index": self.api_key_index,
            "next_nonce": self._next_nonce,
            "synced_from_server": self._synced_from_server,
            "last_synced_at": self._last_synced_at,
        }
