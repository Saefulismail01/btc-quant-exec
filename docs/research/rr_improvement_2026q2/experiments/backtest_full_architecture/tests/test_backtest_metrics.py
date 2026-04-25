from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from backtest.metrics import conditional_win_rates, summarize_trades


def test_summarize_trades_basic() -> None:
    trades = pd.DataFrame(
        [
            {"pnl_pct": 0.01, "holding_minutes": 120},
            {"pnl_pct": -0.005, "holding_minutes": 240},
            {"pnl_pct": 0.02, "holding_minutes": 180},
            {"pnl_pct": -0.01, "holding_minutes": 60},
        ]
    )
    summary = summarize_trades(trades)
    assert summary.trade_count == 4
    assert 0.0 <= summary.win_rate <= 1.0
    assert summary.avg_holding_minutes == 150.0
    assert summary.max_drawdown <= 0.0


def test_conditional_win_rates() -> None:
    trades = pd.DataFrame(
        [
            {
                "pnl_pct": 0.01,
                "l1_regime": "trend",
                "l4_volatility_bucket": "normal",
                "exhaustion_bucket": "low",
            },
            {
                "pnl_pct": -0.01,
                "l1_regime": "trend",
                "l4_volatility_bucket": "high",
                "exhaustion_bucket": "mid",
            },
            {
                "pnl_pct": 0.02,
                "l1_regime": "range",
                "l4_volatility_bucket": "normal",
                "exhaustion_bucket": "high",
            },
        ]
    )
    wr = conditional_win_rates(trades)
    assert "wr_l1_trend" in wr
    assert "wr_l4_normal" in wr
    assert "wr_exhaust_high" in wr
