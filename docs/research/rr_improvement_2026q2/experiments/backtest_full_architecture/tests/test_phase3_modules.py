from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from exhaustion.exhaustion_score import compute_exhaustion_score
from execution.fixed_tp_sl import simulate_trade as simulate_fixed
from execution.partial_tp import simulate_trade as simulate_partial
from execution.trailing_stop import simulate_trade as simulate_trailing


def _bar(ts: str, close: float, atr: float = 100.0) -> pd.Series:
    return pd.Series({"datetime": pd.Timestamp(ts, tz="UTC"), "Close": close, "atr": atr})


def _m1(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_fixed_tp_sl_uses_tp_on_1m_data() -> None:
    now = _bar("2026-01-01 00:00:00", 100.0)
    nxt = _bar("2026-01-01 04:00:00", 100.0)
    one_m = _m1(
        [
            {"datetime": "2026-01-01 00:01:00+00:00", "high": 101.0, "low": 99.8, "close": 100.7},
        ]
    )
    out = simulate_fixed(100.0, 1.0, now, nxt, one_m, 1.0)
    assert out["exit_type"] == "TP"
    assert out["pnl_pct"] > 0.0


def test_partial_tp_runs_and_returns_dict_payload() -> None:
    now = _bar("2026-01-01 00:00:00", 100.0, atr=0.1)
    nxt = _bar("2026-01-01 04:00:00", 100.2)
    one_m = _m1(
        [
            {"datetime": "2026-01-01 00:01:00+00:00", "high": 100.5, "low": 99.95, "close": 100.4},
            {"datetime": "2026-01-01 00:02:00+00:00", "high": 100.45, "low": 100.2, "close": 100.3},
        ]
    )
    out = simulate_partial(100.0, 1.0, now, nxt, one_m, 1.0)
    assert {"exit_price", "pnl_pct", "exit_type", "holding_minutes"}.issubset(out.keys())


def test_trailing_stop_runs_and_returns_dict_payload() -> None:
    now = _bar("2026-01-01 00:00:00", 100.0, atr=0.2)
    nxt = _bar("2026-01-01 04:00:00", 100.0)
    one_m = _m1(
        [
            {"datetime": "2026-01-01 00:01:00+00:00", "high": 100.35, "low": 100.0, "close": 100.3},
            {"datetime": "2026-01-01 00:02:00+00:00", "high": 100.3, "low": 99.8, "close": 100.0},
        ]
    )
    out = simulate_trailing(100.0, 1.0, now, nxt, one_m, 1.0)
    assert {"exit_price", "pnl_pct", "exit_type", "holding_minutes"}.issubset(out.keys())


def test_compute_exhaustion_score_returns_0_1_series() -> None:
    df = pd.DataFrame(
        {
            "Close": [100.0, 101.0, 102.0, 99.0, 100.0],
            "funding": [0.001, 0.002, 0.004, 0.0005, 0.001],
            "cvd": [10.0, 12.0, 9.0, 8.0, 11.0],
        }
    )
    s = compute_exhaustion_score(df)
    assert len(s) == len(df)
    assert float(s.min()) >= 0.0
    assert float(s.max()) <= 1.0

