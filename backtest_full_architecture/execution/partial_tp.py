"""Partial TP (60/40) with breakeven + ATR chandelier trailing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import pandas as pd

Side = Literal["LONG", "SHORT"]
ExitType = Literal["SL", "TP1_ONLY", "TRAIL_STOP", "TIME_EXIT", "NO_EXIT"]


@dataclass(frozen=True)
class PartialTPParams:
    """Parameters for partial TP strategy."""

    tp1_pct: float = 0.004  # 0.4%
    tp1_size: float = 0.60
    trailing_size: float = 0.40
    atr_mult: float = 2.0
    max_hold_minutes: int = 24 * 60


@dataclass(frozen=True)
class PartialExecutionResult:
    """Weighted exit result for partial strategy."""

    exit_price: float
    exit_type: ExitType
    holding_minutes: int
    tp1_hit: bool
    exit_time: Optional[pd.Timestamp]


def simulate_partial_tp(
    candles_1m: pd.DataFrame,
    entry_time: pd.Timestamp,
    entry_price: float,
    side: Side,
    params: PartialTPParams = PartialTPParams(),
) -> PartialExecutionResult:
    """Simulate partial TP with trailing remainder."""
    required = {"high", "low", "close", "atr"}
    if not required.issubset(candles_1m.columns):
        raise ValueError("candles_1m must contain high, low, close, atr.")
    if side not in ("LONG", "SHORT"):
        raise ValueError("side must be LONG or SHORT.")

    initial_sl = entry_price * (1 - 0.01333) if side == "LONG" else entry_price * (1 + 0.01333)
    tp1_price = entry_price * (1 + params.tp1_pct) if side == "LONG" else entry_price * (1 - params.tp1_pct)
    window_end = entry_time + pd.Timedelta(minutes=params.max_hold_minutes)
    trade_window = candles_1m.loc[(candles_1m.index > entry_time) & (candles_1m.index <= window_end)]
    if trade_window.empty:
        return PartialExecutionResult(entry_price, "TIME_EXIT", 0, False, entry_time)

    tp1_hit = False
    trailing_sl = initial_sl
    tp1_realized = entry_price

    for ts, row in trade_window.iterrows():
        low = float(row["low"])
        high = float(row["high"])
        close = float(row["close"])
        atr = max(float(row["atr"]), 1e-9)

        if not tp1_hit:
            if side == "LONG" and low <= initial_sl:
                hold_minutes = max(int((ts - entry_time).total_seconds() // 60), 1)
                return PartialExecutionResult(initial_sl, "SL", hold_minutes, False, ts)
            if side == "SHORT" and high >= initial_sl:
                hold_minutes = max(int((ts - entry_time).total_seconds() // 60), 1)
                return PartialExecutionResult(initial_sl, "SL", hold_minutes, False, ts)

            if side == "LONG" and high >= tp1_price:
                tp1_hit = True
                tp1_realized = tp1_price
                trailing_sl = max(entry_price, close - params.atr_mult * atr)
                continue
            if side == "SHORT" and low <= tp1_price:
                tp1_hit = True
                tp1_realized = tp1_price
                trailing_sl = min(entry_price, close + params.atr_mult * atr)
                continue
        else:
            if side == "LONG":
                trailing_sl = max(trailing_sl, close - params.atr_mult * atr)
                if low <= trailing_sl:
                    weighted = params.tp1_size * tp1_realized + params.trailing_size * trailing_sl
                    hold_minutes = max(int((ts - entry_time).total_seconds() // 60), 1)
                    return PartialExecutionResult(weighted, "TRAIL_STOP", hold_minutes, True, ts)
            else:
                trailing_sl = min(trailing_sl, close + params.atr_mult * atr)
                if high >= trailing_sl:
                    weighted = params.tp1_size * tp1_realized + params.trailing_size * trailing_sl
                    hold_minutes = max(int((ts - entry_time).total_seconds() // 60), 1)
                    return PartialExecutionResult(weighted, "TRAIL_STOP", hold_minutes, True, ts)

    last_ts = trade_window.index[-1]
    last_close = float(trade_window.iloc[-1]["close"])
    hold_minutes = max(int((last_ts - entry_time).total_seconds() // 60), 1)
    if tp1_hit:
        weighted = params.tp1_size * tp1_realized + params.trailing_size * last_close
        return PartialExecutionResult(weighted, "TIME_EXIT", hold_minutes, True, last_ts)
    return PartialExecutionResult(last_close, "TIME_EXIT", hold_minutes, False, last_ts)
