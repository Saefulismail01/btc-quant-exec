"""Pure trailing stop execution with ATR activation."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

INITIAL_SL_PCT = 0.01333
ACTIVATE_PROFIT_PCT = 0.003
ATR_MULT = 3.0


def _get_col(row: pd.Series, names: list[str], default: float = 0.0) -> float:
    for name in names:
        if name in row and pd.notna(row[name]):
            return float(row[name])
    return float(default)


def _minute_window(one_minute_df: pd.DataFrame, bar_now: pd.Series, bar_next: pd.Series) -> pd.DataFrame:
    if "datetime" not in one_minute_df.columns:
        return pd.DataFrame()
    start = pd.to_datetime(bar_now.get("datetime"), utc=True, errors="coerce")
    end = pd.to_datetime(bar_next.get("datetime"), utc=True, errors="coerce")
    if pd.isna(start) or pd.isna(end):
        return pd.DataFrame()
    dt = pd.to_datetime(one_minute_df["datetime"], utc=True, errors="coerce")
    return one_minute_df.loc[(dt > start) & (dt <= end)].copy().sort_values("datetime")


def _pnl_pct(entry_price: float, exit_price: float, side: float, size: float) -> float:
    raw_ret = (float(exit_price) / float(entry_price) - 1.0) * float(np.sign(side))
    return raw_ret * float(size)


def _atr_from_bar(bar_now: pd.Series, entry_price: float) -> float:
    atr = _get_col(bar_now, ["atr", "ATR", "atr14", "ATR14"], default=0.0)
    if atr > 0:
        return atr
    return max(entry_price * 0.004, 1e-9)


def simulate_trade(
    entry_price: float,
    side: float,
    bar_now: pd.Series,
    bar_next: pd.Series,
    one_minute_df: pd.DataFrame,
    size: float,
) -> dict[str, Any]:
    """Initial SL, activate trailing after +0.3%, trail by 3x ATR."""
    entry = float(entry_price)
    is_long = float(np.sign(side)) >= 0
    atr = _atr_from_bar(bar_now, entry)
    start = pd.to_datetime(bar_now.get("datetime"), utc=True, errors="coerce")

    if is_long:
        initial_sl = entry * (1.0 - INITIAL_SL_PCT)
        activate_price = entry * (1.0 + ACTIVATE_PROFIT_PCT)
    else:
        initial_sl = entry * (1.0 + INITIAL_SL_PCT)
        activate_price = entry * (1.0 - ACTIVATE_PROFIT_PCT)

    window = _minute_window(one_minute_df, bar_now, bar_next)
    if window.empty:
        exit_price = _get_col(bar_next, ["Close", "close"], default=entry)
        return {
            "exit_price": exit_price,
            "pnl_pct": _pnl_pct(entry, exit_price, side, size),
            "exit_type": "next_bar_close",
            "holding_minutes": 240.0,
        }

    trailing_active = False
    trailing_sl = initial_sl

    for _, minute in window.iterrows():
        low = _get_col(minute, ["low", "Low"], default=entry)
        high = _get_col(minute, ["high", "High"], default=entry)
        close = _get_col(minute, ["close", "Close"], default=entry)
        ts = pd.to_datetime(minute.get("datetime"), utc=True, errors="coerce")
        hold = max((ts - start).total_seconds() / 60.0, 1.0) if pd.notna(ts) and pd.notna(start) else 1.0

        if not trailing_active:
            if is_long and low <= initial_sl:
                return {"exit_price": initial_sl, "pnl_pct": _pnl_pct(entry, initial_sl, side, size), "exit_type": "SL", "holding_minutes": hold}
            if (not is_long) and high >= initial_sl:
                return {"exit_price": initial_sl, "pnl_pct": _pnl_pct(entry, initial_sl, side, size), "exit_type": "SL", "holding_minutes": hold}

            if is_long and high >= activate_price:
                trailing_active = True
                trailing_sl = max(initial_sl, close - ATR_MULT * atr)
                continue
            if (not is_long) and low <= activate_price:
                trailing_active = True
                trailing_sl = min(initial_sl, close + ATR_MULT * atr)
                continue

        else:
            if is_long:
                trailing_sl = max(trailing_sl, close - ATR_MULT * atr)
                if low <= trailing_sl:
                    return {"exit_price": trailing_sl, "pnl_pct": _pnl_pct(entry, trailing_sl, side, size), "exit_type": "TRAIL", "holding_minutes": hold}
            else:
                trailing_sl = min(trailing_sl, close + ATR_MULT * atr)
                if high >= trailing_sl:
                    return {"exit_price": trailing_sl, "pnl_pct": _pnl_pct(entry, trailing_sl, side, size), "exit_type": "TRAIL", "holding_minutes": hold}

    exit_price = _get_col(bar_next, ["Close", "close"], default=entry)
    return {
        "exit_price": exit_price,
        "pnl_pct": _pnl_pct(entry, exit_price, side, size),
        "exit_type": "TIME_EXIT",
        "holding_minutes": 240.0,
    }

