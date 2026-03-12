# 🧠 Logika Lapis 3: AI Signal Intelligence (MLP)

Dokumen ini menjelaskan arsitektur, fitur, dan logika kerja model AI (Multi-Layer Perceptron) yang digunakan sebagai **Layer 3** dalam sistem BTC-Quant.

---

## 1. Peran MLP dalam Sistem
MLP bertindak sebagai "kecerdasan tambahan" yang memvalidasi sinyal dari Layer 1 (BCD) dan Layer 2 (EMA). Tugas utamanya adalah memprediksi **probabilitas arah pergerakan harga** pada candle berikutnya berdasarkan pola teknikal dan rejim pasar saat ini.

Output dari MLP adalah **Confidence Score** (50-100%) dan **Directional Vote** ([-1, +1]).

---

## 2. Fitur Input (Features)
MLP tidak melihat harga mentah, melainkan menggunakan fitur-fitur yang sudah dinormalisasi agar model dapat mempelajari pola secara objektif.

### A. Fitur Teknikal (Base - 5 Fitur)
| Fitur | Penjelasan | Tujuan |
|---|---|---|
| `rsi_14` | Relative Strength Index (14) | Mengukur kondisi Overbought/Oversold. |
| `macd_hist` | MACD Histogram | Mengukur momentum dan divergensi. |
| `ema20_dist` | Jarak harga dari EMA20 | Mengukur seberapa jauh harga menyimpang dari rata-rata pendek. |
| `log_return` | Log Return candle saat ini | Mengukur volatilitas return candle terakhir. |
| `norm_atr` | ATR dinormalisasi (`ATR / Price`) | Mengukur tingkat volatilitas relatif terhadap harga. |

### B. Fitur Cross-Regime (Integrated - 4 Fitur Tambahan)
Jika Layer 1 (BCD/HMM) aktif, MLP menggunakan fitur **One-Hot Encoding** dari rejim pasar:
- `hmm_state_0` sd `hmm_state_3`: Mewakili 4 rejim (contoh: Bullish Volatile, Bearish Stable, dll.)
- Ini memungkinkan MLP untuk belajar: *"Pola RSI tertentu lebih akurat di rejim Bullish daripada Bearish."*

Total fitur saat integrasi aktif: **9 fitur**.

---

## 3. Struktur Model (Architecture)
Model ini menggunakan **Dual-Layer Neural Network** dengan struktur yang adaptif:

- **Mode Standalone (5 fitur)**: 
  - Hidden Layers: `(64, 32)`
- **Mode Cross-Regime (9 fitur)**: 
  - Hidden Layers: `(128, 64)` (Kapasitas lebih besar untuk menangkap hubungan antar rejim).
- **Aktivasi**: `ReLU` (Rectified Linear Unit) untuk menangkap hubungan non-linear.
- **Optimization**: `Adam Solver` dengan Early Stopping (berhenti jika sudah tidak ada perbaikan untuk mencegah overfitting).

---

## 4. Logika Training (Retraining)
MLP di sistem ini bersifat **Walk-Forward Adaptive**:
1. **Interval**: Model dilatih ulang setiap **48 candle 4H** (~8 hari).
2. **Data**: Menggunakan data historis terbaru untuk menyesuaikan diri dengan "wajah" market yang terus berubah.
3. **Persistensi**: Model dan Scaler disimpan ke disk (`model_cache/`) agar tidak perlu latihan ulang saat sistem restart.

---

## 5. Logika Prediksi & Confidence
Dari output model, kita mengambil probabilitas dari fungsi `Softmax`:

- **Bias**: Jika `P(Bull) > P(Bear)` maka **BULL**, sebaliknya **BEAR**.
- **Confidence**: Nilai probabilitas tertinggi yang dipetakan ke skala 50-100%.
- **Vote (Spectrum)**: Digunakan untuk voting di modul Spectrum.
  - Rumus: `Vote = Arah * (Confidence - 50) / 50`
  - Contoh: Bias BULL dengan Conf 75% → `+1 * (75-50)/50 = +0.5`.

---

## 6. Rencana Perbaikan (Next Roadmap)
Berdasarkan hasil riset terakhir, logika MLP akan ditingkatkan pada:
1. **Target Label Cerdas**: MLP hanya akan belajar dari pergerakan harga yang signifikan (> 0.5× ATR) untuk mengurangi kebisingan (noise).
2. **Fitur Eksternal**: Penambahan data CVD (Cumulative Volume Delta), Funding Rate, dan OI (Open Interest).

---

*File: `backend/engines/layer3_ai.py`*  
*Update Terakhir: 3 Maret 2026*
