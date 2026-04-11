"""
  BCD PRECISION FILTER SEARCH

  Mencari kombinasi filter di atas sinyal BCD yang menghasilkan
  presisi > 65% untuk prediksi arah 4H.

  Filter yang diuji:
    1. Regime age    — berapa lama regime aktif (candle sejak changepoint)
    2. Momentum      — konfirmasi arah dari log return N-candle terakhir
    3. EMA alignment — price vs EMA20 searah dengan prediksi BCD
    4. Volume spike  — volume > MA(volume) * threshold
    5. ATR filter    — hanya trade saat volatilitas tidak ekstrem

  Output:
    - Tabel semua kombinasi yang mencapai presisi > 65%
    - Coverage (% candle yang lolos filter)
    - Best combo recommendation

Usage:
    cd btc-scalping-execution_layer
    python backtest/scripts/evaluate_bcd_precision_filter.py
"""

from __future__ import annotations

import sys
import warnings
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_ta as ta

warnings.filterwarnings("ignore")

_ROOT_DIR = Path(r"C:\Users\ThinkPad\Documents\Windsurf\btc-scalping-execution_layer")
sys.path.insert(0, str(_ROOT_DIR / "backend" / "app" / "core"))
sys.path.insert(0, str(_ROOT_DIR / "backend" / "app" / "core" / "engines"))
sys.path.insert(0, str(_ROOT_DIR / "backend"))

from engines.layer1_bcd import BayesianChangepointModel as BCDModel

FORWARD_H    = 4
WARMUP       = 200
SAMPLE_EVERY = 8
TARGET_PREC  = 0.65
MIN_SAMPLES  = 20   # minimum sample untuk dianggap valid


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


def enrich_features(df: pd.DataFrame) -> pd.DataFrame:
    """Tambahkan fitur teknikal yang akan digunakan sebagai filter."""
    d = df.copy()

    # Momentum: log return N candle terakhir
    d["ret_1"]  = np.log(d["Close"] / d["Close"].shift(1))
    d["ret_3"]  = np.log(d["Close"] / d["Close"].shift(3))
    d["ret_6"]  = np.log(d["Close"] / d["Close"].shift(6))

    # EMA
    d["ema20"]  = ta.ema(d["Close"], length=20)
    d["ema50"]  = ta.ema(d["Close"], length=50)
    d["ema_dist"] = (d["Close"] - d["ema20"]) / d["ema20"]  # + = di atas EMA

    # Volume z-score
    vol_ma  = d["Volume"].rolling(20).mean()
    vol_std = d["Volume"].rolling(20).std().replace(0, np.nan)
    d["vol_z"] = (d["Volume"] - vol_ma) / vol_std

    # ATR normalized
    atr = ta.atr(d["High"], d["Low"], d["Close"], length=14)
    d["norm_atr"] = atr / d["Close"]
    d["atr_pct"]  = d["norm_atr"].rank(pct=True)  # percentile

    # RSI
    d["rsi"] = ta.rsi(d["Close"], length=14)

    return d.fillna(0)


def build_sample_df(
    df_feat: pd.DataFrame,
    global_states: np.ndarray,
    bcd: BCDModel,
) -> pd.DataFrame:
    """Buat DataFrame satu baris per sample dengan semua fitur dan label aktual."""
    n = len(df_feat)
    actual_dir = pd.Series(
        np.where(df_feat["Close"].shift(-FORWARD_H) > df_feat["Close"], "UP", "DOWN"),
        index=df_feat.index,
    )

    # Hitung regime age (candle sejak changepoint terakhir)
    cps = sorted(bcd._changepoints)
    regime_age = np.zeros(n, dtype=np.int32)
    cp_ptr = 0
    for i in range(n):
        while cp_ptr < len(cps) and cps[cp_ptr] <= i:
            cp_ptr += 1
        last_cp = cps[cp_ptr - 1] if cp_ptr > 0 else 0
        regime_age[i] = i - last_cp

    indices = list(range(WARMUP, n - FORWARD_H, SAMPLE_EVERY))
    records = []
    for i in indices:
        seg_id = int(global_states[i])
        label  = bcd.state_map.get(seg_id, "Unknown")

        if "Bullish" in label:
            pred = "UP"
        elif "Bearish" in label:
            pred = "DOWN"
        else:
            pred = "NEUTRAL"

        if pred == "NEUTRAL":
            continue  # skip sideways — tidak ada directional bet

        act     = actual_dir.iloc[i]
        correct = (pred == act)
        row     = df_feat.iloc[i]

        # Momentum searah dengan prediksi?
        mom1_aligned = (pred == "UP" and row["ret_1"] > 0) or (pred == "DOWN" and row["ret_1"] < 0)
        mom3_aligned = (pred == "UP" and row["ret_3"] > 0) or (pred == "DOWN" and row["ret_3"] < 0)
        mom6_aligned = (pred == "UP" and row["ret_6"] > 0) or (pred == "DOWN" and row["ret_6"] < 0)

        # EMA searah?
        ema_aligned  = (pred == "UP" and row["ema_dist"] > 0) or (pred == "DOWN" and row["ema_dist"] < 0)
        ema50_aligned = (
            (pred == "UP"   and row["Close"] > row["ema50"]) or
            (pred == "DOWN" and row["Close"] < row["ema50"])
        )

        # Volume tinggi?
        vol_high = row["vol_z"] > 0.5
        vol_low  = row["vol_z"] < -0.3

        # ATR moderate (tidak terlalu ekstrem = lebih predictable)
        atr_moderate = 0.20 < row["atr_pct"] < 0.80
        atr_low      = row["atr_pct"] < 0.40

        # RSI tidak overbought/oversold
        rsi_ok_bull = row["rsi"] < 70
        rsi_ok_bear = row["rsi"] > 30
        rsi_ok = (pred == "UP" and rsi_ok_bull) or (pred == "DOWN" and rsi_ok_bear)

        # Regime sudah mature (bukan baru ganti)
        age_gt5  = regime_age[i] >= 5
        age_gt10 = regime_age[i] >= 10
        age_gt20 = regime_age[i] >= 20

        records.append({
            "i":            i,
            "datetime":     df_feat["Datetime"].iloc[i],
            "pred":         pred,
            "actual":       act,
            "correct":      correct,
            "label":        label,
            "regime_age":   regime_age[i],
            # Filter flags
            "mom1":         mom1_aligned,
            "mom3":         mom3_aligned,
            "mom6":         mom6_aligned,
            "ema20":        ema_aligned,
            "ema50":        ema50_aligned,
            "vol_high":     vol_high,
            "vol_low":      vol_low,
            "atr_moderate": atr_moderate,
            "atr_low":      atr_low,
            "rsi_ok":       rsi_ok,
            "age_gt5":      age_gt5,
            "age_gt10":     age_gt10,
            "age_gt20":     age_gt20,
        })

    return pd.DataFrame(records)


def search_filter_combos(sdf: pd.DataFrame) -> pd.DataFrame:
    """Brute-force search semua kombinasi filter, cari yang presisi > TARGET_PREC."""
    filter_cols = [
        "mom1", "mom3", "mom6",
        "ema20", "ema50",
        "vol_high",
        "atr_moderate", "atr_low",
        "rsi_ok",
        "age_gt5", "age_gt10", "age_gt20",
    ]

    total_base = len(sdf)
    results = []

    # Baseline (no filter)
    results.append({
        "filters":   "baseline (no filter)",
        "n":         total_base,
        "coverage":  1.0,
        "precision": sdf["correct"].mean(),
        "up_prec":   sdf[sdf["pred"]=="UP"]["correct"].mean() if (sdf["pred"]=="UP").any() else 0,
        "dn_prec":   sdf[sdf["pred"]=="DOWN"]["correct"].mean() if (sdf["pred"]=="DOWN").any() else 0,
    })

    # Single filters
    for f in filter_cols:
        sub = sdf[sdf[f] == True]
        if len(sub) < MIN_SAMPLES:
            continue
        results.append({
            "filters":   f,
            "n":         len(sub),
            "coverage":  len(sub) / total_base,
            "precision": sub["correct"].mean(),
            "up_prec":   sub[sub["pred"]=="UP"]["correct"].mean() if (sub["pred"]=="UP").any() else 0,
            "dn_prec":   sub[sub["pred"]=="DOWN"]["correct"].mean() if (sub["pred"]=="DOWN").any() else 0,
        })

    # Double filters
    for i, f1 in enumerate(filter_cols):
        for f2 in filter_cols[i+1:]:
            sub = sdf[(sdf[f1] == True) & (sdf[f2] == True)]
            if len(sub) < MIN_SAMPLES:
                continue
            prec = sub["correct"].mean()
            if prec < 0.55:  # prune yang jelas tidak berguna
                continue
            results.append({
                "filters":   f"{f1} + {f2}",
                "n":         len(sub),
                "coverage":  len(sub) / total_base,
                "precision": prec,
                "up_prec":   sub[sub["pred"]=="UP"]["correct"].mean() if (sub["pred"]=="UP").any() else 0,
                "dn_prec":   sub[sub["pred"]=="DOWN"]["correct"].mean() if (sub["pred"]=="DOWN").any() else 0,
            })

    # Triple filters (hanya yang sudah > 0.58 di double)
    high_singles = [r["filters"] for r in results if r["precision"] >= 0.58 and "+" not in r["filters"] and r["filters"] != "baseline (no filter)"]
    for i, f1 in enumerate(high_singles):
        for j, f2 in enumerate(high_singles[i+1:], i+1):
            for f3 in high_singles[j+1:]:
                sub = sdf[(sdf[f1]==True) & (sdf[f2]==True) & (sdf[f3]==True)]
                if len(sub) < MIN_SAMPLES:
                    continue
                prec = sub["correct"].mean()
                results.append({
                    "filters":   f"{f1} + {f2} + {f3}",
                    "n":         len(sub),
                    "coverage":  len(sub) / total_base,
                    "precision": prec,
                    "up_prec":   sub[sub["pred"]=="UP"]["correct"].mean() if (sub["pred"]=="UP").any() else 0,
                    "dn_prec":   sub[sub["pred"]=="DOWN"]["correct"].mean() if (sub["pred"]=="DOWN").any() else 0,
                })

    res_df = pd.DataFrame(results).sort_values("precision", ascending=False)
    return res_df


def main():
    print("\n" + "=" * 65)
    print("  BCD PRECISION FILTER SEARCH — Target Presisi > 65%")
    print("=" * 65)

    df = load_data()

    print("  Enriching features...")
    df_feat = enrich_features(df)

    print("  Training BCD...")
    bcd = BCDModel()
    bcd.train_global(df)
    print(f"  BCD: {len(bcd._changepoints)} changepoints, {len(bcd.state_map)} segments")

    print("  Pre-computing state sequence...")
    global_states, global_idx = bcd.get_state_sequence_raw(df)

    print("  Building sample dataframe...")
    sdf = build_sample_df(df_feat, global_states, bcd)
    print(f"  Directional samples: {len(sdf)} (exclude NEUTRAL)")

    print("  Searching filter combinations...")
    res_df = search_filter_combos(sdf)

    # ── Semua yang > TARGET_PREC ────────────────────────────────────────
    hits = res_df[res_df["precision"] >= TARGET_PREC]

    print("\n" + "=" * 65)
    print(f"  KOMBINASI FILTER PRESISI >= {TARGET_PREC:.0%}")
    print("=" * 65)
    if hits.empty:
        print(f"\n  Tidak ada kombinasi yang mencapai {TARGET_PREC:.0%}.")
        print("  Menampilkan top 15 hasil terbaik:\n")
        show = res_df.head(15)
    else:
        print(f"\n  Ditemukan {len(hits)} kombinasi!\n")
        show = hits.head(20)

    print(f"  {'Filters':<35}  {'N':>5}  {'Cov':>6}  {'Prec':>7}  {'UP':>7}  {'DN':>7}")
    print("  " + "-" * 65)
    for _, row in show.iterrows():
        print(
            f"  {str(row['filters']):<35}  {int(row['n']):>5}  "
            f"{row['coverage']:>6.1%}  {row['precision']:>7.1%}  "
            f"{row['up_prec']:>7.1%}  {row['dn_prec']:>7.1%}"
        )

    # ── Breakdown BEAR vs BULL untuk top combo ─────────────────────────
    best = res_df.iloc[0]
    print(f"\n  Best combo: [{best['filters']}]")
    print(f"    Overall precision : {best['precision']:.1%}")
    print(f"    UP  signal prec   : {best['up_prec']:.1%}")
    print(f"    DOWN signal prec  : {best['dn_prec']:.1%}")
    print(f"    Coverage          : {best['coverage']:.1%} ({int(best['n'])} sampel)")

    # ── Rekomendasi ────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  REKOMENDASI")
    print("=" * 65)
    top_hit = hits.iloc[0] if not hits.empty else res_df.iloc[0]
    reached = hits is not None and not hits.empty

    if reached:
        print(f"\n  Target {TARGET_PREC:.0%} TERCAPAI dengan filter:")
        print(f"    -> {top_hit['filters']}")
        print(f"    -> Presisi: {top_hit['precision']:.1%}  Coverage: {top_hit['coverage']:.1%}")
        print(f"\n  Artinya: dari semua sinyal BCD, ambil hanya yang lolos filter ini.")
        print(f"  Frekuensi trade akan turun ke {top_hit['coverage']:.0%} dari sinyal total.")
    else:
        top3 = res_df.head(3)
        print(f"\n  Target {TARGET_PREC:.0%} belum tercapai dengan filter teknikal sederhana.")
        print(f"  Best yang bisa dicapai: {res_df.iloc[0]['precision']:.1%}")
        print(f"\n  Top 3 filter terbaik:")
        for _, r in top3.iterrows():
            print(f"    [{r['filters']}] prec={r['precision']:.1%} cov={r['coverage']:.1%}")
        print(f"\n  Rekomendasi:")
        print(f"    1. Fokus ke sinyal BEAR saja (lebih akurat dari BULL)")
        print(f"    2. Tambah data microstructure (CVD/OI) untuk L3 MLP yang lebih baik")
        print(f"    3. Gunakan walk-forward dengan retrain BCD per periode")

    # ── Save ───────────────────────────────────────────────────────────
    out_combo = _ROOT_DIR / "backtest" / "results" / "bcd_filter_combos.csv"
    out_sdf   = _ROOT_DIR / "backtest" / "results" / "bcd_sample_features.csv"
    res_df.to_csv(out_combo, index=False)
    sdf.to_csv(out_sdf, index=False)
    print(f"\n  Saved: {out_combo.name}")
    print(f"  Saved: {out_sdf.name}\n")


if __name__ == "__main__":
    main()
