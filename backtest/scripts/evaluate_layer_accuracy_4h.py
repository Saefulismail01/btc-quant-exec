"""

  LAYER ACCURACY TEST - Prediksi Arah 4h

  Mengukur seberapa akurat L1 (BCD) + L2 (EMA) + L3 (MLP)
  memprediksi arah harga 4 candle (16 jam) ke depan.

  Output:
    - Akurasi per layer (L1, L2, L3, Combined)
    - Confusion matrix per layer

Usage:
    cd backtest/scripts
    python evaluate_layer_accuracy_4h.py
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# Setup path to import engines - use absolute path
_ROOT_DIR = Path(r"C:\Users\ThinkPad\Documents\Windsurf\btc-scalping-execution_layer")
_BACKEND_CORE = _ROOT_DIR / "backend" / "app" / "core"
_ENGINES_DIR = _BACKEND_CORE / "engines"

if str(_ENGINES_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINES_DIR))

if str(_BACKEND_CORE) not in sys.path:
    sys.path.insert(0, str(_BACKEND_CORE))

print(f"Adding to path: {_ENGINES_DIR}")
print(f"Adding to path: {_BACKEND_CORE}")

from engines.layer1_bcd import BayesianChangepointModel as BCDModel
from engines.layer2_ema import EMAStructureModel as EMAModel
from engines.layer3_ai import SignalIntelligenceModel as AIModel

print("Models imported successfully")


_ROOT = _ROOT_DIR
_RESULTS = _ROOT / "backtest" / "results"

FORWARD_H = 4  # 4h ke depan


def load_data() -> pd.DataFrame:
    data_file = _ROOT / "backtest" / "data" / "BTC_USDT_4h_2025.csv"
    if not data_file.exists():
        data_file = _ROOT / "backtest" / "data" / "BTC_USDT_4h_2023.csv"

    if not data_file.exists():
        # Try absolute path
        data_file = Path(
            r"C:\Users\ThinkPad\Documents\Windsurf\btc-scalping-execution_layer\backtest\data\BTC_USDT_4h_2025.csv"
        )
        if not data_file.exists():
            data_file = Path(
                r"C:\Users\ThinkPad\Documents\Windsurf\btc-scalping-execution_layer\backtest\data\BTC_USDT_4h_2023.csv"
            )

    if not data_file.exists():
        raise FileNotFoundError("Data file not found")

    df = pd.read_csv(data_file)
    df.columns = [c.capitalize() for c in df.columns]
    df = df.sort_values("Datetime").reset_index(drop=True)
    print(f"[LOAD] Loaded {len(df)} candles from {data_file.name}")
    return df


def compute_actual_direction(df: pd.DataFrame, forward_h: int = 4) -> pd.Series:
    future_close = df["Close"].shift(-forward_h)
    actual = np.where(future_close > df["Close"], "UP", "DOWN")
    return pd.Series(actual, index=df.index)


def _make_fresh_mlp() -> AIModel:
    """
    Buat instance MLP baru tanpa load disk cache.
    Mencegah shape mismatch antara model cached (live trading, mungkin 12 features)
    dan eval CSV yang hanya punya OHLCV (8 features).
    """
    ai = AIModel.__new__(AIModel)
    # Inisialisasi manual — skip _load_from_disk()
    import joblib as _joblib
    from sklearn.preprocessing import StandardScaler as _SS

    class _FreshScaler:
        """Wrapper ringan agar kompatibel dengan ThreadSafeScalerManager API."""
        def __init__(self):
            self._s = _SS()
            self._fitted = False
        def fit_transform(self, X):
            r = self._s.fit_transform(X)
            self._fitted = True
            return r
        def transform(self, X):
            if not self._fitted:
                raise RuntimeError("Scaler belum di-fit")
            return self._s.transform(X)

    ai.model = None
    ai.scaler = _FreshScaler()
    ai.is_cross_enabled = False
    ai._is_trained = False
    ai._last_trained_len = 0
    ai._data_hash = ""
    return ai


def run_layer_inference(df: pd.DataFrame) -> pd.DataFrame:
    results = []
    n = len(df)

    # Initialize models
    bcd = BCDModel()
    ema = EMAModel()

    # ── Step 1: Train BCD globally (sekali) ─────────────────────────────
    bcd.train_global(df)
    print(f"  BCD trained on {len(df)} candles, changepoints={len(bcd._changepoints)}")

    # ── Step 2: Pre-compute BCD state sequence SATU KALI untuk seluruh data
    # Menghindari O(n²) BOCPD per-sample yang membuat loop jadi O(n³)
    print("  Pre-computing global BCD state sequence (may take ~30s)...")
    try:
        global_states, global_states_idx = bcd.get_state_sequence_raw(df)
        global_states_arr = np.array(global_states_idx)
    except Exception as e:
        print(f"  Warning: state sequence failed ({e}). Using fallback neutral.")
        global_states = np.zeros(n, dtype=np.int32)
        global_states_idx = pd.RangeIndex(n)
        global_states_arr = np.arange(n)

    print(f"  Global BCD states computed ({len(global_states)} rows).")

    # ── Step 3: Pre-compute L2 EMA columns (sekali, vectorized) ─────────
    import pandas_ta as _ta
    ema_fast = _ta.ema(df["Close"], length=20)
    ema_slow = _ta.ema(df["Close"], length=50)

    # ── Step 4: Fresh MLP ────────────────────────────────────────────────
    ai = _make_fresh_mlp()

    # Warming period
    warmup = 200

    # Sample every SAMPLE_EVERY candles for speed
    SAMPLE_EVERY = 8
    indices = range(warmup, n - FORWARD_H, SAMPLE_EVERY)
    total = len(indices)
    print(f"  Running inference on {total} samples (every {SAMPLE_EVERY} candle)...")

    for idx, i in enumerate(indices):
        if idx % 50 == 0:
            print(f"    Progress: {idx}/{total} ({100 * idx // total}%)")

        # ── L1: BCD dari pre-computed states (O(1) lookup, no BOCPD) ────
        try:
            seg_id = int(global_states[i])
            label = bcd.state_map.get(seg_id, "Unknown Regime")
            if "Bullish" in label:
                l1_tag = "bull"
            elif "Bearish" in label:
                l1_tag = "bear"
            else:
                l1_tag = "neutral"
            # Confidence dari R matrix jika tersedia, else 0.6 flat
            l1_conf = 0.6
        except Exception:
            l1_tag = "neutral"
            l1_conf = 0.33

        # ── L2: EMA dari kolom pre-computed (O(1) lookup) ────────────────
        try:
            price  = float(df["Close"].iloc[i])
            ef     = float(ema_fast.iloc[i])
            es     = float(ema_slow.iloc[i])
            if l1_tag == "bull":
                l2_aligned = price > ef > es
            elif l1_tag == "bear":
                l2_aligned = price < ef < es
            else:
                l2_aligned = False
        except Exception:
            l2_aligned = False

        # ── L3: MLP dengan BCD cross features (O(n) training per retrain) ─
        ai_bias = "NEUTRAL"
        ai_conf = 50.0
        try:
            row_df = df.iloc[: i + 1].copy()
            curr_states = global_states[:i + 1]
            curr_idx = global_states_idx[:i + 1]
            ai_bias, ai_conf = ai.get_ai_confidence(row_df, curr_states, curr_idx)
        except Exception:
            pass

        results.append(
            {
                "idx": i,
                "datetime": str(df["Datetime"].iloc[i]),
                "close": df["Close"].iloc[i],
                "l1_tag": l1_tag,
                "l1_conf": l1_conf,
                "l2_aligned": l2_aligned,
                "l3_bias": ai_bias,
                "l3_conf": ai_conf,
            }
        )

    return pd.DataFrame(results)


def compute_accuracies(pred_df: pd.DataFrame, actual_series: pd.Series) -> dict:
    pred_df = pred_df.set_index("idx")
    actual_aligned = actual_series.loc[pred_df.index]

    # L1: BCD only
    l1_pred = np.where(pred_df["l1_tag"] == "bull", "UP", "DOWN")
    l1_actual = actual_aligned.values
    l1_correct = l1_pred == l1_actual
    l1_accuracy = np.mean(l1_correct)

    # L2: EMA only
    l2_pred = np.where(pred_df["l2_aligned"] == True, "UP", "DOWN")
    l2_correct = l2_pred == l1_actual
    l2_accuracy = np.mean(l2_correct)

    # L3: MLP only
    l3_pred = np.where(
        pred_df["l3_bias"] == "BULL",
        "UP",
        np.where(pred_df["l3_bias"] == "BEAR", "DOWN", "NEUTRAL"),
    )
    l3_pred_binary = np.where(l3_pred == "UP", "UP", "DOWN")
    l3_correct = l3_pred_binary == l1_actual
    l3_accuracy = np.mean(l3_correct)

    # Combined: Majority vote
    def majority(row):
        votes = []
        if row["l1_tag"] == "bull":
            votes.append("UP")
        elif row["l1_tag"] == "bear":
            votes.append("DOWN")

        if row["l2_aligned"]:
            votes.append("UP")
        else:
            votes.append("DOWN")

        if row["l3_bias"] == "BULL":
            votes.append("UP")
        elif row["l3_bias"] == "BEAR":
            votes.append("DOWN")

        if not votes:
            return "NEUTRAL"
        up_count = votes.count("UP")
        down_count = votes.count("DOWN")
        return "UP" if up_count > down_count else "DOWN"

    combined_pred = pred_df.apply(majority, axis=1)
    combined_correct = combined_pred == actual_aligned
    combined_accuracy = np.mean(combined_correct)

    return {
        "n_samples": len(pred_df),
        "l1_accuracy": l1_accuracy,
        "l2_accuracy": l2_accuracy,
        "l3_accuracy": l3_accuracy,
        "combined_accuracy": combined_accuracy,
        "l1_preds": l1_pred,
        "l2_preds": l2_pred,
        "l3_preds": l3_pred_binary,
        "combined_preds": combined_pred.values,
        "actuals": l1_actual,
    }


def print_confusion_matrix(preds, actuals, layer_name: str):
    tp = np.sum((preds == "UP") & (actuals == "UP"))
    tn = np.sum((preds == "DOWN") & (actuals == "DOWN"))
    fp = np.sum((preds == "UP") & (actuals == "DOWN"))
    fn = np.sum((preds == "DOWN") & (actuals == "UP"))

    print(f"\n  {layer_name} Confusion Matrix:")
    print(f"       Predicted")
    print(f"       UP   DOWN")
    print(f"  UP   {tp:4d}  {fn:4d}")
    print(f"  DN   {fp:4d}  {tn:4d}")

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = (
        2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    )

    print(f"  Precision: {precision:.1%}, Recall: {recall:.1%}, F1: {f1:.1%}")
    return {
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def main():
    print("\n" + "=" * 60)
    print("  LAYER ACCURACY TEST - Prediksi Arah 4h")
    print("=" * 60)

    df = load_data()
    actual_direction = compute_actual_direction(df, FORWARD_H)

    print(f"\n  Running layer inference ({FORWARD_H}h forecasting)...")
    pred_df = run_layer_inference(df)
    print(f"  Inferred {len(pred_df)} samples")

    acc = compute_accuracies(pred_df, actual_direction)

    print("\n" + "=" * 60)
    print("  RESULTS - Layer Accuracy for 4h Direction Prediction")
    print("=" * 60)
    print(f"\n  Total samples: {acc['n_samples']}")
    print(f"\n  Layer Accuracy:")
    print(f"    L1 (BCD)      : {acc['l1_accuracy']:+.1%}")
    print(f"    L2 (EMA)      : {acc['l2_accuracy']:+.1%}")
    print(f"    L3 (MLP)      : {acc['l3_accuracy']:+.1%}")
    print(f"    Combined      : {acc['combined_accuracy']:+.1%}")

    print_confusion_matrix(acc["l1_preds"], acc["actuals"], "L1 (BCD)")
    print_confusion_matrix(acc["l2_preds"], acc["actuals"], "L2 (EMA)")
    print_confusion_matrix(acc["l3_preds"], acc["actuals"], "L3 (MLP)")
    print_confusion_matrix(acc["combined_preds"], acc["actuals"], "Combined")

    # Save to CSV
    results_df = pred_df.copy()
    results_df["actual_direction"] = actual_direction.loc[results_df["idx"]].values
    results_df["combined_pred"] = acc["combined_preds"]

    out_path = (
        _RESULTS / f"layer_accuracy_4h_{datetime.utcnow().strftime('%Y%m%d')}.csv"
    )
    results_df.to_csv(out_path, index=False)
    print(f"\n  Results saved to: {out_path.name}")

    # Interpretation
    print("\n" + "=" * 60)
    print("  INTERPRETATION")
    print("=" * 60)
    combined_acc = acc["combined_accuracy"]
    if combined_acc >= 0.55:
        print(f"  GOOD - Combined accuracy {combined_acc:.1%} > 55% (random is 50%)")
    elif combined_acc >= 0.52:
        print(
            f"  MARGINAL - Combined accuracy {combined_acc:.1%} (slightly above random)"
        )
    else:
        print(f"  POOR - Combined accuracy {combined_acc:.1%} (no better than random)")

    print("\n  Done.\n")


if __name__ == "__main__":
    main()
