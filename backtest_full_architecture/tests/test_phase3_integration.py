from pathlib import Path
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))

from backtest_full_architecture.exhaustion.exhaustion_score import (
    ExhaustionInputs,
    calculate_exhaustion_score,
)
from backtest_full_architecture.exhaustion.veto_logic import get_veto_decision
from backtest_full_architecture.execution.fixed_tp_sl import simulate_fixed_tp_sl


def _df(rows: list[dict], start: str = "2026-01-01 00:00:00") -> pd.DataFrame:
    index = pd.date_range(start=start, periods=len(rows), freq="1min")
    return pd.DataFrame(rows, index=index)


def test_integration_allow_path_runs_execution() -> None:
    score = calculate_exhaustion_score(
        ExhaustionInputs(
            funding_zscore=0.4,
            price_stretch=0.003,
            cvd_divergence=0.1,
        )
    )
    decision = get_veto_decision(score)
    assert decision.decision == "ALLOW"
    assert decision.size_multiplier == 1.0

    entry_time = pd.Timestamp("2026-01-01 00:00:00")
    candles = _df(
        [
            {"high": 100.0, "low": 100.0, "close": 100.0},
            {"high": 101.0, "low": 99.7, "close": 100.8},
            {"high": 101.2, "low": 100.1, "close": 101.0},
        ]
    )
    result = simulate_fixed_tp_sl(candles, entry_time, 100.0, "LONG")
    assert result.exit_type in {"TP", "SL", "TIME_EXIT"}
    assert result.holding_minutes >= 1


def test_integration_reduce_path_scales_position_only() -> None:
    score = calculate_exhaustion_score(
        ExhaustionInputs(
            funding_zscore=1.8,
            price_stretch=0.012,
            cvd_divergence=0.6,
        )
    )
    decision = get_veto_decision(score)
    assert decision.decision == "REDUCE"
    assert decision.size_multiplier == 0.5


def test_integration_veto_path_blocks_execution() -> None:
    score = calculate_exhaustion_score(
        ExhaustionInputs(
            funding_zscore=3.0,
            price_stretch=0.02,
            cvd_divergence=1.0,
        )
    )
    decision = get_veto_decision(score)
    assert decision.decision == "VETO"
    assert decision.size_multiplier == 0.0
