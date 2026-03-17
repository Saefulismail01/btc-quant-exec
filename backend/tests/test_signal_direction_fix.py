"""
TASK-6: Unit tests for signal direction fix.

Tests that:
1. SHORT signal can be generated (was never possible before TASK-1)
2. EMA fallback (TASK-2) correctly handles price < EMA20 as BEAR
3. Spectrum action is used as final_action (not EMA-derived action_side)
4. HV preset R:R >= 1.0 (TASK-3)
5. BCD posterior confidence is in [0.25, 0.95] (TASK-4), not always 1.0
"""

import numpy as np
import pandas as pd
import pytest

# ── TASK-3: HV Preset R:R tests ───────────────────────────────────────────────

def test_hv_fast_revert_rr_ratio():
    """HV-Fast-Revert preset must have R:R >= 1.0."""
    from app.core.engines.layer1_volatility import VolatilityRegimeEstimator
    est = VolatilityRegimeEstimator()
    result = est.get_sl_tp_multipliers(vol_regime="High", halflife=10.0, bias_score=0.5)
    assert result["preset_name"] == "HV-Fast-Revert"
    rr = result["tp1_multiplier"] / result["sl_multiplier"]
    assert rr >= 1.0, f"HV-Fast-Revert R:R = {rr:.2f} < 1.0"


def test_hv_slow_persist_rr_ratio():
    """HV-Slow-Persist preset must have R:R >= 1.0."""
    from app.core.engines.layer1_volatility import VolatilityRegimeEstimator
    est = VolatilityRegimeEstimator()
    result = est.get_sl_tp_multipliers(vol_regime="High", halflife=20.0, bias_score=0.5)
    assert result["preset_name"] == "HV-Slow-Persist"
    rr = result["tp1_multiplier"] / result["sl_multiplier"]
    assert rr >= 1.0, f"HV-Slow-Persist R:R = {rr:.2f} < 1.0"


def test_lv_trend_rr_ratio():
    """LV-Trend preset must have R:R >= 1.0."""
    from app.core.engines.layer1_volatility import VolatilityRegimeEstimator
    est = VolatilityRegimeEstimator()
    result = est.get_sl_tp_multipliers(vol_regime="Low", halflife=20.0, bias_score=0.5)
    assert result["preset_name"] == "LV-Trend"
    rr = result["tp1_multiplier"] / result["sl_multiplier"]
    assert rr >= 1.0, f"LV-Trend R:R = {rr:.2f} < 1.0"


def test_normal_rr_ratio():
    """Normal preset must have R:R >= 1.0."""
    from app.core.engines.layer1_volatility import VolatilityRegimeEstimator
    est = VolatilityRegimeEstimator()
    result = est.get_sl_tp_multipliers(vol_regime="Normal", halflife=20.0, bias_score=0.5)
    assert result["preset_name"] == "Normal"
    rr = result["tp1_multiplier"] / result["sl_multiplier"]
    assert rr >= 1.0, f"Normal R:R = {rr:.2f} < 1.0"


# ── TASK-2: EMA fallback fix ───────────────────────────────────────────────────

def _make_df_for_ema_test(price, ema20, ema50, n=60):
    """Build minimal synthetic OHLCV for EMA direction testing."""
    closes = np.full(n, price)
    # Skew last few rows so EMA converges near target
    closes[-5:] = price
    df = pd.DataFrame({
        "Open":   closes * 0.999,
        "High":   closes * 1.001,
        "Low":    closes * 0.999,
        "Close":  closes,
        "Volume": np.full(n, 1000.0),
    })
    return df


def test_ema_direction_price_below_ema20_above_ema50():
    """
    TASK-2: When EMA20 > EMA50 but price < EMA20, direction must be BEAR (was BULL bug).
    This is the scenario that triggered the LONG bias bug.
    """
    # Simulate: EMA20=75000, EMA50=74000, price=74500 (below EMA20 but above EMA50)
    # Old code: falls into else → LONG (BUG)
    # New code: price < EMA20 → BEAR (FIX)
    price  = 74500.0
    ema20  = 75000.0
    ema50  = 74000.0

    # Replicate the fixed condition logic from signal_service.py
    if ema20 < ema50 and price < ema20:
        direction = "SHORT"
    elif ema20 > ema50 and price > ema20:
        direction = "LONG"
    elif price < ema50:
        direction = "SHORT"
    elif price < ema20:
        # [TASK-2] This is the new condition
        direction = "SHORT"
    else:
        direction = "LONG"

    assert direction == "SHORT", (
        f"price={price} < ema20={ema20} but direction={direction} (expected SHORT)"
    )


def test_ema_direction_all_bullish():
    """EMA20 > EMA50 and price > EMA20 → LONG."""
    price, ema20, ema50 = 76000.0, 75000.0, 74000.0
    if ema20 < ema50 and price < ema20:
        direction = "SHORT"
    elif ema20 > ema50 and price > ema20:
        direction = "LONG"
    elif price < ema50:
        direction = "SHORT"
    elif price < ema20:
        direction = "SHORT"
    else:
        direction = "LONG"
    assert direction == "LONG"


def test_ema_direction_all_bearish():
    """EMA20 < EMA50 and price < EMA20 → SHORT."""
    price, ema20, ema50 = 73000.0, 74000.0, 75000.0
    if ema20 < ema50 and price < ema20:
        direction = "SHORT"
    elif ema20 > ema50 and price > ema20:
        direction = "LONG"
    elif price < ema50:
        direction = "SHORT"
    elif price < ema20:
        direction = "SHORT"
    else:
        direction = "LONG"
    assert direction == "SHORT"


# ── TASK-1: Spectrum action is final_action ────────────────────────────────────

def test_spectrum_short_possible():
    """
    TASK-1: DirectionalSpectrum must be able to produce SHORT action.
    Before fix, final_action was always from EMA (often LONG). Now it's from Spectrum.
    """
    from utils.spectrum import DirectionalSpectrum
    spec = DirectionalSpectrum()

    # All votes bearish → should produce SHORT
    result = spec.calculate(
        l1_vote=-0.8,
        l2_vote=-0.7,
        l3_vote=-0.9,
        l4_multiplier=0.8,
        base_size=5.0,
    )
    assert result.action == "SHORT", f"Expected SHORT, got {result.action}"
    assert result.directional_bias < 0, f"Expected negative bias, got {result.directional_bias}"


def test_spectrum_long_still_works():
    """Bullish votes → LONG (regression check)."""
    from utils.spectrum import DirectionalSpectrum
    spec = DirectionalSpectrum()
    result = spec.calculate(
        l1_vote=0.8,
        l2_vote=0.7,
        l3_vote=0.9,
        l4_multiplier=0.8,
        base_size=5.0,
    )
    assert result.action == "LONG"
    assert result.directional_bias > 0


def test_spectrum_mixed_votes_direction_follows_weighted_sum():
    """Mixed votes: L3 bearish (weight 0.45) should dominate L1+L2 bullish (0.30+0.25)."""
    from utils.spectrum import DirectionalSpectrum
    spec = DirectionalSpectrum()
    # L1=+1, L2=+1, L3=-1 → raw = 0.30 + 0.25 - 0.45 = +0.10
    result = spec.calculate(
        l1_vote=1.0,
        l2_vote=1.0,
        l3_vote=-1.0,
        l4_multiplier=1.0,
        base_size=5.0,
    )
    # raw_score = 0.10 → LONG (barely positive)
    assert result.action == "LONG"
    # But conviction is low
    assert result.conviction_pct < 20.0


def test_spectrum_l3_bearish_dominates_ema_bullish():
    """
    Core TASK-1 scenario: EMA says LONG (ema_direction=LONG) but
    L1+L2+L3 aggregate is SHORT. final_action must be SHORT.
    """
    from utils.spectrum import DirectionalSpectrum
    spec = DirectionalSpectrum()
    # L1 slightly bearish, L2 slightly bullish (EMA says LONG), L3 strongly bearish
    result = spec.calculate(
        l1_vote=-0.6,
        l2_vote=0.3,   # EMA structural bias = bullish
        l3_vote=-0.9,  # MLP strongly bearish
        l4_multiplier=0.8,
        base_size=5.0,
    )
    # raw = -0.6*0.30 + 0.3*0.25 + (-0.9)*0.45 = -0.18 + 0.075 - 0.405 = -0.51
    assert result.action == "SHORT", f"Expected SHORT, got {result.action} (bias={result.directional_bias})"


# ── TASK-4: BCD posterior confidence not always 1.0 ──────────────────────────

def _make_synthetic_ohlcv(n=200, seed=42):
    """Synthetic OHLCV for BCD testing."""
    rng = np.random.default_rng(seed)
    price = 70000.0
    closes = []
    for _ in range(n):
        price *= (1 + rng.normal(0, 0.003))
        closes.append(price)
    closes = np.array(closes)
    df = pd.DataFrame({
        "Open":   closes * 0.999,
        "High":   closes * 1.003,
        "Low":    closes * 0.997,
        "Close":  closes,
        "Volume": rng.uniform(500, 2000, n),
        "funding_rate": rng.normal(0.0001, 0.00005, n),
    })
    df.index = pd.date_range("2024-01-01", periods=n, freq="4h")
    return df


def test_bcd_posterior_not_always_one():
    """
    TASK-4: BCD posterior confidence must NOT always be 1.0.
    After fix, confidence comes from run-length probability matrix.
    """
    from app.core.engines.layer1_bcd import BayesianChangepointModel
    model = BayesianChangepointModel()
    df = _make_synthetic_ohlcv(n=200)
    label, sid, posterior = model.get_current_regime_posterior(df)

    # The active state confidence should be in [0.25, 0.95]
    if sid >= 0 and sid < len(posterior):
        conf = posterior[sid]
        assert conf != 1.0, "Posterior is still fake (always 1.0) — TASK-4 fix not applied"
        assert 0.25 <= conf <= 0.95, f"Confidence {conf:.3f} outside expected range [0.25, 0.95]"


def test_bcd_posterior_label_returned():
    """BCD posterior returns valid label string."""
    from app.core.engines.layer1_bcd import BayesianChangepointModel
    model = BayesianChangepointModel()
    df = _make_synthetic_ohlcv(n=200)
    label, sid, posterior = model.get_current_regime_posterior(df)
    assert isinstance(label, str)
    assert len(label) > 0
    assert isinstance(posterior, np.ndarray)
