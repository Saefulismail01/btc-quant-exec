# Evaluasi Historis Engine Layer 1 (Market Regime Detection)

Dokumen ini mencatat perjalanan riset kuantitatif dalam mencari model _Machine Learning_ (_Econophysics_) terbaik untuk mendeteksi rezim pasar (Layer 1) pada arsitektur BTC-Quant Scalper.

Pemilihan model Layer 1 sangat krusial karena ia bertindak sebagai kompas utama (_bias persistence_) yang menentukan apakah bot akan berani memegang posisi tren panjang atau harus waspada dalam kondisi _sideways_.

---

## Tahap 1: Standard Hidden Markov Model (HMM) Gaussian

Awalnya, sistem menggunakan **Gaussian HMM** standar (`hmmlearn.hmm.GaussianHMM`).
*   **Konsep:** Harga pasar dianggap memiliki status tersembunyi (misal: Bullish, Bearish, Sideways) yang tidak bisa diamati langsung, namun memancarkan nilai observasi (seperti _return_, volatilitas, dan _volume_).
*   **Kelebihan:** Sangat konseptual dan mudah dipahami. Mudah dilatih dengan rutinitas _Expectation-Maximization_ (Baum-Welch).
*   **Kekurangan:** Matriks probabilitas transisi antar-rezim bersifat **tetap (konstan)**. Kenyataannya, di pasar kripto, probabilitas untuk pindah dari _Bullish_ ke _Bearish_ sangat bergantung pada faktor eksternal (seperti _funding rate_ atau sentimen makro), bukan angka statis.

## Tahap 2: Non-Homogeneous Hidden Markov Model (NHHM)

Untuk mengatasi masalah probabilitas transisi yang kaku pada HMM Standar, sistem dievolusikan menuju **Non-Homogeneous HMM (NHHM)**.
*   **Konsep:** Variabel makro (seperti _Open Interest_ dan _Funding Rate_) dimasukkan sebagai _regressor_ eksternal. Jika _Funding Rate_ tiba-tiba sangat positif ekstrem, probabilitas transisi menuju rezim "Crash/Bearish" akan meroket tajam secara dinamis.
*   **Kelebihan:** Secara teori ini adalah model yang sangat sempurna dan merepresentasikan dinamika mikrostruktur pasar secara _real-time_.
*   **Kekurangan Terbesar (The Blocker):** Kompleksitas komputasi. Mengkalibrasi matriks transisi yang berubah-ubah di _setiap titik waktu_ (t) menggunakan optimasi non-linear (`scipy.optimize.minimize`) membutuhkan waktu komputasi yang tak masuk akal (berjam-jam untuk data yang relatif kecil). Untuk bot _scalping_ yang perlu inferensi cepat, NHHM terpaksa digugurkan karena masalah **performa (bottleneck)**.

## Tahap 3: Gaussian Mixture Model HMM (GMM-HMM)

Karena NHHM terlalu lambat, pendekatan dikembalikan lagi pada _clustering_ probabilistik, namun dengan meningkatkan keluwesan emisi datanya menggunakan **GMM-HMM** (`hmmlearn.hmm.GMMHMM`).
*   **Konsep:** Mengganti distribusi emisi dari satu _bell-curve_ Gaussian menjadi campuran (_mixture_) beberapa Gaussian. Ini sangat cocok untuk pasar kripto yang terkenal memiliki *Fat-Tail* (Ekor Gemuk / banyak anomali ekstrem yang gagal ditangkap oleh kurva normal standar).
*   **Kekurangan Terbesar (The Bug):** Implementasi _library_ `hmmlearn` untuk algoritma GMM-HMM ternyata memiliki masalah mendasar (_bug_) pada arsitektur **Windows Multi-processing**. Saat proses sinkronisasi _threads_ di Windows, *library* ini mengalami _deadlock_ atau  *Hanging* (berhenti merespon) tanpa _error log_ saat melakukan `.fit()`.
*   **Resolusi Sementara:** Karena di-_block_ oleh _library_, GMM-HMM terpaksa diturunkan menjadi murni **GaussianMixture** (_Clustering_ GMM biasa dari `scikit-learn` tanpa aspek _Time-Series Markov_). GMM biasa bisa melatih data dalam hitungan milidetik, namun sayangnya **kehilangan sifat memori waktu**. Rezim yang diduduki saat ini tidak peduli dengan rezim di *candle* sebelumnya, menyebabkan sinyal sering "berkedip" (_flickering_).

## Tahap 4: Uji Validitas Prediktif (Modul C Walk-Forward)

Demi menetapkan basis ilmiah pada _engine_ yang tersisa (GMM dari `layer1_hmm.py`), dibuatlah **Modul C (Walk-Forward Validation - PRD I-00)**.
*   Tujuannya adalah mengiris historis data 4 Jam BTC menjadi potongan 3 bulanan, mengidentifikasi status *Bullish/Bearish*, dan mengecek apakah 1-to-5 _candle_ ke depan pasca-deteksi memang benar-benar memiliki probabilitas T-Test yang menguntungkan.
*   **Hasil Evaluasi (GMM-HMM Legacy):** HMM Legacy murni gagal diuji. Model ini konsisten mendapatkan **❌ FAIL** pada semua _window testing_ karena distribusi _return_ kemenangannya berantakan (tidak lolos uji _predictive power_ di luar _in-sample_).

## Tahap 5: Bayesian Online Changepoint Detection (BCD)

Kegagalan statistik GMM Legacy mengharuskan pencarian algoritma Layer 1 baru. Lahirlah pendekatan yang diwariskan dari ranah ekonofisika: **Bayesian Changepoint Detection (BCD)** (`layer1_bcd.py`).

*   **Konsep Utama:** BCD tidak lagi mengkluster data secara keseluruhan dari awal hingga akhir seperti HMM. BCD bergerak dari kiri ke kanan secara kronologis, menghitung ekspektasi varians secara Bayesian, dan mencari titik "Patah Struktur" (_structural break_ / _changepoint_).
*   Jika volatilitas meledak atau arah tren berbalik tajam melebihi hipotesis (_Prior Parameter_), BCD akan mendaklarasikan bahwa umur rezim (_Run Length_) kembali menjadi **Nol (0)**, lalu memulai periode tren/rezim baru.
*   **Keunggulan Mutlak BCD:**
    1.  **Dinamis dan Lokal:** Tidak memaksakan data 2 tahun lalu untuk menentukan klaster hari ini. Rezim dinilai dari seberapa besar patahan harga *lokal* terjadi.
    2.  **Solusi Bebas Flickering:** Berbeda dengan GMM yang melompat pindah setiap saat, BCD sangat kukuh. Selama belum ada titik retakan yang dikonfirmasi oleh hitungan _Joint Probability_, rezim akan terus dipertahankan (_high persistence_).
    3.  **Tervalidasi secara Statistik:** Setelah melalui modifikasi pelebaran sensitivitas (penyesuaian _Hazard Rate_, _MAP Run Length Drop_, dan limitasi deteksi anomali _local variance_), BCD diajukan kembali pada **Uji Validasi PRD I-03 (Modul C - Walk-Forward)**.
    4.  **HASIL AKHIR:** BCD berhasil mendeteksi tren dan _sideways_ secara prediktif dengan akurat pada irisan data *out-of-sample*. Skrip pengujian akhirnya mendeklarasikan **✅ I-00 PASS**.

### Dimana Letak "Ekonofisika"-nya?

Perpindahan dari _Machine Learning_ tradisional menuju **Pendekatan Ekonofisika** terjadi secara nyata pada keputusan desain arsitektur final ini:

1.  **Pengakuan atas Distribusi Non-Gaussian (Lévy Flights & Fat-Tails):**
    Model Gaussian (HMM biasa) berasumsi bahwa _return_ pasar kripto bergerak layaknya _bell-curve_ acak (Brownian Motion). Ekonofisika (Mandelbrot & Taleb) membuktikan bahwa harga bergerak dalam "Lévy Flights"—lompatan mendadak yang menghasilkan "Ekor Gemuk" (*Fat-Tails*).
    *   **Penerapan pada BCD:** Dalam kode `layer1_bcd.py` (Baris 172), kita mengganti fungsi distribusi normal dengan **Student-T Predictive Posterior**. Secara fisik, Student-T memiliki _kurtosis_ yang lebih tinggi, memungkinkannya menyerap "noise" ekstrem tanpa langsung merusak model. Ini adalah pengakuan matematis bahwa anomali di kripto adalah fitur, bukan error.

2.  **Patahan Struktur sebagai Fase Transisi (Phase Transitions):**
    Dalam fisika, sistem berpindah fase (seperti air menjadi es) saat mencapai titik kritis. Ekonofisika memandang pergantian tren pasar sebagai fase transisi sistem kompleks.
    *   **Penerapan pada BCD:** Algoritma BCD secara cerdas menghitung **Run Length (R)**. Jika data baru sangat tidak konsisten dengan distribusi saat ini, probabilitas _growth_ akan turun dan probabilitas _reset_ (*Changepoint*) akan naik. Ini adalah detektor otomatis terhadap "Fase Transisi" pasar tanpa harus menunggu konfirmasi indikator teknikal yang lambat (*lagging*).

3.  **Dinamika Non-Stasioner (Non-Equilibrium Dynamics):**
    Asumsi ML klasik adalah pasar bersifat stasioner (statistik masa lalu mencerminkan masa depan). Ekonofisika berpendapat pasar adalah sistem *non-equilibrium*.
    *   **Penerapan pada BCD:** HMM mencoba menemukan parameter global untuk "state 1" atau "state 2" dari data 2 tahun. BCD justru melakukan **Local Parameter Estimation**. BCD hanya peduli pada data *sejak changepoint terakhir*. Artinya, sistem kita mengakui bahwa "sifat fisika" pasar hari ini bisa sangat berbeda dengan bulan lalu, dan hanya data terbaru yang relevan untuk inferensi saat ini.

2.  **Volatilitas Stokastik (The Heston Model - Modul B):**
    Berbeda dengan _technical analysis_ (TA) klasik seperti _Bollinger Bands_ atau ATR yang memandang volatilitas sebagai rerata selisih harga absolut (_moving average_ statis), **Modul B (Heston Volatility)** memandang volatilitas sebagai **entitas acak yang hidup dan memiliki gravitasinya sendiri (Reverting Process)**. 
    *Rumus Fisika Difusi:* $dv(t) = -\gamma(v - \eta)dt + \kappa \sqrt{v} dB_v(t)$
    Dalam implementasinya di `layer1_volatility.py`:
    *   $\gamma$ (Kecepatan _Mean-Reversion_): Bot menghitung secara matematis berapa _candle_ (waktu paruh / _half-life_) yang dibutuhkan agar badai volatilitas saat ini mereda kembali ke lautan tenang.
    *   $\eta$ (Varians Jangka Panjang): Titik gravitasi atau keseimbangan pasar.
    *   $\kappa$ (Vol-of-Vol): Mengukur fluktuasi dari volatilitas itu sendiri.
    Berdasarkan persamaan stokastik di atas, sistem mengatur ukuran pengali Stop-Loss (SL) dan Take-Profit (TP) secara dinamis. Bila $\gamma$ menunjukkan badai akan berlangsung lama, SL akan dilebarkan secara eksponensial untuk menghindari _whipsaw_ (bukan sekadar patokan ATR 1.5x konstan).

3.  **Matriks Probabilitas Transisi (Proses Markov Tersembunyi - Modul A):**
    Penggunaan teori *Markov Chain*. Di sinilah probabilitas peralihan (Transisi) antarkondisi diekstrak menjadi matriks $P_{ij}$. Berbeda dengan HMM standar yang menggunakannya sebagai fungsi pelatihan internal, kita mengekstrak probabilitas empiris ini untuk mengalkulasi **Regime Bias**. 
    *   Contohnya, jika hari ini status "_Bullish_", engine menghitung probabilitas persentase besok akan tetap "_Bullish_" vs "_Bearish_" (Probabilitas _Persitence_). Angka ekspektasi probabilitas ketahanan usia tren ini disetorkan _engine_ untuk menilai keyakinan arah (*Directional Bias*). Model BCD tetap menyumbangkan _run length_ yang kemudian diterjemahkan menjadi probabilitas persistensi empiris dalam _state space_.

### Keputusan Arsitektur Final

Berdasarkan perjalanan riset panjang dan kegagalan pada validasi data empiris:
1.  **HMM, NHHM, dan GMM resmi dinyatakan sebagai komponen Legacy (Pensiun/Usang).**
2.  **Bayesian Changepoint Detection (BCD)** diangkat sebagai otak utama (_Primary Engine_) dari Layer 1 dalam aplikasi *Scalper* BTC ini.
3.  Sebagai tambahan, untuk menambal kepekaan volatilitas lokal pasca-BCD, diimplementasikan **Heston Stochastic Volatility Model (Modul B)** yang mengatur ukuran agresivitas perlindungan modal (_Dynamic SL/TP_). 

Kedua modul peraih predikat sukses tervalidasi inilah yang akan diteruskan ke Layer ke-4 (**Agentic LLM**) untuk dikemas menjadi *Trading Signal* institusional.
