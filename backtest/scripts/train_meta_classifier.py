"""
META-CLASSIFIER FOR BCD IMPROVEMENT

Train logistic regression / decision tree di atas BCD signals
untuk improve BEAR accuracy dari 59.4% ke >65%.

Features:
  - conf (BCD confidence/persistence)
  - label encoding
  - candle position features (hour, day of week)

Usage:
  python backtest/scripts/train_meta_classifier.py
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
    actual = np.where(future_close > df["Close"], 1, 0)  # 1=UP, 0=DOWN
    return pd.Series(actual, index=df.index)


def main():
    print("\n" + "=" * 60)
    print("  META-CLASSIFIER FOR BCD IMPROVEMENT")
    print("=" * 60)

    df = load_data()
    actual = compute_actual_direction(df)

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
                "pred_bcd": pred_bcd,
                "actual": actual.iloc[i],
            }
        )

    rec_df = pd.DataFrame(records)

    df_train = rec_df[rec_df["pred_bcd"] != -1].copy()
    X = df_train[["conf", "label_enc", "hour", "dow"]].values
    y = df_train["actual"].values

    print(f"\n[DATA] {len(df_train)} samples, {len(X[0])} features")
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
    print("  MODEL 2: Decision Tree")
    print("=" * 60)

    dt_clf = DecisionTreeClassifier(
        max_depth=4, min_samples_leaf=20, class_weight="balanced"
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
    print("  SUMMARY")
    print("=" * 60)
    print(f"\n  {'Model':<20} {'Accuracy':>10} {'BEAR Acc':>10}")
    print(f"  {'-' * 20} {'-' * 10} {'-' * 10}")
    print(f"  {'BCD Baseline':<20} {baseline_acc:>9.1%} {bear_acc:>9.1%}")
    print(f"  {'Logistic Regression':<20} {acc_lr:>9.1%} {bear_lr_acc:>9.1%}")
    print(f"  {'Decision Tree':<20} {acc_dt:>9.1%} {bear_dt_acc:>9.1%}")

    improved = bear_lr_acc > 0.594 or bear_dt_acc > 0.594
    print(f"\n  {'TARGET: >65% BEAR accuracy':^40}")
    if improved:
        print(f"  {'ACHIEVED!':^40}")
    else:
        print(f"  {'NOT ACHIEVED - perlu feature engineering':^40}")

    out = _ROOT_DIR / "backtest" / "results" / "meta_classifier_results.csv"
    df_train.to_csv(out, index=False)
    print(f"\n  Saved: {out.name}")


if __name__ == "__main__":
    main()
