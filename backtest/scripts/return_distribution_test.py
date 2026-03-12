"""
╔══════════════════════════════════════════════════════════════╗
║  BTC-QUANT: RETURN DISTRIBUTION TEST                        ║
║  Analisis Distribusi Return per Regime                      ║
║                                                              ║
║  ECONOPHYSICS — Modul C                                      ║
║  Berdasarkan: Palupi, Dwi Satya (2022)                      ║
║  "Pasar Keuangan dan Proses Stokastik"                       ║
║  Slide 22-24: Perbandingan distribusi teoritis vs empiris   ║
║                                                              ║
║  Menjawab I-00 PRD (HMM Predictive Power Test) dengan       ║
║  framework statistik yang lebih kaya dari sekadar           ║
║  win-rate: forward return, t-test, kurtosis, fat-tail.      ║
║                                                              ║
║  Dasar teori:                                               ║
║  - Distribusi ln-return saham memiliki ekor lebih tebal     ║
║    dari Gaussian (fat tail / excess kurtosis > 0)           ║
║  - Untuk BTC efek ini jauh lebih ekstrem                    ║
║  - Validasi: distribusi per regime harus berbeda secara     ║
║    statistik antara Bull / Bear / Sideways                  ║
╚══════════════════════════════════════════════════════════════╝

Usage:
    python backtest/return_distribution_test.py

Output:
    backtest/results/return_distribution_by_regime.csv
    backtest/results/transition_statistics.csv
    backtest/results/hmm_power_test_decision.md   (update I-00 PRD)
"""

from __future__ import annotations

import sys
import logging
import warnings
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from scipy import stats

# ── Path setup ────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _ROOT / "backend"
_ENGINES = _BACKEND / "engines"
_RESULTS = Path(__file__).resolve().parent / "results"
_RESULTS.mkdir(parents=True, exist_ok=True)

for p in [str(_BACKEND), str(_ENGINES)]:
    if p not in sys.path:
        sys.path.insert(0, p)

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# ════════════════════════════════════════════════════════════
#  KONSTANTA
# ════════════════════════════════════════════════════════════

FORWARD_HORIZONS = [1, 3, 5]    # Candle ke depan yang diuji
FAT_TAIL_THRESHOLD     = 1.0    # Excess kurtosis > ini = fat tail praktis
PREDICTIVE_P_THRESHOLD = 0.10   # p-value untuk menentukan "signifikan"
WIN_RATE_THRESHOLD     = 0.53   # Win-rate minimum agar regime dianggap predictive

# Window untuk walk-forward test (3 partisi non-overlapping)
WINDOWS = [
    ("W1-Early",  0.00, 0.33),
    ("W2-Mid",    0.33, 0.67),
    ("W3-Recent", 0.67, 1.00),
]


# ════════════════════════════════════════════════════════════
#  CORE FUNCTIONS
# ════════════════════════════════════════════════════════════

def analyze_return_distribution_by_regime(
    df: pd.DataFrame,
    hidden_states: np.ndarray,
    state_map: dict,
    window_name: str = "Full",
) -> pd.DataFrame:
    """
    Untuk setiap regime, hitung distribusi ln-return dan statistik
    prediktif terhadap forward return.

    Dari materi ekonofisika (Palupi, 2022 — Slide 21-24):
    Distribusi return pasar memiliki fat tail (kurtosis > 3).
    Validasi ini memastikan setiap regime memiliki karakteristik
    statistik yang BERBEDA — jika tidak, regime tidak informatif.

    Returns DataFrame dengan kolom:
        window, regime_label, n_candles, mean_return, std_return,
        skewness, excess_kurtosis, is_fat_tail, jb_p_value,
        is_non_gaussian, forward_Xc_mean, forward_Xc_winrate,
        t_stat, t_p_value, is_predictive, pass_i00
    """
    log_returns = np.log(df["Close"] / df["Close"].shift(1)).fillna(0).values
    rows: list[dict] = []

    for state_id in np.unique(hidden_states):
        label = state_map.get(int(state_id), f"State {state_id}")
        mask  = hidden_states == state_id
        r     = log_returns[mask]

        if len(r) < 5:
            logging.warning(f"  [Modul C] {label}: hanya {len(r)} candle, skip.")
            continue

        # ── Statistik distribusi ────────────────────────────────────────
        mean_r = float(np.mean(r))
        std_r  = float(np.std(r))
        skew_r = float(stats.skew(r))
        kurt_r = float(stats.kurtosis(r))      # excess kurtosis (Gaussian = 0)

        # Jarque-Bera test: H0 = distribusi normal
        jb_stat, jb_p = stats.jarque_bera(r)

        row: dict = {
            "window":          window_name,
            "regime_label":    label,
            "n_candles":       int(np.sum(mask)),
            "coverage_pct":    round(float(np.sum(mask)) / len(hidden_states) * 100, 1),
            "mean_return":     round(mean_r, 6),
            "std_return":      round(std_r,  6),
            "skewness":        round(skew_r, 4),
            "excess_kurtosis": round(kurt_r, 4),
            "is_fat_tail":     kurt_r > FAT_TAIL_THRESHOLD,
            "jb_p_value":      round(float(jb_p), 4),
            "is_non_gaussian": jb_p < 0.05,
        }

        # ── Forward return analysis (inti I-00) ─────────────────────────
        # Untuk setiap candle berlabel X, hitung return N candle ke depan
        indices = np.where(mask)[0]

        for h in FORWARD_HORIZONS:
            fwd_returns = []
            for idx in indices:
                future_idx = idx + h
                if future_idx < len(log_returns):
                    # Akumulasi return h candle ke depan
                    fwd = float(np.sum(log_returns[idx + 1: future_idx + 1]))
                    fwd_returns.append(fwd)

            if len(fwd_returns) < 10:
                row[f"forward_{h}c_mean"]    = np.nan
                row[f"forward_{h}c_winrate"] = np.nan
                row[f"forward_{h}c_t_stat"]  = np.nan
                row[f"forward_{h}c_p_value"] = np.nan
                row[f"forward_{h}c_predictive"] = False
                continue

            fwd_arr   = np.array(fwd_returns)
            fwd_mean  = float(np.mean(fwd_arr))
            win_rate  = float(np.mean(fwd_arr > 0))
            t_stat, t_p = stats.ttest_1samp(fwd_arr, 0)

            # Directional alignment check
            is_bull_label = "Bullish" in label
            is_bear_label = "Bearish" in label

            if is_bull_label:
                directional_ok = fwd_mean > 0 and win_rate > WIN_RATE_THRESHOLD
            elif is_bear_label:
                directional_ok = fwd_mean < 0 and win_rate < (1 - WIN_RATE_THRESHOLD)
            else:
                directional_ok = True   # Sideways tidak perlu directionality

            is_pred = directional_ok and float(t_p) < PREDICTIVE_P_THRESHOLD

            row[f"forward_{h}c_mean"]       = round(fwd_mean,        6)
            row[f"forward_{h}c_winrate"]    = round(win_rate,         4)
            row[f"forward_{h}c_t_stat"]     = round(float(t_stat),    4)
            row[f"forward_{h}c_p_value"]    = round(float(t_p),       4)
            row[f"forward_{h}c_predictive"] = is_pred

        # ── I-00 PASS/FAIL per regime ───────────────────────────────────
        # Regime lulus jika setidaknya 2 dari 3 horizon menunjukkan prediktivitas
        predictive_count = sum(
            row.get(f"forward_{h}c_predictive", False)
            for h in FORWARD_HORIZONS
        )
        row["predictive_horizon_count"] = predictive_count
        row["pass_i00"] = predictive_count >= 2

        rows.append(row)

    return pd.DataFrame(rows)


def compute_transition_statistics(
    hidden_states: np.ndarray,
    state_map: dict,
) -> pd.DataFrame:
    """
    Hitung statistik durasi regime dari urutan state.

    Dari teori rantai Markov (Palupi, 2022 — Materi 1):
    Sifat memori pendek Proses Markov menghasilkan distribusi
    durasi eksponensial untuk setiap regime.

    Memvalidasi konsistensi state_map: regime yang terlalu singkat
    atau terlalu dominan adalah tanda labeling yang buruk.
    """
    n_states  = int(max(hidden_states)) + 1
    durations: dict[int, list] = {i: [] for i in range(n_states)}

    cur_state = int(hidden_states[0])
    cur_dur   = 1

    for t in range(1, len(hidden_states)):
        s = int(hidden_states[t])
        if s == cur_state:
            cur_dur += 1
        else:
            durations[cur_state].append(cur_dur)
            cur_state = s
            cur_dur   = 1
    durations[cur_state].append(cur_dur)

    rows = []
    for state_id in range(n_states):
        label = state_map.get(state_id, f"State {state_id}")
        d     = durations.get(state_id, [])
        if not d:
            continue
        freq = float(np.sum(hidden_states == state_id) / len(hidden_states))
        rows.append({
            "state_id":               state_id,
            "regime_label":           label,
            "n_runs":                 len(d),
            "mean_duration_candles":  round(float(np.mean(d)), 1),
            "median_duration_candles": round(float(np.median(d)), 1),
            "max_duration_candles":   int(np.max(d)),
            "min_duration_candles":   int(np.min(d)),
            "frequency_pct":          round(freq * 100, 1),
            # Teoritis: jika Markovian, durasi ~ Geometrik(1-P[i,i])
            # E[T] = 1/(1-P[i,i]) → P[i,i] = 1 - 1/E[T]
            "implied_persistence":    round(1.0 - 1.0 / max(float(np.mean(d)), 1.0), 4),
        })

    return pd.DataFrame(rows)


def run_walkforward_test(
    df: pd.DataFrame,
    hmm_model,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Jalankan analisis distribusi pada 3 window non-overlapping.
    Ini adalah core dari I-00 PRD: HMM harus menunjukkan prediktivitas
    yang konsisten di setidaknya 2 dari 3 window.

    Returns:
        (dist_df, trans_df) — combined DataFrames dari semua windows
    """
    all_dist  = []
    all_trans = []
    n         = len(df)

    for wname, frac_start, frac_end in WINDOWS:
        i_start = int(n * frac_start)
        i_end   = int(n * frac_end)
        df_win  = df.iloc[i_start:i_end].reset_index(drop=True)

        if len(df_win) < 100:
            logging.warning(f"  [Modul C] Window {wname} terlalu kecil ({len(df_win)} baris), skip.")
            continue

        logging.info(f"  [Modul C] Menjalankan window {wname} "
                     f"(candle {i_start}–{i_end}, n={len(df_win)})")

        try:
            # Train HMM pada window ini
            success = hmm_model.train_global(df_win)
            if not success:
                logging.warning(f"  [Modul C] train_global gagal untuk {wname}")
                continue

            # Dapatkan hidden states untuk seluruh window
            df_feat = hmm_model.prepare_features(df_win)
            df_feat_clean = df_feat.dropna(subset=hmm_model._active_features)
            X_raw   = df_feat_clean[hmm_model._active_features].values
            X_scaled = hmm_model.scaler.transform(X_raw)
            
            # Mendukung baik HMM (sklearn) maupun BCD (custom array generator)
            if hasattr(hmm_model, "train_model"):
                # BCD engine / custom wrapper
                hidden_states = hmm_model.train_model(X_scaled, current_len=len(df_win))
            elif hasattr(hmm_model, "model") and hasattr(hmm_model.model, "predict"):
                # HMM / SkLearn engine
                hidden_states = hmm_model.model.predict(X_scaled)
            else:
                logging.error(f"Engine {type(hmm_model).__name__} tidak support batch prediction.")
                continue

            # Distribusi return per regime
            dist_df  = analyze_return_distribution_by_regime(
                df_win, hidden_states, hmm_model.state_map, window_name=wname
            )
            all_dist.append(dist_df)

            # Statistik transisi
            trans_df = compute_transition_statistics(hidden_states, hmm_model.state_map)
            trans_df.insert(0, "window", wname)
            all_trans.append(trans_df)

        except Exception as exc:
            logging.error(f"  [Modul C] Window {wname} error: {exc}")
            continue

    combined_dist  = pd.concat(all_dist,  ignore_index=True) if all_dist  else pd.DataFrame()
    combined_trans = pd.concat(all_trans, ignore_index=True) if all_trans else pd.DataFrame()
    return combined_dist, combined_trans


def generate_i00_decision(dist_df: pd.DataFrame) -> str:
    """
    Buat keputusan I-00 (PASS/FAIL) dan tulis ke Markdown.

    Kriteria PASS (dari PRD v1.1):
    - Regime Bullish: mean forward return POSITIF dan signifikan (p < 0.1)
      dalam setidaknya 2 dari 3 window
    - Regime Bearish: mean forward return NEGATIF dan signifikan
      dalam setidaknya 2 dari 3 window
    - Win-rate Bullish > 53% out-of-sample
    """
    if dist_df.empty:
        verdict      = "INCONCLUSIVE"
        summary_text = "Tidak cukup data untuk evaluasi."
    else:
        # Agregasi per regime + window
        bull_rows = dist_df[dist_df["regime_label"].str.contains("Bullish", na=False)]
        bear_rows = dist_df[dist_df["regime_label"].str.contains("Bearish", na=False)]

        bull_pass_windows = int(bull_rows["pass_i00"].sum()) if not bull_rows.empty else 0
        bear_pass_windows = int(bear_rows["pass_i00"].sum()) if not bear_rows.empty else 0

        bull_pass = bull_pass_windows >= 2
        bear_pass = bear_pass_windows >= 2

        # Win-rate check
        col_wr = "forward_1c_winrate"
        if col_wr in dist_df.columns:
            bull_wr = bull_rows[col_wr].mean() if not bull_rows.empty else np.nan
            bear_wr_inv = (1 - bear_rows[col_wr]).mean() if not bear_rows.empty else np.nan
        else:
            bull_wr = np.nan
            bear_wr_inv = np.nan

        wr_ok = (
            (pd.isna(bull_wr) or float(bull_wr) > WIN_RATE_THRESHOLD) and
            (pd.isna(bear_wr_inv) or float(bear_wr_inv) > WIN_RATE_THRESHOLD)
        )

        if bull_pass and bear_pass and wr_ok:
            verdict = "PASS"
        elif bull_pass or bear_pass:
            verdict = "PARTIAL"
        else:
            verdict = "FAIL"

        summary_text = (
            f"- Bullish pass windows : {bull_pass_windows}/3 (butuh ≥2)\n"
            f"- Bearish pass windows : {bear_pass_windows}/3 (butuh ≥2)\n"
            f"- Bull win-rate mean   : {bull_wr:.3f}" if not pd.isna(bull_wr) else "N/A"
        )

    now_str  = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    md = f"""# I-00 HMM Predictive Power Test — Decision Record

**Tanggal evaluasi:** {now_str}  
**Verdict:** `{verdict}`

---

## Ringkasan

```
{summary_text}
```

## Kriteria Evaluasi (PRD v1.1)

| Kriteria | Threshold | Hasil |
|---|---|---|
| Bullish: mean fwd return positif & signifikan | p < 0.10, ≥2/3 windows | {'✅ PASS' if verdict in ('PASS', 'PARTIAL') else '❌ FAIL'} |
| Bearish: mean fwd return negatif & signifikan | p < 0.10, ≥2/3 windows | {'✅ PASS' if verdict in ('PASS', 'PARTIAL') else '❌ FAIL'} |
| Bull win-rate out-of-sample | > 53% | {'✅' if not pd.isna(bull_wr) and bull_wr > WIN_RATE_THRESHOLD else '⚠️'} |

## Tindak Lanjut

{"**→ PROCEED**: Lanjutkan I-01 → I-02 → I-03 sesuai PRD v1.1." if verdict == 'PASS' else "**→ PARTIAL**: Review label_states() dan BIC n_states. Jalankan ulang setelah perbaikan." if verdict == 'PARTIAL' else "**→ REDESIGN LAYER 1**: HMM tidak menunjukkan prediktivitas. Pertimbangkan GMMHMM, Markov Switching, atau BCD sebagai pengganti."}

## Data Lengkap

Lihat: `backtest/results/return_distribution_by_regime.csv`  
Lihat: `backtest/results/transition_statistics.csv`

---
*Generated by: `backtest/return_distribution_test.py` (Modul C — Econophysics)*
"""
    return md, verdict


# ════════════════════════════════════════════════════════════
#  MAIN RUNNER
# ════════════════════════════════════════════════════════════

def main():
    print("\n ⚡ BTC-QUANT · Modul C — Return Distribution Test (I-00 PRD)")
    print(" ─" * 40)

    # ── Load data ────────────────────────────────────────────────────────────
    try:
        from data_engine import get_latest_market_data
        df, _ = get_latest_market_data()
    except Exception as exc:
        logging.error(f"Tidak bisa load data dari DuckDB: {exc}")
        df = None

    # Fallback: load dari backtest/data jika ada
    if df is None or df.empty:
        data_files = list((_ROOT / "backtest" / "data").glob("*.csv"))
        if data_files:
            logging.info(f"Menggunakan file CSV: {data_files[0].name}")
            df = pd.read_csv(data_files[0])
            df.columns = [c.capitalize() for c in df.columns]
        else:
            logging.error("Tidak ada data tersedia. Jalankan data_engine.py terlebih dahulu.")
            return

    if len(df) < 100:
        logging.error(f"Data terlalu sedikit: {len(df)} baris. Butuh minimal 100.")
        return

    print(f"\n  📊 Total data: {len(df)} candle")

    # ── Load HMM model ───────────────────────────────────────────────────────
    try:
        from app.services.bcd_service import get_bcd_service
        hmm_model = get_bcd_service()._model
    except Exception as exc:
        logging.error(f"Tidak bisa load HMM/BCD Service: {exc}")
        return

    # ── Run walk-forward test ────────────────────────────────────────────────
    print("\n  🔄 Menjalankan walk-forward test (3 window)...")
    dist_df, trans_df = run_walkforward_test(df, hmm_model)

    if dist_df.empty:
        print("  ⚠  Tidak ada hasil — periksa log error di atas.")
        return

    # ── Simpan hasil ─────────────────────────────────────────────────────────
    dist_path  = _RESULTS / "return_distribution_by_regime.csv"
    trans_path = _RESULTS / "transition_statistics.csv"

    dist_df.to_csv(dist_path,  index=False)
    trans_df.to_csv(trans_path, index=False)
    print(f"\n  💾 Distribusi tersimpan → {dist_path.name}")
    print(f"  💾 Transisi tersimpan  → {trans_path.name}")

    # ── Generate I-00 decision ───────────────────────────────────────────────
    md_content, verdict = generate_i00_decision(dist_df)
    md_path = _RESULTS / "hmm_power_test_decision.md"
    md_path.write_text(md_content, encoding="utf-8")
    print(f"  📋 I-00 decision       → {md_path.name}")

    # ── Print ringkasan ke terminal ──────────────────────────────────────────
    print(f"\n  {'═'*60}")
    print(f"  I-00 VERDICT: {verdict}")
    print(f"  {'═'*60}")

    print("\n  Ringkasan per regime:\n")
    summary_cols = [
        "window", "regime_label", "n_candles",
        "mean_return", "excess_kurtosis", "is_fat_tail",
        "forward_1c_winrate", "forward_1c_p_value", "pass_i00",
    ]
    available_cols = [c for c in summary_cols if c in dist_df.columns]
    print(dist_df[available_cols].to_string(index=False))

    if not trans_df.empty:
        print("\n  Statistik durasi regime:\n")
        print(trans_df.to_string(index=False))

    print("\n  ✅ Modul C selesai.\n")


if __name__ == "__main__":
    main()
