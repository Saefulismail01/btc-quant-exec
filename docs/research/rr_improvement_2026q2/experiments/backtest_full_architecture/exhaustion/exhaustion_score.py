"""Exhaustion score computation for each 4H row."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _safe_col(df: pd.DataFrame, names: list[str], default: float = 0.0) -> pd.Series:
    for name in names:
        if name in df.columns:
            return pd.to_numeric(df[name], errors="coerce").fillna(default)
    return pd.Series(default, index=df.index, dtype=float)


def _rolling_zscore(s: pd.Series, window: int = 60) -> pd.Series:
    mean = s.rolling(window=window, min_periods=max(10, window // 3)).mean()
    std = s.rolling(window=window, min_periods=max(10, window // 3)).std(ddof=0).replace(0.0, np.nan)
    return ((s - mean) / std).fillna(0.0)


def compute_exhaustion_score(df: pd.DataFrame) -> pd.Series:
    """Return exhaustion score in [0, 1] aligned to input rows."""
    close = _safe_col(df, ["Close", "close"], default=0.0)
    funding = _safe_col(df, ["funding", "FundingRate", "funding_rate"], default=0.0)
    cvd = _safe_col(df, ["cvd", "CVD"], default=0.0)

    ema20 = close.ewm(span=20, adjust=False).mean().replace(0.0, np.nan)
    price_stretch = ((close - ema20) / ema20).fillna(0.0).abs().clip(0.0, 0.05) / 0.05

    funding_z = _rolling_zscore(funding, window=60).abs().clip(0.0, 3.0) / 3.0

    price_z = _rolling_zscore(close.pct_change(fill_method=None).fillna(0.0), window=40)
    cvd_z = _rolling_zscore(cvd.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0), window=40)
    cvd_div = (price_z - cvd_z).abs().clip(0.0, 3.0) / 3.0

    score = (0.30 * funding_z) + (0.35 * price_stretch) + (0.35 * cvd_div)
    return score.clip(0.0, 1.0).fillna(0.0)

