from pathlib import Path
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))

from backtest_full_architecture.exhaustion.exhaustion_score import ExhaustionInputs
from backtest_full_architecture.phase3_adapter import run_phase3_decision_and_execution


def _df(rows: list[dict], start: str = "2026-01-01 00:00:00") -> pd.DataFrame:
    index = pd.date_range(start=start, periods=len(rows), freq="1min")
    return pd.DataFrame(rows, index=index)


def test_adapter_veto_skips_execution() -> None:
    result = run_phase3_decision_and_execution(
        candles_1m=_df([{"high": 100.0, "low": 100.0, "close": 100.0, "atr": 0.1}]),
        entry_time=pd.Timestamp("2026-01-01 00:00:00"),
        entry_price=100.0,
        side="LONG",
        exhaustion_inputs=ExhaustionInputs(
            funding_zscore=3.0,
            price_stretch=0.02,
            cvd_divergence=1.0,
        ),
    )
    assert result.veto_decision.decision == "VETO"
    assert result.execution is None


def test_adapter_allow_runs_fixed_tp_sl() -> None:
    result = run_phase3_decision_and_execution(
        candles_1m=_df(
            [
                {"high": 100.0, "low": 100.0, "close": 100.0, "atr": 0.1},
                {"high": 101.0, "low": 99.9, "close": 100.8, "atr": 0.1},
            ]
        ),
        entry_time=pd.Timestamp("2026-01-01 00:00:00"),
        entry_price=100.0,
        side="LONG",
        exhaustion_inputs=ExhaustionInputs(
            funding_zscore=0.3,
            price_stretch=0.002,
            cvd_divergence=0.1,
        ),
        execution_mode="fixed_tp_sl",
    )
    assert result.veto_decision.decision == "ALLOW"
    assert result.execution is not None
    assert result.execution.mode == "fixed_tp_sl"


def test_adapter_allow_runs_partial_tp() -> None:
    result = run_phase3_decision_and_execution(
        candles_1m=_df(
            [
                {"high": 100.0, "low": 100.0, "close": 100.0, "atr": 0.1},
                {"high": 100.6, "low": 99.9, "close": 100.5, "atr": 0.1},
                {"high": 100.55, "low": 100.2, "close": 100.4, "atr": 0.1},
            ]
        ),
        entry_time=pd.Timestamp("2026-01-01 00:00:00"),
        entry_price=100.0,
        side="LONG",
        exhaustion_inputs=ExhaustionInputs(
            funding_zscore=0.3,
            price_stretch=0.002,
            cvd_divergence=0.1,
        ),
        execution_mode="partial_tp",
    )
    assert result.veto_decision.decision == "ALLOW"
    assert result.execution is not None
    assert result.execution.mode == "partial_tp"
    assert result.execution.tp1_hit is True


def test_adapter_allow_runs_pure_trailing() -> None:
    result = run_phase3_decision_and_execution(
        candles_1m=_df(
            [
                {"high": 100.0, "low": 100.0, "close": 100.0, "atr": 0.2},
                {"high": 100.4, "low": 100.0, "close": 100.35, "atr": 0.2},
                {"high": 100.35, "low": 99.7, "close": 100.0, "atr": 0.2},
            ]
        ),
        entry_time=pd.Timestamp("2026-01-01 00:00:00"),
        entry_price=100.0,
        side="LONG",
        exhaustion_inputs=ExhaustionInputs(
            funding_zscore=0.3,
            price_stretch=0.002,
            cvd_divergence=0.1,
        ),
        execution_mode="pure_trailing",
    )
    assert result.veto_decision.decision == "ALLOW"
    assert result.execution is not None
    assert result.execution.mode == "pure_trailing"
    assert result.execution.exit_type in {"SL", "TRAIL_STOP", "TIME_EXIT"}

