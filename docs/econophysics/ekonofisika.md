# 📐 Fondasi Ekonofisika untuk BTC-Quant: Penentuan Regime Bias

> **Dokumen:** Proposal Pengembangan Berbasis Teori  
> **Project:** `btc-scalping-quant`  
> **Dasar Teori:** Proses Stokastik & Pasar Keuangan (Dwi Satya Palupi, 2022)  
> **Versi:** v1.0 — Maret 2026

---

## 1. Landasan Teoritis: Mengapa Ekonofisika Relevan untuk BTC

Materi ekonofisika yang dipelajari memberikan dua **pijakan fundamental** yang langsung menyentuh arsitektur BTC-Quant saat ini:

### 1.1 Dari Materi 1 — Proses Stokastik

BTC bukan aset deterministik. Pergerakan harganya adalah **proses stokastik** — keluarga variabel acak yang sifat statistiknya berubah terhadap waktu:

$$X: \Omega \times T \rightarrow \mathbb{R}$$

Yang lebih penting: BTC mendekati **Proses Markov** — harga berikutnya hanya bergantung pada kondisi **saat ini**, bukan seluruh riwayat:

$$P(X(t) \in B \mid X(t_m)=x_m, \ldots, X(t_1)=x_1) = P(X(t) \in B \mid X(t_m)=x_m)$$

> **Implikasi langsung ke kode:** Inilah yang memvalidasi penggunaan `GaussianMixture` di `layer1_hmm.py` — model bekerja atas asumsi bahwa setiap candle membawa informasi lengkap tentang regime saat ini tanpa perlu memori panjang.

### 1.2 Dari Materi 2 — Pasar Keuangan & Proses Stokastik

Harga saham (dan BTC) dimodelkan sebagai **persamaan diferensial stokastik (PDS)**:

$$dS(t) = \varphi S(t) \, dt + \sigma S \, dW$$

Di mana:
- $\varphi$ = **drift** — tren deterministik (fundamental, sentimen makro)
- $\sigma$ = **volatilitas** — besarnya fluktuasi acak
- $dW$ = proses Wiener standar (Gerak Brown)

Untuk BTC, temuan dari data BEI sangat relevan: distribusi return memiliki **ekor lebih tebal dari Gaussian** (*fat tail*). Untuk BTC, efek ini jauh lebih ekstrem — crash -20% dalam satu hari lebih sering dari prediksi model normal.

---

## 2. Pemetaan Teori → Komponen Existing BTC-Quant

| Konsep Ekonofisika | Komponen Existing | Status |
|---|---|---|
| Proses Markov (ingatan pendek) | `layer1_hmm.py` GaussianMixture | ✅ Sesuai teori |
| 4 tipe proses stokastik | 4 regime label (Bull/Bear/HV-SW/LV-SW) | ✅ Sesuai teori |
| Komponen drift $\varphi$ | `layer2_ema.py` — EMA trend direction | ✅ Ada |
| Komponen stokastik $\sigma dW$ | `realized_vol`, `hl_spread` features | ✅ Ada |
| Persamaan Fokker-Planck | Belum ada distribusi peluang transisi | ❌ Gap |
| Fat tail / distribusi ekor | Belum ada model distribusi return BTC | ❌ Gap |
| Model Heston (volatilitas stokastik) | Volatilitas dianggap konstan | ⚠️ Perlu upgrade |
| Log-return analysis | `ln_return` sebagai fitur HMM | ✅ Ada |
| Distribusi log-normal harga | Belum digunakan untuk validasi regime | ❌ Gap |

---

## 3. Gap Kritis: Masalah yang Belum Terjawab Secara Teoritis

### Gap 1 — HMM Tidak Memiliki Model Peluang Transisi Eksplisit

`layer1_hmm.py` saat ini menggunakan **GaussianMixture** (clustering), bukan HMM sejati. `GaussianMixture` tidak memiliki `transmat_` (matriks probabilitas transisi antar state). Ini berarti:

> Sistem tidak bisa menjawab: *"Jika sekarang Bullish Trend, berapa peluang berikutnya masih Bullish vs berbalik Bearish?"*

Padahal, dari teori proses Markov, **peluang transisi inilah inti dari regime bias**:

$$P_{ij} = P(X(t+1) = j \mid X(t) = i)$$

### Gap 2 — Volatilitas Dianggap Konstan ($\sigma = \text{konst}$)

Model GBM dasar mengasumsikan $\sigma$ konstan. Untuk BTC, ini jelas salah — volatilitas BTC bisa berbeda 10x antara periode tenang dan periode krisis. **Model Heston** dari materi 2 menyelesaikan ini dengan membuat $\sigma$ sendiri mengikuti proses stokastik.

### Gap 3 — Tidak Ada Pengukuran Kualitas Distribusi Return

Saat ini tidak ada perbandingan antara distribusi empiris ln-return BTC dengan distribusi teoritis. Padahal, dari materi 2 (slide perbandingan IHSG/LQ45/JII), inilah cara memvalidasi apakah model stokastik yang dipilih sesuai dengan data nyata.

---

## 4. Proposal Pengembangan: Regime Bias dari Perspektif Ekonofisika

Berdasarkan dua gap di atas, berikut tiga modul pengembangan yang diusulkan, tersusun dari yang paling fundamental hingga paling advanced.

---

### Modul A — Transition Probability Matrix (Prioritas Tinggi)

**Dasar teori:** Proses Markov — peluang event berikutnya hanya bergantung pada state saat ini.

**Masalah saat ini:** `GaussianMixture` tidak memiliki `transmat_`. Akibatnya, `get_directional_vote()` di `layer1_hmm.py` hanya menggunakan *posterior probability* pada satu candle terakhir — tanpa memperhitungkan **ke mana regime cenderung bergerak**.

**Solusi yang diusulkan:**

Setelah `GaussianMixture` men-*predict* urutan state untuk seluruh data historis, hitung matriks transisi empiris secara manual:

```python
# File: backend/engines/layer1_hmm.py — tambahan pada train_global()

def _compute_transition_matrix(self, hidden_states: np.ndarray) -> np.ndarray:
    """
    Hitung matriks transisi empiris dari urutan state.
    
    Dari teori Proses Markov:
      P[i, j] = P(state_t+1 = j | state_t = i)
    
    Ini adalah perkiraan empiris dari matriks transisi Markov,
    dihitung langsung dari data historis.
    
    Returns:
        transition_matrix: ndarray shape (n_states, n_states)
        Setiap baris dinormalisasi sehingga sum = 1.0
    """
    n = self._active_n_states
    trans_matrix = np.zeros((n, n))
    
    for t in range(len(hidden_states) - 1):
        i = hidden_states[t]
        j = hidden_states[t + 1]
        trans_matrix[i, j] += 1
    
    # Normalisasi per baris (row-stochastic matrix)
    row_sums = trans_matrix.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1  # hindari division by zero
    transition_matrix = trans_matrix / row_sums
    
    return transition_matrix

def get_regime_bias(self) -> dict:
    """
    Dari matriks transisi, hitung 'regime bias' untuk setiap state:
    Bias = P(masih di state sama) - P(berbalik ke state berlawanan)
    
    Interpretasi untuk trader:
    - bias > 0.5: regime cenderung berlanjut (trend following valid)
    - bias < 0.3: regime cenderung berbalik (mean-reversion valid)
    """
    if self._transition_matrix is None:
        return {}
    
    bias_report = {}
    for state_id, label in self.state_map.items():
        if state_id >= len(self._transition_matrix):
            continue
        row = self._transition_matrix[state_id]
        
        # Persistence: peluang tetap di regime saat ini
        persistence = row[state_id]
        
        # Reversal probability ke state berlawanan
        reversal = 0.0
        for other_id, other_label in self.state_map.items():
            if other_id == state_id:
                continue
            # State "berlawanan" = jika sekarang Bull, lawannya Bear
            if ("Bullish" in label and "Bearish" in other_label) or \
               ("Bearish" in label and "Bullish" in other_label):
                reversal += row[other_id]
        
        bias_report[label] = {
            "persistence":   round(float(persistence), 4),
            "reversal_prob": round(float(reversal), 4),
            "bias_score":    round(float(persistence - reversal), 4),
            "next_state_probs": {
                self.state_map.get(j, f"State {j}"): round(float(p), 4)
                for j, p in enumerate(row)
            }
        }
    
    return bias_report
```

**Output yang dihasilkan untuk API `/signal`:**

```json
{
  "current_regime": "Bullish Trend",
  "regime_bias": {
    "Bullish Trend": {
      "persistence": 0.74,
      "reversal_prob": 0.08,
      "bias_score": 0.66,
      "next_state_probs": {
        "Bullish Trend": 0.74,
        "High Volatility Sideways": 0.18,
        "Low Volatility Sideways": 0.08,
        "Bearish Trend": 0.00
      }
    }
  }
}
```

**Interpretasi untuk trader scalper:** `bias_score = 0.66` → regime Bullish sangat persistent, trend-following entry valid. Jika `bias_score < 0.3` → regime tidak stabil, hindari entry atau gunakan SL lebih ketat.

---

### Modul B — Stochastic Volatility: Upgrade ke Model Heston (Prioritas Menengah)

**Dasar teori:** Model Heston dari materi 2 — volatilitas sendiri mengikuti proses stokastik:

$$dS(t) = \varphi S(t) \, dt + \sqrt{v(t)} \, S \, dB_S$$
$$dv(t) = -\gamma(v - \eta) \, dt + \kappa \sqrt{v} \, dB_v$$

Di mana:
- $v(t) = \sigma^2(t)$ = variansi yang berubah terhadap waktu
- $\gamma$ = kecepatan mean-reversion volatilitas
- $\eta$ = volatilitas jangka panjang (long-run mean)
- $\kappa$ = volatilitas dari volatilitas (*vol-of-vol*)

**Relevansi ke BTC-Quant:** Saat ini `realized_vol` digunakan sebagai fitur HMM, tetapi perlakuannya sama dengan fitur lain. Dengan model Heston, volatilitas diperlakukan sebagai **variabel state tersendiri** dengan dinamika yang lebih kaya.

**Implementasi yang diusulkan:**

```python
# File: backend/engines/layer1_volatility.py (BARU)

class VolatilityRegimeEstimator:
    """
    Estimasi parameter model Heston dari data historis BTC.
    
    Dari materi ekonofisika (Dwi Satya Palupi, 2022):
    Model Heston memungkinkan volatilitas bergerak secara stokastik
    dengan kecenderungan kembali ke rata-rata jangka panjang (mean-reverting).
    
    Parameter yang diestimasi:
    - gamma (γ): kecepatan mean-reversion
    - eta (η): volatilitas long-run
    - kappa (κ): vol-of-vol
    """
    
    def estimate_heston_params(self, df: pd.DataFrame) -> dict:
        """
        Estimasi parameter Heston menggunakan Metode Moments.
        """
        log_returns = np.log(df["Close"] / df["Close"].shift(1)).dropna()
        
        # Realized variance per candle (proxy untuk v(t))
        realized_var = log_returns.rolling(14).var().dropna()
        
        # dv = perubahan realized variance
        dv = realized_var.diff().dropna()
        v = realized_var.iloc[:-1]
        
        # Estimasi gamma (mean-reversion speed) dan eta (long-run mean)
        # dv ≈ -gamma*(v - eta)*dt + noise
        # OLS: dv = alpha + beta*v → alpha = gamma*eta, beta = -gamma
        from numpy.linalg import lstsq
        
        X = np.column_stack([np.ones(len(v)), v.values])
        y = dv.values
        
        coeffs, _, _, _ = lstsq(X, y, rcond=None)
        alpha, beta = coeffs
        
        gamma = max(-beta, 1e-6)          # kecepatan mean-reversion (harus positif)
        eta   = alpha / gamma             # volatilitas jangka panjang
        
        # Estimasi kappa (vol of vol)
        residuals = y - (alpha + beta * v.values)
        kappa = float(np.std(residuals) / np.sqrt(np.mean(v.values)))
        
        current_vol = float(np.sqrt(realized_var.iloc[-1]))
        
        return {
            "gamma":         round(gamma, 6),   # mean-reversion speed
            "eta":           round(eta, 6),      # long-run variance
            "kappa":         round(kappa, 6),    # vol of vol
            "current_vol":   round(current_vol, 6),
            "vol_regime":    "High" if current_vol > np.sqrt(eta) * 1.5 else
                             "Low"  if current_vol < np.sqrt(eta) * 0.7 else "Normal",
            "mean_reversion_halflife_candles": round(np.log(2) / gamma, 1)
        }
```

**Penggunaan output untuk regime bias:**

```python
# Dalam signal_service.py
vol_params = vol_estimator.estimate_heston_params(df)

# Jika volatilitas saat ini jauh di atas long-run mean DAN mean-reverting cepat
# → Regime tidak stabil, bias ke Sideways dalam N candle ke depan
if vol_params["vol_regime"] == "High" and vol_params["gamma"] > 0.3:
    # Perkiraan: volatilitas akan kembali ke normal dalam X candle
    reversion_candles = vol_params["mean_reversion_halflife_candles"]
    # Gunakan ini untuk menyesuaikan SL/TP horizon
```

---

### Modul C — Return Distribution Validator (Prioritas Menengah)

**Dasar teori:** Dari materi 2 — distribusi ln-return harga saham mengikuti distribusi dengan ekor tebal, divalidasi dengan perbandingan teoritis vs empiris seperti pada data IHSG/LQ45/JII.

**Tujuan di BTC-Quant:** Menjawab pertanyaan I-00 di PRD (*"apakah regime label HMM berkorelasi dengan forward return?"*) dengan cara yang lebih kaya secara statistik.

**Implementasi yang diusulkan:**

```python
# File: backtest/return_distribution_test.py (BARU)
"""
Mengimplementasikan analisis distribusi return seperti pada:
Palupi, Dwi Satya (2022) - Pasar Keuangan dan Proses Stokastik
Slide 22-24: Perbandingan distribusi teoritis vs empiris
"""

import numpy as np
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt


def analyze_return_distribution_by_regime(df: pd.DataFrame, regime_labels: np.ndarray) -> dict:
    """
    Untuk setiap regime, hitung distribusi ln-return dan bandingkan
    dengan distribusi Normal (Gaussian).
    
    Dari teori: distribusi return pasar umumnya memiliki fat tail
    (kurtosis > 3). Validasi ini memastikan regime yang terdeteksi
    memang memiliki karakteristik statistik yang berbeda.
    
    Returns dict dengan statistik per regime:
    - mean, std, skewness, kurtosis
    - p-value Jarque-Bera test (apakah normal?)
    - tail_index (ukuran ketebalan ekor)
    """
    log_returns = np.log(df["Close"] / df["Close"].shift(1)).fillna(0).values
    
    regime_stats = {}
    unique_regimes = np.unique(regime_labels)
    
    for regime_id in unique_regimes:
        mask = regime_labels == regime_id
        regime_returns = log_returns[mask]
        
        if len(regime_returns) < 20:
            continue
        
        # Statistik deskriptif
        mean_r   = float(np.mean(regime_returns))
        std_r    = float(np.std(regime_returns))
        skew_r   = float(stats.skew(regime_returns))
        kurt_r   = float(stats.kurtosis(regime_returns))  # Excess kurtosis
        
        # Jarque-Bera test: H0 = distribusi normal
        # p < 0.05 → distribusi BUKAN normal → fat tail terdeteksi
        jb_stat, jb_p = stats.jarque_bera(regime_returns)
        
        # Forward return analysis (inti dari I-00 PRD)
        forward_1c  = np.roll(log_returns, -1)[mask]   # return 1 candle ke depan
        forward_3c  = np.roll(log_returns, -3)[mask]   # return 3 candle ke depan
        forward_5c  = np.roll(log_returns, -5)[mask]   # return 5 candle ke depan
        
        win_rate_1c = float(np.mean(forward_1c > 0))
        win_rate_3c = float(np.mean(forward_3c > 0))
        
        # T-test: apakah mean forward return berbeda secara signifikan dari 0?
        t_stat, t_p = stats.ttest_1samp(forward_1c[:-1], 0)  # exclude last (NaN)
        
        regime_stats[int(regime_id)] = {
            "n_candles":        int(np.sum(mask)),
            "mean_return":      round(mean_r,  6),
            "std_return":       round(std_r,   6),
            "skewness":         round(skew_r,  4),
            "excess_kurtosis":  round(kurt_r,  4),  # > 0 = fat tail
            "is_fat_tail":      kurt_r > 1.0,        # threshold praktis
            "jb_p_value":       round(jb_p,   4),
            "is_non_gaussian":  jb_p < 0.05,
            "forward_1c_mean":  round(float(np.mean(forward_1c)), 6),
            "forward_1c_winrate": round(win_rate_1c, 4),
            "forward_3c_winrate": round(win_rate_3c, 4),
            "t_stat":           round(float(t_stat), 4),
            "t_p_value":        round(float(t_p),    4),
            "is_predictive":    t_p < 0.1,   # signifikan pada 90% confidence
        }
    
    return regime_stats


def compute_transition_statistics(hidden_states: np.ndarray, state_map: dict) -> dict:
    """
    Hitung statistik tambahan dari urutan state:
    - Expected duration (rata-rata berapa candle tiap regime berlangsung)
    - Regime frequency distribution
    - Most likely next regime
    
    Berdasarkan properti rantai Markov dari materi 1.
    """
    n_states = max(hidden_states) + 1
    
    # Durasi rata-rata per regime
    durations = {i: [] for i in range(n_states)}
    current_state = hidden_states[0]
    current_duration = 1
    
    for t in range(1, len(hidden_states)):
        if hidden_states[t] == current_state:
            current_duration += 1
        else:
            durations[current_state].append(current_duration)
            current_state = hidden_states[t]
            current_duration = 1
    durations[current_state].append(current_duration)
    
    result = {}
    for state_id in range(n_states):
        label = state_map.get(state_id, f"State {state_id}")
        d = durations[state_id]
        if not d:
            continue
        result[label] = {
            "mean_duration_candles": round(float(np.mean(d)), 1),
            "max_duration_candles":  int(np.max(d)),
            "min_duration_candles":  int(np.min(d)),
            "frequency":             round(float(np.sum(hidden_states == state_id) / len(hidden_states)), 4)
        }
    
    return result
```

---

## 5. Integrasi ke Arsitektur Existing

### 5.1 Alur yang Diusulkan

```
Data OHLCV + Microstructure
          │
          ▼
┌─────────────────────────────────┐
│  layer1_hmm.py (ENHANCED)       │
│  ─────────────────────────────  │
│  1. train_global()              │
│     → GaussianMixture predict   │
│     → _compute_transition_matrix() [BARU — Modul A]
│     → label_states() (existing) │
│                                 │
│  2. get_directional_vote()      │
│     → posterior × bias_score   [ENHANCED — Modul A]
│                                 │
│  Output:                        │
│  - regime_label (existing)      │
│  - posterior (existing)         │
│  - transition_matrix [BARU]     │
│  - regime_bias dict [BARU]      │
└─────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────┐
│  layer1_volatility.py [BARU — Modul B]
│  ─────────────────────────────  │
│  estimate_heston_params()       │
│  → gamma, eta, kappa            │
│  → vol_regime (High/Normal/Low) │
│  → reversion_halflife           │
└─────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────┐
│  signal_service.py (ENHANCED)   │
│  ─────────────────────────────  │
│  DirectionalSpectrum.calculate()│
│  → Gabungkan regime_bias +      │
│     vol_regime untuk SL/TP      │
│     adjustment (I-05 PRD)       │
└─────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────┐
│  backtest/return_distribution_  │
│  test.py [BARU — Modul C]       │
│  ─────────────────────────────  │
│  analyze_return_distribution_   │
│  by_regime()                    │
│  → Menjawab I-00 PRD dengan     │
│     statistik yang lebih kaya   │
└─────────────────────────────────┘
```

### 5.2 Perubahan di `signal_service.py`

```python
# Tambahan di DirectionalSpectrum.calculate()

# Layer 1: Regime + Bias (ENHANCED)
regime_label, state_id, posterior = hmm_model.get_current_regime_posterior(df)
regime_bias = hmm_model.get_regime_bias()  # BARU — Modul A
bias_score  = regime_bias.get(regime_label, {}).get("bias_score", 0.5)
persistence = regime_bias.get(regime_label, {}).get("persistence", 0.5)

# Volatility Regime (BARU — Modul B)
vol_params    = vol_estimator.estimate_heston_params(df)
vol_regime    = vol_params["vol_regime"]        # "High" / "Normal" / "Low"
revert_candles = vol_params["mean_reversion_halflife_candles"]

# Penyesuaian conviction berdasarkan regime bias
# Dari teori Markov: jika persistence tinggi → conviction lebih tinggi
conviction_multiplier = 0.7 + (0.6 * bias_score)  # range: 0.7 — 1.3

# Penyesuaian SL/TP berdasarkan Heston vol regime
# Dari teori: saat vol tinggi dan mean-reverting cepat → TP lebih ketat
if vol_regime == "High" and revert_candles < 10:
    # Volatilitas sedang tinggi dan akan cepat turun
    # → Ambil profit lebih cepat, SL lebih lebar
    sl_multiplier = 2.0
    tp1_multiplier = 1.2
    tp2_multiplier = 1.8
elif vol_regime == "Low":
    # Volatilitas tenang → trend lebih reliable
    sl_multiplier = 1.0
    tp1_multiplier = 1.8
    tp2_multiplier = 2.5
else:
    # Normal
    sl_multiplier = 1.5
    tp1_multiplier = 2.0
    tp2_multiplier = 3.0
```

### 5.3 Penambahan Field di API Response

```json
{
  "regime": "Bullish Trend",
  "regime_bias": {
    "persistence": 0.74,
    "reversal_prob": 0.08,
    "bias_score": 0.66,
    "interpretation": "Regime berlanjut dengan probabilitas tinggi. Trend-following valid."
  },
  "volatility_regime": {
    "current_vol": 0.024,
    "long_run_vol": 0.018,
    "vol_regime": "High",
    "mean_reversion_halflife_candles": 8.3,
    "interpretation": "Volatilitas sedang tinggi, perkiraan kembali normal dalam ~8 candle"
  },
  "sl_tp_preset": {
    "sl_multiplier": 2.0,
    "tp1_multiplier": 1.2,
    "tp2_multiplier": 1.8,
    "basis": "Heston-High-Vol + Regime-Bias"
  }
}
```

---

## 6. Koneksi Langsung ke PRD v1.1

| Item PRD | Hubungan dengan Proposal Ini |
|---|---|
| **I-00** HMM Predictive Power Test | Modul C menyediakan framework statistik yang lebih kaya: forward return, t-test, win-rate per regime |
| **I-03** Walk-Forward Validation | Modul C `analyze_return_distribution_by_regime()` dapat dijalankan per window untuk validasi konsistensi |
| **I-05** Regime-Aware SL/TP | Modul A `bias_score` + Modul B `vol_regime` memberikan dua dimensi penyesuaian SL/TP yang lebih justified secara teoritis |
| **I-06** Enforce Verdict Logic | Modul A `persistence` dapat digunakan: jika persistence rendah, LLM verdict diberi bobot lebih tinggi |

---

## 7. Urutan Implementasi yang Disarankan

Implementasi sebaiknya dilakukan secara bertahap, mengikuti urutan dari yang paling fundamental:

**Tahap 1 — Modul A (1-2 hari):** Tambahkan `_compute_transition_matrix()` dan `get_regime_bias()` ke `layer1_hmm.py`. Update `cache_info()` untuk expose `transition_matrix` dan `regime_bias`. Tambahkan field ke API response. Ini tidak mengubah logika apa pun yang ada — hanya menambah informasi.

**Tahap 2 — Modul C (1 hari):** Buat `backtest/return_distribution_test.py`. Jalankan sebagai bagian dari I-00. Output-nya langsung mengisi `hmm_power_test.csv` yang dibutuhkan PRD.

**Tahap 3 — Modul B (2-3 hari):** Buat `layer1_volatility.py`. Integrasikan ke `signal_service.py` untuk menggerakkan SL/TP multiplier (I-05). Ini membutuhkan validasi lebih lama karena mengubah logika output.

---

## 8. Ringkasan: Dari Teori ke Kode

| Konsep Teori (Materi Ekonofisika) | Implementasi Konkret di BTC-Quant |
|---|---|
| Proses Markov: kondisi masa depan hanya bergantung pada masa kini | Validasi asumsi Markovian pada data BTC historis; gunakan sebagai justifikasi GaussianMixture |
| Matriks transisi $P_{ij}$ | `_compute_transition_matrix()` → `regime_bias` → persistence score untuk conviction |
| Persamaan Fokker-Planck: evolusi distribusi peluang terhadap waktu | `return_distribution_test.py` — distribusi return per regime, validasi non-Gaussian |
| Model Heston: $dv(t) = -\gamma(v-\eta)dt + \kappa\sqrt{v}dB_v$ | `VolatilityRegimeEstimator` → gamma, eta, kappa → `vol_regime` → SL/TP multiplier |
| Fat tail / distribusi ekor tebal | Kurtosis > 3 sebagai metrik validasi regime; SL lebih lebar saat fat tail terdeteksi |
| Log-return $l_r = \ln(S(t)/S(0))$ | Sudah ada di `layer1_hmm.py` sebagai `log_return` feature |
| Distribusi log-normal harga | Forward return distribution per regime untuk I-00 |

---

*Dokumen ini menghubungkan teori ekonofisika (proses stokastik & pasar keuangan) dengan implementasi konkret pada project `btc-scalping-quant`. Seluruh pengembangan yang diusulkan bersifat **additive** — tidak memecahkan fungsionalitas yang sudah ada, melainkan memperkuat landasan teoritis dari regime detection yang sudah berjalan.*