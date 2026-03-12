# Dokumentasi Pengujian Layer 1: HMM vs BCD (Ekspansi 2023-2026)

## 1. Latar Belakang
Pengujian tahap kedua ini dilakukan dengan skala data yang jauh lebih besar untuk memvalidasi performa jangka panjang (multi-year cycles). Kita membandingkan:
1.  **HMM (Gaussian Mixture Model)**: Clustering probabilistik statis.
2.  **BCD (Bayesian Online Changepoint Detection)**: Deteksi perubahan struktural dinamis.

Fokus utama adalah melihat bagaimana kedua model menangani transisi pasar dari Bull Market 2023, Sideways 2024, hingga dinamika awal 2026.

## 2. Metode Pengujian (Ultra-Long Timeframe)
- **Rentang Waktu**: 18 November 2022 s/d 02 Maret 2026 (± 3,3 Tahun).
- **Timeframe**: 4 Jam (4H).
- **Dataset**: BTC/USDT Perpetual (Binance) - 7.200 Candles.
- **Proses Data**: Data historis di-backfill menggunakan `backfill_historical.py` untuk mencakup 1.200 hari terakhir.
- **Strategi Evaluasi**: *Global Training Mode* — model dilatih pada seluruh 7.200 lilin untuk menguji ketahanan struktur rejim yang dihasilkan terhadap variasi volatilitas jangka sangat panjang.

## 3. Variabel & Parameter Uji
| Parameter | Konfigurasi HMM | Konfigurasi BCD |
| :--- | :--- | :--- |
| **Engine Core** | GaussianMixture (Full Covariance) | Normal-Inverse-Gamma Prior |
| **Selection Logic** | Optimal N via BIC Scan (Dynamic) | Structural Break via Hazard Rate |
| **Sensitivity** | BIC-Guided (Candidate 2-6) | Hazard Rate = 0.033 (1/30) |
| **Features** | 8 Microstructure Features | 8 Microstructure Features (Identik) |

## 4. Hasil Pengujian (Data 7.200 Candles)
Hasil menunjukkan perbedaan performa yang sangat kontras antara HMM dan BCD pada skala waktu 3 tahun:

| Metrik Evaluasi | HMM (Gaussian Mixture) | BCD (Bayesian Online) |
| :--- | :--- | :--- |
| **Durasi Training** | 2,70 detik | 145,78 detik |
| **Total Perubahan Rejim** | **4.997 kali** (Noise Tinggi) | **36 kali** (Stabil) |
| **Rata-rata Persistensi** | 1,4 Lilin (~5,6 Jam) | **194,6 Lilin** (~32 Hari) |
| **Bullish 5C Fwd Return** | +0,3149% | **+1,1758%** |
| **Bearish 5C Fwd Return** | +0,2749% (Gagal/Positif) | **-0.1686% (Berhasil/Negatif)** |
| **Skala Stabilitas** | 1,0x (Baseline) | **138,8x Lebih Stabil** |

### Visualisasi Rejim
Plot visualisasi yang mencakup seluruh 7.200 candle tersedia di: `docs/history/long_compare_viz.png`. 
*Catatan: Pada plot HMM terlihat sangat padat (noise), sedangkan BCD menunjukkan blok warna yang solid sesuai siklus pasar.*

## 5. Analisis Mendalam
1.  **Kegagalan HMM pada Skala Panjang**: HMM mengalami "over-flickering" dengan hampir 5.000 pergantian rejim. Artinya, hampir setiap 1-2 candle, model mendeteksi perubahan rejim. Ini membuat HMM tidak berguna untuk strategi *trend following* tanpa adanya *smoothing* atau *sliding window* yang sangat ketat.
2.  **Keunggulan BCD**: BCD menunjukkan persistensi yang luar biasa (rata-rata 32 hari per rejim). Ini sangat ideal untuk Layer 1 yang bertugas memberikan "konteks besar" bagi Layer 2 (Signal) dan Layer 3 (MLP).
3.  **Akurasi Prediksi**: BCD memberikan sinyal 'Bullish Trend' yang jauh lebih kuat (+1,17% vs +0,31%). Yang paling krusial, BCD adalah satu-satunya yang berhasil mendeteksi rejim 'Bearish' dengan *forward return* negatif (-0,16%). HMM justru memberikan return positif pada label Bearish-nya, yang berarti label tersebut salah/bias.

## 6. Kesimpulan Akhir
**BCD Terbukti Unggul Mutlak (Pass PRD I-00 s/d I-02).**

**Rekomendasi Tindakan:**
- **Primary Engine**: Tetapkan BCD sebagai engine utama Layer 1.
- **Global Training**: Gunakan dataset minimal 2.000+ candle untuk training BCD agar mendapatkan *prior* yang matang.
- **Inference**: Lakukan inferensi BCD secara online untuk mendeteksi *changepoint* baru secara real-time.

---
**Status**: FINAL (Expanded to 3Y Data)
**Update Terakhir**: 02 Maret 2026, 11:58
**Engineer**: Antigravity AI
