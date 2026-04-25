"""Phase 1 feature extraction for Agent A."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[6]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from cloud_core.engines.layer1_bcd import BayesianChangepointModel
from cloud_core.engines.layer2_ema import EMASignalModel
from cloud_core.engines.layer4_risk import RiskModel

try:
    from .load_data import PROCESSED_DIR, load_1m_data, load_4h_data, save_preprocessed
except ImportError:
    from load_data import PROCESSED_DIR, load_1m_data, load_4h_data, save_preprocessed


@dataclass
class LContextConfig:
    min_warmup: int = 220
    step: int = 12


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100 - (100 / (1 + rs))


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    hl = df["High"] - df["Low"]
    hc = (df["High"] - df["Close"].shift(1)).abs()
    lc = (df["Low"] - df["Close"].shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def compute_technical_features(df_4h: pd.DataFrame) -> pd.DataFrame:
    out = df_4h.copy()
    close = out["Close"]

    out["rsi_14"] = _rsi(close, period=14)

    ema12 = _ema(close, span=12)
    ema26 = _ema(close, span=26)
    macd_line = ema12 - ema26
    signal = _ema(macd_line, span=9)
    out["macd_hist"] = macd_line - signal

    ema20 = _ema(close, span=20)
    out["ema20_dist"] = (close - ema20) / ema20.replace(0.0, np.nan)
    out["log_return"] = np.log(close / close.shift(1))

    atr14 = _atr(out, period=14)
    out["norm_atr"] = atr14 / close.replace(0.0, np.nan)

    if "CVD" in out.columns and "Volume" in out.columns:
        out["norm_cvd"] = out["CVD"] / out["Volume"].replace(0.0, np.nan)
    else:
        out["norm_cvd"] = 0.0

    out["funding"] = out["Funding"] if "Funding" in out.columns else 0.0
    out["oi_change"] = out["OI"].pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)

    return out


def compute_l1_l2_l4_context(df_4h: pd.DataFrame, cfg: LContextConfig | None = None) -> pd.DataFrame:
    cfg = cfg or LContextConfig()
    bcd = BayesianChangepointModel()
    ema_model = EMASignalModel()
    risk_model = RiskModel()

    out = df_4h.copy()
    out["l1_regime"] = "unknown"
    out["l1_confidence"] = np.nan
    out["l2_vote"] = np.nan
    out["l4_multiplier"] = np.nan
    out["l4_volatility_ratio"] = np.nan

    fit_window = out.iloc[: max(cfg.min_warmup, 300)].copy()
    bcd.fit(fit_window)

    for idx in range(cfg.min_warmup, len(out), cfg.step):
        hist = out.iloc[: idx + 1]
        regime, conf, _ = bcd.predict_regime(hist)
        out.at[idx, "l1_regime"] = regime
        out.at[idx, "l1_confidence"] = conf

        out.at[idx, "l2_vote"] = ema_model.get_directional_vote(hist)
        out.at[idx, "l4_multiplier"] = risk_model.get_multiplier(hist)
        out.at[idx, "l4_volatility_ratio"] = risk_model.calculate_volatility_ratio(hist)

    out[["l1_regime"]] = out[["l1_regime"]].replace("unknown", np.nan).ffill().fillna("unknown")
    out[["l1_confidence", "l2_vote", "l4_multiplier", "l4_volatility_ratio"]] = out[
        ["l1_confidence", "l2_vote", "l4_multiplier", "l4_volatility_ratio"]
    ].ffill()

    return out


def run_phase1() -> tuple[Path, Path, Path]:
    df_4h = load_4h_data()
    df_1m = load_1m_data()

    enriched_4h = compute_technical_features(df_4h)
    enriched_4h = compute_l1_l2_l4_context(enriched_4h)

    out_4h, out_1m = save_preprocessed(enriched_4h, df_1m)
    features_path = PROCESSED_DIR / "features.parquet"
    feature_cols = [
        "datetime",
        "rsi_14",
        "macd_hist",
        "ema20_dist",
        "log_return",
        "norm_atr",
        "norm_cvd",
        "funding",
        "oi_change",
        "l1_regime",
        "l1_confidence",
        "l2_vote",
        "l4_multiplier",
        "l4_volatility_ratio",
    ]
    enriched_4h[feature_cols].to_parquet(features_path, index=False)
    return out_4h, out_1m, features_path


if __name__ == "__main__":
    out_4h, out_1m, out_features = run_phase1()
    print("Phase 1 complete.")
    print(f"Data at: {out_4h}")
    print(f"Data at: {out_1m}")
    print(f"Features at: {out_features}")
