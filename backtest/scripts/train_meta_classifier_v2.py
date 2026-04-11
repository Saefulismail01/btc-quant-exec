"""
META-CLASSIFIER FOR BCD IMPROVEMENT V2

Train logistic regression / decision tree di atas BCD signals
dengan enhanced features untuk improve BEAR accuracy ke >65%.

Features:
  - conf (BCD confidence/persistence)
  - label encoding
  - candle position features (hour, day of week)
  - price momentum (returns)
  - volatility (ATR)
  - volume features

Usage:
  python backtest/scripts/train_meta_classifier_v2.py
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.tree import DecisionTreeClassifier

warnings.filterwarnings("ignore")

_ROOT_DIR = Path(r"C:\Users\ThinkPad\Documents\Windsurf\btc-scalping-execution_layer")

FORWARD_H = 4
WARMUP = 200
SAMPLE_EVERY = 8


def load_data() -> pd.DataFrame:
    for name in ["BTC_USDT_4h_2025.csv", "BTC_USDT_4h_2023.csv"]:
        p = _ROOT_DIR / "backtest" / "data" / name
        if p.exists():
            df = pd.read_csv(p)
            df.columns = [c.capitalize() for c in df.columns]
            df = df.sort_values("Datetime").reset_index(drop=True)
            print(f"[LOAD] {len(df)} candles dari {name}")
            return df
    raise FileNotFoundError("Data tidak ditemukan")


def compute_actual_direction(df: pd.DataFrame) -> pd.Series:
    future_close = df["Close"].shift(-FORWARD_H)
    actual = np.where(future_close > df["Close"], 1, 0)
    return pd.Series(actual, index=df.index)


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["High"]
    low = df["Low"]
    prev_close = df["Close"].shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr


def main():
    print("\n" + "=" * 60)
    print("  META-CLASSIFIER V2 - ENHANCED FEATURES")
    print("=" * 60)

    df = load_data()
    actual = compute_actual_direction(df)

    df["Return_1"] = df["Close"].pct_change(1)
    df["Return_4"] = df["Close"].pct_change(4)
    df["Return_8"] = df["Close"].pct_change(8)
    df["ATR"] = compute_atr(df)
    df["ATR_Pct"] = df["ATR"] / df["Close"]
    df["Vol_MA4"] = df["Volume"].rolling(4).mean()
    df["Vol_Ratio"] = df["Volume"] / df["Vol_MA4"]

    sys.path.insert(0, str(_ROOT_DIR / "backend" / "app" / "core"))
    sys.path.insert(0, str(_ROOT_DIR / "backend" / "app" / "core" / "engines"))
    sys.path.insert(0, str(_ROOT_DIR / "backend"))

    from engines.layer1_bcd import BayesianChangepointModel as BCDModel

    bcd = BCDModel()
    bcd.train_global(df)
    global_states, _ = bcd.get_state_sequence_raw(df)

    tm = bcd._transition_matrix
    seg_persistence = {}
    if tm is not None:
        n = len(tm)
        for sid in bcd.state_map:
            seg_persistence[sid] = float(tm[sid, sid]) if sid < n else 0.5
    else:
        for sid in bcd.state_map:
            seg_persistence[sid] = 0.5

    n = len(df)
    indices = list(range(WARMUP, n - FORWARD_H, SAMPLE_EVERY))

    records = []
    for i in indices:
        seg_id = int(global_states[i])
        label = bcd.state_map.get(seg_id, "Unknown")
        persist = seg_persistence.get(seg_id, 0.5)

        dt = pd.to_datetime(df["Datetime"].iloc[i])

        label_enc = 0
        if "Bullish" in label:
            pred_bcd = 1
        elif "Bearish" in label:
            pred_bcd = 0
            label_enc = 1
        else:
            pred_bcd = -1
            label_enc = 2

        records.append(
            {
                "i": i,
                "conf": persist,
                "label_enc": label_enc,
                "hour": dt.hour,
                "dow": dt.dayofweek,
                "ret_1": df["Return_1"].iloc[i],
                "ret_4": df["Return_4"].iloc[i],
                "ret_8": df["Return_8"].iloc[i],
                "atr_pct": df["ATR_Pct"].iloc[i],
                "vol_ratio": df["Vol_Ratio"].iloc[i],
                "pred_bcd": pred_bcd,
                "actual": actual.iloc[i],
            }
        )

    rec_df = pd.DataFrame(records)
    rec_df = rec_df.dropna()

    df_train = rec_df[rec_df["pred_bcd"] != -1].copy()

    feature_cols = [
        "conf",
        "label_enc",
        "hour",
        "dow",
        "ret_1",
        "ret_4",
        "ret_8",
        "atr_pct",
        "vol_ratio",
    ]
    X = df_train[feature_cols].values
    y = df_train["actual"].values

    print(f"\n[DATA] {len(df_train)} samples, {len(feature_cols)} features")
    print(f"  Class distribution: UP={sum(y)}, DOWN={len(y) - sum(y)}")

    print("\n" + "=" * 60)
    print("  BASELINE: BCD saja")
    print("=" * 60)
    baseline_acc = df_train["pred_bcd"].eq(df_train["actual"]).mean()
    print(f"  BCD accuracy: {baseline_acc:.1%}")

    bear_mask = df_train["label_enc"] == 1
    bear_acc = (
        df_train.loc[bear_mask, "pred_bcd"].eq(df_train.loc[bear_mask, "actual"]).mean()
    )
    print(f"  BEAR accuracy: {bear_acc:.1%}")

    print("\n" + "=" * 60)
    print("  MODEL 1: Logistic Regression")
    print("=" * 60)

    lr = LogisticRegression(max_iter=1000, C=1.0, class_weight="balanced")
    cv_scores = cross_val_score(lr, X, y, cv=5, scoring="accuracy")
    print(f"  CV Accuracy: {cv_scores.mean():.1%} (+/- {cv_scores.std():.1%})")

    lr.fit(X, y)
    pred_lr = lr.predict(X)
    acc_lr = (pred_lr == y).mean()
    print(f"  Train accuracy: {acc_lr:.1%}")

    df_train["pred_lr"] = pred_lr
    bear_lr_acc = (
        df_train.loc[bear_mask, "pred_lr"].eq(df_train.loc[bear_mask, "actual"]).mean()
    )
    print(f"  BEAR accuracy: {bear_lr_acc:.1%}")

    print("\n" + "=" * 60)
    print("  MODEL 2: Decision Tree (tuned)")
    print("=" * 60)

    dt_clf = DecisionTreeClassifier(
        max_depth=5, min_samples_leaf=15, class_weight="balanced"
    )
    cv_scores_dt = cross_val_score(dt_clf, X, y, cv=5, scoring="accuracy")
    print(f"  CV Accuracy: {cv_scores_dt.mean():.1%} (+/- {cv_scores_dt.std():.1%})")

    dt_clf.fit(X, y)
    pred_dt = dt_clf.predict(X)
    acc_dt = (pred_dt == y).mean()
    print(f"  Train accuracy: {acc_dt:.1%}")

    df_train["pred_dt"] = pred_dt
    bear_dt_acc = (
        df_train.loc[bear_mask, "pred_dt"].eq(df_train.loc[bear_mask, "actual"]).mean()
    )
    print(f"  BEAR accuracy: {bear_dt_acc:.1%}")

    print("\n" + "=" * 60)
    print("  FEATURE IMPORTANCE (Decision Tree)")
    print("=" * 60)
    importance = pd.DataFrame(
        {"feature": feature_cols, "importance": dt_clf.feature_importances_}
    ).sort_values("importance", ascending=False)
    for _, row in importance.iterrows():
        print(f"  {row['feature']:>12} : {row['importance']:.3f}")

    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"\n  {'Model':<20} {'Accuracy':>10} {'BEAR Acc':>10}")
    print(f"  {'-' * 20} {'-' * 10} {'-' * 10}")
    print(f"  {'BCD Baseline':<20} {baseline_acc:>9.1%} {bear_acc:>9.1%}")
    print(f"  {'Logistic Regression':<20} {acc_lr:>9.1%} {bear_lr_acc:>9.1%}")
    print(f"  {'Decision Tree':<20} {acc_dt:>9.1%} {bear_dt_acc:>9.1%}")

    best_bear = max(bear_acc, bear_lr_acc, bear_dt_acc)
    improved = best_bear > 0.65
    print(f"\n  {'TARGET: >65% BEAR accuracy':^40}")
    print(f"  Best BEAR: {best_bear:.1%}")
    if improved:
        print(f"  {'ACHIEVED!':^40}")
    else:
        gap = 0.65 - best_bear
        print(f"  Gap: {gap:.1%} - perlu feature tambahan")

    out = _ROOT_DIR / "backtest" / "results" / "meta_classifier_v2_results.csv"
    df_train.to_csv(out, index=False)
    print(f"\n  Saved: {out.name}")


if __name__ == "__main__":
    main()
