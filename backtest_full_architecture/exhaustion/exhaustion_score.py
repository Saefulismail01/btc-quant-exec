"""Exhaustion score calculation for entry filtering."""

from __future__ import annotations

from dataclasses import dataclass


def _clamp_01(value: float) -> float:
    return max(0.0, min(1.0, value))


@dataclass(frozen=True)
class ExhaustionInputs:
    """Normalized exhaustion components."""

    funding_zscore: float
    price_stretch: float
    cvd_divergence: float


def _normalize_funding_zscore(funding_zscore: float) -> float:
    # z >= 3 is considered extreme
    return _clamp_01(abs(funding_zscore) / 3.0)


def _normalize_price_stretch(price_stretch: float) -> float:
    # Expect input as decimal stretch from trend anchor (e.g. 0.012 = 1.2%)
    return _clamp_01(abs(price_stretch) / 0.02)


def _normalize_cvd_divergence(cvd_divergence: float) -> float:
    # Assume pre-normalized value in [-1, 1] where higher abs means stronger divergence.
    return _clamp_01(abs(cvd_divergence))


def calculate_exhaustion_score(inputs: ExhaustionInputs) -> float:
    """Compute exhaustion score in [0, 1] from three components."""
    funding_component = _normalize_funding_zscore(inputs.funding_zscore)
    stretch_component = _normalize_price_stretch(inputs.price_stretch)
    cvd_component = _normalize_cvd_divergence(inputs.cvd_divergence)

    # Slightly higher weight for stretch and divergence because they are execution-near.
    score = (
        0.30 * funding_component
        + 0.35 * stretch_component
        + 0.35 * cvd_component
    )
    return _clamp_01(score)
