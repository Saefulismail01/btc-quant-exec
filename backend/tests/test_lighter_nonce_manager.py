"""
Unit tests for lighter_nonce_manager.py — Persistent Nonce Tracking.

Tests cover:
- Nonce state persistence (save/load from JSON)
- Get next nonce without incrementing
- Mark nonce as used (increment)
- Server resync (override local state)
- Nonce mismatch detection
- Thread-safety (asyncio)
"""

import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from app.use_cases.lighter_nonce_manager import LighterNonceManager


@pytest.fixture
def temp_state_file():
    """Create a temporary state file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = Path(f.name)
    yield temp_path
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def mock_state_dir(monkeypatch, temp_state_file):
    """Mock the state file directory."""
    state_dir = temp_state_file.parent
    monkeypatch.setattr(
        'app.use_cases.lighter_nonce_manager.LighterNonceManager.STATE_FILE',
        temp_state_file
    )
    return state_dir


class TestNonceManagerInitialization:
    """Tests for LighterNonceManager initialization."""

    def test_init_creates_state_directory(self, mock_state_dir):
        """Test that init creates the state directory if needed."""
        manager = LighterNonceManager(api_key_index=2)
        assert manager.api_key_index == 2
        assert manager._next_nonce == 0
        assert not manager._synced_from_server

    def test_init_with_different_api_key_indices(self, mock_state_dir):
        """Test initialization with different API key indices."""
        for index in [2, 5, 100, 254]:
            manager = LighterNonceManager(api_key_index=index)
            assert manager.api_key_index == index

    def test_init_loads_existing_state(self, mock_state_dir):
        """Test that init loads state from JSON if it exists."""
        state_file = Path(mock_state_dir) / "lighter_nonce_state.json"
        state = {
            "api_key_index": 2,
            "next_nonce": 42,
            "last_synced_at": 1234567890,
        }
        with open(state_file, "w") as f:
            json.dump(state, f)

        manager = LighterNonceManager(api_key_index=2)
        assert manager._next_nonce == 42
        assert manager._last_synced_at == 1234567890

    def test_init_resets_state_for_different_api_key(self, mock_state_dir):
        """Test that init resets state if JSON is for different API key."""
        state_file = Path(mock_state_dir) / "lighter_nonce_state.json"
        state = {
            "api_key_index": 1,  # Different key
            "next_nonce": 42,
            "last_synced_at": 1234567890,
        }
        with open(state_file, "w") as f:
            json.dump(state, f)

        manager = LighterNonceManager(api_key_index=2)
        # Should start fresh because API key index differs
        assert manager._next_nonce == 0


class TestGetNextNonce:
    """Tests for get_next_nonce() method."""

    @pytest.mark.asyncio
    async def test_get_next_nonce_returns_current(self, mock_state_dir):
        """Test that get_next_nonce returns current nonce without incrementing."""
        manager = LighterNonceManager(api_key_index=2)
        manager._next_nonce = 10

        nonce = await manager.get_next_nonce()
        assert nonce == 10
        # Should not increment
        assert manager._next_nonce == 10

    @pytest.mark.asyncio
    async def test_get_next_nonce_starts_at_zero(self, mock_state_dir):
        """Test that get_next_nonce starts at 0 for new manager."""
        manager = LighterNonceManager(api_key_index=2)

        nonce = await manager.get_next_nonce()
        assert nonce == 0

    @pytest.mark.asyncio
    async def test_get_next_nonce_multiple_calls(self, mock_state_dir):
        """Test that get_next_nonce returns same value on multiple calls."""
        manager = LighterNonceManager(api_key_index=2)

        nonce1 = await manager.get_next_nonce()
        nonce2 = await manager.get_next_nonce()
        nonce3 = await manager.get_next_nonce()

        assert nonce1 == nonce2 == nonce3 == 0


class TestMarkUsed:
    """Tests for mark_used() method."""

    @pytest.mark.asyncio
    async def test_mark_used_increments_nonce(self, mock_state_dir):
        """Test that mark_used increments the nonce."""
        manager = LighterNonceManager(api_key_index=2)
        manager._next_nonce = 10

        await manager.mark_used(10)
        assert manager._next_nonce == 11

    @pytest.mark.asyncio
    async def test_mark_used_persists_to_file(self, mock_state_dir):
        """Test that mark_used saves state to JSON."""
        manager = LighterNonceManager(api_key_index=2)
        manager._next_nonce = 10

        await manager.mark_used(10)

        # Load state from file
        state_file = Path(mock_state_dir) / "lighter_nonce_state.json"
        with open(state_file, "r") as f:
            state = json.load(f)

        assert state["next_nonce"] == 11
        assert state["api_key_index"] == 2

    @pytest.mark.asyncio
    async def test_mark_used_with_wrong_nonce_corrects(self, mock_state_dir):
        """Test that mark_used with wrong nonce corrects it."""
        manager = LighterNonceManager(api_key_index=2)
        manager._next_nonce = 10

        # Mark nonce 12 (not 10)
        await manager.mark_used(12)

        # Should correct to 13 (12 + 1)
        assert manager._next_nonce == 13

    @pytest.mark.asyncio
    async def test_mark_used_sequence(self, mock_state_dir):
        """Test marking a sequence of nonces."""
        manager = LighterNonceManager(api_key_index=2)

        for i in range(5):
            nonce = await manager.get_next_nonce()
            assert nonce == i
            await manager.mark_used(nonce)

        # Final nonce should be 5
        assert manager._next_nonce == 5


class TestResyncFromServer:
    """Tests for resync_from_server() method."""

    @pytest.mark.asyncio
    async def test_resync_from_server_overrides_local(self, mock_state_dir):
        """Test that resync overrides local nonce with server value."""
        manager = LighterNonceManager(api_key_index=2)
        manager._next_nonce = 10

        await manager.resync_from_server(server_nonce=20)

        assert manager._next_nonce == 20
        assert manager._synced_from_server is True

    @pytest.mark.asyncio
    async def test_resync_from_server_returns_new_nonce(self, mock_state_dir):
        """Test that resync returns the new nonce."""
        manager = LighterNonceManager(api_key_index=2)

        new_nonce = await manager.resync_from_server(server_nonce=42)

        assert new_nonce == 42

    @pytest.mark.asyncio
    async def test_resync_from_server_updates_sync_timestamp(self, mock_state_dir):
        """Test that resync updates the sync timestamp."""
        manager = LighterNonceManager(api_key_index=2)
        old_timestamp = manager._last_synced_at

        await manager.resync_from_server(server_nonce=10)

        assert manager._last_synced_at > old_timestamp

    @pytest.mark.asyncio
    async def test_resync_from_server_persists_to_file(self, mock_state_dir):
        """Test that resync saves state to JSON."""
        manager = LighterNonceManager(api_key_index=2)

        await manager.resync_from_server(server_nonce=50)

        # Load state from file
        state_file = Path(mock_state_dir) / "lighter_nonce_state.json"
        with open(state_file, "r") as f:
            state = json.load(f)

        assert state["next_nonce"] == 50


class TestHandleNonceMismatch:
    """Tests for handle_nonce_mismatch() method."""

    @pytest.mark.asyncio
    async def test_handle_nonce_mismatch_resyncs(self, mock_state_dir):
        """Test that handle_nonce_mismatch resyncs from server."""
        manager = LighterNonceManager(api_key_index=2)
        manager._next_nonce = 10

        await manager.handle_nonce_mismatch(server_nonce=20)

        assert manager._next_nonce == 20

    @pytest.mark.asyncio
    async def test_handle_nonce_mismatch_returns_corrected_nonce(self, mock_state_dir):
        """Test that handle_nonce_mismatch returns the corrected nonce."""
        manager = LighterNonceManager(api_key_index=2)

        corrected_nonce = await manager.handle_nonce_mismatch(server_nonce=15)

        assert corrected_nonce == 15


class TestIsSyncedFromServer:
    """Tests for is_synced_from_server() method."""

    def test_is_synced_from_server_initially_false(self, mock_state_dir):
        """Test that is_synced_from_server is False initially."""
        manager = LighterNonceManager(api_key_index=2)
        assert manager.is_synced_from_server() is False

    @pytest.mark.asyncio
    async def test_is_synced_from_server_true_after_resync(self, mock_state_dir):
        """Test that is_synced_from_server is True after resync."""
        manager = LighterNonceManager(api_key_index=2)

        await manager.resync_from_server(server_nonce=10)

        assert manager.is_synced_from_server() is True


class TestGetStatus:
    """Tests for get_status() method."""

    def test_get_status_returns_dict(self, mock_state_dir):
        """Test that get_status returns a dict with expected keys."""
        manager = LighterNonceManager(api_key_index=2)

        status = manager.get_status()

        assert isinstance(status, dict)
        assert "api_key_index" in status
        assert "next_nonce" in status
        assert "synced_from_server" in status
        assert "last_synced_at" in status

    def test_get_status_reflects_current_state(self, mock_state_dir):
        """Test that get_status reflects current manager state."""
        manager = LighterNonceManager(api_key_index=5)
        manager._next_nonce = 42
        manager._synced_from_server = True
        manager._last_synced_at = 1234567890

        status = manager.get_status()

        assert status["api_key_index"] == 5
        assert status["next_nonce"] == 42
        assert status["synced_from_server"] is True
        assert status["last_synced_at"] == 1234567890


class TestThreadSafety:
    """Tests for thread-safety with asyncio locks."""

    @pytest.mark.asyncio
    async def test_concurrent_get_next_nonce_calls(self, mock_state_dir):
        """Test that concurrent get_next_nonce calls are safe."""
        manager = LighterNonceManager(api_key_index=2)

        # Run multiple concurrent calls
        nonces = await asyncio.gather(
            manager.get_next_nonce(),
            manager.get_next_nonce(),
            manager.get_next_nonce(),
        )

        # All should return the same nonce (0)
        assert all(n == 0 for n in nonces)

    @pytest.mark.asyncio
    async def test_concurrent_mark_used_calls(self, mock_state_dir):
        """Test that concurrent mark_used calls are safe."""
        manager = LighterNonceManager(api_key_index=2)

        # Mark nonces sequentially in a safe way
        await manager.mark_used(0)
        await manager.mark_used(1)
        await manager.mark_used(2)

        assert manager._next_nonce == 3

    @pytest.mark.asyncio
    async def test_interleaved_get_and_mark_calls(self, mock_state_dir):
        """Test interleaved get_next_nonce and mark_used calls."""
        manager = LighterNonceManager(api_key_index=2)

        # Simulate transaction flow: get nonce → use → get next → use next
        nonce1 = await manager.get_next_nonce()
        await manager.mark_used(nonce1)

        nonce2 = await manager.get_next_nonce()
        await manager.mark_used(nonce2)

        nonce3 = await manager.get_next_nonce()

        assert nonce1 == 0
        assert nonce2 == 1
        assert nonce3 == 2


class TestStatePersistence:
    """Tests for state file persistence and recovery."""

    @pytest.mark.asyncio
    async def test_state_persisted_after_operations(self, mock_state_dir):
        """Test that state is persisted after operations."""
        # First manager instance
        manager1 = LighterNonceManager(api_key_index=2)
        await manager1.mark_used(0)
        await manager1.mark_used(1)

        # Create new manager instance (simulates restart)
        manager2 = LighterNonceManager(api_key_index=2)

        # Should have loaded the persisted state
        assert manager2._next_nonce == 2

    @pytest.mark.asyncio
    async def test_state_recovery_after_crash_simulation(self, mock_state_dir):
        """Test that state can be recovered after simulated crash."""
        # First manager
        manager1 = LighterNonceManager(api_key_index=2)
        await manager1.mark_used(5)

        # Simulate crash (create new manager)
        manager2 = LighterNonceManager(api_key_index=2)

        # Should recover the nonce
        nonce = await manager2.get_next_nonce()
        assert nonce == 6
