from pathlib import Path
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))

from backtest_full_architecture.execution.fixed_tp_sl import simulate_fixed_tp_sl
from backtest_full_architecture.execution.partial_tp import simulate_partial_tp
from backtest_full_architecture.execution.trailing_stop import simulate_pure_trailing


def _df(rows: list[dict], start: str = "2026-01-01 00:00:00") -> pd.DataFrame:
    index = pd.date_range(start=start, periods=len(rows), freq="1min")
    return pd.DataFrame(rows, index=index)


def test_fixed_tp_sl_long_hits_tp_first() -> None:
    entry_time = pd.Timestamp("2026-01-01 00:00:00")
    candles = _df(
        [
            {"high": 101.0, "low": 99.0, "close": 100.0},
            {"high": 101.0, "low": 99.0, "close": 100.0},
            {"high": 101.0, "low": 99.0, "close": 100.0},
        ]
    )
    result = simulate_fixed_tp_sl(candles, entry_time, 100.0, "LONG")
    assert result.exit_type == "TP"
    assert result.exit_price > 100.0
    assert result.holding_minutes == 1


def test_fixed_tp_sl_returns_time_exit_when_window_empty() -> None:
    entry_time = pd.Timestamp("2026-01-01 00:00:00")
    candles = _df([{"high": 100.0, "low": 100.0, "close": 100.0}], start="2025-12-31 23:50:00")
    result = simulate_fixed_tp_sl(candles, entry_time, 100.0, "LONG")
    assert result.exit_type == "TIME_EXIT"
    assert result.holding_minutes == 0
    assert result.exit_time == entry_time


def test_partial_tp_hits_tp1_then_trailing_stop() -> None:
    entry_time = pd.Timestamp("2026-01-01 00:00:00")
    candles = _df(
        [
            {"high": 100.0, "low": 100.0, "close": 100.0, "atr": 0.1},
            {"high": 100.6, "low": 99.9, "close": 100.5, "atr": 0.1},
            {"high": 100.55, "low": 100.2, "close": 100.4, "atr": 0.1},
        ]
    )
    result = simulate_partial_tp(candles, entry_time, 100.0, "LONG")
    assert result.tp1_hit is True
    assert result.exit_type == "TRAIL_STOP"
    assert result.exit_price > 100.0


def test_pure_trailing_hits_initial_sl_before_activation() -> None:
    entry_time = pd.Timestamp("2026-01-01 00:00:00")
    candles = _df(
        [
            {"high": 100.0, "low": 100.0, "close": 100.0, "atr": 0.2},
            {"high": 100.1, "low": 98.5, "close": 99.0, "atr": 0.2},
        ]
    )
    result = simulate_pure_trailing(candles, entry_time, 100.0, "LONG")
    assert result.exit_type == "SL"
    assert result.exit_price < 100.0

