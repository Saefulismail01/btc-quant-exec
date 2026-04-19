import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.use_cases.telegram_command_handler import TelegramCommandHandler
from app.adapters.gateways.lighter_execution_gateway import PositionInfo
import time

@pytest.fixture
def handler():
    with patch('app.use_cases.telegram_command_handler.LighterExecutionGateway'), \
         patch('app.use_cases.telegram_command_handler.LiveTradeRepository'), \
         patch('app.use_cases.telegram_command_handler.MarketRepository'):
        h = TelegramCommandHandler()
        h._send = AsyncMock() # Mock sending messages to Telegram
        return h

@pytest.mark.asyncio
async def test_cmd_pnl_normal_flow(handler):
    """Test /pnl when everything is synced and open."""
    # Mock live position from exchange
    mock_pos = PositionInfo(
        symbol="BTC/USDC",
        side="LONG",
        entry_price=70000.0,
        quantity=0.01,
        unrealized_pnl=50.5,
        leverage=10,
        sl_order_id=None,
        tp_order_id=None,
        opened_at_ts=int(time.time() * 1000)
    )
    handler.gateway.get_open_position = AsyncMock(return_value=mock_pos)
    handler.gateway.get_current_price = AsyncMock(return_value=75000.0)
    
    # Mock local trade
    mock_local = MagicMock()
    mock_local.sl_price = 68000.0
    mock_local.tp_price = 72000.0
    handler.live_repo.get_open_trade.return_value = mock_local

    await handler._cmd_pnl(12345)

    # Verify message sent with correct PnL info
    handler._send.assert_called_once()
    args = handler._send.call_args[0]
    chat_id, msg = args
    assert chat_id == 12345
    assert "75,000.00" in msg # Current price
    assert "+50.500 USDT" in msg # Unreal PnL from exchange
    assert "synchronized with Lighter" in msg

@pytest.mark.asyncio
async def test_cmd_pnl_self_healing_orphaned_trade(handler):
    """Test /pnl when exchange has no position but local DB does (should close local)."""
    from unittest.mock import ANY
    # 1. Exchange says NO POSITION
    handler.gateway.get_open_position = AsyncMock(return_value=None)
    handler.gateway.fetch_last_closed_order = AsyncMock(return_value={"filled_price": 71000.0})
    
    # 2. Local DB says OLD OPEN TRADE
    mock_local = MagicMock()
    mock_local.id = "trade_abc"
    mock_local.timestamp_open = int(time.time() * 1000) - 3600000
    handler.live_repo.get_open_trade.return_value = mock_local

    await handler._cmd_pnl(12345)

    # Verify self-healing triggered
    handler.live_repo.close_trade.assert_called_once_with("trade_abc", 71000.0)
    handler._send.assert_called_with(12345, ANY)
    
    # Check if the sync message was sent
    msg = handler._send.call_args[0][1]
    assert "Posisi tersinkronisasi" in msg

@pytest.mark.asyncio
async def test_cmd_status_live_sync(handler):
    """Test /status uses live data."""
    mock_pos = PositionInfo(
        symbol="BTC/USDC",
        side="SHORT",
        entry_price=75000.0,
        quantity=0.01,
        unrealized_pnl=-10.0,
        leverage=10,
        sl_order_id=None,
        tp_order_id=None,
        opened_at_ts=int(time.time() * 1000)
    )
    handler.gateway.get_open_position = AsyncMock(return_value=mock_pos)
    handler.gateway.get_current_price = AsyncMock(return_value=76000.0)
    handler.live_repo.get_daily_pnl.return_value = (100.0, 1.0)

    await handler._cmd_status(12345)

    msg = handler._send.call_args[0][1]
    assert "SHORT" in msg
    assert "75,000.00" in msg # Entry from live pos
    assert "76,000.00" in msg # Price from live fetch
