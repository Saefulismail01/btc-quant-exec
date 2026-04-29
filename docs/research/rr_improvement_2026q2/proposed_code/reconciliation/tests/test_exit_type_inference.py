"""
Tests for exit_type_inference.py — pure function, no DB, no async.

Covers:
  - order_type string → TP / SL (Rule 1)
  - price matching vs intended levels (Rule 2)
  - manual / market order heuristic (Rule 3)
  - fallback UNKNOWN
  - tolerance boundary conditions
"""

import pytest

from reconciliation.exit_type_inference import infer_exit_type, _within_tolerance
from reconciliation.models import ExitType


# ── Rule 1: order_type string matching ────────────────────────────────────────

class TestRule1OrderTypeString:
    def test_tp_order_type(self):
        result = infer_exit_type(order_type="take-profit-limit")
        assert result == ExitType.TP

    def test_sl_order_type(self):
        result = infer_exit_type(order_type="stop-loss-limit")
        assert result == ExitType.SL

    def test_tp_with_extra_whitespace(self):
        result = infer_exit_type(order_type="  take-profit-limit  ")
        assert result == ExitType.TP

    def test_sl_uppercase_normalized(self):
        # Lighter returns lowercase; normalize defensively
        result = infer_exit_type(order_type="STOP-LOSS-LIMIT")
        assert result == ExitType.SL

    def test_tp_takes_priority_over_price(self):
        # Even if price doesn't match intended TP, order_type wins
        result = infer_exit_type(
            order_type="take-profit-limit",
            exit_price=90_000.0,
            intended_tp_price=99_000.0,
        )
        assert result == ExitType.TP


# ── Rule 2: price comparison ───────────────────────────────────────────────────

class TestRule2PriceComparison:
    def test_price_matches_tp(self):
        result = infer_exit_type(
            order_type="market",
            exit_price=95_000.0,
            intended_tp_price=95_000.0,
        )
        assert result == ExitType.TP

    def test_price_matches_tp_within_tolerance(self):
        # 0.4% deviation — within default 0.5%
        result = infer_exit_type(
            order_type="market",
            exit_price=95_380.0,
            intended_tp_price=95_000.0,
        )
        assert result == ExitType.TP

    def test_price_outside_tp_tolerance(self):
        # 0.6% deviation — outside 0.5%, should not match TP
        result = infer_exit_type(
            order_type="market",
            exit_price=95_570.0,
            intended_tp_price=95_000.0,
        )
        # Falls to manual (market order)
        assert result == ExitType.MANUAL

    def test_price_matches_sl(self):
        result = infer_exit_type(
            order_type="limit",
            exit_price=93_000.0,
            intended_sl_price=93_000.0,
        )
        assert result == ExitType.SL

    def test_tp_checked_before_sl(self):
        # Both intended prices equal exit — TP wins (checked first)
        result = infer_exit_type(
            order_type="limit",
            exit_price=95_000.0,
            intended_sl_price=95_000.0,
            intended_tp_price=95_000.0,
        )
        assert result == ExitType.TP

    def test_no_intended_prices_market_order(self):
        result = infer_exit_type(order_type="market", exit_price=95_000.0)
        assert result == ExitType.MANUAL


# ── Rule 3: manual heuristic ──────────────────────────────────────────────────

class TestRule3ManualHeuristic:
    def test_market_order_is_manual(self):
        result = infer_exit_type(order_type="market")
        assert result == ExitType.MANUAL

    def test_reduce_only_market_is_manual(self):
        result = infer_exit_type(order_type="reduce-only-market")
        assert result == ExitType.MANUAL

    def test_reduce_only_underscored_is_manual(self):
        result = infer_exit_type(order_type="reduce_only_market")
        assert result == ExitType.MANUAL


# ── Fallback UNKNOWN ───────────────────────────────────────────────────────────

class TestFallbackUnknown:
    def test_unrecognized_order_type_no_prices(self):
        result = infer_exit_type(order_type="some-future-type")
        assert result == ExitType.UNKNOWN

    def test_empty_order_type(self):
        result = infer_exit_type(order_type="")
        assert result == ExitType.UNKNOWN

    def test_none_order_type(self):
        result = infer_exit_type(order_type=None)
        assert result == ExitType.UNKNOWN

    def test_limit_order_no_price_match(self):
        # "limit" is not market, but price doesn't match either → UNKNOWN
        result = infer_exit_type(
            order_type="limit",
            exit_price=95_000.0,
            intended_tp_price=85_000.0,
            intended_sl_price=80_000.0,
        )
        assert result == ExitType.UNKNOWN


# ── Tolerance helper ───────────────────────────────────────────────────────────

class TestWithinTolerance:
    def test_exact_match(self):
        assert _within_tolerance(100.0, 100.0, 0.5) is True

    def test_at_boundary(self):
        assert _within_tolerance(100.5, 100.0, 0.5) is True

    def test_just_over_boundary(self):
        assert _within_tolerance(100.51, 100.0, 0.5) is False

    def test_zero_target(self):
        assert _within_tolerance(1.0, 0.0, 0.5) is False

    def test_custom_tolerance(self):
        assert _within_tolerance(103.0, 100.0, 3.0) is True
        assert _within_tolerance(104.0, 100.0, 3.0) is False
