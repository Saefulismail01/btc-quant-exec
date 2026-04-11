"""
  BCD HIGH-CONFIDENCE ACCURACY TEST

  Mengukur akurasi L1 BCD berdasarkan confidence threshold.
  Hipotesis: candle dengan BCD posterior tinggi punya akurasi lebih baik dari 57.4%.

  Output:
    - Akurasi BCD di semua confidence level (0.3, 0.5, 0.6, 0.7, 0.8)
    - Distribusi regime label
    - Coverage (% candle yang masuk threshold)

Usage:
    cd btc-scalping-execution_layer
    python backtest/scripts/evaluate_bcd_confidence.py
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

_ROOT_DIR = Path(r"C:\Users\ThinkPad\Documents\Windsurf\btc-scalping-execution_layer")
sys.path.insert(0, str(_ROOT_DIR / "backend" / "app" / "core"))
sys.path.insert(0, str(_ROOT_DIR / "backend" / "app" / "core" / "engines"))
sys.path.insert(0, str(_ROOT_DIR / "backend"))

from engines.layer1_bcd import BayesianChangepointModel as BCDModel

FORWARD_H = 4   # prediksi arah 4 candle = 16 jam ke depan
WARMUP    = 200
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
    actual = np.where(future_close > df["Close"], "UP", "DOWN")
    return pd.Series(actual, index=df.index)


def main():
    print("\n" + "=" * 60)
    print("  BCD HIGH-CONFIDENCE ACCURACY TEST")
    print("=" * 60)

    df = load_data()
    actual = compute_actual_direction(df)

    # ── Train BCD sekali ──────────────────────────────────────────
    bcd = BCDModel()
    bcd.train_global(df)
    print(f"  BCD trained: {len(bcd._changepoints)} changepoints")

    # ── Pre-compute global state sequence ─────────────────────────
    print("  Pre-computing state sequence (~30s)...")
    global_states, global_idx = bcd.get_state_sequence_raw(df)
    print(f"  State sequence: {len(global_states)} rows")

    # ── Hitung run-length confidence dari R matrix ────────────────
    # R[-1] sudah dihitung saat train_global (via get_current_regime)
    # Kita perlu confidence per-candle — approx dari segmen persistence
    # Cara: confidence = P(run_length >= 3) dari _R matrix terakhir
    # Untuk efficiency, kita pakai transition matrix persistence sebagai proxy

    # Ambil persistence per segment dari state_map + transition matrix
    seg_persistence = {}
    tm = bcd._transition_matrix
    if tm is not None:
        n = len(tm)
        for sid in bcd.state_map:
            if sid < n:
                seg_persistence[sid] = float(tm[sid, sid])
            else:
                seg_persistence[sid] = 0.5
    else:
        for sid in bcd.state_map:
            seg_persistence[sid] = 0.5

    # ── Collect results per sample ────────────────────────────────
    n = len(df)
    indices = list(range(WARMUP, n - FORWARD_H, SAMPLE_EVERY))
    total = len(indices)
    print(f"  Evaluating {total} samples...")

    records = []
    for i in indices:
        seg_id   = int(global_states[i])
        label    = bcd.state_map.get(seg_id, "Unknown")
        persist  = seg_persistence.get(seg_id, 0.5)

        if "Bullish" in label:
            pred = "UP"
        elif "Bearish" in label:
            pred = "DOWN"
        else:
            pred = "NEUTRAL"

        act = actual.iloc[i]
        correct = (pred == act) if pred != "NEUTRAL" else None

        records.append({
            "i":         i,
            "datetime":  df["Datetime"].iloc[i],
            "label":     label,
            "pred":      pred,
            "actual":    act,
            "correct":   correct,
            "conf":      persist,
        })

    rec_df = pd.DataFrame(records)

    # ── Print hasil per confidence threshold ──────────────────────
    print("\n" + "=" * 60)
    print("  HASIL — Akurasi BCD per Confidence Threshold")
    print("=" * 60)
    print(f"\n  {'Threshold':>10}  {'Coverage':>8}  {'Samples':>7}  {'Accuracy':>9}  {'UP%':>6}  {'DOWN%':>6}")
    print("  " + "-" * 58)

    directional = rec_df[rec_df["pred"] != "NEUTRAL"].copy()

    thresholds = [0.0, 0.3, 0.5, 0.6, 0.7, 0.8]
    for thr in thresholds:
        subset = directional[directional["conf"] >= thr]
        if len(subset) == 0:
            print(f"  {thr:>10.1f}  {'–':>8}  {'–':>7}  {'–':>9}")
            continue
        acc      = subset["correct"].mean()
        coverage = len(subset) / total
        up_pct   = (subset["pred"] == "UP").mean()
        dn_pct   = (subset["pred"] == "DOWN").mean()
        print(f"  {thr:>10.1f}  {coverage:>7.1%}  {len(subset):>7d}  {acc:>9.1%}  {up_pct:>5.1%}  {dn_pct:>5.1%}")

    # ── Distribusi label ──────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  DISTRIBUSI REGIME LABEL")
    print("=" * 60)
    label_counts = rec_df["label"].value_counts()
    for lbl, cnt in label_counts.items():
        pct = cnt / total
        # Akurasi per label
        sub = directional[directional["label"] == lbl]
        acc_str = f"{sub['correct'].mean():.1%}" if len(sub) > 0 else "N/A"
        print(f"  {lbl:35s} {cnt:4d} ({pct:.1%})  acc={acc_str}")

    # ── Akurasi per arah prediksi ─────────────────────────────────
    print("\n" + "=" * 60)
    print("  AKURASI PER ARAH PREDIKSI (semua candle)")
    print("=" * 60)
    for pred_dir in ["UP", "DOWN"]:
        sub = directional[directional["pred"] == pred_dir]
        if len(sub) == 0:
            continue
        acc = sub["correct"].mean()
        print(f"  Prediksi {pred_dir:4s}: {len(sub):3d} candle  acc={acc:.1%}")

    # ── Sweet spot: threshold optimal ────────────────────────────
    print("\n" + "=" * 60)
    print("  SWEET SPOT — Threshold Terbaik")
    print("=" * 60)
    best_acc, best_thr, best_n = 0, 0, 0
    for thr in np.arange(0.0, 0.95, 0.05):
        sub = directional[directional["conf"] >= thr]
        if len(sub) < 10:
            break
        acc = sub["correct"].mean()
        if acc > best_acc:
            best_acc, best_thr, best_n = acc, thr, len(sub)

    print(f"\n  Best threshold : {best_thr:.2f}")
    print(f"  Best accuracy  : {best_acc:.1%}")
    print(f"  Coverage       : {best_n}/{total} ({best_n/total:.1%})")

    if best_acc >= 0.60:
        print(f"\n  GOOD  — {best_acc:.1%} > 60% pada conf >= {best_thr:.2f}")
    elif best_acc >= 0.55:
        print(f"\n  OK    — {best_acc:.1%} > 55% pada conf >= {best_thr:.2f}")
    else:
        print(f"\n  WEAK  — peak accuracy {best_acc:.1%}, confidence tidak bantu banyak")

    # ── Save CSV ──────────────────────────────────────────────────
    out = _ROOT_DIR / "backtest" / "results" / "bcd_confidence_accuracy.csv"
    rec_df.to_csv(out, index=False)
    print(f"\n  Saved: {out.name}\n")


if __name__ == "__main__":
    main()
