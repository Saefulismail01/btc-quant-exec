
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from app.use_cases.telegram_command_handler import TelegramCommandHandler
# Use correct imports if needed, but MagicMock(spec=...) usually works
# from app.schemas.signal import SignalResponse, Confluence, ConfluenceLayers, LayerStatus, TradePlan, TrendInfo, Volatility

@pytest.mark.asyncio
async def test_cmd_signal_caching():
    """Verify /signal command can handle both cached and non-cached signals."""
    handler = TelegramCommandHandler()
    handler._send = AsyncMock()

    # Case 1: No cached signal
    with patch("app.use_cases.telegram_command_handler.get_cached_signal", return_value=None):
        await handler._cmd_signal(123)
        handler._send.assert_called()
        args = handler._send.call_args[0][1]
        assert "Belum ada sinyal" in args

    # Case 2: Signal in cache
    mock_signal = MagicMock()
    mock_signal.trade_plan.status = "ACTIVE"
    mock_signal.trade_plan.sl_price = 60000.0
    mock_signal.trade_plan.tp_price = 70000.0
    mock_signal.trade_plan.leverage = 5
    
    mock_signal.trend.action = "LONG"
    
    mock_signal.confluence.verdict = "STRONG BUY"
    mock_signal.confluence.conviction_pct = 85.5
    
    mock_signal.confluence.layers.l1.aligned = True
    mock_signal.confluence.layers.l1.label = "Bullish"
    mock_signal.confluence.layers.l2.aligned = True
    mock_signal.confluence.layers.l2.label = "Trend Bull"
    mock_signal.confluence.layers.l3.aligned = True
    mock_signal.confluence.layers.l3.label = "BULL"
    
    mock_signal.volatility.label = "Low"

    with patch("app.use_cases.telegram_command_handler.get_cached_signal", return_value=mock_signal):
        await handler._cmd_signal(123)
        args = handler._send.call_args[0][1]
        assert "L1 BCD : Bullish" in args
        assert "L2 EMA : Trend Bull" in args
        assert "85.5%" in args
        assert "ACTIVE" in args

@pytest.mark.asyncio
async def test_cmd_balance_logic():
    """Verify /balance calls the gateway correctly."""
    handler = TelegramCommandHandler()
    handler._send = AsyncMock()
    handler.gateway.get_account_balance = AsyncMock(return_value=1234.56)
    handler.gateway.execution_mode = "mainnet"

    await handler._cmd_balance(123)
    
    args = handler._send.call_args[0][1]
    assert "1,234.56 USDC" in args
    assert "MAINNET" in args

@pytest.mark.asyncio
async def test_cmd_help_version():
    """Verify help shows updated version v4.6."""
    handler = TelegramCommandHandler()
    handler._send = AsyncMock()
    
    await handler._cmd_help(123)
    args = handler._send.call_args[0][1]
    assert "BTC-QUANT LIVE v4.6" in args
    assert "/signal" in args
    assert "/balance" in args
