"""Exit type inference — pure function module (Tier 0b)."""
from __future__ import annotations
from typing import Optional
from .models import ExitType

PRICE_TOLERANCE_PCT: float = 0.5


def infer_exit_type(
    order_type: str,
    exit_price: Optional[float] = None,
    intended_sl_price: Optional[float] = None,
    intended_tp_price: Optional[float] = None,
    price_tolerance_pct: float = PRICE_TOLERANCE_PCT,
) -> ExitType:
    """Infer ExitType from a closed Lighter order."""
    normalized = (order_type or "").strip().lower()

    if normalized == "take-profit-limit":
        return ExitType.TP
    if normalized == "stop-loss-limit":
        return ExitType.SL

    if exit_price is not None:
        if intended_tp_price is not None and _within_tolerance(
            exit_price, intended_tp_price, price_tolerance_pct
        ):
            return ExitType.TP
        if intended_sl_price is not None and _within_tolerance(
            exit_price, intended_sl_price, price_tolerance_pct
        ):
            return ExitType.SL

    if normalized in ("market", "reduce-only-market", "reduce_only_market"):
        return ExitType.MANUAL

    return ExitType.UNKNOWN


def _within_tolerance(price: float, target: float, tolerance_pct: float) -> bool:
    if target == 0:
        return False
    deviation_pct = abs(price - target) / abs(target) * 100.0
    return deviation_pct <= tolerance_pct
