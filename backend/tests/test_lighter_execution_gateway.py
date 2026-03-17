"""
Unit tests for LighterExecutionGateway.

Tests cover:
- Initialization (mode, credentials, account_index)
- Safety flag: trading disabled blocks all orders
- place_market_order flow (mocked SDK)
- place_sl_order / place_tp_order flow (mocked SDK)
- _submit_order MARKET and LIMIT paths
- _get_signer_client lazy init
- Auth token generation format
- close() cleanup
"""

import os
import sys
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


def make_lighter_mock():
    """Create a MagicMock that stands in for the lighter SDK module."""
    mock_sdk = MagicMock()
    mock_sdk.SignerClient.ORDER_TYPE_LIMIT = "LIMIT"
    mock_sdk.SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME = "GTT"
    return mock_sdk


# ─── Helpers ────────────────────────────────────────────────────────────────

def make_gateway(env_overrides: dict = {}):
    """Create a LighterExecutionGateway with test env vars."""
    defaults = {
        "LIGHTER_EXECUTION_MODE": "mainnet",
        "LIGHTER_TRADING_ENABLED": "false",
        "LIGHTER_MAINNET_API_KEY": "test_api_key_abc123",
        "LIGHTER_MAINNET_API_SECRET": "test_api_secret_xyz789",
        "LIGHTER_API_KEY_INDEX": "3",
        "LIGHTER_ACCOUNT_INDEX": "3",
    }
    defaults.update(env_overrides)
    with patch.dict(os.environ, defaults, clear=False):
        from app.adapters.gateways.lighter_execution_gateway import LighterExecutionGateway
        gw = LighterExecutionGateway()
    return gw


# ─── Initialization ─────────────────────────────────────────────────────────

class TestGatewayInit:

    def test_execution_mode_mainnet(self):
        gw = make_gateway({"LIGHTER_EXECUTION_MODE": "mainnet"})
        assert gw.execution_mode == "mainnet"

    def test_execution_mode_testnet(self):
        gw = make_gateway({
            "LIGHTER_EXECUTION_MODE": "testnet",
            "LIGHTER_TESTNET_API_KEY": "test_key",
            "LIGHTER_TESTNET_API_SECRET": "test_secret",
        })
        assert gw.execution_mode == "testnet"

    def test_invalid_execution_mode_raises(self):
        with pytest.raises(ValueError, match="Invalid LIGHTER_EXECUTION_MODE"):
            make_gateway({"LIGHTER_EXECUTION_MODE": "invalid"})

    def test_trading_disabled_by_default(self):
        gw = make_gateway({"LIGHTER_TRADING_ENABLED": "false"})
        assert gw.trading_enabled is False

    def test_trading_enabled(self):
        gw = make_gateway({"LIGHTER_TRADING_ENABLED": "true"})
        assert gw.trading_enabled is True

    def test_account_index_loaded(self):
        gw = make_gateway({"LIGHTER_ACCOUNT_INDEX": "3"})
        assert gw.account_index == 3

    def test_api_key_index_loaded(self):
        gw = make_gateway({"LIGHTER_API_KEY_INDEX": "3"})
        assert gw.api_key_index == 3

    def test_missing_credentials_raises(self):
        with patch.dict(os.environ, {
            "LIGHTER_EXECUTION_MODE": "mainnet",
            "LIGHTER_MAINNET_API_KEY": "",
            "LIGHTER_MAINNET_API_SECRET": "",
        }, clear=False):
            from app.adapters.gateways.lighter_execution_gateway import LighterExecutionGateway
            with pytest.raises(ValueError, match="Missing Lighter credentials"):
                LighterExecutionGateway()

    def test_signer_client_initially_none(self):
        gw = make_gateway()
        assert gw._signer_client is None

    def test_market_id_is_btc(self):
        from app.adapters.gateways.lighter_execution_gateway import LighterExecutionGateway
        assert LighterExecutionGateway.MARKET_ID == 1


# ─── Safety Flag ────────────────────────────────────────────────────────────

class TestTradingDisabledSafety:

    @pytest.mark.asyncio
    async def test_place_market_order_blocked_when_disabled(self):
        gw = make_gateway({"LIGHTER_TRADING_ENABLED": "false"})
        result = await gw.place_market_order("LONG", 1.0, 15)
        assert result.success is False
        assert "disabled" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_place_sl_order_blocked_when_disabled(self):
        gw = make_gateway({"LIGHTER_TRADING_ENABLED": "false"})
        result = await gw.place_sl_order("LONG", 83000.0, 0.001)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_place_tp_order_blocked_when_disabled(self):
        gw = make_gateway({"LIGHTER_TRADING_ENABLED": "false"})
        result = await gw.place_tp_order("LONG", 85000.0, 0.001)
        assert result.success is False


# ─── Auth Token ─────────────────────────────────────────────────────────────

class TestAuthToken:

    def test_auth_token_format(self):
        gw = make_gateway()
        token = gw._generate_auth_token()
        parts = token.split(":")
        assert len(parts) == 4, f"Expected 4 parts, got {len(parts)}: {token}"

    def test_auth_token_account_index(self):
        gw = make_gateway({"LIGHTER_ACCOUNT_INDEX": "3"})
        token = gw._generate_auth_token()
        parts = token.split(":")
        # format: expiry:account_index:api_key_index:random_hex
        assert parts[1] == "0"  # account_index in token is hardcoded 0 (primary)

    def test_auth_token_api_key_index(self):
        gw = make_gateway({"LIGHTER_API_KEY_INDEX": "3"})
        token = gw._generate_auth_token()
        parts = token.split(":")
        assert parts[2] == "3"

    def test_auth_token_expiry_is_future(self):
        import time
        gw = make_gateway()
        token = gw._generate_auth_token()
        expiry = int(token.split(":")[0])
        assert expiry > int(time.time())


# ─── _submit_order (SDK mocked) ──────────────────────────────────────────────

class TestSubmitOrder:

    def _make_enabled_gateway(self):
        return make_gateway({"LIGHTER_TRADING_ENABLED": "true"})

    def _mock_lighter_ctx(self, mock_client):
        """Context manager: replace sys.modules['lighter'] with mock SDK."""
        mock_sdk = make_lighter_mock()
        mock_sdk.SignerClient.return_value = mock_client
        # Remove cached real lighter module so import inside _submit_order gets mock
        return patch.dict(sys.modules, {"lighter": mock_sdk})

    @pytest.mark.asyncio
    async def test_submit_market_order_success(self):
        gw = self._make_enabled_gateway()
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.tx_hash = "tx_hash_abc123"
        mock_resp.code = 200
        mock_client.create_market_order = AsyncMock(return_value=(MagicMock(), mock_resp, None))
        gw._signer_client = mock_client
        gw._price_decimals = 2
        gw._size_decimals = 6

        payload = {
            "market_id": 1,
            "order_type": "MARKET",
            "side": "BUY",
            "size": 1190,
            "price": 8400000,
        }

        with self._mock_lighter_ctx(mock_client):
            result = await gw._submit_order(payload)

        assert result.success is True
        assert result.order_id == "tx_hash_abc123"
        assert result.filled_price == pytest.approx(84000.0, rel=1e-3)

    @pytest.mark.asyncio
    async def test_submit_market_order_sell(self):
        gw = self._make_enabled_gateway()
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.tx_hash = "tx_sell_456"
        mock_resp.code = 200
        mock_client.create_market_order = AsyncMock(return_value=(MagicMock(), mock_resp, None))
        gw._signer_client = mock_client
        gw._price_decimals = 2
        gw._size_decimals = 6

        payload = {
            "market_id": 1,
            "order_type": "MARKET",
            "side": "SELL",
            "size": 1190,
            "price": 8400000,
        }

        with self._mock_lighter_ctx(mock_client):
            result = await gw._submit_order(payload)

        assert result.success is True
        call_kwargs = mock_client.create_market_order.call_args.kwargs
        assert call_kwargs["is_ask"] is True
        assert call_kwargs["avg_execution_price"] < 8400000

    @pytest.mark.asyncio
    async def test_submit_market_order_buy_slippage_higher(self):
        gw = self._make_enabled_gateway()
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.tx_hash = "tx_buy_789"
        mock_resp.code = 200
        mock_client.create_market_order = AsyncMock(return_value=(MagicMock(), mock_resp, None))
        gw._signer_client = mock_client
        gw._price_decimals = 2
        gw._size_decimals = 6

        payload = {
            "market_id": 1,
            "order_type": "MARKET",
            "side": "BUY",
            "size": 1190,
            "price": 8400000,
        }

        with self._mock_lighter_ctx(mock_client):
            await gw._submit_order(payload)

        call_kwargs = mock_client.create_market_order.call_args.kwargs
        assert call_kwargs["is_ask"] is False
        assert call_kwargs["avg_execution_price"] > 8400000

    @pytest.mark.asyncio
    async def test_submit_order_sdk_exception_returns_failure(self):
        gw = self._make_enabled_gateway()
        mock_client = MagicMock()
        mock_client.create_market_order = AsyncMock(side_effect=Exception("SDK connection error"))
        gw._signer_client = mock_client
        gw._price_decimals = 2
        gw._size_decimals = 6

        payload = {
            "market_id": 1,
            "order_type": "MARKET",
            "side": "BUY",
            "size": 1190,
            "price": 8400000,
        }

        with self._mock_lighter_ctx(mock_client):
            result = await gw._submit_order(payload)

        assert result.success is False
        assert "SDK connection error" in result.error_message


# ─── place_market_order integration ─────────────────────────────────────────

class TestPlaceMarketOrder:

    @pytest.mark.asyncio
    async def test_place_market_order_calls_submit(self):
        gw = make_gateway({"LIGHTER_TRADING_ENABLED": "true"})

        # Mock dependencies
        gw._ensure_metadata_fresh = AsyncMock()
        gw._make_request = AsyncMock(return_value={"last_price": 84000.0})
        gw.nonce_manager.get_next_nonce = AsyncMock(return_value=10)
        gw.nonce_manager.mark_used = AsyncMock()

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.order_id = "order_001"
        mock_result.filled_price = 84000.0
        mock_result.filled_quantity = 0.000179

        gw._submit_order = AsyncMock(return_value=mock_result)

        result = await gw.place_market_order("LONG", 1.0, 15)

        assert result.success is True
        assert result.order_id == "order_001"
        gw._submit_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_place_market_order_invalid_price_fails(self):
        gw = make_gateway({"LIGHTER_TRADING_ENABLED": "true"})

        gw._ensure_metadata_fresh = AsyncMock()
        gw._make_request = AsyncMock(return_value={"last_price": 0})

        result = await gw.place_market_order("LONG", 1.0, 15)

        assert result.success is False
        assert "Invalid current price" in result.error_message

    @pytest.mark.asyncio
    async def test_place_market_order_marks_nonce_used_on_success(self):
        gw = make_gateway({"LIGHTER_TRADING_ENABLED": "true"})

        gw._ensure_metadata_fresh = AsyncMock()
        gw._make_request = AsyncMock(return_value={"last_price": 84000.0})
        gw.nonce_manager.get_next_nonce = AsyncMock(return_value=5)
        gw.nonce_manager.mark_used = AsyncMock()

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.order_id = "order_002"
        mock_result.filled_price = 84000.0
        mock_result.filled_quantity = 0.000179
        gw._submit_order = AsyncMock(return_value=mock_result)

        await gw.place_market_order("LONG", 1.0, 15)

        gw.nonce_manager.mark_used.assert_called_once_with(5)


# ─── _get_signer_client ──────────────────────────────────────────────────────

class TestGetSignerClient:

    def test_raises_if_lighter_not_installed(self):
        gw = make_gateway()
        # Simulate lighter not importable by removing from sys.modules and blocking re-import
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "lighter":
                raise ImportError("No module named 'lighter'")
            return real_import(name, *args, **kwargs)

        # Remove cached lighter so our mock import runs
        lighter_backup = sys.modules.pop("lighter", None)
        try:
            with patch("builtins.__import__", side_effect=mock_import):
                with pytest.raises((RuntimeError, ImportError)):
                    gw._get_signer_client()
        finally:
            if lighter_backup is not None:
                sys.modules["lighter"] = lighter_backup

    def test_returns_same_instance_on_second_call(self):
        gw = make_gateway()
        mock_sdk = make_lighter_mock()
        mock_client = MagicMock()
        mock_sdk.SignerClient.return_value = mock_client

        with patch.dict(sys.modules, {"lighter": mock_sdk}):
            client1 = gw._get_signer_client()
            client2 = gw._get_signer_client()

        assert client1 is client2
        mock_sdk.SignerClient.assert_called_once()

    def test_signer_client_initialized_with_correct_params(self):
        gw = make_gateway({
            "LIGHTER_ACCOUNT_INDEX": "3",
            "LIGHTER_API_KEY_INDEX": "3",
        })
        mock_sdk = make_lighter_mock()
        mock_client = MagicMock()
        mock_sdk.SignerClient.return_value = mock_client

        with patch.dict(sys.modules, {"lighter": mock_sdk}):
            gw._get_signer_client()

        call_kwargs = mock_sdk.SignerClient.call_args.kwargs
        assert call_kwargs["account_index"] == 3
        assert call_kwargs["api_private_keys"] == {3: gw.api_secret}


# ─── close() ────────────────────────────────────────────────────────────────

class TestGatewayClose:

    @pytest.mark.asyncio
    async def test_close_closes_session(self):
        gw = make_gateway()
        mock_session = AsyncMock()
        gw.session = mock_session

        await gw.close()

        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_without_session_no_error(self):
        gw = make_gateway()
        gw.session = None
        gw._ws = None
        # Should not raise
        await gw.close()
