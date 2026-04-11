# Layer Accuracy Research — 2026-04-08

## Tujuan

Mengukur seberapa akurat sistem BTC-QUANT (L1 BCD + L2 EMA + L3 MLP) dalam memprediksi
arah harga BTC 4H ke depan. Data yang digunakan: `BTC_USDT_4h_2025.csv` (2190 candles).

---

## Sesi 1 — Full Layer Accuracy Test

**Script:** `backtest/scripts/evaluate_layer_accuracy_4h.py`

### Masalah yang Ditemukan & Fix

| Masalah | Fix |
|---------|-----|
| `SKIP_L3 = True` — L3 tidak pernah dievaluasi | Set ke False, integrasikan L3 properly |
| MLP disk cache shape mismatch — cached model dari live trading pakai 12 features (HMM cross), eval CSV hanya OHLCV = 8 features | `_make_fresh_mlp()`: bypass `_load_from_disk()`, buat scaler baru dari scratch |
| Per-sample BOCPD — `get_current_regime_posterior()` di dalam loop = O(n³) total, tidak selesai | Pre-compute BCD states sekali (`get_state_sequence_raw(df)`), slice per-sample O(1) |
| Per-sample L1 re-run BOCPD — bottleneck loop nyangkut di 0% progress | Ganti L1 lookup ke `global_states[i]` + `bcd.state_map[seg_id]` — O(1) per sample |

### Hasil

| Layer | Akurasi | Catatan |
|-------|---------|---------|
| **L1 BCD** | **57.4%** | Terbaik — regime detection benar |
| L3 MLP | 54.6% | Angka menipu — model degenerate |
| Combined | 53.8% | Lebih buruk dari L1 saja |
| L2 EMA | 48.6% | Di bawah random |

#### Confusion Matrix L1 BCD
```
       Predicted
       UP   DOWN
  UP     52    61
  DN     45    91

Precision: 53.6%  Recall: 46.0%  F1: 49.5%
```

#### Masalah L3 MLP — Degenerate Model
```
UP   :   0  prediksi  (113 kasus missed)
DOWN : 136  prediksi  (selalu DOWN)
```
MLP tidak pernah prediksi UP. Akurasi 54.6% palsu — hanya karena DOWN lebih banyak
dari UP di periode 2025 (136 vs 113). Root cause: fitur microstructure (norm_cvd,
funding, oi_change) semua = 0.0 karena tidak ada di CSV. Model tidak punya signal
valid, collapse ke majority class.

#### Masalah L2 EMA — Logic Terlalu Strict
Kondisi `price > ema_fast > ema_slow` harus terpenuhi semua. Banyak genuine uptrend
yang tidak memenuhi → malah counterproductive, drag down combined accuracy.

### Kesimpulan Sesi 1
L1 BCD (57.4%) adalah satu-satunya layer yang genuinely predictive. L2 dan L3
dalam kondisi current justru menurunkan combined dari 57.4% → 53.8%.

---

## Sesi 2 — BCD Confidence Threshold Analysis

**Script:** `backtest/scripts/evaluate_bcd_confidence.py` *(script baru, tidak ubah existing)*

### Hipotesis
Candle dengan BCD posterior/confidence tinggi punya akurasi lebih baik dari baseline 57.4%.

### Metode
Confidence proxy: segment persistence dari transition matrix (`tm[seg_id, seg_id]`).

### Hasil

| Threshold | Coverage | Samples | Accuracy |
|-----------|----------|---------|----------|
| 0.0 (all) | 77.5% | 193 | 56.5% |
| 0.3 | 77.5% | 193 | 56.5% |
| 0.5 | 77.5% | 193 | 56.5% |
| 0.6 | 77.1% | 192 | 56.2% |
| 0.7 | 77.1% | 192 | 56.2% |
| 0.8 | 77.1% | 192 | 56.2% |

**Confidence threshold tidak membantu** — akurasi flat di semua level.
Transition matrix persistence bukan discriminator yang baik untuk per-candle confidence.

#### Temuan Menarik — Asimetri BULL vs BEAR

| Signal | Count | Akurasi |
|--------|-------|---------|
| **BEAR (DOWN)** | 96 | **59.4%** |
| **BULL (UP)** | 97 | 53.6% |
| Sideways (NEUTRAL) | 56 | — |

BCD secara konsisten lebih akurat untuk sinyal BEAR daripada BULL.
Pattern ini bisa di-exploit: hanya trade sinyal BEAR, skip atau perketat BULL.

### Kesimpulan Sesi 2
Confidence threshold dari transition matrix tidak efektif. Pendekatan filter
berbasis price action lebih promising.

---

## Sesi 3 — Precision Filter Search

**Script:** `backtest/scripts/evaluate_bcd_precision_filter.py` *(script baru, tidak ubah existing)*

### Tujuan
Cari kombinasi filter teknikal di atas sinyal BCD yang menghasilkan presisi > 65%.

### Filter yang Diuji (13 total)
- `mom1`, `mom3`, `mom6` — momentum 1/3/6 candle searah prediksi
- `ema20`, `ema50` — price vs EMA searah prediksi
- `vol_high` — volume z-score > 0.5
- `atr_moderate`, `atr_low` — volatilitas moderate/rendah
- `rsi_ok` — RSI tidak overbought/oversold
- `age_gt5`, `age_gt10`, `age_gt20` — regime sudah aktif > N candle

### Metode
Brute-force search: single filter → double filter → triple filter (dari high scorers).
Minimum 20 sampel untuk dianggap valid.

### Hasil — Target 65% Tercapai

**1 kombinasi ditemukan:**

| Filter | N | Coverage | Precision | UP Prec | DN Prec |
|--------|---|----------|-----------|---------|---------|
| `vol_high + atr_low` | 22 | 11.4% | **72.7%** | 76.9% | 66.7% |

#### Interpretasi Filter
- **vol_high**: volume z-score > 0.5 — volume di atas rata-rata
- **atr_low**: ATR di percentile bawah 40% — volatilitas rendah

**Intuisi**: volume tinggi + volatilitas rendah = ada directional conviction tanpa chaos.
Ini ciri accumulation/distribution yang teratur, bukan random noise.

#### Trade-off
Coverage hanya 11.4% → dari ~249 samples setahun, hanya ~28 trade yang lolos filter.
Frekuensi trade sangat rendah, tapi presisi tinggi.

### Kesimpulan Sesi 3
Target 65% tercapai tapi dengan coverage sangat kecil (11.4%). Untuk meningkatkan
coverage sambil mempertahankan presisi > 65%, perlu meta-classifier (Opsi B).

---

## Ringkasan Temuan Hari Ini

### Angka Kunci
| Metric | Nilai |
|--------|-------|
| L1 BCD baseline accuracy | 57.4% |
| BCD BEAR signal accuracy | 59.4% |
| BCD BULL signal accuracy | 53.6% |
| Best filter (vol_high + atr_low) | 72.7% presisi, 11.4% coverage |
| L2 EMA accuracy | 48.6% (counterproductive) |
| L3 MLP accuracy | 54.6% (degenerate, no real skill) |

### Root Cause Issues
1. **L3 MLP** tidak bisa di-eval fairly dari CSV — butuh data CVD/OI/Funding
2. **L2 EMA** logic terlalu strict — perlu relax kondisi alignment
3. **BCD confidence** dari transition matrix tidak discriminative per-candle

### Next Steps (Direncanakan)
1. **Meta-classifier (Opsi B)** — train logistic regression/decision tree di atas
   fitur saat BCD bilang BEAR, target: apakah 4H ke depan memang turun?
   Data tersedia di `bcd_sample_features.csv`.
2. **Grid search parameter BCD** — optimize TREND_Z_BEAR, HAZARD_RATE, MAX_SEGMENT_LEN
3. **Eval L3 dengan data lengkap** — tambahkan CVD/OI/Funding ke CSV historis

---

## File Output

| File | Lokasi | Isi |
|------|--------|-----|
| `layer_accuracy_4h_20260408.csv` | `backtest/results/` | Per-sample predictions semua layer |
| `bcd_confidence_accuracy.csv` | `backtest/results/` | Per-sample BCD + confidence score |
| `bcd_filter_combos.csv` | `backtest/results/` | Semua kombinasi filter + presisi |
| `bcd_sample_features.csv` | `backtest/results/` | Per-sample features untuk meta-classifier |

## Script yang Dibuat

| Script | Lokasi | Fungsi |
|--------|--------|--------|
| `evaluate_layer_accuracy_4h.py` | `backtest/scripts/` | Full layer accuracy (dimodifikasi untuk fix L3) |
| `evaluate_bcd_confidence.py` | `backtest/scripts/` | BCD confidence threshold analysis |
| `evaluate_bcd_precision_filter.py` | `backtest/scripts/` | Filter combination search |
