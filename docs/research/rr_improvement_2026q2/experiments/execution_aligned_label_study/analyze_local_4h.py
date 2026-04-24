#!/usr/bin/env python3
"""
Analisis sederhana data 4H lokal untuk studi label eksekusi.

Usage:
    python analyze_local_4h.py --csv backtest/data/BTC_USDT_4h_2025.csv
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_ta as ta
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
from sklearn.model_selection import TimeSeriesSplit

# Constants from layer3_ai.py
MLP_FORWARD_RETURN_WINDOW = 1
TP_PCT = 0.0071   # 0.71%
SL_PCT = 0.01333  # 1.333%


def load_and_prepare(csv_path: str) -> pd.DataFrame:
    """Load CSV dan prepare fitur + label."""
    df = pd.read_csv(csv_path)
    
    # Parse timestamp
    if 'timestamp' in df.columns:
        # Try both ms and string format
        try:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        except ValueError:
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    elif 'datetime' in df.columns:
        df['timestamp'] = pd.to_datetime(df['datetime'], utc=True)
    
    df = df.set_index('timestamp').sort_index()
    df = df.rename(columns=str.lower)
    
    print(f"[load] {len(df)} bars, {df.index[0]} to {df.index[-1]}")
    
    # Build features (layer3 style)
    c = df['close']
    df['rsi_14'] = ta.rsi(c, length=14)
    macd_df = ta.macd(c, fast=12, slow=26, signal=9)
    if macd_df is not None and 'MACDh_12_26_9' in macd_df.columns:
        df['macd_hist'] = macd_df['MACDh_12_26_9']
    else:
        df['macd_hist'] = 0.0
    
    ema20 = ta.ema(c, length=20)
    df['ema20_dist'] = (c - ema20) / ema20
    df['log_return'] = np.log(c / c.shift(1))
    
    atr = ta.atr(df['high'], df['low'], c, length=14)
    df['norm_atr'] = atr / c
    df['norm_cvd'] = 0.0
    df['funding'] = 0.0
    df['oi_change'] = 0.0
    
    # Label 3-class (MLP 4H style)
    W = MLP_FORWARD_RETURN_WINDOW
    df['future_close'] = c.shift(-W)
    df['price_move_pct'] = (df['future_close'] - c) / c
    df['target_threshold'] = 0.5 * df['norm_atr'] * (W**0.5)
    
    move = df['price_move_pct'].values
    thr = df['target_threshold'].values
    nan_m = np.isnan(move) | np.isnan(thr)
    lab = np.where(move > thr, 2, np.where(move < -thr, 0, 1)).astype(float)
    lab[nan_m] = np.nan
    df['y_3cls'] = lab
    
    # Label execution (TP before SL) - simplified for 4H only
    # Note: without 1m data, we approximate using next 4H bar
    y_exec = np.full(len(df), np.nan)
    for i in range(len(df) - 1):
        entry = df['close'].iloc[i]
        if pd.isna(entry):
            continue
        tp = entry * (1 + TP_PCT)
        sl = entry * (1 - SL_PCT)
        
        # Check next bar (simplified - should be 1m for accurate simulation)
        next_high = df['high'].iloc[i+1]
        next_low = df['low'].iloc[i+1]
        
        if pd.notna(next_low) and next_low <= sl:
            y_exec[i] = 1  # SL hit
        elif pd.notna(next_high) and next_high >= tp:
            y_exec[i] = 0  # TP hit
        # else: unresolved (nan)
    df['y_exec'] = y_exec
    
    return df


def run_walkforward(df: pd.DataFrame, splits: int = 4):
    """Run walk-forward validation."""
    tech_cols = ['rsi_14', 'macd_hist', 'ema20_dist', 'log_return', 
                 'norm_atr', 'norm_cvd', 'funding', 'oi_change']
    
    # Filter valid rows
    df_valid = df.dropna(subset=tech_cols + ['y_3cls']).copy()
    if len(df_valid) < 50:
        print("[error] Too few valid rows", file=sys.stderr)
        return
    
    X = df_valid[tech_cols].fillna(0).values
    y_3cls = df_valid['y_3cls'].values
    y_exec = df_valid['y_exec'].dropna().values
    
    print(f"[wf] Valid rows: {len(df_valid)}")
    print(f"[wf] 3-class labels: {np.bincount(y_3cls.astype(int))}")
    
    # Walk-forward for 3-class
    tscv = TimeSeriesSplit(n_splits=splits)
    results_3cls = []
    results_exec = []
    
    for train_idx, test_idx in tscv.split(X):
        if len(train_idx) < 30 or len(test_idx) < 10:
            continue
        
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y_3cls[train_idx], y_3cls[test_idx]
        
        # Scale and fit
        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)
        
        clf = MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=500, 
                           early_stopping=True, random_state=42)
        clf.fit(X_train_s, y_train)
        y_pred = clf.predict(X_test_s)
        
        results_3cls.append({
            'acc': accuracy_score(y_test, y_pred),
            'bal': balanced_accuracy_score(y_test, y_pred),
            'f1': f1_score(y_test, y_pred, average='weighted', zero_division=0)
        })
    
    # Print results
    print("\n" + "=" * 60)
    print("WALK-FORWARD (data LOKAL 4H)")
    print("=" * 60)
    
    print("\n  MLP 4H (3-kelas)")
    for metric in ['acc', 'bal', 'f1']:
        vals = [r[metric] for r in results_3cls]
        print(f"     {metric:3} mean+/-std: {np.mean(vals):.3f} / {np.std(vals):.3f}  (n={len(vals)})")
    
    print("\n  Eksekusi TP/SL [long] (aproksimasi 4H)")
    print(f"     note: butuh data 1m untuk akurasi penuh")
    
    print("\n" + "=" * 60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', type=str, required=True, help='Path ke CSV 4H')
    ap.add_argument('--splits', type=int, default=4, help='Jumlah walk-forward splits')
    args = ap.parse_args()
    
    df = load_and_prepare(args.csv)
    run_walkforward(df, splits=args.splits)
    return 0


if __name__ == '__main__':
    sys.exit(main())
