"""
Unit tests for FixedStrategy — Golden v4.4.

Tests cover:
- LONG/SHORT trade parameter calculation
- SL/TP price direction correctness
- Leverage and margin values
- TradeParams fields
"""

import pytest
from app.use_cases.strategies.fixed_strategy import FixedStrategy, SL_PCT, TP_PCT, LEVERAGE, MARGIN_USD


@pytest.fixture
def strategy():
    return FixedStrategy()


class TestFixedStrategyLong:
    """Tests for LONG trade calculations."""

    def test_long_sl_below_entry(self, strategy):
        params = strategy.calculate(84000.0, "LONG", {})
        assert params.sl_price < 84000.0

    def test_long_tp_above_entry(self, strategy):
        params = strategy.calculate(84000.0, "LONG", {})
        assert params.tp_price > 84000.0

    def test_long_sl_price_correct(self, strategy):
        entry = 84000.0
        params = strategy.calculate(entry, "LONG", {})
        expected_sl = round(entry * (1 - SL_PCT / 100), 2)
        assert params.sl_price == expected_sl

    def test_long_tp_price_correct(self, strategy):
        entry = 84000.0
        params = strategy.calculate(entry, "LONG", {})
        expected_tp = round(entry * (1 + TP_PCT / 100), 2)
        assert params.tp_price == expected_tp

    def test_long_sl_pct(self, strategy):
        params = strategy.calculate(84000.0, "LONG", {})
        assert params.sl_pct == SL_PCT

    def test_long_tp_pct(self, strategy):
        params = strategy.calculate(84000.0, "LONG", {})
        assert params.tp_pct == TP_PCT


class TestFixedStrategyShort:
    """Tests for SHORT trade calculations."""

    def test_short_sl_above_entry(self, strategy):
        params = strategy.calculate(84000.0, "SHORT", {})
        assert params.sl_price > 84000.0

    def test_short_tp_below_entry(self, strategy):
        params = strategy.calculate(84000.0, "SHORT", {})
        assert params.tp_price < 84000.0

    def test_short_sl_price_correct(self, strategy):
        entry = 84000.0
        params = strategy.calculate(entry, "SHORT", {})
        expected_sl = round(entry * (1 + SL_PCT / 100), 2)
        assert params.sl_price == expected_sl

    def test_short_tp_price_correct(self, strategy):
        entry = 84000.0
        params = strategy.calculate(entry, "SHORT", {})
        expected_tp = round(entry * (1 - TP_PCT / 100), 2)
        assert params.tp_price == expected_tp


class TestFixedStrategyParams:
    """Tests for fixed parameter values."""

    def test_leverage(self, strategy):
        params = strategy.calculate(84000.0, "LONG", {})
        assert params.leverage == LEVERAGE

    def test_margin_usd(self, strategy):
        params = strategy.calculate(84000.0, "LONG", {})
        assert params.margin_usd == MARGIN_USD

    def test_strategy_name(self, strategy):
        params = strategy.calculate(84000.0, "LONG", {})
        assert "FixedStrategy" in params.strategy_name

    def test_rationale_not_empty(self, strategy):
        params = strategy.calculate(84000.0, "LONG", {})
        assert len(params.rationale) > 0

    def test_signal_data_ignored(self, strategy):
        """FixedStrategy should ignore signal_data content."""
        params1 = strategy.calculate(84000.0, "LONG", {})
        params2 = strategy.calculate(84000.0, "LONG", {"some": "data", "atr": 9999})
        assert params1.sl_price == params2.sl_price
        assert params1.tp_price == params2.tp_price

    def test_various_entry_prices(self, strategy):
        """Test with various BTC price levels."""
        for entry in [30000.0, 50000.0, 84000.0, 100000.0]:
            params = strategy.calculate(entry, "LONG", {})
            assert params.sl_price < entry
            assert params.tp_price > entry
            assert params.leverage == LEVERAGE
            assert params.margin_usd == MARGIN_USD
