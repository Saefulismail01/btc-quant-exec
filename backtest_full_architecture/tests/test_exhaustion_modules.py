import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[2]))

from backtest_full_architecture.exhaustion.exhaustion_score import (
    ExhaustionInputs,
    calculate_exhaustion_score,
)
from backtest_full_architecture.exhaustion.veto_logic import get_veto_decision


def test_exhaustion_score_is_clamped_to_one() -> None:
    score = calculate_exhaustion_score(
        ExhaustionInputs(
            funding_zscore=10.0,
            price_stretch=0.2,
            cvd_divergence=2.0,
        )
    )
    assert score == pytest.approx(1.0)


def test_exhaustion_score_baseline_zero() -> None:
    score = calculate_exhaustion_score(
        ExhaustionInputs(
            funding_zscore=0.0,
            price_stretch=0.0,
            cvd_divergence=0.0,
        )
    )
    assert score == 0.0


def test_veto_logic_allow_reduce_veto_thresholds() -> None:
    allow = get_veto_decision(0.5)
    reduce = get_veto_decision(0.6)
    veto = get_veto_decision(0.8)

    assert allow.decision == "ALLOW"
    assert allow.size_multiplier == 1.0

    assert reduce.decision == "REDUCE"
    assert reduce.size_multiplier == 0.5

    assert veto.decision == "VETO"
    assert veto.size_multiplier == 0.0

