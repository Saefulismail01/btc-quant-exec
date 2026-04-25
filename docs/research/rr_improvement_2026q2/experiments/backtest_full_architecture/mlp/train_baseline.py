"""Train baseline MLP with 4H forward return labels."""

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

MLP_FORWARD_RETURN_WINDOW = 6  # 4H forward return (6 bars = 24H)


def generate_4h_labels(df_4h: pd.DataFrame) -> pd.Series:
    """Generate 3-class labels based on 4H forward return."""
    # Handle both lowercase and uppercase column names
    close_col = "Close" if "Close" in df_4h.columns else "close"
    
    c = df_4h[close_col].values
    W = MLP_FORWARD_RETURN_WINDOW
    
    # Use fixed threshold (1% for 24H forward return)
    target_threshold = 0.01
    
    # Calculate forward return
    future_close = np.roll(c, -W)
    price_move_pct = (future_close - c) / c
    
    # Generate labels: 0=bear, 1=neutral, 2=bull
    move = price_move_pct
    thr = target_threshold
    labels = np.where(move > thr, 2, np.where(move < -thr, 0, 1)).astype(float)
    
    # Set last W bars to NaN (no future data)
    labels[-W:] = np.nan
    
    return pd.Series(labels, index=df_4h.index)


def train_baseline_mlp(
    df_4h: pd.DataFrame,
    n_splits: int = 6,
    random_state: int = 42,
) -> tuple[MLPClassifier, StandardScaler, dict[str, float]]:
    """Train baseline MLP with 4H forward return labels."""
    # Generate labels
    labels = generate_4h_labels(df_4h)
    df_4h["y_4h_3c"] = labels
    
    # Filter valid data
    m_train = df_4h.dropna(subset=_TECH_COLS + ["y_4h_3c"])
    X = m_train[_TECH_COLS].values
    y = m_train["y_4h_3c"].values.astype(int)
    
    print(f"[+] Training data: {len(X)} samples")
    print(f"[+] Class distribution: {np.bincount(y)}")
    
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
    
    print("[+] Training baseline MLP...")
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
    
    if not data_4h_path.exists():
        raise FileNotFoundError(f"4H data not found: {data_4h_path}")
    
    df = pd.read_parquet(data_4h_path)
    print(f"[+] Loaded 4H data with features: {len(df)} rows")
    print(f"[+] Columns: {df.columns.tolist()}")
    
    # Train model
    mlp, scaler, metrics = train_baseline_mlp(df)
    
    # Save model and scaler
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODELS_DIR / "baseline.joblib"
    scaler_path = MODELS_DIR / "baseline_scaler.joblib"
    
    joblib.dump({"model": mlp, "scaler": scaler}, model_path)
    joblib.dump(scaler, scaler_path)
    
    print(f"[+] Model saved to: {model_path}")
    print(f"[+] Scaler saved to: {scaler_path}")
    
    # Save validation results
    results_path = MODELS_DIR.parent / "validation_results.csv"
    results_df = pd.DataFrame([{"model": "baseline", **metrics}])
    
    if results_path.exists():
        existing = pd.read_csv(results_path)
        results_df = pd.concat([existing[existing["model"] != "baseline"], results_df])
    
    results_df.to_csv(results_path, index=False)
    print(f"[+] Validation results saved to: {results_path}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
