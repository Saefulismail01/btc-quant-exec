"""Pure trailing stop execution simulator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import pandas as pd

Side = Literal["LONG", "SHORT"]
ExitType = Literal["SL", "TRAIL_STOP", "TIME_EXIT"]


@dataclass(frozen=True)
class TrailingParams:
    """Parameters for pure trailing mode."""

    initial_sl_pct: float = 0.01333
    activate_profit_pct: float = 0.003
    atr_mult: float = 3.0
    max_hold_minutes: int = 24 * 60


@dataclass(frozen=True)
class TrailingResult:
    """Result of pure trailing execution."""

    exit_price: float
    exit_type: ExitType
    holding_minutes: int
    exit_time: Optional[pd.Timestamp]


def simulate_pure_trailing(
    candles_1m: pd.DataFrame,
    entry_time: pd.Timestamp,
    entry_price: float,
    side: Side,
    params: TrailingParams = TrailingParams(),
) -> TrailingResult:
    """Simulate pure trailing stop as defined in Phase 3 task."""
    required = {"high", "low", "close", "atr"}
    if not required.issubset(candles_1m.columns):
        raise ValueError("candles_1m must contain high, low, close, atr.")
    if side not in ("LONG", "SHORT"):
        raise ValueError("side must be LONG or SHORT.")

    initial_sl = entry_price * (1 - params.initial_sl_pct) if side == "LONG" else entry_price * (1 + params.initial_sl_pct)
    trailing_active = False
    trailing_sl = initial_sl
    window_end = entry_time + pd.Timedelta(minutes=params.max_hold_minutes)
    trade_window = candles_1m.loc[(candles_1m.index > entry_time) & (candles_1m.index <= window_end)]
    if trade_window.empty:
        return TrailingResult(entry_price, "TIME_EXIT", 0, entry_time)

    for ts, row in trade_window.iterrows():
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        atr = max(float(row["atr"]), 1e-9)

        if not trailing_active:
            if side == "LONG" and low <= initial_sl:
                hold_minutes = max(int((ts - entry_time).total_seconds() // 60), 1)
                return TrailingResult(initial_sl, "SL", hold_minutes, ts)
            if side == "SHORT" and high >= initial_sl:
                hold_minutes = max(int((ts - entry_time).total_seconds() // 60), 1)
                return TrailingResult(initial_sl, "SL", hold_minutes, ts)

            if side == "LONG" and high >= entry_price * (1 + params.activate_profit_pct):
                trailing_active = True
                trailing_sl = max(initial_sl, close - params.atr_mult * atr)
            elif side == "SHORT" and low <= entry_price * (1 - params.activate_profit_pct):
                trailing_active = True
                trailing_sl = min(initial_sl, close + params.atr_mult * atr)
            continue

        if side == "LONG":
            trailing_sl = max(trailing_sl, close - params.atr_mult * atr)
            if low <= trailing_sl:
                hold_minutes = max(int((ts - entry_time).total_seconds() // 60), 1)
                return TrailingResult(trailing_sl, "TRAIL_STOP", hold_minutes, ts)
        else:
            trailing_sl = min(trailing_sl, close + params.atr_mult * atr)
            if high >= trailing_sl:
                hold_minutes = max(int((ts - entry_time).total_seconds() // 60), 1)
                return TrailingResult(trailing_sl, "TRAIL_STOP", hold_minutes, ts)

    last_ts = trade_window.index[-1]
    hold_minutes = max(int((last_ts - entry_time).total_seconds() // 60), 1)
    return TrailingResult(float(trade_window.iloc[-1]["close"]), "TIME_EXIT", hold_minutes, last_ts)
