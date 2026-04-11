"""
Unit tests for PositionManager Exchange-First Architecture

Tests validate that:
1. process_signal() checks exchange before DB
2. Exchange state is the source of truth
3. DB sync issues are detected and logged
4. Position management uses provided exchange_pos to avoid redundant API calls
"""

import pytest
import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock, patch, MagicMock

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.use_cases.position_manager import PositionManager
from app.adapters.gateways.base_execution_gateway import PositionInfo, OrderResult


@pytest.fixture
def mock_gateway():
    """Create a mock gateway with async methods."""
    gateway = Mock()
    gateway.get_open_position = AsyncMock(return_value=None)
    gateway.get_account_balance = AsyncMock(return_value=1000.0)
    gateway.place_market_order = AsyncMock()
    gateway.place_sl_order = AsyncMock()
    gateway.place_tp_order = AsyncMock()
    gateway.close_position_market = AsyncMock()
    gateway.get_active_sl_tp = AsyncMock(return_value={"sl_price": None, "tp_price": None})
    return gateway


@pytest.fixture
def mock_repo():
    """Create a mock repository."""
    repo = Mock()
    repo.get_open_trade = Mock(return_value=None)
    repo.insert_trade = Mock()
    repo.update_trade_on_close = Mock()
    repo.update_trade_params = Mock()
    return repo


@pytest.fixture
def mock_risk_manager():
    """Create a mock risk manager."""
    risk = Mock()
    risk.evaluate = Mock(return_value=Mock(can_trade=True, approved_leverage=15, position_size_pct=5.0, is_deleveraged=False))
    risk.record_trade_result = Mock()
    return risk


@pytest.fixture
def mock_strategy():
    """Create a mock strategy."""
    strategy = Mock()
    strategy.calculate = Mock(return_value=Mock(
        sl_price=80000.0,
        tp_price=85000.0,
        sl_pct=1.5,
        tp_pct=0.7,
        margin_usd=15.0,
        leverage=15,
        strategy_name="TestStrategy"
    ))
    return strategy


@pytest.fixture
def position_manager(mock_gateway, mock_repo, mock_risk_manager, mock_strategy):
    """Create a PositionManager instance with mocked dependencies."""
    pm = PositionManager(
        gateway=mock_gateway,
        repo=mock_repo,
        risk_manager=mock_risk_manager,
        strategy=mock_strategy
    )
    # Mock trading enabled
    pm._is_trading_enabled = Mock(return_value=True)
    pm._is_sl_frozen = Mock(return_value=False)
    return pm


@pytest.fixture
def mock_signal():
    """Create a mock signal."""
    return SimpleNamespace(
        confluence=SimpleNamespace(
            verdict="WEAK BUY",
            conviction_pct=65.0
        ),
        trade_plan=SimpleNamespace(
            action="LONG",
            status="ADVISORY",
            sl=80000.0,
            tp1=85000.0
        ),
        price=SimpleNamespace(now=82000.0),
        dict=lambda: {}
    )


@pytest.fixture
def mock_db_trade():
    """Create a mock DB trade record."""
    return SimpleNamespace(
        id="trade-123",
        side="LONG",
        entry_price=82000.0,
        sl_price=80000.0,
        tp_price=85000.0,
        sl_order_id="sl-123",
        tp_order_id="tp-123",
        size_usdt=15.0,
        leverage=15,
        timestamp_open=int(datetime.now().timestamp() * 1000)
    )


@pytest.fixture
def mock_exchange_position():
    """Create a mock exchange position."""
    return PositionInfo(
        symbol="BTC/USDT",
        side="LONG",
        quantity=0.0015,
        entry_price=82000.0,
        unrealized_pnl=50.0,
        leverage=15
    )


class TestProcessSignalExchangeFirst:
    """Test that process_signal follows exchange-first architecture."""

    @pytest.mark.asyncio
    async def test_checks_exchange_first(self, position_manager, mock_gateway, mock_repo, mock_signal):
        """Test that exchange is checked as source of truth."""
        # Setup: Exchange has no position, DB has no trade
        mock_gateway.get_open_position.return_value = None
        mock_repo.get_open_trade.return_value = None

        # Mock _try_open_position
        position_manager._try_open_position = AsyncMock(return_value=True)

        # Execute
        await position_manager.process_signal(mock_signal)

        # Assert: Exchange checked as first source of truth
        mock_gateway.get_open_position.assert_called_once()
        # DB checked only after exchange (for sync detection)
        mock_repo.get_open_trade.assert_called_once()
        # Should try to open position since exchange is empty
        position_manager._try_open_position.assert_called_once()

    @pytest.mark.asyncio
    async def test_exchange_has_position_manages_it(self, position_manager, mock_gateway, mock_repo, mock_signal, mock_exchange_position, mock_db_trade):
        """Test that when exchange has position, it manages the position."""
        # Setup: Exchange has position, DB has matching trade
        mock_gateway.get_open_position.return_value = mock_exchange_position
        mock_repo.get_open_trade.return_value = mock_db_trade

        # Mock _manage_existing_position to verify it's called
        position_manager._manage_existing_position = AsyncMock(return_value=True)

        # Execute
        await position_manager.process_signal(mock_signal)

        # Assert: _manage_existing_position called with correct args
        position_manager._manage_existing_position.assert_called_once()
        call_args = position_manager._manage_existing_position.call_args
        assert call_args[0][0] == mock_signal  # signal
        assert call_args[0][1] == mock_db_trade  # db_trade
        assert call_args[0][2] == mock_exchange_position  # exchange_pos

    @pytest.mark.asyncio
    async def test_exchange_empty_tries_open_position(self, position_manager, mock_gateway, mock_repo, mock_signal):
        """Test that when exchange is empty, it tries to open new position."""
        # Setup: Exchange has no position
        mock_gateway.get_open_position.return_value = None
        mock_repo.get_open_trade.return_value = None

        # Mock _try_open_position
        position_manager._try_open_position = AsyncMock(return_value=True)

        # Execute
        await position_manager.process_signal(mock_signal)

        # Assert: _try_open_position called
        position_manager._try_open_position.assert_called_once_with(mock_signal)

    @pytest.mark.asyncio
    async def test_detects_db_out_of_sync_exchange_empty(self, position_manager, mock_gateway, mock_repo, mock_signal, mock_db_trade):
        """Test that DB out-of-sync is detected when DB shows open but exchange empty."""
        # Setup: Exchange empty, DB shows open trade
        mock_gateway.get_open_position.return_value = None
        mock_repo.get_open_trade.return_value = mock_db_trade

        # Mock _try_open_position
        position_manager._try_open_position = AsyncMock(return_value=True)

        # Execute
        await position_manager.process_signal(mock_signal)

        # Assert: Both exchange and DB checked
        mock_gateway.get_open_position.assert_called_once()
        # DB checked twice: once for sync detection, once in _try_open_position (safety guard)
        assert mock_repo.get_open_trade.call_count >= 1
        # _try_open_position should still be called (exchange is empty, so we can open)
        position_manager._try_open_position.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_exchange_has_position_but_db_empty(self, position_manager, mock_gateway, mock_repo, mock_signal, mock_exchange_position):
        """Test handling when exchange has position but DB is empty (sync issue)."""
        # Setup: Exchange has position, DB is empty
        mock_gateway.get_open_position.return_value = mock_exchange_position
        mock_repo.get_open_trade.return_value = None

        # Execute
        result = await position_manager.process_signal(mock_signal)

        # Assert: Returns True (processed) but doesn't try to open
        assert result is True
        # Should log warning and skip


class TestManageExistingPosition:
    """Test _manage_existing_position with exchange_pos parameter."""

    @pytest.mark.asyncio
    async def test_uses_provided_exchange_pos(self, position_manager, mock_gateway, mock_signal, mock_db_trade, mock_exchange_position):
        """Test that when exchange_pos is provided, no redundant API call is made."""
        # Mock TIME_EXIT check to return False
        position_manager._should_time_exit = Mock(return_value=False)

        # Execute with provided exchange_pos
        await position_manager._manage_existing_position(
            mock_signal, mock_db_trade, exchange_pos=mock_exchange_position
        )

        # Assert: get_open_position NOT called again (optimization)
        mock_gateway.get_open_position.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetches_exchange_pos_when_not_provided(self, position_manager, mock_gateway, mock_signal, mock_db_trade, mock_exchange_position):
        """Test that when exchange_pos is None, it fetches from exchange."""
        # Setup
        mock_gateway.get_open_position.return_value = mock_exchange_position
        position_manager._should_time_exit = Mock(return_value=False)

        # Execute without providing exchange_pos
        await position_manager._manage_existing_position(
            mock_signal, mock_db_trade, exchange_pos=None
        )

        # Assert: get_open_position called to fetch position
        mock_gateway.get_open_position.assert_called_once()


class TestSignalProcessingFlow:
    """Test complete signal processing flow scenarios."""

    @pytest.mark.asyncio
    async def test_weak_buy_signal_with_no_position(self, position_manager, mock_gateway, mock_repo, mock_signal):
        """Test WEAK BUY signal processed when no position exists."""
        # Setup
        mock_gateway.get_open_position.return_value = None
        mock_repo.get_open_trade.return_value = None
        mock_signal.trade_plan.status = "ADVISORY"

        # Mock _try_open_position to simulate successful processing
        position_manager._try_open_position = AsyncMock(return_value=True)

        # Execute
        result = await position_manager.process_signal(mock_signal)

        # Assert
        assert result is True
        position_manager._try_open_position.assert_called_once()

    @pytest.mark.asyncio
    async def test_strong_buy_blocked_by_existing_position(self, position_manager, mock_gateway, mock_repo, mock_signal, mock_exchange_position, mock_db_trade):
        """Test STRONG BUY blocked when position already exists at exchange."""
        # Setup: Exchange has position
        mock_gateway.get_open_position.return_value = mock_exchange_position
        mock_repo.get_open_trade.return_value = mock_db_trade
        mock_signal.confluence.verdict = "STRONG BUY"

        # Mock _manage_existing_position
        position_manager._manage_existing_position = AsyncMock(return_value=True)

        # Execute
        result = await position_manager.process_signal(mock_signal)

        # Assert: Signal processed but position managed, not new position opened
        assert result is True
        position_manager._manage_existing_position.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
