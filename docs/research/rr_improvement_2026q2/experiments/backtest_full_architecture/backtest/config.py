"""Configuration matrix for backtest full architecture."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR = EXPERIMENT_DIR / "results"


@dataclass(frozen=True)
class WalkForwardConfig:
    """Time-series walk-forward split configuration."""

    train_bars: int = 180
    test_bars: int = 30
    step_bars: int = 30
    min_bars_required: int = 260


@dataclass(frozen=True)
class BacktestConfig:
    """Single experiment configuration."""

    name: str
    mlp_variant: str
    exit_strategy: str
    exhaustion_mode: str
    description: str


def get_configuration_matrix() -> list[BacktestConfig]:
    """Return the 6 required configuration variants."""
    return [
        BacktestConfig(
            name="baseline",
            mlp_variant="baseline",
            exit_strategy="fixed_tp_sl",
            exhaustion_mode="none",
            description="Control group: 4H label + fixed TP/SL",
        ),
        BacktestConfig(
            name="a_exec_aligned_fixed",
            mlp_variant="variant_a",
            exit_strategy="fixed_tp_sl",
            exhaustion_mode="none",
            description="Execution-aligned label with baseline exits",
        ),
        BacktestConfig(
            name="b_exec_aligned_partial",
            mlp_variant="variant_a",
            exit_strategy="partial_tp",
            exhaustion_mode="none",
            description="Execution-aligned + partial TP",
        ),
        BacktestConfig(
            name="c_exec_aligned_partial_veto",
            mlp_variant="variant_a",
            exit_strategy="partial_tp",
            exhaustion_mode="veto",
            description="Execution-aligned + partial TP + exhaustion veto",
        ),
        BacktestConfig(
            name="d_exec_aligned_trailing",
            mlp_variant="variant_a",
            exit_strategy="trailing_stop",
            exhaustion_mode="none",
            description="Execution-aligned + pure trailing stop",
        ),
        BacktestConfig(
            name="e_1h_fixed",
            mlp_variant="variant_b",
            exit_strategy="fixed_tp_sl",
            exhaustion_mode="none",
            description="1H label alternative with baseline exits",
        ),
    ]
