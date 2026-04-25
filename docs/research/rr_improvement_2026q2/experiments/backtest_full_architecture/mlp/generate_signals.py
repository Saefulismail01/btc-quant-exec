"""Generate MLP signals for all 3 variants."""

from __future__ import annotations

from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[6]
EXPERIMENT_DIR = Path(__file__).resolve().parents[1]
PROCESSED_DIR = EXPERIMENT_DIR / "data" / "processed"
MODELS_DIR = EXPERIMENT_DIR / "mlp" / "models"
SIGNALS_DIR = EXPERIMENT_DIR / "signals"

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


def generate_signals_for_variant(
    df_4h: pd.DataFrame,
    model_name: str,
) -> pd.Series:
    """Generate signals for a specific MLP variant."""
    # Load model and scaler
    model_path = MODELS_DIR / f"{model_name}.joblib"
    scaler_path = MODELS_DIR / f"{model_name}_scaler.joblib"
    
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    if not scaler_path.exists():
        raise FileNotFoundError(f"Scaler not found: {scaler_path}")
    
    model_data = joblib.load(model_path)
    mlp = model_data["model"]
    scaler = joblib.load(scaler_path)
    
    # Extract features
    X = df_4h[_TECH_COLS].values
    
    # Handle NaN values
    X = np.nan_to_num(X, nan=0.0)
    
    # Scale features
    X_scaled = scaler.transform(X)
    
    # Predict
    if model_name == "variant_a":
        # Binary classification: 0=SL, 1=TP
        probs = mlp.predict_proba(X_scaled)
        # Convert to signal: -1 for short, 1 for long, 0 for neutral
        # Use probability of TP as confidence
        tp_prob = probs[:, 1] if probs.shape[1] > 1 else probs[:, 0]
        signals = np.where(tp_prob > 0.6, 1.0, np.where(tp_prob < 0.4, -1.0, 0.0))
    else:
        # 3-class classification: 0=bear, 1=neutral, 2=bull
        preds = mlp.predict(X_scaled)
        # Convert to signal: -1 for bear, 0 for neutral, 1 for bull
        signals = np.where(preds == 2, 1.0, np.where(preds == 0, -1.0, 0.0))
    
    return pd.Series(signals, index=df_4h.index)


def main() -> int:
    # Load preprocessed data
    data_4h_path = PROCESSED_DIR / "preprocessed_4h.parquet"
    
    if not data_4h_path.exists():
        raise FileNotFoundError(f"4H data not found: {data_4h_path}")
    
    df_4h = pd.read_parquet(data_4h_path)
    print(f"[+] Loaded 4H data: {len(df_4h)} rows")
    
    # Create signals directory
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Generate signals for each variant
    variants = ["baseline", "variant_a", "variant_b"]
    for variant in variants:
        print(f"[+] Generating signals for {variant}...")
        signals = generate_signals_for_variant(df_4h, variant)
        
        # Save signals
        signal_path = SIGNALS_DIR / f"signals_{variant}.parquet"
        signal_df = pd.DataFrame({
            "datetime": df_4h["datetime"],
            "signal": signals
        })
        signal_df.to_parquet(signal_path)
        print(f"[+] Saved signals to: {signal_path}")
        print(f"     Signal distribution: {signals.value_counts().to_dict()}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
