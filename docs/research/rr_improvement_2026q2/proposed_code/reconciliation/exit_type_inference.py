"""
Exit type inference — pure function module (Tier 0b).

Derives ExitType from a closed Lighter order without calling any live API.

Decision rule (frozen, DESIGN_DOC v0.3 "Frozen decisions" #5):
  1. Check `order_type` string from Lighter order model:
     - "take-profit-limit"  → TP (confirmed by Lighter)
     - "stop-loss-limit"    → SL (confirmed by Lighter)
  2. If order_type is neither (e.g. "market" = manual close, "limit" = manual):
     - If `intended_tp_price` available: compare exit_price with tolerance → TP
     - If `intended_sl_price` available: compare exit_price with tolerance → SL
  3. Fallback → UNKNOWN (not MANUAL, because we can't distinguish time-exit
     from manual without additional context at this layer).

Price tolerance: 0.5% (configurable via PRICE_TOLERANCE_PCT).
This guards against rounding in Lighter scaled integers.

All fields are primitive types → 100% unit-testable without mocks.
"""

from __future__ import annotations

from typing import Optional

from .models import ExitType

# Price tolerance for "did exit match intended TP/SL?" check.
# 0.5% chosen to handle Lighter price scaling rounding (max 1 tick at BTC decimals=1).
PRICE_TOLERANCE_PCT: float = 0.5


def infer_exit_type(
    order_type: str,
    exit_price: Optional[float] = None,
    intended_sl_price: Optional[float] = None,
    intended_tp_price: Optional[float] = None,
    price_tolerance_pct: float = PRICE_TOLERANCE_PCT,
) -> ExitType:
    """
    Infer ExitType from a closed Lighter order.

    Args:
        order_type:         Lighter `Order.type` field string.
                            Known values: "take-profit-limit", "stop-loss-limit",
                            "market", "limit", "reduce-only-market", etc.
        exit_price:         Actual fill price of the closing order.
        intended_sl_price:  Intended SL price stored in signal_snapshots
                            (or live_trades.sl_price if available).
        intended_tp_price:  Intended TP price stored in signal_snapshots
                            (or live_trades.tp_price if available).
        price_tolerance_pct: Max % deviation to consider prices "matching".

    Returns:
        ExitType enum value.
    """
    normalized = (order_type or "").strip().lower()

    # Rule 1 — order type is unambiguous
    if normalized == "take-profit-limit":
        return ExitType.TP
    if normalized == "stop-loss-limit":
        return ExitType.SL

    # Rule 2 — price comparison against intended levels
    if exit_price is not None:
        if intended_tp_price is not None and _within_tolerance(
            exit_price, intended_tp_price, price_tolerance_pct
        ):
            return ExitType.TP
        if intended_sl_price is not None and _within_tolerance(
            exit_price, intended_sl_price, price_tolerance_pct
        ):
            return ExitType.SL

    # Rule 3 — manual close heuristic: "market" or "reduce-only-market"
    if normalized in ("market", "reduce-only-market", "reduce_only_market"):
        return ExitType.MANUAL

    return ExitType.UNKNOWN


def _within_tolerance(
    price: float,
    target: float,
    tolerance_pct: float,
) -> bool:
    """Return True if `price` is within `tolerance_pct` % of `target`."""
    if target == 0:
        return False
    deviation_pct = abs(price - target) / abs(target) * 100.0
    return deviation_pct <= tolerance_pct
