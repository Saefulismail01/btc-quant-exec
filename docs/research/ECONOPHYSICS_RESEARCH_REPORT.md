# Laporan Riset: Pondasi Econophysics dalam Pasar Cryptocurrency

Laporan ini menyatukan temuan-temuan kunci dari berbagai literatur akademik mengenai fisika statistik (*Econophysics*) yang diterapkan pada pasar kripto. Riset ini dilakukan menggunakan pustaka `paper-search` untuk mengekstraksi pengetahuan dari sumber-sumber seperti ArXiv dan Semantic Scholar.

---

## 1. Ringkasan Eksekutif (*Executive Summary*)
Pasar Cryptocurrency, khususnya Bitcoin, menunjukkan perilaku yang jauh dari acak murni. Pergerakan harganya dipengaruhi oleh memori jangka panjang, struktur multifraktal, dan distribusi "Ekor Gemuk" (*Fat Tails*). Memahami struktur ini memungkinkan pengembangan sistem trading (seperti **BTC-QUANT**) yang lebih tahan terhadap risiko ekstrem dan lebih cerdas dalam mendeteksi perubahan fase pasar.

## 2. Metodologi Riset
Pencarian dilakukan dengan fokus pada empat pilar utama:
1.  **Multifractality**: Untuk memahami kekacauan dan memori pasar.
2.  **Scaling Laws**: Untuk memodelkan risiko kejadian ekstrem.
3.  **Random Matrix Theory**: Untuk memetakan korelasi antar aset (BTC vs Altcoins vs Makro).
4.  **Bayesian Inference**: Untuk deteksi perubahan rezim (*Regime Switching*) secara real-time.

---

## 3. Temuan Kunci Riset

### 3.1. Sifat Multifraktal Bitcoin (MFDFA)
Bitcoin bukan hanya sekadar aset volatil, melainkan sistem **multifraktal**.
*   **Korelasi Jangka Panjang**: Pergerakan harga saat ini dipengaruhi oleh sejarah masa lalu (bukan *Random Walk* murni).
*   **Asimetri Pasar**: Sifat multifraktal pasar Bitcoin tidak simetris (indeks asimetri ~0.57); pergerakan naik dan turun memiliki karakteristik statistik yang berbeda ([Bucur et al., 2025](https://www.semanticscholar.org/paper/f64caba8b0e46d858f52db3c622e1311713a9ad0)).
*   **Ketidakefisienan Pasar**: Adanya multifraktalitas membuktikan bahwa pasar tidak efisien sempurna (melewati EMH), sehingga strategi trading teknikal memiliki peluang sukses yang lebih tinggi.

### 3.2. Hukum Penskalaan & Risiko "Ekor Gemuk" (*Scaling Laws & Fat Tails*)
Pergerakan harga kripto mengikuti distribusi **Power-Law**.
*   **Risiko Ekstrem**: Kejadian *Black Swan* (keruntuhan harga mendadak) terjadi jauh lebih sering daripada yang diprediksi oleh model keuangan tradisional (Gaussian).
*   **Dualitas Instabilitas**: Bitcoin memiliki daya tarik jangka panjang yang sangat kuat (apresiasi harga), namun memiliki instabilitas jangka pendek yang sangat tinggi ([Vaz et al., 2021](https://www.semanticscholar.org/paper/3f98af9a0dd5bd336504a59b230def3f0fc22cd7)).

### 3.3. Korelasi Non-Linear & Volume
*   **Faktor Makro**: Terdapat hubungan korelasi jangka panjang yang signifikan antara harga Bitcoin dengan Ketidakpastian Kebijakan Ekonomi (*Economic Policy Uncertainty*) di AS.
*   **Pentingnya Volume**: Perubahan harga dan volume berinteraksi secara non-linear. Penggunaan volume sebagai pengonfirmasi tren adalah keharusan mutlak dalam pasar kripto.

### 3.4. Deteksi Rezim & Perubahan Fase (*Regime Detection*)
Transisi antara pasar *Bull* dan *Bear* dapat dideteksi secara statistik.
*   **Bayesian Online Changepoint Detection (BOCPD)**: Metode ini sangat efektif untuk mengidentifikasi titik balik pasar secara otomatis.
*   **Penyaringan Sinyal**: Teknik *smoothing* (perataan) data sangat krusial dalam model HMM (*Hidden Markov Models*) untuk mengurangi *noise* dan meningkatkan persistensi sinyal trading ([Blanchard & Goffard, 2025](https://www.semanticscholar.org/paper/3264d59964038341ea70b053895bc7ed8f91dae2)).

---

## 4. Analisis Paper Utama

| Judul Paper | Penulis | Temuan Utama |
| :--- | :--- | :--- |
| **Multifractal analysis of Bitcoin price dynamics** | Bucur et al. (2025) | Mengonfirmasi *power-law relationship* dan hubungan multifraktal antara Bitcoin, inflasi, dan harga minyak. |
| **Price Appreciation and Roughness Duality in Bitcoin** | Vaz et al. (2021) | Menjelaskan dualitas antara valuasi jangka panjang dan ketidakstabilan jangka pendek. |
| **Bayesian Online Changepoint Detection for Financial...** | Li (2025) | Menunjukkan efektivitas BOCPD dalam mendeteksi perubahan volatilitas pasar secara *real-time*. |

---

## 5. Kesimpulan & Insight Strategis (*Actionable Advice*)

Berdasarkan riset ini, berikut adalah langkah-langkah yang direkomendasikan untuk sistem trading kuantitatif:

1.  **Gunakan Indikator Kekacauan (*Roughness Index*)**: Monitor derajat multifraktalitas (Hurst Exponent). Jika nilai Hurst turun mendekati 0.5, pasar menjadi sangat acak dan berbahaya untuk strategi *trend-following*.
2.  **Modelkan Ekor Gemuk**: Jangan gunakan *Standard Deviation* (Sigma) tunggal untuk penempatan *Stop Loss*. Gunakan model yang mengakomodasi distribusi Power-law (seperti GARCH dengan filter stabil).
3.  **Deteksi Rezim Bayesian**: Implementasikan algoritma BOCPD sebagai filter utama sebelum eksekusi sinyal. Hanya ambil sinyal saat sistem mendeteksi rezim yang stabil.

---
**Disusun oleh**: Antigravity AI
**Tanggal**: 2 April 2026
**Sumber**: ArXiv, Semantic Scholar via `paper-search-lib`
