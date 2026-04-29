"""Single entrypoint for Phase 3 exhaustion + execution flow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import pandas as pd

from backtest_full_architecture.exhaustion.exhaustion_score import (
    ExhaustionInputs,
    calculate_exhaustion_score,
)
from backtest_full_architecture.exhaustion.veto_logic import VetoDecision, get_veto_decision
from backtest_full_architecture.execution.fixed_tp_sl import (
    ExecutionResult,
    FixedTPSLParams,
    simulate_fixed_tp_sl,
)
from backtest_full_architecture.execution.partial_tp import (
    PartialExecutionResult,
    PartialTPParams,
    simulate_partial_tp,
)
from backtest_full_architecture.execution.trailing_stop import (
    TrailingParams,
    TrailingResult,
    simulate_pure_trailing,
)

Side = Literal["LONG", "SHORT"]
ExecutionMode = Literal["fixed_tp_sl", "partial_tp", "pure_trailing"]


@dataclass(frozen=True)
class Phase3ExecutionSummary:
    """Normalized execution payload returned by the adapter."""

    mode: ExecutionMode
    exit_price: float
    exit_type: str
    holding_minutes: int
    exit_time: Optional[pd.Timestamp]
    tp1_hit: Optional[bool]


@dataclass(frozen=True)
class Phase3Result:
    """Final result containing decision and optional execution output."""

    exhaustion_score: float
    veto_decision: VetoDecision
    execution: Optional[Phase3ExecutionSummary]


def _run_execution(
    execution_mode: ExecutionMode,
    candles_1m: pd.DataFrame,
    entry_time: pd.Timestamp,
    entry_price: float,
    side: Side,
    fixed_params: Optional[FixedTPSLParams],
    partial_params: Optional[PartialTPParams],
    trailing_params: Optional[TrailingParams],
) -> Phase3ExecutionSummary:
    if execution_mode == "fixed_tp_sl":
        result: ExecutionResult = simulate_fixed_tp_sl(
            candles_1m=candles_1m,
            entry_time=entry_time,
            entry_price=entry_price,
            side=side,
            params=fixed_params or FixedTPSLParams(),
        )
        return Phase3ExecutionSummary(
            mode=execution_mode,
            exit_price=result.exit_price,
            exit_type=result.exit_type,
            holding_minutes=result.holding_minutes,
            exit_time=result.exit_time,
            tp1_hit=None,
        )

    if execution_mode == "partial_tp":
        result: PartialExecutionResult = simulate_partial_tp(
            candles_1m=candles_1m,
            entry_time=entry_time,
            entry_price=entry_price,
            side=side,
            params=partial_params or PartialTPParams(),
        )
        return Phase3ExecutionSummary(
            mode=execution_mode,
            exit_price=result.exit_price,
            exit_type=result.exit_type,
            holding_minutes=result.holding_minutes,
            exit_time=result.exit_time,
            tp1_hit=result.tp1_hit,
        )

    if execution_mode == "pure_trailing":
        result: TrailingResult = simulate_pure_trailing(
            candles_1m=candles_1m,
            entry_time=entry_time,
            entry_price=entry_price,
            side=side,
            params=trailing_params or TrailingParams(),
        )
        return Phase3ExecutionSummary(
            mode=execution_mode,
            exit_price=result.exit_price,
            exit_type=result.exit_type,
            holding_minutes=result.holding_minutes,
            exit_time=result.exit_time,
            tp1_hit=None,
        )

    raise ValueError(f"Unsupported execution_mode: {execution_mode}")


def run_phase3_decision_and_execution(
    *,
    candles_1m: pd.DataFrame,
    entry_time: pd.Timestamp,
    entry_price: float,
    side: Side,
    exhaustion_inputs: ExhaustionInputs,
    execution_mode: ExecutionMode = "fixed_tp_sl",
    fixed_params: Optional[FixedTPSLParams] = None,
    partial_params: Optional[PartialTPParams] = None,
    trailing_params: Optional[TrailingParams] = None,
) -> Phase3Result:
    """Run full Phase 3 flow in one call."""
    exhaustion_score = calculate_exhaustion_score(exhaustion_inputs)
    decision = get_veto_decision(exhaustion_score)
    if decision.decision == "VETO":
        return Phase3Result(exhaustion_score=exhaustion_score, veto_decision=decision, execution=None)

    execution = _run_execution(
        execution_mode=execution_mode,
        candles_1m=candles_1m,
        entry_time=entry_time,
        entry_price=entry_price,
        side=side,
        fixed_params=fixed_params,
        partial_params=partial_params,
        trailing_params=trailing_params,
    )
    return Phase3Result(exhaustion_score=exhaustion_score, veto_decision=decision, execution=execution)

