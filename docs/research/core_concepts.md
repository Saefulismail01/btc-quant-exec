# BTC-QUANT — Konsep, Model, dan Teori

> Dokumen ini menjelaskan **mengapa** dan **bagaimana** BTC-QUANT bekerja secara konseptual — bukan cara instalasi atau struktur kode, melainkan ide-ide yang mendasari setiap keputusan desain.

---

## Daftar Isi

1. [Filosofi Dasar](#1-filosofi-dasar)
2. [Teori Market Regime](#2-teori-market-regime)
3. [Layer 1 — Hidden Markov Model (HMM)](#3-layer-1--hidden-markov-model-hmm)
4. [Fitur-Fitur yang Diobservasi](#4-fitur-fitur-yang-diobservasi)
5. [Layer 3 — MLP Neural Network](#5-layer-3--mlp-neural-network)
6. [Layer 4 — Sistem Konfluens & Decision Engine](#6-layer-4--sistem-konfluens--decision-engine)
7. [Layer 5 — Naratif & Truth Enforcer](#7-layer-5--naratif--truth-enforcer)
8. [Manajemen Risiko Berbasis ATR](#8-manajemen-risiko-berbasis-atr)
9. [Metrik Pasar — Informasi Tambahan](#9-metrik-pasar--informasi-tambahan)
10. [Keterbatasan dan Asumsi](#10-keterbatasan-dan-asumsi)

---

## 1. Filosofi Dasar

BTC-QUANT dibangun di atas satu premis sederhana: **pasar cryptocurrency tidak bergerak secara acak, tetapi bergerak dalam regime yang dapat diidentifikasi.**

Scalping konvensional sering gagal bukan karena masalah eksekusi, melainkan karena trader mencoba menerapkan strategi yang sama di kondisi pasar yang berbeda — masuk long di tengah bear regime, atau terlalu agresif di pasar yang sedang konsolidasi. BTC-QUANT mencoba mengatasi masalah ini dengan selalu mengetahui *di mana* posisi pasar sebelum memutuskan *apa* yang harus dilakukan.

Pendekatan ini punya dua konsekuensi penting. Pertama, sistem tidak selalu menghasilkan sinyal — ada kalanya jawaban yang paling tepat adalah "tidak ada setup yang valid sekarang." Kedua, kepercayaan diri sistem pada suatu sinyal diukur secara kuantitatif melalui skor konfluens, bukan hanya label biner "beli" atau "jual."

---

## 2. Teori Market Regime

### Apa itu Regime Pasar?

Regime pasar adalah kondisi statistik pasar yang berlangsung selama suatu periode tertentu dan memiliki karakteristik yang berbeda-beda. Sebuah pasar yang sedang dalam *bull trend* berperilaku secara fundamental berbeda dari pasar yang sedang dalam *crash* atau *konsolidasi* — distribusi return, volatilitas, volume, dan momentum semuanya berbeda.

Konsep ini berasal dari literatur ekonometrika (Hamilton, 1989) yang menunjukkan bahwa deret waktu ekonomi — termasuk harga aset — lebih baik dimodelkan sebagai proses yang beralih antar regime daripada sebagai satu distribusi tunggal yang stabil.

### Mengapa 4 Regime?

BTC-QUANT menggunakan 4 regime karena kombinasi antara kemampuan interpretasi dan kelengkapan deskriptif:

**Bullish Trend** — Return positif dominan, volatilitas moderat hingga tinggi, volume meningkat. Pasar sedang dalam fase akumulasi atau distribusi ke atas. Scalping long memiliki probabilitas lebih tinggi di regime ini.

**Bearish Trend** — Return negatif dominan, volatilitas moderat hingga tinggi, volume bisa tinggi (capitulation) atau rendah (bleeding). Scalping short memiliki probabilitas lebih tinggi.

**High Volatility Sideways** — Return mendekati nol secara agregat, tapi volatilitas sangat tinggi. Ini adalah kondisi paling berbahaya untuk scalping karena pergerakan besar terjadi ke kedua arah tanpa tren yang jelas. Di sini sistem cenderung memberikan sinyal SUSPENDED.

**Low Volatility Sideways** — Return mendekati nol, volatilitas rendah, range sempit. Pasar sedang konsolidasi. Scalping bisa dilakukan dengan target kecil, tapi potensi reward terbatas.

### Kenapa Regime Lebih Berguna dari Indikator Tunggal?

Indikator tunggal seperti RSI atau MACD memberikan pembacaan yang sama terlepas dari apakah pasar sedang trending atau choppy. RSI 30 bisa berarti oversold dalam bull market yang sehat, atau hanya satu titik dalam bear trend yang panjang. Regime memberikan *konteks* — RSI 30 dalam Bullish Trend sangat berbeda artinya dari RSI 30 dalam High Volatility Sideways.

---

## 3. Layer 1 — Hidden Markov Model (HMM)

### Intuisi Dasar

Bayangkan pasar sebagai mesin yang memiliki beberapa *mode operasi* tersembunyi. Setiap mode menghasilkan pola pergerakan harga yang berbeda, tetapi kita tidak bisa langsung melihat mode mana yang aktif — kita hanya bisa mengobservasi harga dan volume yang muncul ke permukaan. HMM adalah alat matematika untuk menyimpulkan mode tersembunyi tersebut dari observasi yang ada.

"Hidden" (tersembunyi) mengacu pada fakta bahwa *state* pasar — apakah sedang trending, crash, atau konsolidasi — tidak bisa diobservasi secara langsung. Yang bisa diobservasi hanyalah sinyal-sinyal yang dipancarkan: pergerakan harga, spread candle, anomali volume.

### Komponen HMM

**States (S)** — Kumpulan kondisi tersembunyi yang bisa ada. BTC-QUANT menggunakan 4 state yang kemudian diberi label secara dinamis berdasarkan karakteristik statistiknya.

**Transition Matrix (A)** — Matriks probabilitas perpindahan antar state. `A[i][j]` adalah peluang bahwa jika sekarang di state *i*, candle berikutnya akan berada di state *j*. Diagonal matriks ini (persistensi) sangat penting: nilai tinggi berarti state tersebut cenderung bertahan lama, nilai rendah berarti state mudah berpindah.

Berdasarkan data empiris BTC 2018–2024 (Machimbo et al., 2025), persistensi tiap state berbeda drastis. State "crash" hanya persisten 48% per hari — artinya crash BTC sering berakhir dalam 1–2 hari. Sebaliknya, state "bear lemah" persisten 92% — sekali masuk bear trend, cenderung bertahan lama.

**Emission Distribution (B)** — Distribusi probabilitas yang mendefinisikan "seperti apa" suatu state dari sisi observasi. BTC-QUANT menggunakan **Gaussian Mixture** untuk setiap state, artinya setiap state diasumsikan menghasilkan fitur-fitur yang berdistribusi normal dengan mean dan variance tertentu. State "High Volatility" akan memiliki mean variance yang tinggi; state "Calm" akan memiliki mean variance yang rendah.

**Initial Probabilities (π)** — Distribusi probabilitas state pada waktu awal.

### Algoritma Baum-Welch (EM)

HMM dilatih menggunakan algoritma Expectation-Maximization yang disebut Baum-Welch. Prosesnya iteratif:

**E-step** — Dengan parameter model yang ada, hitung probabilitas posterior setiap state untuk setiap titik data. Ini memberikan "soft assignment" — seberapa mungkin candle ke-t berada di masing-masing state.

**M-step** — Perbarui semua parameter (transition matrix, mean, variance tiap state) agar memaksimalkan likelihood data yang diobservasi, menggunakan soft assignment dari E-step.

Proses ini diulang hingga konvergensi atau mencapai batas iterasi (1000 iterasi di BTC-QUANT). Semakin banyak iterasi, semakin model punya kesempatan menemukan konfigurasi parameter yang optimal.

### Algoritma Viterbi

Setelah model dilatih, untuk menentukan state terbaik pada setiap titik waktu digunakan algoritma Viterbi. Ini adalah algoritma dynamic programming yang mencari **sequence of states paling mungkin** secara keseluruhan — bukan hanya state paling mungkin di setiap titik secara independen.

Viterbi mempertimbangkan koherensi temporal: sequence `[Bull, Bull, Bull, Bear]` mungkin lebih masuk akal dari `[Bull, Bear, Bull, Bear]` bahkan jika di titik ke-2 dan ke-3 probabilitas individual-nya sama — karena transisi yang lebih sedikit lebih konsisten dengan perilaku pasar nyata.

### Pelabelan Dinamis

Ini salah satu desain paling penting di BTC-QUANT. HMM murni hanya menghasilkan angka state (0, 1, 2, 3) tanpa label. Nomor state bisa berubah setiap retrain — state "Bullish" bisa jadi nomor 2 di training pertama dan nomor 0 di training berikutnya.

BTC-QUANT mengatasi ini dengan **pelabelan dinamis post-hoc**: setelah setiap training, sistem menghitung statistik agregat (rata-rata return dan rata-rata volatilitas) untuk setiap state, lalu memetakan:
- State dengan return tertinggi → "Bullish Trend"
- State dengan return terendah → "Bearish Trend"
- Dari dua state sisanya: volatilitas lebih tinggi → "High Volatility Sideways", lebih rendah → "Low Volatility Sideways"

Ini memastikan label selalu konsisten dengan realita pasar, terlepas dari bagaimana HMM mengalokasikan nomor state-nya.

### AIC dan BIC sebagai Monitor Konvergensi

AIC (Akaike Information Criterion) dan BIC (Bayesian Information Criterion) adalah dua metrik standar untuk mengevaluasi kualitas model probabilistik. Keduanya mengukur trade-off antara goodness-of-fit (seberapa baik model menjelaskan data) dan kompleksitas model (seberapa banyak parameter yang digunakan).

BTC-QUANT menghitung AIC/BIC setelah setiap retrain sebagai sinyal kesehatan. Jika nilai ini tiba-tiba melonjak jauh dibandingkan sesi sebelumnya, itu bisa mengindikasikan data yang masuk memiliki karakteristik yang sangat berbeda dari biasanya, atau model tidak berhasil konvergen dengan baik.

---

## 4. Fitur-Fitur yang Diobservasi

HMM dan MLP di BTC-QUANT tidak bekerja langsung pada harga mentah, melainkan pada 5 fitur yang diturunkan dari OHLCV. Pemilihan fitur ini memiliki alasan konseptual masing-masing.

### Log Return: `ln(Close_t / Close_{t-1})`

Log return digunakan alih-alih persentase return biasa karena sifat matematisnya lebih baik untuk pemodelan statistik. Log return bersifat aditif secara temporal (return 3 hari = jumlah log return harian), dan distribusinya mendekati normal untuk periode pendek. Ini sesuai dengan asumsi Gaussian di dalam HMM.

### Realized Volatility: Rolling Standard Deviation (14 candle)

Volatilitas adalah ukuran dispersi return. Rolling std dari 14 candle memberikan estimasi volatilitas yang "disadari" dalam jendela waktu terbaru. Ini adalah fitur yang membedakan regime trending (volatilitas moderat-tinggi) dari regime konsolidasi (volatilitas rendah).

### High-Low Spread: `(High - Low) / Close`

Spread harian yang dinormalisasi oleh harga mencerminkan intensitas pertarungan antara buyer dan seller dalam satu candle. Candle dengan spread tinggi menandakan ketidakpastian atau momentum kuat. Fitur ini komplementer dengan realized volatility — realized vol melihat pergerakan close-to-close, sementara HL spread melihat range intra-candle.

### Volume Z-Score: `(Volume - mean_20) / std_20`

Z-score mengukur seberapa "anomali" volume saat ini dibandingkan volume rata-rata 20 candle terakhir. Volume spike sering mendahului atau bersamaan dengan pergantian regime — capitulation dalam bear market, breakout dalam bull market, atau panic buying/selling dalam crash. Tanpa fitur ini, HMM hanya melihat pergerakan harga tanpa mempertimbangkan partisipasi pasar.

### Volatility Trend: `realized_vol[t] - realized_vol[t-1]`

Dua candle dengan realized volatility yang sama — misalnya 0.8% — bisa berada dalam kondisi pasar yang sangat berbeda: yang satu dalam keadaan volatilitas yang sedang naik (regime akan berubah), yang lain dalam keadaan volatilitas yang sedang turun (regime sedang menstabilkan diri). Fitur ini menangkap arah perubahan volatilitas, informasi yang tidak ada dalam realized volatility itu sendiri.

---

## 5. Layer 3 — MLP Neural Network

### Pertanyaan yang Berbeda dari HMM

Sementara HMM menjawab "pasar sedang dalam kondisi apa?", MLP menjawab pertanyaan yang lebih operasional: "apakah candle berikutnya akan naik atau turun?"

Ini adalah masalah klasifikasi biner dengan cakrawala prediksi satu candle ke depan (4 jam untuk timeframe yang digunakan).

### Arsitektur

BTC-QUANT menggunakan MLP (Multi-Layer Perceptron) dengan arsitektur `Input(5) → Dense(64, ReLU) → Dense(32, ReLU) → Output(2, Softmax)`.

ReLU (Rectified Linear Unit) sebagai fungsi aktivasi dipilih karena kemampuannya mengatasi vanishing gradient dan efisiensinya secara komputasional. Layer 64 dan 32 neuron memungkinkan model belajar representasi non-linear dari hubungan antar fitur, yang tidak bisa ditangkap oleh model linear.

Output layer menghasilkan dua probabilitas: probabilitas candle naik dan probabilitas candle turun. Keduanya selalu berjumlah 1.

### Fitur untuk MLP

MLP menggunakan fitur teknikal yang berbeda dari HMM, karena pertanyaannya berbeda:

**RSI (14)** — Relative Strength Index mengukur momentum relatif harga. RSI > 70 mengindikasikan kondisi overbought (tekanan jual potensial), RSI < 30 mengindikasikan oversold (tekanan beli potensial). Ini memberikan konteks apakah pasar sudah "terlalu jauh" ke satu arah.

**MACD Histogram** — Selisih antara MACD line dan signal line. Perubahan arah histogram sering mendahului pembalikan momentum jangka pendek. Ini adalah fitur "early warning" untuk perubahan arah.

**Jarak dari EMA20** — `(Close - EMA20) / EMA20` mengukur seberapa jauh harga menyimpang dari rata-rata bergerak 20 periode. Harga yang sangat jauh di atas EMA20 cenderung mean-revert; harga yang sangat dekat EMA20 dalam trend kuat cenderung melanjutkan trend.

**Log Return** — Konteks momentum terbaru. Apakah candle sebelumnya bullish atau bearish, dan seberapa kuat.

**Normalized ATR** — `ATR / Close` mengukur volatilitas relatif. MLP menggunakannya untuk memahami apakah kondisi saat ini "tenang" atau "bergejolak", yang mempengaruhi reliabilitas sinyal teknikal.

### Online Learning

Setiap kali dipanggil, MLP dilatih ulang dari nol menggunakan data terbaru. Ini berbeda dari pendekatan ML konvensional yang melatih model sekali lalu menggunakan bobot yang tetap. Alasannya adalah karakteristik pasar kripto berubah terlalu cepat — model yang dilatih 3 bulan lalu mungkin sudah tidak relevan.

Pendekatan ini juga berarti model tidak "memorizing" pola historis yang sudah tidak berlaku, melainkan selalu menyesuaikan diri dengan regime terkini.

Early stopping digunakan selama training: 15% data dipisahkan sebagai validation set, dan training berhenti jika performa di validation set tidak meningkat — mencegah overfitting pada data training.

### Output: Bias dan Confidence

MLP tidak hanya menghasilkan label "BULL" atau "BEAR", melainkan probabilitas mentah. Confidence dihitung dari probabilitas kelas yang menang:
- Confidence 50% = model sama bimbangnya antara dua arah (tidak berguna)
- Confidence 70% = model cukup yakin
- Confidence 90%+ = model sangat yakin (jarang terjadi, justru harus diwaspadai — bisa overfitting)

Threshold minimum confidence yang dipakai sistem untuk mengaktifkan Layer 3 adalah 55%.

---

## 6. Layer 4 — Sistem Konfluens & Decision Engine

### Filosofi Konfluens

Konfluens dalam trading berarti beberapa perspektif yang berbeda semua menunjuk ke arah yang sama. Satu sinyal bisa salah; empat sinyal independen yang semuanya sepakat jauh lebih sulit untuk semuanya salah sekaligus.

BTC-QUANT mengimplementasikan ini sebagai **Layer 4**, yang mengagregasi input dari Layer 1, 2, dan 3. Keempat komponen dievaluasi secara independen, kemudian hasilnya digabungkan.

### Layer 1 — HMM Regime (Konteks Makro)

Layer ini menjawab: *apakah kondisi pasar mendukung arah yang sedang kita pertimbangkan?*

Layer 1 dinyatakan ALIGNED jika regime yang terdeteksi HMM konsisten dengan arah sinyal. Jika sinyal adalah SHORT (bearish), layer ini aligned jika HMM mendeteksi "Bearish Trend" atau "bear" state. Jika tidak aligned — misalnya kita ingin short tapi HMM mendeteksi "Bullish Trend" — itu warning keras bahwa kita sedang melawan arus.

### Layer 2 — Struktur EMA (Konfirmasi Teknikal)

Layer ini menjawab: *apakah struktur tren yang terbentuk konsisten dengan arah sinyal?*

EMA20 dan EMA50 (Exponential Moving Average) adalah dua indikator trend yang sangat fundamental. EMA20 bergerak lebih responsif terhadap harga terbaru; EMA50 lebih lambat dan stabil. Ketika EMA20 di atas EMA50 dan harga di atas EMA20, itu adalah struktur bullish yang jelas — tiga level support tersusun dari bawah ke atas.

Layer 2 aligned jika susunan EMA konsisten dengan arah trend yang ditetapkan sistem.

### Layer 3 — MLP AI (Prediksi Short-Term)

Layer ini menjawab: *apakah ML model memperkirakan candle berikutnya bergerak ke arah yang kita inginkan?*

Layer 3 adalah lapisan paling "lokal" dan paling cepat berubah. Ia hanya melihat 4 jam ke depan, berbeda dari HMM yang melihat kondisi yang lebih lama. Layer ini aligned jika MLP memberikan bias yang sama dengan arah sinyal DAN confidence-nya di atas 55%.

### Layer 4 — Volatilitas (Gate Risiko)

Layer ini menjawab: *apakah kondisi volatilitas memungkinkan parameter risiko yang aman?*

Berbeda dari tiga layer lainnya yang bersifat direktional, Layer 4 adalah filter risiko murni. Layer ini aligned jika ATR ratio (ATR dibagi harga) di bawah 2% — artinya market tidak sedang dalam kondisi volatilitas ekstrem yang membuat stop-loss menjadi terlalu jauh dari entry.

Ketika volatilitas sangat tinggi, bahkan sinyal yang secara arah benar bisa menghasilkan loss karena stop-loss yang diperlukan menjadi terlalu besar relatif terhadap potensi reward.

### Skor Konfluens

Setiap layer yang aligned memberikan 25 poin. Total skor berkisar dari 0 hingga 100:

| Skor | Interpretasi | Trade Plan |
|------|-------------|------------|
| 0–25 | Konfluens sangat lemah | SUSPENDED — jangan entry |
| 25–50 | Konfluens rendah | SUSPENDED — tunggu setup lebih baik |
| 50–75 | Konfluens sedang | ADVISORY — kurangi size, perlu konfirmasi tambahan |
| 75–100 | Konfluens kuat | ACTIVE — eksekusi saat harga masuk zona entry |

Bobot yang sama (25 poin per layer) adalah keputusan desain yang disengaja. Mempertimbangkan bahwa kita tidak punya data historis yang cukup untuk mengkalibrasi bobot yang berbeda secara statistik, equal-weight adalah pendekatan yang paling defensif dan paling mudah dipahami.

---

## 7. Layer 5 — Naratif & Truth Enforcer

**Layer 5 (Narrative Engine)** adalah lapisan terakhir yang bertugas menerjemahkan angka kuantitatif menjadi bahasa manusia.

### Input dari Layer 4
Berbeda dengan sistem analisis murni, Layer 5 menerima output dari **Layer 4 (Decision Engine)** sebagai masukan utama. Ini memastikan bahwa narasi yang dihasilkan LLM selalu memiliki konteks tentang skor konfluens, status alignment tiap layer, dan parameter risiko.

### Mekanisme Truth Enforcer
Mekanisme ini memastikan skor kuantitatif selalu menjadi otoritas final:

**Skor < 40** → Verdict dipaksa menjadi NEUTRAL, apapun yang dikatakan LLM. Konfluens terlalu lemah untuk menginisiasi posisi apapun.

**Skor ≥ 80** → Verdict dipaksa menjadi STRONG BUY atau STRONG SELL sesuai arah trend, apapun yang dikatakan LLM. Pada skor setinggi ini, konfluens sudah sangat kuat sehingga tidak perlu menunggu persetujuan LLM.

**Skor 40–79** → LLM verdict diterima *jika dan hanya jika* arahnya konsisten dengan trend. LLM tidak bisa mengubah arah sinyal; ia hanya bisa menentukan kekuatannya (WEAK vs STRONG) dalam rentang skor sedang.

Prinsip ini penting karena mencegah "mode collapse" di mana sistem menjadi terlalu bergantung pada output LLM yang bisa dipengaruhi oleh cara pertanyaan diframing.

---

## 8. Manajemen Risiko Berbasis ATR

### ATR sebagai Unit Risiko

Average True Range (ATR) adalah indikator yang mengukur volatilitas pasar sebagai rata-rata dari "true range" selama N periode. True range pada setiap candle adalah nilai maksimum dari: (High - Low), (|High - Close sebelumnya|), (|Low - Close sebelumnya|).

ATR berguna karena ia adaptif — pada pasar yang volatile, ATR besar dan stop-loss yang ditetapkan sistem secara otomatis lebih lebar; pada pasar yang tenang, ATR kecil dan stop-loss lebih ketat. Ini mencegah stop-loss yang "terlalu sempit" di pasar volatile (sering kena) atau "terlalu lebar" di pasar tenang (risk-reward jelek).

### Kalkulasi Parameter Risiko

**Stop-Loss** ditempatkan di jarak 1.5× ATR dari entry. Multiplier 1.5 memberikan cukup ruang untuk noise normal pasar tanpa membuat risiko terlalu besar.

**Take Profit 1** ditempatkan di 1.5× ATR risk (risk-reward 1:1). Ini adalah target konservatif untuk mengamankan sebagian profit.

**Take Profit 2** ditempatkan di 2.5× ATR risk (risk-reward 1:1.67). Ini adalah target optimal jika trend berlanjut.

**Leverage** ditentukan secara inverse terhadap volatilitas:
- ATR/Close > 1.5% → leverage 2× (pasar sangat volatile)
- ATR/Close 1.2–1.5% → leverage 3×
- ATR/Close 0.8–1.2% → leverage 5×
- ATR/Close < 0.8% → leverage 7× (pasar tenang)

Logika di balik ini: pada pasar yang sangat volatile, pergerakan melawan posisi bisa sangat cepat dan besar. Leverage rendah memastikan bahwa meskipun stop-loss lebih jauh (dalam nilai absolut), ukuran kerugian relatif terhadap portfolio tetap terkontrol.

---

## 9. Metrik Pasar — Informasi Tambahan

Selain OHLCV dan model-model di atas, BTC-QUANT juga mengumpulkan tiga metrik pasar yang memberikan konteks ekstra.

### Funding Rate

Funding rate adalah mekanisme di pasar perpetual futures cryptocurrency untuk menjaga harga futures tetap dekat dengan harga spot. Jika funding rate positif, trader yang long membayar trader yang short secara periodik; jika negatif, sebaliknya.

Funding rate yang sangat positif mengindikasikan bahwa banyak trader yang long dan bersedia membayar premium — ini bisa berarti pasar sedang sangat optimis (bullish) tetapi juga menciptakan risiko *squeeze* karena long yang terlalu banyak bisa dipaksa keluar serentak. Funding rate yang sangat negatif mengindikasikan posisi short yang dominan.

### Open Interest

Open Interest adalah total nilai posisi terbuka yang belum diselesaikan di pasar futures. Peningkatan OI dengan kenaikan harga menandakan tren yang kuat (uang baru masuk). Penurunan OI dengan kenaikan harga bisa berarti short squeeze sementara, bukan tren sejati. Penurunan OI dengan penurunan harga bisa berarti capitulation — long yang keluar massal.

### Order Book Imbalance (OBI)

OBI mengukur ketidakseimbangan antara total volume bid (beli) dan ask (jual) di buku order dalam depth tertentu:

```
OBI = (Total Bid Volume - Total Ask Volume) / (Total Bid Volume + Total Ask Volume)
```

Range OBI adalah -1.0 (semua ask, tekanan jual dominan) hingga +1.0 (semua bid, tekanan beli dominan). OBI memberikan snapshot real-time tentang sentimen trader di level harga saat ini — sesuatu yang tidak bisa dilihat dari OHLCV yang hanya mencatat transaksi yang sudah terjadi.

---

## 10. Keterbatasan dan Asumsi

### Asumsi Stasionaritas Lokal

HMM mengasumsikan bahwa distribusi emisi setiap state (mean dan variance return, volatilitas, dll.) relatif stabil dalam jendela training. Ini adalah asumsi yang wajar untuk jendela pendek (150 candle = ~25 hari), tetapi bisa dilanggar saat terjadi perubahan struktural pasar seperti halving Bitcoin atau krisis sistemik.

### Homogeneous vs Non-Homogeneous HMM

HMM yang digunakan BTC-QUANT adalah *homogeneous* — transition matrix-nya tetap, tidak berubah berdasarkan kondisi eksternal. Penelitian menunjukkan bahwa *Non-Homogeneous Hidden Markov Model* (NHHM) di mana transition matrix berubah berdasarkan faktor seperti VIX (indeks fear) bisa lebih akurat. Ini adalah pengembangan yang direncanakan untuk versi mendatang.

### Overfitting MLP

MLP yang dilatih pada jendela data yang pendek rentan terhadap overfitting — model bisa "menghafal" pola spesifik data training yang tidak general. Early stopping dan validation set membantu, tetapi tidak sepenuhnya menyelesaikan masalah ini. Confidence tinggi dari MLP harus ditafsirkan dengan skeptisisme, bukan keyakinan penuh.

### Bukan Auto-Trading

BTC-QUANT dirancang sebagai *decision support system*, bukan sistem auto-trading. Skor konfluens dan sinyal yang dihasilkan adalah input untuk proses pengambilan keputusan manusia, bukan eksekusi otomatis. Konteks yang tidak bisa dikuantifikasi — berita, sentiment sosial, kebijakan regulasi — tetap harus dipertimbangkan oleh trader.

### Past Performance

Semua model dalam BTC-QUANT dilatih pada data historis. Performa historis tidak menjamin performa masa depan, terutama dalam pasar yang strukturnya berubah secara fundamental. Model selalu perlu divalidasi secara berkala dengan data live.

---

*Dokumen ini bersifat living document — akan diperbarui seiring perkembangan sistem.*
