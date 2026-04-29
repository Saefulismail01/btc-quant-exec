"""Fixed TP/SL execution simulator for 1m candle data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import pandas as pd

Side = Literal["LONG", "SHORT"]
ExitType = Literal["SL", "TP", "TIME_EXIT", "NO_EXIT"]


@dataclass(frozen=True)
class FixedTPSLParams:
    """Parameters for fixed TP/SL strategy."""

    tp_pct: float = 0.0071
    sl_pct: float = 0.01333
    max_hold_minutes: int = 24 * 60


@dataclass(frozen=True)
class ExecutionResult:
    """Standardized output for execution simulation."""

    exit_price: float
    exit_type: ExitType
    holding_minutes: int
    exit_time: Optional[pd.Timestamp]


def _bar_hits_stop_or_take(side: Side, low: float, high: float, sl_price: float, tp_price: float) -> ExitType:
    if side == "LONG":
        sl_hit = low <= sl_price
        tp_hit = high >= tp_price
    else:
        sl_hit = high >= sl_price
        tp_hit = low <= tp_price

    # Conservative tie-breaker: if both are touched in the same minute, assume SL first.
    if sl_hit:
        return "SL"
    if tp_hit:
        return "TP"
    return "NO_EXIT"


def simulate_fixed_tp_sl(
    candles_1m: pd.DataFrame,
    entry_time: pd.Timestamp,
    entry_price: float,
    side: Side,
    params: FixedTPSLParams = FixedTPSLParams(),
) -> ExecutionResult:
    """Simulate fixed TP/SL from entry using subsequent 1m candles."""
    if entry_price <= 0:
        raise ValueError("entry_price must be > 0.")
    if side not in ("LONG", "SHORT"):
        raise ValueError("side must be LONG or SHORT.")
    if not {"high", "low", "close"}.issubset(candles_1m.columns):
        raise ValueError("candles_1m must contain columns: high, low, close.")

    if side == "LONG":
        tp_price = entry_price * (1.0 + params.tp_pct)
        sl_price = entry_price * (1.0 - params.sl_pct)
    else:
        tp_price = entry_price * (1.0 - params.tp_pct)
        sl_price = entry_price * (1.0 + params.sl_pct)

    window_end = entry_time + pd.Timedelta(minutes=params.max_hold_minutes)
    trade_window = candles_1m.loc[(candles_1m.index > entry_time) & (candles_1m.index <= window_end)]
    if trade_window.empty:
        return ExecutionResult(entry_price, "TIME_EXIT", 0, entry_time)

    for ts, row in trade_window.iterrows():
        exit_type = _bar_hits_stop_or_take(side, float(row["low"]), float(row["high"]), sl_price, tp_price)
        if exit_type == "SL":
            hold_minutes = max(int((ts - entry_time).total_seconds() // 60), 1)
            return ExecutionResult(sl_price, "SL", hold_minutes, ts)
        if exit_type == "TP":
            hold_minutes = max(int((ts - entry_time).total_seconds() // 60), 1)
            return ExecutionResult(tp_price, "TP", hold_minutes, ts)

    last_ts = trade_window.index[-1]
    hold_minutes = max(int((last_ts - entry_time).total_seconds() // 60), 1)
    return ExecutionResult(float(trade_window.iloc[-1]["close"]), "TIME_EXIT", hold_minutes, last_ts)
