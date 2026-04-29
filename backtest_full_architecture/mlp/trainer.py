from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import joblib
import numpy as np
import pandas as pd
import pandas_ta as ta
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

FEATURE_COLS = [
    "rsi_14",
    "macd_hist",
    "ema20_dist",
    "log_return",
    "norm_atr",
    "norm_cvd",
    "funding",
    "oi_change",
]

TP_PCT = 0.0071
SL_PCT = 0.01333
BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_4H_PATH = BASE_DIR / "backtest" / "data" / "BTC_USDT_4h_2020_2026_with_real_orderflow.csv"
DEFAULT_1M_CACHE_DIR = (
    BASE_DIR
    / "docs"
    / "research"
    / "rr_improvement_2026q2"
    / "experiments"
    / "execution_aligned_label_study"
    / ".cache"
)


@dataclass
class ValidationResult:
    model_name: str
    accuracy_mean: float
    accuracy_std: float
    f1_mean: float
    f1_std: float
    folds_used: int
    train_rows: int
    label_type: str


def _normalize_ohlcv_cols(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d.columns = [c.lower() for c in d.columns]
    rename_map = {"datetime": "timestamp"}
    d = d.rename(columns=rename_map)
    if "timestamp" not in d.columns:
        raise ValueError("Missing timestamp/datetime column in 4H source data")
    ts = d["timestamp"]
    if np.issubdtype(ts.dtype, np.number):
        d["timestamp"] = pd.to_datetime(ts, unit="ms", utc=True)
    else:
        d["timestamp"] = pd.to_datetime(ts, utc=True)
    return d


def load_4h_frame(csv_path: Path = DEFAULT_4H_PATH) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df = _normalize_ohlcv_cols(df)
    for required in ("open", "high", "low", "close"):
        if required not in df.columns:
            raise ValueError(f"Missing required column: {required}")
    if "volume" not in df.columns:
        df["volume"] = 0.0
    if "cvd" not in df.columns:
        df["cvd"] = 0.0
    if "funding" not in df.columns:
        df["funding"] = 0.0
    if "oi" not in df.columns:
        df["oi"] = np.nan
    out = df.set_index("timestamp").sort_index()
    return out


def load_1m_cache(cache_dir: Path = DEFAULT_1M_CACHE_DIR) -> pd.DataFrame:
    files = sorted(cache_dir.glob("btc_1m_*.parquet"))
    if not files:
        raise FileNotFoundError(f"No 1m cache parquet found in: {cache_dir}")
    parts = [pd.read_parquet(p) for p in files]
    df = pd.concat(parts).sort_index()
    if "timestamp" in df.columns:
        ts = df["timestamp"]
        if np.issubdtype(ts.dtype, np.number):
            idx = pd.to_datetime(ts, unit="ms", utc=True)
        else:
            idx = pd.to_datetime(ts, utc=True)
        df = df.drop(columns=["timestamp"])
        df.index = idx
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df[~df.index.duplicated(keep="last")].sort_index()


def build_features(df_4h: pd.DataFrame) -> pd.DataFrame:
    d = df_4h.copy()
    close = d["close"]
    d["rsi_14"] = ta.rsi(close, length=14)
    macd_df = ta.macd(close, fast=12, slow=26, signal=9)
    d["macd_hist"] = (
        macd_df["MACDh_12_26_9"] if macd_df is not None and "MACDh_12_26_9" in macd_df else 0.0
    )
    ema20 = ta.ema(close, length=20)
    d["ema20_dist"] = (close - ema20) / ema20
    d["log_return"] = np.log(close / close.shift(1))
    atr = ta.atr(d["high"], d["low"], close, length=14)
    d["norm_atr"] = atr / close
    d["norm_cvd"] = (d["cvd"] / d["volume"].replace(0, np.nan)).fillna(0.0)
    d["funding"] = d.get("funding", 0.0).fillna(0.0)
    d["oi_change"] = (
        d.get("oi", pd.Series(index=d.index, data=np.nan))
        .pct_change(fill_method=None)
        .fillna(0.0)
    )
    return d


def add_baseline_label(features: pd.DataFrame) -> pd.DataFrame:
    d = features.copy()
    d["future_close_4h"] = d["close"].shift(-1)
    d["price_move_pct"] = (d["future_close_4h"] - d["close"]) / d["close"]
    d["thr"] = 0.5 * d["norm_atr"] * np.sqrt(1.0)
    move = d["price_move_pct"].values
    thr = d["thr"].values
    labels = np.where(move > thr, 2, np.where(move < -thr, 0, 1)).astype(float)
    labels[np.isnan(move) | np.isnan(thr)] = np.nan
    d["label"] = labels
    return d


def _tp_before_sl(high: np.ndarray, low: np.ndarray, entry: float) -> int:
    tp = entry * (1.0 + TP_PCT)
    sl = entry * (1.0 - SL_PCT)
    for i in range(len(high)):
        # Pessimistic intrabar ordering: low then high.
        if low[i] <= sl:
            return 0
        if high[i] >= tp:
            return 1
    return -1


def add_exec_aligned_label(features: pd.DataFrame, df_1m: pd.DataFrame, max_forward_bars: int = 7 * 24 * 60) -> pd.DataFrame:
    d = features.copy()
    t1 = df_1m.index.astype("int64").to_numpy()
    high_all = df_1m["high"].to_numpy()
    low_all = df_1m["low"].to_numpy()
    labels = np.full(len(d), np.nan)
    for i, (idx, row) in enumerate(d.iterrows()):
        entry = float(row["close"])
        start = int(np.searchsorted(t1, int(pd.Timestamp(idx).value), side="right"))
        if start >= len(low_all) or (start + max_forward_bars) > len(low_all):
            continue
        labels[i] = _tp_before_sl(
            high_all[start : start + max_forward_bars],
            low_all[start : start + max_forward_bars],
            entry,
        )
    d["label"] = labels
    return d


def add_1h_label(features: pd.DataFrame, df_1m: pd.DataFrame) -> pd.DataFrame:
    d = features.copy()
    close_1m = df_1m["close"].sort_index()
    one_hour_forward = []
    for ts, row in d.iterrows():
        target_ts = ts + pd.Timedelta(hours=1)
        pos = close_1m.index.searchsorted(target_ts, side="left")
        if pos >= len(close_1m):
            one_hour_forward.append(np.nan)
            continue
        future_close = float(close_1m.iloc[pos])
        ret = (future_close - float(row["close"])) / float(row["close"])
        one_hour_forward.append(ret)
    d["ret_1h"] = one_hour_forward
    d["label"] = (d["ret_1h"] > 0.0).astype(float)
    d.loc[d["ret_1h"].isna(), "label"] = np.nan
    return d


def _walkforward_metrics(X: np.ndarray, y: np.ndarray, n_splits: int = 4) -> tuple[list[float], list[float]]:
    tscv = TimeSeriesSplit(n_splits=max(2, min(n_splits, len(y) // 20)))
    accs: list[float] = []
    f1s: list[float] = []
    for train_idx, test_idx in tscv.split(X):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        if len(np.unique(y_train)) < 2:
            continue
        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)
        clf = MLPClassifier(
            hidden_layer_sizes=(128, 64),
            activation="relu",
            solver="adam",
            max_iter=400,
            random_state=42,
        )
        clf.fit(X_train_s, y_train)
        pred = clf.predict(X_test_s)
        accs.append(float(accuracy_score(y_test, pred)))
        if len(np.unique(y)) == 2:
            f1s.append(float(f1_score(y_test, pred, average="binary", pos_label=1, zero_division=0)))
        else:
            f1s.append(float(f1_score(y_test, pred, average="macro", zero_division=0)))
    return accs, f1s


def train_variant(
    model_name: str,
    labeled_frame: pd.DataFrame,
    model_path: Path,
    label_type: str,
    min_rows: int = 120,
) -> ValidationResult:
    clean = labeled_frame.dropna(subset=FEATURE_COLS + ["label"]).copy()
    if label_type == "execution_aligned":
        clean = clean[(clean["label"] == 0) | (clean["label"] == 1)]
    if len(clean) < min_rows:
        raise ValueError(f"{model_name}: insufficient rows after labeling ({len(clean)} < {min_rows})")

    X = clean[FEATURE_COLS].to_numpy()
    y = clean["label"].astype(int).to_numpy()
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    clf = MLPClassifier(
        hidden_layer_sizes=(128, 64),
        activation="relu",
        solver="adam",
        max_iter=400,
        random_state=42,
    )
    clf.fit(Xs, y)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model_name": model_name,
            "feature_cols": FEATURE_COLS,
            "label_type": label_type,
            "scaler": scaler,
            "model": clf,
        },
        model_path,
    )

    accs, f1s = _walkforward_metrics(X, y)
    if not accs:
        raise ValueError(f"{model_name}: walk-forward produced zero usable folds")
    return ValidationResult(
        model_name=model_name,
        accuracy_mean=float(np.mean(accs)),
        accuracy_std=float(np.std(accs)) if len(accs) > 1 else 0.0,
        f1_mean=float(np.mean(f1s)),
        f1_std=float(np.std(f1s)) if len(f1s) > 1 else 0.0,
        folds_used=len(accs),
        train_rows=len(clean),
        label_type=label_type,
    )


def write_validation_rows(output_csv: Path, rows: list[ValidationResult]) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([r.__dict__ for r in rows])
    df.to_csv(output_csv, index=False)


def prepare_common_frames(
    csv_4h: Path = DEFAULT_4H_PATH,
    cache_1m_dir: Path = DEFAULT_1M_CACHE_DIR,
    training_days: int = 180,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df_4h = load_4h_frame(csv_4h)
    df_1m = load_1m_cache(cache_1m_dir)
    if training_days > 0:
        end_ts = df_4h.index.max()
        start_ts = end_ts - pd.Timedelta(days=training_days)
        df_4h = df_4h[df_4h.index >= start_ts].copy()
        df_1m = df_1m[df_1m.index >= start_ts].copy()
    features = build_features(df_4h)
    return features, df_1m

