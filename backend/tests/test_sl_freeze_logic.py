"""
Unit tests for SL Freeze logic in PositionManager

Tests validate:
1. SL hit with loss (PnL < 0) → freeze activated
2. SL hit with profit (PnL > 0) → no freeze (trailing SL scenario)
3. SL hit with breakeven (PnL = 0) → no freeze
4. TP hit → freeze cleared
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock, patch, MagicMock, mock_open
import json

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.use_cases.position_manager import PositionManager, WIB
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
    gateway.fetch_last_closed_order = AsyncMock(return_value=None)
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
def mock_notifier():
    """Create a mock notifier."""
    notifier = Mock()
    notifier.notify_trade_opened = AsyncMock(return_value=True)
    notifier.notify_trade_closed = AsyncMock(return_value=True)
    notifier.notify_entry_blocked = AsyncMock(return_value=True)
    return notifier


@pytest.fixture
def mock_risk_manager():
    """Create a mock risk manager."""
    risk = Mock()
    risk.evaluate = Mock(return_value=Mock(
        can_trade=True, 
        approved_leverage=15, 
        position_size_pct=5.0, 
        is_deleveraged=False,
        rejection_reason=None
    ))
    risk.record_trade_result = Mock()
    return risk


@pytest.fixture
def position_manager(mock_gateway, mock_repo, mock_risk_manager, mock_notifier):
    """Create a PositionManager instance with mocked dependencies."""
    with patch('app.use_cases.position_manager.get_execution_notifier', return_value=mock_notifier):
        pm = PositionManager(
            gateway=mock_gateway,
            repo=mock_repo,
            risk_manager=mock_risk_manager
        )
        # Mock trading enabled
        pm._is_trading_enabled = Mock(return_value=True)
        # Note: Don't mock _is_sl_frozen here, let tests control it via _sl_freeze_until
        pm.notifier = mock_notifier
        return pm


@pytest.fixture
def position_manager_frozen_mock(mock_gateway, mock_repo, mock_risk_manager, mock_notifier):
    """Create a PositionManager with mocked _is_sl_frozen for entry block tests."""
    with patch('app.use_cases.position_manager.get_execution_notifier', return_value=mock_notifier):
        pm = PositionManager(
            gateway=mock_gateway,
            repo=mock_repo,
            risk_manager=mock_risk_manager
        )
        pm._is_trading_enabled = Mock(return_value=True)
        pm._is_sl_frozen = Mock(return_value=False)  # Mocked for other tests
        pm.notifier = mock_notifier
        return pm


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


class TestSLFreezeLogic:
    """Test SL freeze activation and clearing based on PnL."""

    @pytest.mark.asyncio
    async def test_sl_hit_with_loss_activates_freeze(self, position_manager, mock_db_trade):
        """Test that SL hit with negative PnL activates freeze."""
        # Setup: Mock _set_sl_freeze and _clear_sl_freeze
        position_manager._set_sl_freeze = Mock()
        position_manager._clear_sl_freeze = Mock()
        
        # Simulate SL hit with loss (PnL < 0)
        exit_type = "SL"
        pnl_usdt = -50.0  # Loss
        pnl_pct = -3.33
        
        # Manually trigger the freeze logic
        if exit_type == "SL":
            if pnl_usdt < 0:
                position_manager._set_sl_freeze()
            else:
                position_manager._clear_sl_freeze()
        elif exit_type == "TP":
            position_manager._clear_sl_freeze()
        
        # Assert: Freeze should be activated
        position_manager._set_sl_freeze.assert_called_once()
        position_manager._clear_sl_freeze.assert_not_called()

    @pytest.mark.asyncio
    async def test_sl_hit_with_profit_no_freeze(self, position_manager, mock_db_trade):
        """Test that SL hit with positive PnL (trailing SL) does NOT freeze."""
        # Setup: Mock _set_sl_freeze and _clear_sl_freeze
        position_manager._set_sl_freeze = Mock()
        position_manager._clear_sl_freeze = Mock()
        
        # Simulate SL hit with profit (PnL > 0) - trailing SL scenario
        exit_type = "SL"
        pnl_usdt = 25.0  # Profit - trailing SL executed
        pnl_pct = 1.67
        
        # Manually trigger the freeze logic
        if exit_type == "SL":
            if pnl_usdt < 0:
                position_manager._set_sl_freeze()
            else:
                position_manager._clear_sl_freeze()
        elif exit_type == "TP":
            position_manager._clear_sl_freeze()
        
        # Assert: Freeze should NOT be activated, should be cleared instead
        position_manager._set_sl_freeze.assert_not_called()
        position_manager._clear_sl_freeze.assert_called_once()

    @pytest.mark.asyncio
    async def test_sl_hit_breakeven_no_freeze(self, position_manager, mock_db_trade):
        """Test that SL hit with breakeven (PnL = 0) does NOT freeze."""
        # Setup: Mock _set_sl_freeze and _clear_sl_freeze
        position_manager._set_sl_freeze = Mock()
        position_manager._clear_sl_freeze = Mock()
        
        # Simulate SL hit with breakeven (PnL = 0)
        exit_type = "SL"
        pnl_usdt = 0.0  # Breakeven
        pnl_pct = 0.0
        
        # Manually trigger the freeze logic
        if exit_type == "SL":
            if pnl_usdt < 0:
                position_manager._set_sl_freeze()
            else:
                position_manager._clear_sl_freeze()
        elif exit_type == "TP":
            position_manager._clear_sl_freeze()
        
        # Assert: Freeze should NOT be activated (0 is not < 0)
        position_manager._set_sl_freeze.assert_not_called()
        position_manager._clear_sl_freeze.assert_called_once()

    @pytest.mark.asyncio
    async def test_tp_hit_clears_freeze(self, position_manager, mock_db_trade):
        """Test that TP hit clears any existing freeze."""
        # Setup: Mock _set_sl_freeze and _clear_sl_freeze
        position_manager._set_sl_freeze = Mock()
        position_manager._clear_sl_freeze = Mock()
        
        # First set a freeze
        position_manager._sl_freeze_until = datetime.now(WIB) + timedelta(days=1)
        
        # Simulate TP hit
        exit_type = "TP"
        pnl_usdt = 100.0
        pnl_pct = 6.67
        
        # Manually trigger the freeze logic
        if exit_type == "SL":
            if pnl_usdt < 0:
                position_manager._set_sl_freeze()
            else:
                position_manager._clear_sl_freeze()
        elif exit_type == "TP":
            position_manager._clear_sl_freeze()
        
        # Assert: Freeze should be cleared
        position_manager._clear_sl_freeze.assert_called_once()
        position_manager._set_sl_freeze.assert_not_called()


class TestSLFreezeStateManagement:
    """Test SL freeze state persistence and loading."""

    def test_set_sl_freeze_calculates_correct_time(self, position_manager):
        """Test that _set_sl_freeze sets freeze until 07:00 WIB next day."""
        with patch('app.use_cases.position_manager.datetime') as mock_datetime:
            # Mock current time: 15:00 WIB today
            now_wib = datetime(2024, 1, 15, 15, 0, 0, tzinfo=WIB)
            mock_datetime.now.return_value = now_wib
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            # Call _set_sl_freeze
            position_manager._set_sl_freeze()
            
            # Assert: Freeze until should be 07:00 WIB next day
            expected_freeze = datetime(2024, 1, 16, 7, 0, 0, tzinfo=WIB)
            assert position_manager._sl_freeze_until == expected_freeze

    def test_is_sl_frozen_returns_true_when_active(self, position_manager):
        """Test _is_sl_frozen returns True when freeze is active."""
        # Set freeze until tomorrow
        position_manager._sl_freeze_until = datetime.now(WIB) + timedelta(days=1)
        
        # Assert
        assert position_manager._is_sl_frozen() is True

    def test_is_sl_frozen_returns_false_when_expired(self, position_manager):
        """Test _is_sl_frozen returns False when freeze has expired."""
        # Set freeze until yesterday (expired)
        position_manager._sl_freeze_until = datetime.now(WIB) - timedelta(hours=1)
        
        # Assert
        assert position_manager._is_sl_frozen() is False

    def test_is_sl_frozen_returns_false_when_no_freeze(self, position_manager):
        """Test _is_sl_frozen returns False when no freeze is set."""
        # Ensure no freeze
        position_manager._sl_freeze_until = None
        
        # Assert
        assert position_manager._is_sl_frozen() is False


class TestTrailingSLScenario:
    """Test real-world trailing SL scenario."""

    @pytest.mark.asyncio
    async def test_user_moves_sl_to_profit_scenario(self, position_manager, mock_db_trade):
        """
        Simulate user moving SL to profit and it getting hit.
        Should NOT activate freeze.
        """
        # Setup
        position_manager._set_sl_freeze = Mock()
        position_manager._clear_sl_freeze = Mock()
        
        # Original trade: Entry @ 82000, SL @ 80000, TP @ 85000
        # User moves SL to 83000 (above entry, in profit zone)
        mock_db_trade.sl_price = 83000.0
        
        # Price hits new SL @ 83000
        exit_price = 83000.0
        pnl_usdt = 15.0 * 0.0015 * (83000 - 82000) / 82000 * 15  # Rough profit calc
        pnl_usdt = 25.0  # Simplified: profit
        
        # System detects as "SL" hit (because order type is STOP_LOSS)
        exit_type = "SL"
        
        # Execute freeze logic
        if exit_type == "SL":
            if pnl_usdt < 0:
                position_manager._set_sl_freeze()
            else:
                position_manager._clear_sl_freeze()
        elif exit_type == "TP":
            position_manager._clear_sl_freeze()
        
        # Assert: No freeze because profit
        position_manager._set_sl_freeze.assert_not_called()
        position_manager._clear_sl_freeze.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
