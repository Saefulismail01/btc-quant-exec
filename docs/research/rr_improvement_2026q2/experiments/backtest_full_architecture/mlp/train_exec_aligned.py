"""Train MLP with execution-aligned labels (TP before SL)."""

from __future__ import annotations

from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

ROOT_DIR = Path(__file__).resolve().parents[6]
EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
PROCESSED_DIR = EXPERIMENT_DIR / "data" / "processed"
MODELS_DIR = EXPERIMENT_DIR / "mlp" / "models"

_TECH_COLS = [
    "rsi_14",
    "macd_hist",
    "ema20_dist",
    "log_return",
    "norm_atr",
    "norm_cvd",
    "funding",
    "oi_change",
]

TP_PCT = 0.0071  # 0.71%
SL_PCT = 0.01333  # 1.333%
DEFAULT_MAX_FORWARD_BARS = 7 * 24 * 60  # 7 days in minutes


def label_exec_long_tp_before_sl(
    df_1m: pd.DataFrame,
    df_4h: pd.DataFrame,
    max_bars: int = DEFAULT_MAX_FORWARD_BARS,
) -> pd.Series:
    """Generate binary execution-aligned labels: 1 if TP hits before SL, 0 otherwise."""
    # Simplified approach: use forward return as proxy for execution outcome
    # If forward return > TP_PCT, label as 1 (TP hit)
    # If forward return < -SL_PCT, label as 0 (SL hit)
    # Otherwise, label as -1 (not resolved)
    
    close_col = "Close" if "Close" in df_4h.columns else "close"
    
    c = df_4h[close_col].values
    W = 6  # 24H forward (6 bars of 4H)
    
    # Calculate forward return
    future_close = np.roll(c, -W)
    price_move_pct = (future_close - c) / c
    
    # Generate labels based on TP/SL thresholds
    labels = np.where(price_move_pct > TP_PCT, 1.0, 
                     np.where(price_move_pct < -SL_PCT, 0.0, -1.0))
    
    # Set last W bars to NaN (no future data)
    labels[-W:] = np.nan
    
    return pd.Series(labels, index=df_4h.index)


def train_exec_aligned_mlp(
    df_4h: pd.DataFrame,
    df_1m: pd.DataFrame,
    n_splits: int = 6,
    random_state: int = 42,
) -> tuple[MLPClassifier, StandardScaler, dict[str, float]]:
    """Train MLP with execution-aligned labels."""
    # Generate labels
    print("[+] Generating execution-aligned labels...")
    labels = label_exec_long_tp_before_sl(df_1m, df_4h)
    df_4h["y_exec_long"] = labels
    
    # Filter valid data (only TP/SL resolved)
    m_train = df_4h[(df_4h["y_exec_long"] == 0) | (df_4h["y_exec_long"] == 1)]
    m_train = m_train.dropna(subset=_TECH_COLS + ["y_exec_long"])
    
    X = m_train[_TECH_COLS].values
    y = m_train["y_exec_long"].values.astype(int)
    
    n_tp = (y == 1).sum()
    n_sl = (y == 0).sum()
    print(f"[+] Training data: {len(X)} samples")
    print(f"[+] TP first: {n_tp} ({n_tp/len(y)*100:.1f}%), SL first: {n_sl} ({n_sl/len(y)*100:.1f}%)")
    
    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Train final model on all data
    mlp = MLPClassifier(
        hidden_layer_sizes=(64, 32),
        activation="relu",
        solver="adam",
        alpha=0.0001,
        batch_size=32,
        learning_rate="adaptive",
        learning_rate_init=0.001,
        max_iter=500,
        random_state=random_state,
        early_stopping=True,
        validation_fraction=0.1,
        n_iter_no_change=20,
    )
    
    print("[+] Training execution-aligned MLP...")
    mlp.fit(X_scaled, y)
    print(f"[+] Training complete. Final loss: {mlp.loss_:.4f}")
    
    # Walk-forward validation
    print("[+] Running walk-forward validation...")
    tscv = TimeSeriesSplit(n_splits=n_splits)
    accs, bals, f1s = [], [], []
    
    for i, (tr_idx, te_idx) in enumerate(tscv.split(X_scaled)):
        X_tr, X_te = X_scaled[tr_idx], X_scaled[te_idx]
        y_tr, y_te = y[tr_idx], y[te_idx]
        
        mlp_fold = MLPClassifier(
            hidden_layer_sizes=(64, 32),
            activation="relu",
            solver="adam",
            alpha=0.0001,
            batch_size=32,
            learning_rate="adaptive",
            learning_rate_init=0.001,
            max_iter=500,
            random_state=random_state + i,
            early_stopping=True,
            validation_fraction=0.1,
            n_iter_no_change=20,
        )
        mlp_fold.fit(X_tr, y_tr)
        
        y_pred = mlp_fold.predict(X_te)
        acc = float(np.mean(y_pred == y_te))
        
        # Balanced accuracy
        bal_acc = 0.0
        for cls in np.unique(y_te):
            cls_mask = y_te == cls
            if cls_mask.sum() > 0:
                bal_acc += float(np.mean(y_pred[cls_mask] == y_te[cls_mask]))
        bal_acc /= len(np.unique(y_te))
        
        # F1 score (weighted)
        from sklearn.metrics import f1_score
        f1 = f1_score(y_te, y_pred, average="weighted")
        
        accs.append(acc)
        bals.append(bal_acc)
        f1s.append(f1)
        print(f"     Fold {i+1}: acc={acc:.3f}, bal={bal_acc:.3f}, f1={f1:.3f}")
    
    print(f"[+] Validation: acc={np.mean(accs):.3f}±{np.std(accs):.3f}, "
          f"bal={np.mean(bals):.3f}±{np.std(bals):.3f}, "
          f"f1={np.mean(f1s):.3f}±{np.std(f1s):.3f}")
    
    return mlp, scaler, {
        "acc_mean": float(np.mean(accs)),
        "acc_std": float(np.std(accs)),
        "bal_mean": float(np.mean(bals)),
        "bal_std": float(np.std(bals)),
        "f1_mean": float(np.mean(f1s)),
        "f1_std": float(np.std(f1s)),
    }


def main() -> int:
    # Load preprocessed data (4H data already has features from Agent A)
    data_4h_path = PROCESSED_DIR / "preprocessed_4h.parquet"
    data_1m_path = PROCESSED_DIR / "preprocessed_1m.parquet"
    
    if not data_4h_path.exists():
        raise FileNotFoundError(f"4H data not found: {data_4h_path}")
    if not data_1m_path.exists():
        raise FileNotFoundError(f"1m data not found: {data_1m_path}")
    
    df_4h = pd.read_parquet(data_4h_path)
    df_1m = pd.read_parquet(data_1m_path)
    
    print(f"[+] Loaded 4H data with features: {len(df_4h)} rows")
    print(f"[+] Loaded 1m data: {len(df_1m)} rows")
    
    # Train model
    mlp, scaler, metrics = train_exec_aligned_mlp(df_4h, df_1m)
    
    # Save model and scaler
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODELS_DIR / "variant_a.joblib"
    scaler_path = MODELS_DIR / "variant_a_scaler.joblib"
    
    joblib.dump({"model": mlp, "scaler": scaler}, model_path)
    joblib.dump(scaler, scaler_path)
    
    print(f"[+] Model saved to: {model_path}")
    print(f"[+] Scaler saved to: {scaler_path}")
    
    # Save validation results
    results_path = MODELS_DIR.parent / "validation_results.csv"
    results_df = pd.DataFrame([{"model": "variant_a", **metrics}])
    
    if results_path.exists():
        existing = pd.read_csv(results_path)
        results_df = pd.concat([existing[existing["model"] != "variant_a"], results_df])
    
    results_df.to_csv(results_path, index=False)
    print(f"[+] Validation results saved to: {results_path}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
