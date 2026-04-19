import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from app.use_cases.position_manager import PositionManager
from app.schemas.signal import SignalResponse, TradePlan, Confluence, PriceSnapshot
from datetime import datetime

@pytest.fixture
def mock_gateway():
    gateway = MagicMock()
    gateway.get_open_position = AsyncMock(return_value=None)
    gateway.place_market_order = AsyncMock()
    gateway.get_account_balance = AsyncMock(return_value=10000.0)
    gateway.get_current_price = AsyncMock(return_value=75000.0)
    return gateway

@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_open_trade = MagicMock(return_value=None)
    return repo

@pytest.fixture
def mock_strategy():
    strategy = MagicMock()
    # Return something simple
    params = MagicMock()
    params.sl_price = 74000.0
    params.tp_price = 76000.0
    params.margin_usd = 100.0
    params.leverage = 10
    params.strategy_name = "Fixed"
    params.sl_pct = 1.33
    params.tp_pct = 0.71
    strategy.calculate.return_value = params
    return strategy

def create_mock_signal(status="ADVISORY", verdict="NEUTRAL", is_fallback=False):
    # Setup nested objects for Pydantic SignalResponse
    price = MagicMock(spec=PriceSnapshot)
    price.now = 75000.0
    price.atr14 = 500.0
    
    plan = MagicMock(spec=TradePlan)
    plan.status = status
    plan.action = "LONG"
    plan.position_size_pct = 5.0
    plan.leverage = 15
    plan.sl = 74000.0
    plan.tp1 = 76000.0
    
    confluence = MagicMock(spec=Confluence)
    confluence.verdict = verdict
    confluence.conviction_pct = 11.6
    
    signal = MagicMock(spec=SignalResponse)
    signal.is_fallback = is_fallback
    signal.price = price
    signal.trade_plan = plan
    signal.confluence = confluence
    signal.timestamp = datetime.utcnow().isoformat()
    
    # dict() method for service calls
    signal.dict.return_value = {
        "price": {"now": 75000.0},
        "trade_plan": {"action": "LONG", "status": status},
        "confluence": {"verdict": verdict, "conviction_pct": 11.6}
    }
    
    return signal

@pytest.mark.asyncio
async def test_position_manager_blocks_neutral_verdict(mock_gateway, mock_repo, mock_strategy):
    """Test that PositionManager blocks entry if verdict is NEUTRAL, even if status is ADVISORY."""
    pm = PositionManager(gateway=mock_gateway, repo=mock_repo, strategy=mock_strategy)
    
    # Force trading enabled
    with patch.object(pm, '_is_trading_enabled', return_value=True):
        # Case 1: ADVISORY + NEUTRAL (Your case)
        signal = create_mock_signal(status="ADVISORY", verdict="NEUTRAL")
        result = await pm.process_signal(signal)
        
        assert result is True
        # Verify NO market order was placed
        mock_gateway.place_market_order.assert_not_called()
        
        # Case 2: ACTIVE + NEUTRAL (Should also be blocked)
        signal_active = create_mock_signal(status="ACTIVE", verdict="NEUTRAL")
        result_active = await pm.process_signal(signal_active)
        
        assert result_active is True
        mock_gateway.place_market_order.assert_not_called()

@pytest.mark.asyncio
async def test_position_manager_blocks_fallback_signal(mock_gateway, mock_repo, mock_strategy):
    """Test that PositionManager blocks all actions if is_fallback is True."""
    pm = PositionManager(gateway=mock_gateway, repo=mock_repo, strategy=mock_strategy)
    
    # Fallback signal
    signal = create_mock_signal(is_fallback=True)
    
    result = await pm.process_signal(signal)
    
    assert result is True
    # Verify it stopped at the very beginning (no status sync, no exchange calls)
    mock_gateway.get_open_position.assert_not_called()
    mock_gateway.place_market_order.assert_not_called()

@pytest.mark.asyncio
async def test_position_manager_allows_active_weak_buy(mock_gateway, mock_repo, mock_strategy):
    """Test that PositionManager correctly allows entry for non-neutral strong signals."""
    pm = PositionManager(gateway=mock_gateway, repo=mock_repo, strategy=mock_strategy)
    
    # Mocking necessary methods for entry
    pm.risk_manager = MagicMock()
    pm.risk_manager.evaluate.return_value = MagicMock(can_trade=True, approved_leverage=15, position_size_pct=5.0)
    
    with patch.object(pm, '_is_trading_enabled', return_value=True):
        # ACTIVE + STRONG BUY
        signal = create_mock_signal(status="ACTIVE", verdict="STRONG BUY")
        
        # Mock successful order
        order_res = MagicMock()
        order_res.success = True
        order_res.filled_price = 75000.0
        order_res.filled_quantity = 0.01
        order_res.order_id = "test_order"
        mock_gateway.place_market_order.return_value = order_res
        
        # Mock entry quote fill
        mock_gateway.fetch_entry_fill_quote.return_value = 750.0
        
        result = await pm.process_signal(signal)
        
        assert result is True
        # Verify market order WAS placed
        mock_gateway.place_market_order.assert_called_once()
