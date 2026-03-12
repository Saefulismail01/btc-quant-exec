# Laporan Evaluasi Engine Layer 1: HMM vs BCD

Laporan ini menyajikan hasil pengujian perbandingan kuantitatif antara dua mesin deteksi rezim pasar dalam arsitektur BTC-Quant Scalper: **HMM (Gaussian Mixture)** dan **BCD (Bayesian Online Changepoint Detection)**.

## 1. Metode Pengujian (Test Methodology)
Kami menggunakan metode **Side-by-Side Global Benchmarking**, di mana kedua model diuji secara bersamaan menggunakan data yang identik:
*   **Global Training**: Kedua model dilatih menggunakan seluruh dataset historis untuk menentukan klaster (HMM) atau titik patahan struktur (BCD) yang stabil.
*   **Inference Alignment**: Kami menyelaraskan deret waktu (*time-series*) agar setiap candle yang dianalisis oleh HMM memiliki pasangan yang tepat pada BCD.
*   **Stability Metric (Flickering)**: Kami menghitung seberapa sering model mengubah label rezimnya. Model yang baik untuk *scalping* harus memiliki "bias persistence" (tidak berubah-ubah setiap 1-2 candle).

## 2. Data yang Digunakan (Data Source)
Data diambil langsung dari database operasional sistem (`btc-quant.db`) menggunakan `data_engine.py`:
*   **Asset**: Bitcoin (BTC) Futures.
*   **Interval**: 500 candle terakhir (OHLCV).
*   **Kualitas Data**: Data real pasar yang sudah dibersihkan, mencakup variasi volatilitas dari kondisi *sideways* hingga *trending*.

## 3. Variabel yang Digunakan (Feature Variables)
Kedua engine menggunakan **8 fitur mikrostruktur** yang sama (paritas fitur) untuk memastikan keadilan pengujian:
1.  **Log Return**: Perubahan harga logaritmik untuk mendeteksi arah tren.
2.  **Realized Volatility**: Standar deviasi harga dalam jendela tertentu (mengukur ketakutan/ketenangan pasar).
3.  **HL Spread**: Selisih High-Low (mengukur likuiditas dan urgensi harga).
4.  **Volume Z-Score**: Normalisasi volume untuk mendeteksi lonjakan aktivitas yang tidak wajar.
5.  **Volatility Trend**: Perubahan volatilitas antar candle.
6.  **CVD Z-Score** (*Cumulative Volume Delta*): Mengukur dominasi agresor beli vs jual (fitur ekonofisika).
7.  **OI Rate of Change** (*Open Interest*): Kecepatan uang baru masuk ke pasar derivatif.
8.  **Liq Intensity**: Intensitas likuidasi paksa (posisi *margin call*) yang sering menjadi pemicu perubahan rezim.

## 4. Hasil Analisis Kuantitatif
Pengujian dilakukan pada 500 candle data historis BTC.

| Metrik | HMM (GMM Legacy) | BCD (Bayesian Focus) | Perbaikan |
| :--- | :--- | :--- | :--- |
| **Total Perpindahan Rezim** | 360 kali | 7 kali | **~51x Lebih Stabil** |
| **Ketahanan Rata-rata** | 1.4 candle | 62.5 candle | **Bias Lebih Kuat** |
| **Waktu Pelatihan** | 21.4 detik | 22.2 detik | Setara |

## 5. Visualisasi Perbandingan
![HMM vs BCD Regime Detection](bcd_vs_hmm.png)

*Catatan: Gambar di atas menunjukkan bagaimana HMM (atas) mengalami "flickering" (perubahan cepat seperti barcode), sementara BCD (bawah) mempertahankan blok warna yang solid sesuai tren pasar.*

## 6. Kesimpulan
Engine **BCD (Bayesian)** dikonfirmasi sebagai pilihan superior untuk Layer 1. BCD berhasil mengabaikan *noise* lokal dan hanya bereaksi pada perubahan struktur pasar yang signifikan ("structural breaks"). Hal ini memberikan stabilitas bias yang diperlukan untuk strategi *scalping* berfrekuensi tinggi, memvalidasi evolusi arsitektur dari model klastering tradisional menuju pendekatan ekonofisika Bayesian.

---
*Laporan ini dihasilkan secara otomatis oleh BTC-Quant Diagnostic Tools pada 2026-03-02.*
