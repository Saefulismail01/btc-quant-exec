#!/usr/bin/env python3
"""
Gabungkan cache parquet dan jalankan walk-forward analysis.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from run_study import (
    ohlcv_1m_to_4h,
    build_4h_features,
    label_exec_long_tp_before_sl,
    _mlp_fit_predict_fold,
    run_mlp_walkforward,
    _run_pipeline_from_1m,
)

# Define TECH_COLS locally (from run_study.py)
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

DEFAULT_MAX_FORWARD_BARS = 7 * 24 * 60  # 7 days

def main():
    cache_dir = Path("docs/research/rr_improvement_2026q2/experiments/execution_aligned_label_study/.cache")
    
    # Find all parquet files
    parquet_files = sorted(cache_dir.glob("btc_1m_*.parquet"))
    
    if len(parquet_files) < 2:
        print(f"[error] Need at least 2 parquet files, found {len(parquet_files)}")
        return 1
    
    print(f"[+] Combining {len(parquet_files)} parquet files...")
    
    # Read and concatenate
    dfs = []
    for p in parquet_files:
        df = pd.read_parquet(p)
        print(f"     {p.name}: {len(df)} bars")
        dfs.append(df)
    
    df_combined = pd.concat(dfs, ignore_index=True)
    df_combined = df_combined.drop_duplicates(subset=['timestamp']).sort_values('timestamp')
    
    print(f"[+] Combined: {len(df_combined)} bars total")
    print(f"[+] Date range: {df_combined['timestamp'].min()} to {df_combined['timestamp'].max()}")
    
    # Convert timestamp to datetime and set as index
    df_combined['timestamp'] = pd.to_datetime(df_combined['timestamp'], unit='ms', utc=True)
    df_combined = df_combined.set_index('timestamp')
    
    # Manual pipeline
    print("[2/3] Resample 1m ke 4H...")
    df_4h = ohlcv_1m_to_4h(df_combined)
    print(f"     4H bars: {len(df_4h):,}")
    
    print("[3/3] Build features...")
    feat = build_4h_features(df_4h)
    
    print("[4/4] Label execution...")
    y_exec = label_exec_long_tp_before_sl(df_combined, feat, max_bars=DEFAULT_MAX_FORWARD_BARS)
    feat["y_exec_long"] = y_exec
    
    n_tp = (feat["y_exec_long"] == 1).sum()
    n_sl = (feat["y_exec_long"] == 0).sum()
    n_none = (feat["y_exec_long"] < 0).sum()
    print(f"     TP dulu={int(n_tp)}  SL dulu={int(n_sl)}  belum terselesaikan={int(n_none)}")
    
    # Filter valid
    m_train = feat.dropna(subset=_TECH_COLS + ["y_4h_3c"])
    m_bin0 = m_train[(m_train["y_exec_long"] == 0) | (m_train["y_exec_long"] == 1)]
    print(f"     m_train (ada target 4H)={len(m_train)}  m_bin (sudah TP/SL)={len(m_bin0)}")
    
    # Prepare data for 3-class
    X_3cls = m_train[_TECH_COLS].values
    y_3cls = m_train["y_4h_3c"].values
    
    # Prepare data for binary (execution)
    X_bin = m_bin0[_TECH_COLS].values
    y_bin = m_bin0["y_exec_long"].values
    
    # Run walk-forward for 3-class
    result_3cls = run_mlp_walkforward(
        X_3cls, y_3cls, n_classes=3, name="MLP 4H (3-kelas)", n_splits=6
    )
    
    # Run walk-forward for binary
    result_bin = run_mlp_walkforward(
        X_bin, y_bin, n_classes=2, name="Eksekusi TP/SL 1m [long]", n_splits=6
    )
    
    print("\n" + "=" * 60)
    print("WALK-FORWARD (combined cache)")
    print("=" * 60)
    
    for result in [result_3cls, result_bin]:
        print(f"\n  {result.name}")
        print(f"     acc mean+/-std: {result.acc_mean:.3f} / {result.acc_std:.3f}")
        print(f"     bal mean+/-std: {result.bal_mean:.3f} / {result.bal_std:.3f}")
        print(f"     f1  mean+/-std: {result.f1_mean:.3f} / {result.f1_std:.3f}  (lipatan={result.n_folds})")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
