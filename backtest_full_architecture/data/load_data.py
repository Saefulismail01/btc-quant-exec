"""Phase 1 data loading pipeline for backtest_full_architecture."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[2]
PACKAGE_DIR = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PACKAGE_DIR / "data" / "processed"
DEFAULT_4H_CSV = ROOT_DIR / "backtest" / "data" / "BTC_USDT_4h_2020_2026_with_real_orderflow.csv"


def _find_first_existing(candidates: Iterable[Path]) -> Path | None:
    for path in candidates:
        if path.exists():
            return path
    return None


def resolve_1m_path() -> Path:
    """Resolve 1m parquet path from expected cache locations."""
    candidates = [
        ROOT_DIR / "docs" / "research" / "rr_improvement_2026q2" / "experiments" / "execution_aligned_label_study" / ".cache",
        ROOT_DIR / "docs" / "research" / "rr_improvement_2026q2" / "experiments" / "backtest_full_architecture" / ".cache",
        ROOT_DIR / ".cache",
    ]
    for cache_dir in candidates:
        if not cache_dir.exists():
            continue
        parquet_files = sorted(cache_dir.glob("btc_1m_*.parquet"))
        if parquet_files:
            return parquet_files[-1]
    searched = ", ".join(str(p) for p in candidates)
    raise FileNotFoundError(
        "1m cache file not found. Expected pattern `btc_1m_*.parquet` in one of: "
        f"{searched}"
    )


def _standardize_ohlcv_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
        "cvd": "CVD",
        "fut_oi": "OI",
        "fut_funding_rate": "Funding",
    }
    out = df.copy()
    lower_to_actual = {col.lower(): col for col in out.columns}
    for src_lower, dst in mapping.items():
        if src_lower in lower_to_actual:
            out[dst] = out[lower_to_actual[src_lower]]
    return out


def load_4h_data(csv_path: Path = DEFAULT_4H_CSV) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"4H CSV not found: {csv_path}")
    df = pd.read_csv(csv_path, parse_dates=["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    df = _standardize_ohlcv_columns(df)
    return df


def load_1m_data(parquet_path: Path | None = None) -> pd.DataFrame:
    path = parquet_path or resolve_1m_path()
    df = pd.read_parquet(path)
    time_col = "datetime" if "datetime" in df.columns else "timestamp"
    if time_col not in df.columns:
        raise ValueError("1m parquet must include `datetime` or `timestamp` column")
    df[time_col] = pd.to_datetime(df[time_col], utc=True, errors="coerce")
    df = df.dropna(subset=[time_col]).sort_values(time_col).reset_index(drop=True)
    if time_col != "datetime":
        df = df.rename(columns={time_col: "datetime"})
    df = _standardize_ohlcv_columns(df)
    return df


def save_preprocessed(df_4h: pd.DataFrame, df_1m: pd.DataFrame) -> tuple[Path, Path]:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_4h = PROCESSED_DIR / "preprocessed_4h.parquet"
    out_1m = PROCESSED_DIR / "preprocessed_1m.parquet"
    df_4h.to_parquet(out_4h, index=False)
    df_1m.to_parquet(out_1m, index=False)
    return out_4h, out_1m
