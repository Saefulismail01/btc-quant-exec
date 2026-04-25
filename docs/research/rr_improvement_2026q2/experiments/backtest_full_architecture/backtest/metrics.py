"""Metrics utilities for backtest full architecture."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class MetricsSummary:
    trade_count: int
    win_rate: float
    rr: float
    ev: float
    sharpe: float
    max_drawdown: float
    profit_factor: float
    avg_winner: float
    avg_loser: float
    avg_holding_minutes: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator == 0.0:
        return default
    return float(numerator / denominator)


def _compute_max_drawdown(equity_curve: pd.Series) -> float:
    if equity_curve.empty:
        return 0.0
    running_peak = equity_curve.cummax()
    drawdown = (equity_curve - running_peak) / running_peak.replace(0.0, np.nan)
    return float(drawdown.min()) if not drawdown.empty else 0.0


def summarize_trades(trades: pd.DataFrame, bars_per_year: int = 365) -> MetricsSummary:
    """Compute primary and secondary metrics from executed trades."""
    if trades.empty:
        return MetricsSummary(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    pnl = trades["pnl_pct"].fillna(0.0)
    winners = pnl[pnl > 0.0]
    losers = pnl[pnl < 0.0]

    win_rate = float((pnl > 0.0).mean())
    avg_winner = float(winners.mean()) if not winners.empty else 0.0
    avg_loser = float(losers.mean()) if not losers.empty else 0.0
    rr = _safe_div(avg_winner, abs(avg_loser), default=0.0)
    ev = float(pnl.mean())

    std = float(pnl.std(ddof=0))
    sharpe = _safe_div(ev, std, default=0.0) * np.sqrt(bars_per_year) if std > 0 else 0.0

    equity_curve = (1.0 + pnl).cumprod()
    max_drawdown = _compute_max_drawdown(equity_curve)

    gross_profit = float(winners.sum()) if not winners.empty else 0.0
    gross_loss = float(abs(losers.sum())) if not losers.empty else 0.0
    profit_factor = _safe_div(gross_profit, gross_loss, default=0.0)

    avg_holding_minutes = float(trades["holding_minutes"].fillna(0.0).mean())

    return MetricsSummary(
        trade_count=len(trades),
        win_rate=win_rate,
        rr=rr,
        ev=ev,
        sharpe=float(sharpe),
        max_drawdown=max_drawdown,
        profit_factor=profit_factor,
        avg_winner=avg_winner,
        avg_loser=avg_loser,
        avg_holding_minutes=avg_holding_minutes,
    )


def conditional_win_rates(trades: pd.DataFrame) -> dict[str, float]:
    """Compute conditional win rates for required contexts."""
    if trades.empty:
        return {}

    out: dict[str, float] = {}

    if "l1_regime" in trades.columns:
        by_regime = trades.groupby("l1_regime")["pnl_pct"].apply(lambda s: float((s > 0).mean()))
        for regime, wr in by_regime.items():
            out[f"wr_l1_{regime}"] = wr

    if "l4_volatility_bucket" in trades.columns:
        by_vol = trades.groupby("l4_volatility_bucket")["pnl_pct"].apply(lambda s: float((s > 0).mean()))
        for bucket, wr in by_vol.items():
            out[f"wr_l4_{bucket}"] = wr

    if "exhaustion_bucket" in trades.columns:
        by_exhaust = trades.groupby("exhaustion_bucket")["pnl_pct"].apply(lambda s: float((s > 0).mean()))
        for bucket, wr in by_exhaust.items():
            out[f"wr_exhaust_{bucket}"] = wr

    return out
