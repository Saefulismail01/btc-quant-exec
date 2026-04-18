"""
Unit tests for signal_executor.py

Covers:
1. parse_signal() — verdict/status mapping to action + margin
2. execute_trade() — order submission flow (entry, SL, TP)
3. execute_trade() — dry-run when TRADING_ENABLED=false
4. execute_trade() — slippage direction (LONG 1.02x, SHORT 0.98x)
5. execute_trade() — base_amount calculation from margin + leverage
6. execute_trade() — entry failure aborts SL/TP
7. run_cycle() — skips when position already open
8. run_cycle() — skips when no actionable signal
9. run_cycle() — calls execute_trade when signal is actionable
"""

import sys
import os
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

# ── Path setup: execution_layer/lighter/tests → root ─────────────────────────
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
_BACKEND = os.path.join(_ROOT, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ── Stub out `lighter` SDK before importing the module under test ──────────────
_lighter_stub = MagicMock()
_lighter_stub.Configuration = MagicMock()
_lighter_stub.ApiClient = MagicMock()
_lighter_stub.OrderApi = MagicMock()
_lighter_stub.AccountApi = MagicMock()
_lighter_stub.TransactionApi = MagicMock()
_lighter_stub.SignerClient = MagicMock()
_lighter_stub.SignerClient.ORDER_TYPE_STOP_LOSS_LIMIT = "STOP_LOSS_LIMIT"
_lighter_stub.SignerClient.ORDER_TYPE_TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"
_lighter_stub.SignerClient.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME = "GTT"
sys.modules["lighter"] = _lighter_stub

# Also stub out backend app imports that aren't needed for these tests
_signal_stub = MagicMock()
sys.modules.setdefault("app", MagicMock())
sys.modules.setdefault("app.use_cases", MagicMock())
sys.modules.setdefault("app.use_cases.signal_service", _signal_stub)

# Now import the module under test
import importlib
import execution_layer.lighter.signal_executor as executor_mod

# Re-export for convenience
parse_signal = executor_mod.parse_signal
execute_trade = executor_mod.execute_trade
run_cycle = executor_mod.run_cycle


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_signal(verdict: str, status: str = "ACTIVE", price: float = 70000.0, sl: float = None, tp: float = None):
    """Build a mock signal object matching the shape signal_service returns.
    
    For new FixedStrategy-based SL/TP calculation, provide 'price' as entry price.
    Legacy 'sl' and 'tp' parameters are kept for backward compatibility in some tests.
    """
    signal = MagicMock()
    signal.is_fallback = False
    signal.confluence.verdict = verdict
    signal.confluence.conviction_pct = 75.0
    # Handle price=None for negative tests
    if price is not None:
        signal.confluence.btc_price = price
        signal.price = price
    else:
        # For missing price test, don't set btc_price attribute
        del signal.confluence.btc_price
    signal.trade_plan.status = status
    signal.trade_plan.sl = sl or 0
    signal.trade_plan.tp1 = tp or 0
    return signal


# ─── parse_signal tests ───────────────────────────────────────────────────────

class TestParseSignal:

    def test_none_signal_returns_none(self):
        assert parse_signal(None) is None

    def test_fallback_signal_returns_none(self):
        s = make_signal("STRONG BUY")
        s.is_fallback = True
        assert parse_signal(s) is None

    def test_suspended_status_returns_none(self):
        s = make_signal("STRONG BUY", status="SUSPENDED")
        assert parse_signal(s) is None

    def test_neutral_verdict_returns_none(self):
        s = make_signal("NEUTRAL")
        assert parse_signal(s) is None

    def test_strong_buy_maps_to_long_with_100_margin(self):
        s = make_signal("STRONG BUY", price=70000.0)
        result = parse_signal(s)
        assert result is not None
        assert result["action"] == "LONG"
        assert result["margin"] == 100.0  # $100 for all signals

    def test_strong_sell_maps_to_short_with_100_margin(self):
        s = make_signal("STRONG SELL", price=70000.0)
        result = parse_signal(s)
        assert result is not None
        assert result["action"] == "SHORT"
        assert result["margin"] == 100.0  # $100 for all signals

    def test_weak_buy_maps_to_long_with_100_margin(self):
        """WEAK signals also use $100 margin (simplified config)"""
        s = make_signal("WEAK BUY", price=70000.0)
        result = parse_signal(s)
        assert result is not None
        assert result["action"] == "LONG"
        assert result["margin"] == 100.0  # Same as STRONG

    def test_weak_sell_maps_to_short_with_100_margin(self):
        """WEAK signals also use $100 margin (simplified config)"""
        s = make_signal("WEAK SELL", price=70000.0)
        result = parse_signal(s)
        assert result is not None
        assert result["action"] == "SHORT"
        assert result["margin"] == 100.0  # Same as STRONG

    def test_sl_tp_calculated_from_fixed_strategy_pct(self):
        """SL/TP calculated from entry price using FixedStrategy v4.4 percentages"""
        entry_price = 70000.0
        s = make_signal("STRONG BUY", price=entry_price)
        result = parse_signal(s)
        assert result is not None
        # LONG: SL = price * (1 - 1.333%), TP = price * (1 + 0.71%)
        expected_sl = entry_price * (1 - 1.333 / 100)
        expected_tp = entry_price * (1 + 0.71 / 100)
        assert abs(result["sl"] - expected_sl) < 0.01
        assert abs(result["tp"] - expected_tp) < 0.01

    def test_sl_tp_calculated_correctly_for_short(self):
        """SHORT: SL above entry, TP below entry"""
        entry_price = 70000.0
        s = make_signal("STRONG SELL", price=entry_price)
        result = parse_signal(s)
        assert result is not None
        # SHORT: SL = price * (1 + 1.333%), TP = price * (1 - 0.71%)
        expected_sl = entry_price * (1 + 1.333 / 100)
        expected_tp = entry_price * (1 - 0.71 / 100)
        assert abs(result["sl"] - expected_sl) < 0.01
        assert abs(result["tp"] - expected_tp) < 0.01

    def test_invalid_price_returns_none(self):
        """Invalid price (0 or negative) should return None"""
        s = make_signal("STRONG BUY", price=0.0)
        assert parse_signal(s) is None

    def test_negative_price_returns_none(self):
        """Negative price should return None"""
        s = make_signal("STRONG BUY", price=-100.0)
        assert parse_signal(s) is None

    def test_missing_price_returns_none(self):
        """Missing price should return None"""
        s = make_signal("STRONG BUY", price=None)
        assert parse_signal(s) is None

    def test_margin_usd_is_100(self):
        """All signals use $100 margin (FixedStrategy v4.4)"""
        assert executor_mod.MARGIN_USD == 100.0

    def test_leverage_is_5(self):
        """Leverage is 5x (FixedStrategy v4.4)"""
        assert executor_mod.LEVERAGE == 5

    def test_sl_pct_is_1_333(self):
        """SL is 1.333% (FixedStrategy v4.4)"""
        assert executor_mod.SL_PCT == 1.333

    def test_tp_pct_is_0_71(self):
        """TP is 0.71% (FixedStrategy v4.4)"""
        assert executor_mod.TP_PCT == 0.71


# ─── execute_trade tests ──────────────────────────────────────────────────────

class TestExecuteTrade:
    """Test execute_trade() with mocked lighter SDK calls."""

    def _make_signer_client(self, entry_err=None, sl_err=None, tp_err=None):
        """Build a mock SignerClient with configurable errors."""
        entry_resp = MagicMock()
        entry_resp.tx_hash = "tx_entry_001"
        mock_client = MagicMock()
        mock_client.create_market_order = AsyncMock(
            return_value=(MagicMock(), entry_resp, entry_err)
        )
        mock_client.create_order = AsyncMock(side_effect=[
            (MagicMock(), MagicMock(), sl_err),   # first call = SL
            (MagicMock(), MagicMock(), tp_err),   # second call = TP
        ])
        mock_client.close = AsyncMock()
        return mock_client

    def _patch_dependencies(self, price=84000.0, nonce=42, mock_client=None):
        """Patch all external calls used by execute_trade."""
        patches = [
            patch.object(executor_mod, "get_current_price", new=AsyncMock(return_value=price)),
            patch.object(executor_mod, "get_nonce", new=AsyncMock(return_value=nonce)),
            patch.object(executor_mod, "get_open_position", new=AsyncMock(return_value=None)),
            patch("time.sleep"),  # don't actually sleep
        ]
        if mock_client is not None:
            # Patch lighter.SignerClient to return our mock
            _lighter_stub.SignerClient.return_value = mock_client
        return patches

    @pytest.mark.asyncio
    async def test_dry_run_returns_false_when_trading_disabled(self):
        original = executor_mod.TRADING_ENABLED
        executor_mod.TRADING_ENABLED = False
        try:
            result = await execute_trade("LONG", 15.0, 80000.0, 90000.0)
            assert result is False
        finally:
            executor_mod.TRADING_ENABLED = original

    @pytest.mark.asyncio
    async def test_entry_order_placed_with_correct_side_long(self):
        mock_client = self._make_signer_client()
        patches = self._patch_dependencies(price=84000.0, mock_client=mock_client)
        executor_mod.TRADING_ENABLED = True

        try:
            for p in patches:
                p.start()

            await execute_trade("LONG", 15.0, 80000.0, 90000.0)

            call_kwargs = mock_client.create_market_order.call_args.kwargs
            assert call_kwargs["is_ask"] is False  # LONG = BUY = not ask
        finally:
            executor_mod.TRADING_ENABLED = False
            for p in patches:
                p.stop()

    @pytest.mark.asyncio
    async def test_entry_order_placed_with_correct_side_short(self):
        mock_client = self._make_signer_client()
        patches = self._patch_dependencies(price=84000.0, mock_client=mock_client)
        executor_mod.TRADING_ENABLED = True

        try:
            for p in patches:
                p.start()

            await execute_trade("SHORT", 15.0, 90000.0, 80000.0)

            call_kwargs = mock_client.create_market_order.call_args.kwargs
            assert call_kwargs["is_ask"] is True  # SHORT = SELL = ask
        finally:
            executor_mod.TRADING_ENABLED = False
            for p in patches:
                p.stop()

    @pytest.mark.asyncio
    async def test_slippage_direction_long_uses_higher_price(self):
        """LONG entry: avg_execution_price must be > price_scaled (1.02x)."""
        mock_client = self._make_signer_client()
        patches = self._patch_dependencies(price=84000.0, mock_client=mock_client)
        executor_mod.TRADING_ENABLED = True

        try:
            for p in patches:
                p.start()

            await execute_trade("LONG", 15.0, 80000.0, 90000.0)

            call_kwargs = mock_client.create_market_order.call_args.kwargs
            price_scaled = int(84000.0 * 10)  # price_decimals=1
            assert call_kwargs["avg_execution_price"] > price_scaled
            assert call_kwargs["avg_execution_price"] == int(price_scaled * 1.02)
        finally:
            executor_mod.TRADING_ENABLED = False
            for p in patches:
                p.stop()

    @pytest.mark.asyncio
    async def test_slippage_direction_short_uses_lower_price(self):
        """SHORT entry: avg_execution_price must be < price_scaled (0.98x)."""
        mock_client = self._make_signer_client()
        patches = self._patch_dependencies(price=84000.0, mock_client=mock_client)
        executor_mod.TRADING_ENABLED = True

        try:
            for p in patches:
                p.start()

            await execute_trade("SHORT", 15.0, 90000.0, 80000.0)

            call_kwargs = mock_client.create_market_order.call_args.kwargs
            price_scaled = int(84000.0 * 10)
            assert call_kwargs["avg_execution_price"] < price_scaled
            assert call_kwargs["avg_execution_price"] == int(price_scaled * 0.98)
        finally:
            executor_mod.TRADING_ENABLED = False
            for p in patches:
                p.stop()

    @pytest.mark.asyncio
    async def test_base_amount_calculation_100_margin_5x_leverage(self):
        """$100 margin × 5x leverage / $84000 × 1e5 = 595 base_amount."""
        mock_client = self._make_signer_client()
        patches = self._patch_dependencies(price=84000.0, mock_client=mock_client)
        executor_mod.TRADING_ENABLED = True

        try:
            for p in patches:
                p.start()

            await execute_trade("LONG", 100.0, 80000.0, 90000.0)

            call_kwargs = mock_client.create_market_order.call_args.kwargs
            # $100 * 5x = $500 notional / $84000 = 0.00595 BTC * 1e5 = 595
            expected = int(100.0 * 5 / 84000.0 * 1e5)
            assert call_kwargs["base_amount"] == expected
        finally:
            executor_mod.TRADING_ENABLED = False
            for p in patches:
                p.stop()

    @pytest.mark.asyncio
    async def test_entry_failure_aborts_sl_tp(self):
        """If entry order fails, SL and TP must NOT be submitted."""
        mock_client = self._make_signer_client(entry_err="nonce mismatch")
        patches = self._patch_dependencies(price=84000.0, mock_client=mock_client)
        executor_mod.TRADING_ENABLED = True

        try:
            for p in patches:
                p.start()

            result = await execute_trade("LONG", 15.0, 80000.0, 90000.0)

            assert result is False
            mock_client.create_order.assert_not_called()
        finally:
            executor_mod.TRADING_ENABLED = False
            for p in patches:
                p.stop()

    @pytest.mark.asyncio
    async def test_sl_order_uses_stop_loss_limit_type(self):
        mock_client = self._make_signer_client()
        patches = self._patch_dependencies(price=84000.0, mock_client=mock_client)
        executor_mod.TRADING_ENABLED = True

        try:
            for p in patches:
                p.start()

            await execute_trade("LONG", 15.0, 80000.0, 90000.0)

            sl_call_kwargs = mock_client.create_order.call_args_list[0].kwargs
            assert sl_call_kwargs["order_type"] == "STOP_LOSS_LIMIT"
        finally:
            executor_mod.TRADING_ENABLED = False
            for p in patches:
                p.stop()

    @pytest.mark.asyncio
    async def test_tp_order_uses_take_profit_limit_type(self):
        mock_client = self._make_signer_client()
        patches = self._patch_dependencies(price=84000.0, mock_client=mock_client)
        executor_mod.TRADING_ENABLED = True

        try:
            for p in patches:
                p.start()

            await execute_trade("LONG", 15.0, 80000.0, 90000.0)

            tp_call_kwargs = mock_client.create_order.call_args_list[1].kwargs
            assert tp_call_kwargs["order_type"] == "TAKE_PROFIT_LIMIT"
        finally:
            executor_mod.TRADING_ENABLED = False
            for p in patches:
                p.stop()

    @pytest.mark.asyncio
    async def test_sl_tp_are_reduce_only(self):
        mock_client = self._make_signer_client()
        patches = self._patch_dependencies(price=84000.0, mock_client=mock_client)
        executor_mod.TRADING_ENABLED = True

        try:
            for p in patches:
                p.start()

            await execute_trade("LONG", 15.0, 80000.0, 90000.0)

            for order_call in mock_client.create_order.call_args_list:
                assert order_call.kwargs["reduce_only"] == 1
        finally:
            executor_mod.TRADING_ENABLED = False
            for p in patches:
                p.stop()

    @pytest.mark.asyncio
    async def test_sl_price_scaled_correctly(self):
        """SL price at $80000 should be scaled to 80000 * 10 = 800000."""
        mock_client = self._make_signer_client()
        patches = self._patch_dependencies(price=84000.0, mock_client=mock_client)
        executor_mod.TRADING_ENABLED = True

        try:
            for p in patches:
                p.start()

            await execute_trade("LONG", 15.0, 80000.0, 90000.0)

            sl_call_kwargs = mock_client.create_order.call_args_list[0].kwargs
            assert sl_call_kwargs["price"] == int(80000.0 * 10)
            assert sl_call_kwargs["trigger_price"] == int(80000.0 * 10)
        finally:
            executor_mod.TRADING_ENABLED = False
            for p in patches:
                p.stop()

    @pytest.mark.asyncio
    async def test_tp_price_scaled_correctly(self):
        """TP price at $90000 should be scaled to 90000 * 10 = 900000."""
        mock_client = self._make_signer_client()
        patches = self._patch_dependencies(price=84000.0, mock_client=mock_client)
        executor_mod.TRADING_ENABLED = True

        try:
            for p in patches:
                p.start()

            await execute_trade("LONG", 15.0, 80000.0, 90000.0)

            tp_call_kwargs = mock_client.create_order.call_args_list[1].kwargs
            assert tp_call_kwargs["price"] == int(90000.0 * 10)
            assert tp_call_kwargs["trigger_price"] == int(90000.0 * 10)
        finally:
            executor_mod.TRADING_ENABLED = False
            for p in patches:
                p.stop()

    @pytest.mark.asyncio
    async def test_sl_closes_long_with_sell(self):
        """SL for LONG position must be SELL side (is_ask=True)."""
        mock_client = self._make_signer_client()
        patches = self._patch_dependencies(price=84000.0, mock_client=mock_client)
        executor_mod.TRADING_ENABLED = True

        try:
            for p in patches:
                p.start()

            await execute_trade("LONG", 15.0, 80000.0, 90000.0)

            sl_call_kwargs = mock_client.create_order.call_args_list[0].kwargs
            assert sl_call_kwargs["is_ask"] is True  # LONG SL = SELL
        finally:
            executor_mod.TRADING_ENABLED = False
            for p in patches:
                p.stop()

    @pytest.mark.asyncio
    async def test_sl_closes_short_with_buy(self):
        """SL for SHORT position must be BUY side (is_ask=False)."""
        mock_client = self._make_signer_client()
        patches = self._patch_dependencies(price=84000.0, mock_client=mock_client)
        executor_mod.TRADING_ENABLED = True

        try:
            for p in patches:
                p.start()

            await execute_trade("SHORT", 15.0, 90000.0, 80000.0)

            sl_call_kwargs = mock_client.create_order.call_args_list[0].kwargs
            assert sl_call_kwargs["is_ask"] is False  # SHORT SL = BUY
        finally:
            executor_mod.TRADING_ENABLED = False
            for p in patches:
                p.stop()

    @pytest.mark.asyncio
    async def test_nonce_increments_across_orders(self):
        """Each order must use a different nonce (entry, entry+1, entry+2)."""
        mock_client = self._make_signer_client()
        patches = self._patch_dependencies(price=84000.0, nonce=100, mock_client=mock_client)
        executor_mod.TRADING_ENABLED = True

        try:
            for p in patches:
                p.start()

            await execute_trade("LONG", 15.0, 80000.0, 90000.0)

            entry_nonce = mock_client.create_market_order.call_args.kwargs["nonce"]
            sl_nonce = mock_client.create_order.call_args_list[0].kwargs["nonce"]
            tp_nonce = mock_client.create_order.call_args_list[1].kwargs["nonce"]

            assert entry_nonce == 100
            assert sl_nonce == 101
            assert tp_nonce == 102
        finally:
            executor_mod.TRADING_ENABLED = False
            for p in patches:
                p.stop()

    @pytest.mark.asyncio
    async def test_client_close_called_on_success(self):
        """SignerClient.close() must be called even on success."""
        mock_client = self._make_signer_client()
        patches = self._patch_dependencies(price=84000.0, mock_client=mock_client)
        executor_mod.TRADING_ENABLED = True

        try:
            for p in patches:
                p.start()

            await execute_trade("LONG", 15.0, 80000.0, 90000.0)

            mock_client.close.assert_called_once()
        finally:
            executor_mod.TRADING_ENABLED = False
            for p in patches:
                p.stop()

    @pytest.mark.asyncio
    async def test_client_close_called_on_entry_failure(self):
        """SignerClient.close() must be called even when entry fails."""
        mock_client = self._make_signer_client(entry_err="bad nonce")
        patches = self._patch_dependencies(price=84000.0, mock_client=mock_client)
        executor_mod.TRADING_ENABLED = True

        try:
            for p in patches:
                p.start()

            await execute_trade("LONG", 15.0, 80000.0, 90000.0)

            mock_client.close.assert_called_once()
        finally:
            executor_mod.TRADING_ENABLED = False
            for p in patches:
                p.stop()

    @pytest.mark.asyncio
    async def test_returns_true_on_successful_entry(self):
        mock_client = self._make_signer_client()
        patches = self._patch_dependencies(price=84000.0, mock_client=mock_client)
        executor_mod.TRADING_ENABLED = True

        try:
            for p in patches:
                p.start()

            result = await execute_trade("LONG", 15.0, 80000.0, 90000.0)
            assert result is True
        finally:
            executor_mod.TRADING_ENABLED = False
            for p in patches:
                p.stop()


# ─── run_cycle tests ──────────────────────────────────────────────────────────

class TestRunCycle:

    def _make_signal(self, verdict="STRONG BUY"):
        return make_signal(verdict)

    def _signal_dict(self, verdict="STRONG BUY", price=70000.0):
        """Build SimpleNamespace response from API (matching actual signal shape)."""
        from types import SimpleNamespace
        return SimpleNamespace(
            is_fallback=False,
            confluence=SimpleNamespace(
                verdict=verdict,
                conviction_pct=75.0,
                btc_price=price  # For SL/TP calculation
            ),
            trade_plan=SimpleNamespace(status="ACTIVE"),
            price=price
        )

    @pytest.mark.asyncio
    async def test_skips_when_position_already_open(self):
        pos = {"side": "LONG", "size": 0.003, "entry": 84000.0, "pnl": 0.5, "tied_orders": 2}
        with patch.object(executor_mod, "get_open_position", new=AsyncMock(return_value=pos)), \
             patch.object(executor_mod, "get_signal_from_api", new=AsyncMock(return_value=self._signal_dict())), \
             patch.object(executor_mod, "execute_trade", new=AsyncMock()) as mock_exec:

            await run_cycle()

            mock_exec.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_signal_is_none(self):
        with patch.object(executor_mod, "get_open_position", new=AsyncMock(return_value=None)), \
             patch.object(executor_mod, "get_signal_from_api", new=AsyncMock(return_value=None)), \
             patch.object(executor_mod, "execute_trade", new=AsyncMock()) as mock_exec:

            await run_cycle()

            mock_exec.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_neutral_signal(self):
        with patch.object(executor_mod, "get_open_position", new=AsyncMock(return_value=None)), \
             patch.object(executor_mod, "get_signal_from_api", new=AsyncMock(return_value=self._signal_dict("NEUTRAL"))), \
             patch.object(executor_mod, "execute_trade", new=AsyncMock()) as mock_exec:

            await run_cycle()

            mock_exec.assert_not_called()

    @pytest.mark.asyncio
    async def test_sl_tp_calculated_from_fixed_strategy_in_run_cycle(self):
        """SL/TP dihitung otomatis dari FixedStrategy v4.4 percentages"""
        mock_execute = AsyncMock(return_value=True)
        entry_price = 70000.0
        with patch.object(executor_mod, "get_open_position", new=AsyncMock(return_value=None)), \
             patch.object(executor_mod, "get_signal_from_api", new=AsyncMock(return_value=self._signal_dict("STRONG BUY", price=entry_price))), \
             patch.object(executor_mod, "execute_trade", new=mock_execute), \
             patch.object(executor_mod, "get_balance", new=AsyncMock(return_value=100.0)):

            await run_cycle()

            mock_execute.assert_called_once()
            call_kwargs = mock_execute.call_args.kwargs
            # LONG: SL should be below entry, TP above entry
            assert call_kwargs["sl_price"] < entry_price  # SL = entry * (1 - 1.333%)
            assert call_kwargs["tp_price"] > entry_price  # TP = entry * (1 + 0.71%)

    @pytest.mark.asyncio
    async def test_executes_on_strong_buy_with_100_margin(self):
        """STRONG BUY uses $100 margin with 5x leverage"""
        mock_execute = AsyncMock(return_value=True)
        with patch.object(executor_mod, "get_open_position", new=AsyncMock(return_value=None)), \
             patch.object(executor_mod, "get_signal_from_api", new=AsyncMock(return_value=self._signal_dict("STRONG BUY"))), \
             patch.object(executor_mod, "execute_trade", new=mock_execute), \
             patch.object(executor_mod, "get_balance", new=AsyncMock(return_value=100.0)):

            await run_cycle()

            mock_execute.assert_called_once()
            call_kwargs = mock_execute.call_args.kwargs
            assert call_kwargs["action"] == "LONG"
            assert call_kwargs["margin"] == 100.0  # $100 for all signals

    @pytest.mark.asyncio
    async def test_executes_on_strong_sell_with_100_margin(self):
        """STRONG SELL uses $100 margin with 5x leverage"""
        mock_execute = AsyncMock(return_value=True)
        with patch.object(executor_mod, "get_open_position", new=AsyncMock(return_value=None)), \
             patch.object(executor_mod, "get_signal_from_api", new=AsyncMock(return_value=self._signal_dict("STRONG SELL"))), \
             patch.object(executor_mod, "execute_trade", new=mock_execute), \
             patch.object(executor_mod, "get_balance", new=AsyncMock(return_value=100.0)):

            await run_cycle()

            mock_execute.assert_called_once()
            call_kwargs = mock_execute.call_args.kwargs
            assert call_kwargs["action"] == "SHORT"
            assert call_kwargs["margin"] == 100.0  # $100 for all signals

    @pytest.mark.asyncio
    async def test_executes_on_weak_buy_with_100_margin(self):
        """WEAK BUY also uses $100 margin (simplified config)"""
        mock_execute = AsyncMock(return_value=True)
        with patch.object(executor_mod, "get_open_position", new=AsyncMock(return_value=None)), \
             patch.object(executor_mod, "get_signal_from_api", new=AsyncMock(return_value=self._signal_dict("WEAK BUY"))), \
             patch.object(executor_mod, "execute_trade", new=mock_execute), \
             patch.object(executor_mod, "get_balance", new=AsyncMock(return_value=100.0)):

            await run_cycle()

            mock_execute.assert_called_once()
            call_kwargs = mock_execute.call_args.kwargs
            assert call_kwargs["margin"] == 100.0  # Same as STRONG

    @pytest.mark.asyncio
    async def test_sl_tp_passed_from_signal_trade_plan(self):
        mock_execute = AsyncMock(return_value=True)
        with patch.object(executor_mod, "get_open_position", new=AsyncMock(return_value=None)), \
             patch.object(executor_mod, "get_signal_from_api", new=AsyncMock(return_value=self._signal_dict("STRONG BUY", sl=78500.0, tp=95000.0))), \
             patch.object(executor_mod, "execute_trade", new=mock_execute), \
             patch.object(executor_mod, "get_balance", new=AsyncMock(return_value=100.0)):

            await run_cycle()

            call_kwargs = mock_execute.call_args.kwargs
            assert call_kwargs["sl_price"] == 78500.0
            assert call_kwargs["tp_price"] == 95000.0

    @pytest.mark.asyncio
    async def test_position_check_error_aborts_cycle(self):
        mock_execute = AsyncMock(return_value=True)
        with patch.object(executor_mod, "get_open_position", new=AsyncMock(side_effect=Exception("network error"))), \
             patch.object(executor_mod, "execute_trade", new=mock_execute):

            await run_cycle()  # should not raise

            mock_execute.assert_not_called()
