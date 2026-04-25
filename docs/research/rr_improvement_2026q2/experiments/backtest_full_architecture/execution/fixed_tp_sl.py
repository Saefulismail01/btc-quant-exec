"""Fixed TP/SL execution simulator using 1m candles."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

TP_PCT = 0.0071
SL_PCT = 0.01333


def _get_col(row: pd.Series, names: list[str], default: float = 0.0) -> float:
    for name in names:
        if name in row and pd.notna(row[name]):
            return float(row[name])
    return float(default)


def _pnl_pct(entry_price: float, exit_price: float, side: float, size: float) -> float:
    raw_ret = (float(exit_price) / float(entry_price) - 1.0) * float(np.sign(side))
    return raw_ret * float(size)


def _minute_window(one_minute_df: pd.DataFrame, bar_now: pd.Series, bar_next: pd.Series) -> pd.DataFrame:
    if "datetime" not in one_minute_df.columns:
        return pd.DataFrame()
    start = pd.to_datetime(bar_now.get("datetime"), utc=True, errors="coerce")
    end = pd.to_datetime(bar_next.get("datetime"), utc=True, errors="coerce")
    if pd.isna(start) or pd.isna(end):
        return pd.DataFrame()
    dt = pd.to_datetime(one_minute_df["datetime"], utc=True, errors="coerce")
    window = one_minute_df.loc[(dt > start) & (dt <= end)].copy()
    return window.sort_values("datetime")


def simulate_trade(
    entry_price: float,
    side: float,  # 1.0 long, -1.0 short
    bar_now: pd.Series,
    bar_next: pd.Series,
    one_minute_df: pd.DataFrame,
    size: float,
) -> dict[str, Any]:
    """Simulate fixed TP 0.71% / SL 1.333% on intrabar 1m data."""
    entry = float(entry_price)
    if float(np.sign(side)) >= 0:
        tp = entry * (1.0 + TP_PCT)
        sl = entry * (1.0 - SL_PCT)
        is_long = True
    else:
        tp = entry * (1.0 - TP_PCT)
        sl = entry * (1.0 + SL_PCT)
        is_long = False

    window = _minute_window(one_minute_df, bar_now, bar_next)
    if window.empty:
        exit_price = _get_col(bar_next, ["Close", "close"], default=entry)
        return {
            "exit_price": exit_price,
            "pnl_pct": _pnl_pct(entry, exit_price, side, size),
            "exit_type": "next_bar_close",
            "holding_minutes": 240.0,
        }

    start = pd.to_datetime(bar_now.get("datetime"), utc=True, errors="coerce")
    for _, minute in window.iterrows():
        low = _get_col(minute, ["low", "Low"], default=entry)
        high = _get_col(minute, ["high", "High"], default=entry)
        ts = pd.to_datetime(minute.get("datetime"), utc=True, errors="coerce")

        # Conservative intrabar ordering: SL has priority when both touched.
        if is_long:
            if low <= sl:
                hold = max((ts - start).total_seconds() / 60.0, 1.0) if pd.notna(ts) and pd.notna(start) else 1.0
                return {"exit_price": sl, "pnl_pct": _pnl_pct(entry, sl, side, size), "exit_type": "SL", "holding_minutes": hold}
            if high >= tp:
                hold = max((ts - start).total_seconds() / 60.0, 1.0) if pd.notna(ts) and pd.notna(start) else 1.0
                return {"exit_price": tp, "pnl_pct": _pnl_pct(entry, tp, side, size), "exit_type": "TP", "holding_minutes": hold}
        else:
            if high >= sl:
                hold = max((ts - start).total_seconds() / 60.0, 1.0) if pd.notna(ts) and pd.notna(start) else 1.0
                return {"exit_price": sl, "pnl_pct": _pnl_pct(entry, sl, side, size), "exit_type": "SL", "holding_minutes": hold}
            if low <= tp:
                hold = max((ts - start).total_seconds() / 60.0, 1.0) if pd.notna(ts) and pd.notna(start) else 1.0
                return {"exit_price": tp, "pnl_pct": _pnl_pct(entry, tp, side, size), "exit_type": "TP", "holding_minutes": hold}

    exit_price = _get_col(bar_next, ["Close", "close"], default=entry)
    return {
        "exit_price": exit_price,
        "pnl_pct": _pnl_pct(entry, exit_price, side, size),
        "exit_type": "TIME_EXIT",
        "holding_minutes": 240.0,
    }

