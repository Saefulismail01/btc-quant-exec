"""
Unit tests for lighter_math.py — Integer Scaling Engine.

Tests cover:
- Float to int scaling conversions
- Int to float unscaling (round-trip)
- BTC quantity calculations
- Edge cases: zero, negative, NaN, inf
- Precision validation
"""

import pytest
import math
from app.utils.lighter_math import (
    scale_price,
    scale_size,
    unscale_price,
    unscale_size,
    calculate_btc_quantity,
    validate_scaled_values,
)


class TestScalePrice:
    """Tests for scale_price() function."""

    def test_scale_price_whole_number(self):
        """Test scaling a whole number price."""
        result = scale_price(45000.0, 2)
        assert result == 4500000

    def test_scale_price_decimal(self):
        """Test scaling a price with decimals."""
        result = scale_price(45000.25, 2)
        assert result == 4500025

    def test_scale_price_many_decimals(self):
        """Test scaling with many decimal places."""
        result = scale_price(0.123456, 6)
        assert result == 123456

    def test_scale_price_zero(self):
        """Test scaling zero price."""
        result = scale_price(0.0, 2)
        assert result == 0

    def test_scale_price_small(self):
        """Test scaling very small price."""
        result = scale_price(0.00001, 6)
        assert result == 10

    def test_scale_price_large(self):
        """Test scaling large price."""
        result = scale_price(100000.0, 2)
        assert result == 10000000

    def test_scale_price_negative_raises(self):
        """Test that negative price raises ValueError."""
        with pytest.raises(ValueError, match="must be non-negative"):
            scale_price(-100.0, 2)

    def test_scale_price_nan_raises(self):
        """Test that NaN raises ValueError."""
        with pytest.raises(ValueError, match="must be a finite number"):
            scale_price(float('nan'), 2)

    def test_scale_price_inf_raises(self):
        """Test that infinity raises ValueError."""
        with pytest.raises(ValueError, match="must be a finite number"):
            scale_price(float('inf'), 2)

    def test_scale_price_rounding(self):
        """Test that scaling uses proper rounding."""
        # 1.555 with 2 decimals should round to 156 (not 155)
        result = scale_price(1.555, 2)
        assert result == 156


class TestScaleSize:
    """Tests for scale_size() function."""

    def test_scale_size_whole_number(self):
        """Test scaling a whole number size."""
        result = scale_size(1.0, 6)
        assert result == 1000000

    def test_scale_size_fractional(self):
        """Test scaling a fractional BTC size."""
        result = scale_size(0.001, 6)
        assert result == 1000

    def test_scale_size_very_small(self):
        """Test scaling very small size."""
        result = scale_size(0.000001, 6)
        assert result == 1

    def test_scale_size_zero(self):
        """Test scaling zero size."""
        result = scale_size(0.0, 6)
        assert result == 0

    def test_scale_size_negative_raises(self):
        """Test that negative size raises ValueError."""
        with pytest.raises(ValueError, match="must be non-negative"):
            scale_size(-0.001, 6)

    def test_scale_size_nan_raises(self):
        """Test that NaN raises ValueError."""
        with pytest.raises(ValueError, match="must be a finite number"):
            scale_size(float('nan'), 6)


class TestUnscalePrice:
    """Tests for unscale_price() function."""

    def test_unscale_price_whole(self):
        """Test unscaling a whole number."""
        result = unscale_price(4500000, 2)
        assert result == 45000.0

    def test_unscale_price_decimal(self):
        """Test unscaling with decimals."""
        result = unscale_price(4500025, 2)
        assert result == 45000.25

    def test_unscale_price_zero(self):
        """Test unscaling zero."""
        result = unscale_price(0, 2)
        assert result == 0.0

    def test_unscale_price_negative_decimals_raises(self):
        """Test that negative decimals raises ValueError."""
        with pytest.raises(ValueError, match="must be non-negative"):
            unscale_price(100, -1)


class TestUnscaleSize:
    """Tests for unscale_size() function."""

    def test_unscale_size_whole(self):
        """Test unscaling a whole number."""
        result = unscale_size(1000000, 6)
        assert result == 1.0

    def test_unscale_size_fractional(self):
        """Test unscaling to fractional BTC."""
        result = unscale_size(1000, 6)
        assert result == 0.001

    def test_unscale_size_zero(self):
        """Test unscaling zero."""
        result = unscale_size(0, 6)
        assert result == 0.0


class TestRoundTrip:
    """Test round-trip scaling: float → int → float."""

    def test_roundtrip_price(self):
        """Test that price survives a round-trip conversion."""
        original_price = 45000.25
        scaled = scale_price(original_price, 2)
        unscaled = unscale_price(scaled, 2)
        assert unscaled == original_price

    def test_roundtrip_size(self):
        """Test that size survives a round-trip conversion."""
        original_size = 0.001234
        scaled = scale_size(original_size, 6)
        unscaled = unscale_size(scaled, 6)
        # Allow tiny floating-point error
        assert abs(unscaled - original_size) < 1e-8

    def test_roundtrip_multiple_precisions(self):
        """Test round-trip with various precisions."""
        test_cases = [
            (45000.5, 2),
            (0.001, 6),
            (1.23456789, 8),
            (100000.001, 3),
        ]

        for value, decimals in test_cases:
            scaled = scale_price(value, decimals)
            unscaled = unscale_price(scaled, decimals)
            assert abs(unscaled - value) < 1e-9


class TestCalculateBtcQuantity:
    """Tests for calculate_btc_quantity() function."""

    def test_calculate_btc_quantity_standard(self):
        """Test standard calculation: $1000 margin at $45k price."""
        quantity_float, quantity_scaled = calculate_btc_quantity(
            size_usdt=1000.0,
            price=45000.0,
            size_decimals=6
        )

        # 1000 / 45000 = 0.0222...
        expected_float = 1000.0 / 45000.0
        expected_scaled = int(round(expected_float * 1000000))

        assert abs(quantity_float - expected_float) < 1e-8
        assert quantity_scaled == expected_scaled

    def test_calculate_btc_quantity_with_leverage(self):
        """Test calculation with leverage (notional amount)."""
        # $1000 margin × 15x leverage = $15000 notional
        # At $45k: 15000 / 45000 = 0.333... BTC
        quantity_float, quantity_scaled = calculate_btc_quantity(
            size_usdt=1000.0 * 15,
            price=45000.0,
            size_decimals=6
        )

        expected_float = (1000.0 * 15) / 45000.0
        expected_scaled = int(round(expected_float * 1000000))

        assert abs(quantity_float - expected_float) < 1e-8
        assert quantity_scaled == expected_scaled

    def test_calculate_btc_quantity_zero_margin(self):
        """Test with zero margin."""
        quantity_float, quantity_scaled = calculate_btc_quantity(
            size_usdt=0.0,
            price=45000.0,
            size_decimals=6
        )
        assert quantity_float == 0.0
        assert quantity_scaled == 0

    def test_calculate_btc_quantity_zero_price_raises(self):
        """Test that zero price raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            calculate_btc_quantity(1000.0, 0.0, 6)

    def test_calculate_btc_quantity_negative_price_raises(self):
        """Test that negative price raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            calculate_btc_quantity(1000.0, -45000.0, 6)

    def test_calculate_btc_quantity_negative_margin_raises(self):
        """Test that negative margin raises ValueError."""
        with pytest.raises(ValueError, match="must be non-negative"):
            calculate_btc_quantity(-1000.0, 45000.0, 6)

    def test_calculate_btc_quantity_returns_tuple(self):
        """Test that function returns (float, int) tuple."""
        result = calculate_btc_quantity(1000.0, 45000.0, 6)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], float)
        assert isinstance(result[1], int)


class TestValidateScaledValues:
    """Tests for validate_scaled_values() function."""

    def test_validate_valid_values(self):
        """Test validation of valid scaled values."""
        result = validate_scaled_values(4500000, 1000000)
        assert result is True

    def test_validate_zero_values(self):
        """Test validation of zero values (should be valid)."""
        result = validate_scaled_values(0, 0)
        assert result is True

    def test_validate_large_values(self):
        """Test validation of large values."""
        result = validate_scaled_values(10**12, 10**9)
        assert result is True

    def test_validate_float_price_raises(self):
        """Test that float price raises ValueError."""
        with pytest.raises(ValueError, match="must be integers"):
            validate_scaled_values(4500000.5, 1000000)

    def test_validate_float_size_raises(self):
        """Test that float size raises ValueError."""
        with pytest.raises(ValueError, match="must be integers"):
            validate_scaled_values(4500000, 1000000.5)

    def test_validate_negative_price_raises(self):
        """Test that negative price raises ValueError."""
        with pytest.raises(ValueError, match="must be non-negative"):
            validate_scaled_values(-4500000, 1000000)

    def test_validate_negative_size_raises(self):
        """Test that negative size raises ValueError."""
        with pytest.raises(ValueError, match="must be non-negative"):
            validate_scaled_values(4500000, -1000000)


class TestPrecisionEdgeCases:
    """Test precision and rounding edge cases."""

    def test_scale_price_precision_loss_minimal(self):
        """Test that precision loss is minimal in standard cases."""
        # Typical Lighter case: BTC/USDC with 2 price decimals
        prices = [45000.0, 45000.01, 45000.99, 50000.0, 40000.0]
        for price in prices:
            scaled = scale_price(price, 2)
            unscaled = unscale_price(scaled, 2)
            # Should be exact or within rounding tolerance
            assert abs(unscaled - price) < 0.01

    def test_scale_size_precision_loss_minimal(self):
        """Test that size precision loss is minimal."""
        # Typical Lighter case: BTC size with 6 decimals
        sizes = [0.001, 0.01, 0.1, 1.0, 10.0]
        for size in sizes:
            scaled = scale_size(size, 6)
            unscaled = unscale_size(scaled, 6)
            # Should be exact or within rounding tolerance
            assert abs(unscaled - size) < 1e-7

    def test_scale_with_different_decimals(self):
        """Test scaling with various decimal precisions."""
        decimal_cases = [
            (100.0, 0, 100),      # No decimals
            (100.5, 1, 1005),     # 1 decimal
            (100.25, 2, 10025),   # 2 decimals
            (100.001, 3, 100001), # 3 decimals
        ]

        for value, decimals, expected in decimal_cases:
            result = scale_price(value, decimals)
            assert result == expected
