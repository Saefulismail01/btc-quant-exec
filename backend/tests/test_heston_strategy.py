"""
Unit tests for HestonStrategy — ATR-based SL/TP.

Tests cover:
- LONG/SHORT price direction correctness
- ATR × multiplier calculation
- Fallback to FixedStrategy when sl_tp_preset missing
- ATR fallback when ATR=0
"""

import pytest
from app.use_cases.strategies.heston_strategy import HestonStrategy, LEVERAGE, MARGIN_USD
from app.use_cases.strategies.fixed_strategy import SL_PCT, TP_PCT


ENTRY = 84000.0
SIGNAL_WITH_PRESET = {
    "sl_tp_preset": {
        "sl_multiplier": 1.5,
        "tp1_multiplier": 1.0,
        "preset_name": "Normal",
        "rationale": "Normal vol regime",
    },
    "price": {"atr14": 1200.0},
}

SIGNAL_NO_PRESET = {
    "price": {"atr14": 1200.0},
}

SIGNAL_PRESET_ZERO_ATR = {
    "sl_tp_preset": {
        "sl_multiplier": 1.5,
        "tp1_multiplier": 1.0,
        "preset_name": "Normal",
    },
    "price": {"atr14": 0.0},
}


@pytest.fixture
def strategy():
    return HestonStrategy()


class TestHestonStrategyLong:
    """Tests for LONG trade with preset."""

    def test_long_sl_below_entry(self, strategy):
        params = strategy.calculate(ENTRY, "LONG", SIGNAL_WITH_PRESET)
        assert params.sl_price < ENTRY

    def test_long_tp_above_entry(self, strategy):
        params = strategy.calculate(ENTRY, "LONG", SIGNAL_WITH_PRESET)
        assert params.tp_price > ENTRY

    def test_long_sl_price_correct(self, strategy):
        atr = 1200.0
        sl_mult = 1.5
        expected_sl = round(ENTRY - atr * sl_mult, 2)
        params = strategy.calculate(ENTRY, "LONG", SIGNAL_WITH_PRESET)
        assert params.sl_price == expected_sl

    def test_long_tp_price_correct(self, strategy):
        atr = 1200.0
        tp_mult = 1.0
        expected_tp = round(ENTRY + atr * tp_mult, 2)
        params = strategy.calculate(ENTRY, "LONG", SIGNAL_WITH_PRESET)
        assert params.tp_price == expected_tp


class TestHestonStrategyShort:
    """Tests for SHORT trade with preset."""

    def test_short_sl_above_entry(self, strategy):
        params = strategy.calculate(ENTRY, "SHORT", SIGNAL_WITH_PRESET)
        assert params.sl_price > ENTRY

    def test_short_tp_below_entry(self, strategy):
        params = strategy.calculate(ENTRY, "SHORT", SIGNAL_WITH_PRESET)
        assert params.tp_price < ENTRY

    def test_short_sl_price_correct(self, strategy):
        atr = 1200.0
        sl_mult = 1.5
        expected_sl = round(ENTRY + atr * sl_mult, 2)
        params = strategy.calculate(ENTRY, "SHORT", SIGNAL_WITH_PRESET)
        assert params.sl_price == expected_sl

    def test_short_tp_price_correct(self, strategy):
        atr = 1200.0
        tp_mult = 1.0
        expected_tp = round(ENTRY - atr * tp_mult, 2)
        params = strategy.calculate(ENTRY, "SHORT", SIGNAL_WITH_PRESET)
        assert params.tp_price == expected_tp


class TestHestonStrategyFallback:
    """Tests for fallback behavior when sl_tp_preset missing."""

    def test_fallback_when_no_preset(self, strategy):
        params = strategy.calculate(ENTRY, "LONG", SIGNAL_NO_PRESET)
        # Should use FixedStrategy values
        expected_sl = round(ENTRY * (1 - SL_PCT / 100), 2)
        assert params.sl_price == expected_sl

    def test_fallback_when_preset_none(self, strategy):
        params = strategy.calculate(ENTRY, "LONG", {"sl_tp_preset": None, "price": {}})
        expected_sl = round(ENTRY * (1 - SL_PCT / 100), 2)
        assert params.sl_price == expected_sl

    def test_fallback_when_empty_signal(self, strategy):
        params = strategy.calculate(ENTRY, "LONG", {})
        expected_sl = round(ENTRY * (1 - SL_PCT / 100), 2)
        assert params.sl_price == expected_sl

    def test_fallback_strategy_name_contains_fixed(self, strategy):
        params = strategy.calculate(ENTRY, "LONG", SIGNAL_NO_PRESET)
        assert "Fixed" in params.strategy_name


class TestHestonStrategyATRFallback:
    """Tests for ATR fallback when ATR=0."""

    def test_zero_atr_uses_fallback_value(self, strategy):
        """When ATR=0, should use _DEFAULT_ATR_FALLBACK."""
        from app.use_cases.strategies.heston_strategy import _DEFAULT_ATR_FALLBACK
        params = strategy.calculate(ENTRY, "LONG", SIGNAL_PRESET_ZERO_ATR)
        sl_mult = 1.5
        expected_sl = round(ENTRY - _DEFAULT_ATR_FALLBACK * sl_mult, 2)
        assert params.sl_price == expected_sl

    def test_missing_atr_key_uses_fallback(self, strategy):
        """When price.atr14 key missing entirely."""
        from app.use_cases.strategies.heston_strategy import _DEFAULT_ATR_FALLBACK
        signal = {
            "sl_tp_preset": {
                "sl_multiplier": 1.5,
                "tp1_multiplier": 1.0,
                "preset_name": "Normal",
            }
        }
        params = strategy.calculate(ENTRY, "LONG", signal)
        sl_mult = 1.5
        expected_sl = round(ENTRY - _DEFAULT_ATR_FALLBACK * sl_mult, 2)
        assert params.sl_price == expected_sl


class TestHestonStrategyParams:
    """Tests for fixed parameter values."""

    def test_leverage(self, strategy):
        params = strategy.calculate(ENTRY, "LONG", SIGNAL_WITH_PRESET)
        assert params.leverage == LEVERAGE

    def test_margin_usd(self, strategy):
        params = strategy.calculate(ENTRY, "LONG", SIGNAL_WITH_PRESET)
        assert params.margin_usd == MARGIN_USD

    def test_strategy_name_contains_heston(self, strategy):
        params = strategy.calculate(ENTRY, "LONG", SIGNAL_WITH_PRESET)
        assert "Heston" in params.strategy_name

    def test_strategy_name_contains_preset_name(self, strategy):
        params = strategy.calculate(ENTRY, "LONG", SIGNAL_WITH_PRESET)
        assert "Normal" in params.strategy_name

    def test_sl_pct_calculated(self, strategy):
        params = strategy.calculate(ENTRY, "LONG", SIGNAL_WITH_PRESET)
        atr = 1200.0
        sl_mult = 1.5
        expected_sl_pct = round((atr * sl_mult / ENTRY) * 100, 3)
        assert abs(params.sl_pct - expected_sl_pct) < 0.001
