# Deep Quant Analysis: Formulasi Matematis BTC-QUANT-BTC v2

Dokumen ini menjelaskan fondasi matematis pipeline kuantitatif BTC-QUANT-BTC dengan bahasa yang lebih naratif.  
Tujuannya bukan hanya menampilkan rumus, tetapi memperjelas **mengapa** rumus tersebut dipakai, **apa maknanya** dalam praktik trading, dan **bagaimana** tiap komponen saling terhubung dari data mentah menjadi keputusan posisi.

Secara garis besar, sistem bekerja dalam 4 tahap:
1. Mengidentifikasi "rezim pasar" (kondisi laten) menggunakan HMM.
2. Memperkirakan probabilitas arah harga dengan MLP yang sadar-rezim.
3. Menggabungkan semua sinyal menjadi skor keyakinan arah (`D_t`).
4. Menerjemahkan skor tersebut ke manajemen risiko adaptif (SL/TP, leverage, size).

Dengan demikian, sistem tidak beroperasi sebagai aturan if-else kaku, tetapi sebagai mesin probabilistik: semakin tinggi keyakinan, semakin besar eksposur; semakin tidak pasti, semakin kecil risiko.

---

## 1. Probabilistic Market Regime (HMM)

Pada kenyataannya, pasar jarang berada dalam satu mode statis. Ada fase trending, mean-reverting, hingga fase transisi yang noisy.  
HMM memodelkan kondisi-kondisi ini sebagai **state tersembunyi** yang tidak diamati langsung, namun bisa diinferensi dari observasi harga/indikator.

HMM didefinisikan sebagai tuple $\lambda = (A, B, \pi)$, di mana parameter diestimasi untuk memaksimalkan kemungkinan data:
$$\max_\lambda P(O|\lambda)$$

Makna praktis:
- $A$: probabilitas perpindahan antarkondisi pasar (mis. dari trend ke exit/risk-off).
- $B$: distribusi observasi pada masing-masing state (bagaimana indikator "terlihat" saat state tertentu aktif).
- $\pi$: probabilitas state awal.

### A. Dynamic N-States Optimization (BIC)
Jumlah state tersembunyi $K$ sangat krusial.  
Jika terlalu sedikit, model gagal menangkap struktur pasar. Jika terlalu banyak, model "menghafal noise".  
Karena itu, $K$ dipilih otomatis melalui kriteria informasi BIC:
$$BIC(K) = -2\mathcal{L}(\hat{\theta}) + \left( K^2 + 2Kd - 1 \right) \ln(T)$$
Di mana:
- $\mathcal{L}(\hat{\theta})$: Log-likelihood maksimum dari model dengan $K$ states.
- $K^2$: Jumlah parameter pada matriks transisi $A$.
- $2Kd$: Parameter untuk distribusi Gaussian (Mean $\mu$ dan Kovarians $\Sigma$) dengan dimensi fitur $d$.
- $T$: Jumlah observasi (candle).

Intuisi BIC: komponen pertama menghargai model yang fit terhadap data, komponen kedua memberi penalti kompleksitas.  
Model terbaik adalah titik kompromi antara akurasi dan kesederhanaan.

### B. Non-Homogeneous Transition Matrix (NHHM Bias)
Pada HMM standar, matriks transisi dianggap stasioner (konstan).  
Di pasar kripto, perilaku perpindahan regime bisa berubah tergantung konteks mikrostruktur, salah satunya funding rate.

Karena itu, transisi diberi bias kondisional:
$$P(S_{t+1} = \text{Exit} | S_t = \text{Trend}, f_t) = A_{i, \text{Exit}} \times (1 + \min(0.15, \text{sgn}(f_t) \cdot f_t \cdot 500))$$
Setelah bias diterapkan, baris matriks dinormalisasi ulang:
$$A'_{ij} = \frac{A_{ij}}{\sum_{k=1}^K A_{ik}}$$

Makna praktis: sistem menjadi lebih responsif terhadap tekanan posisi pasar.  
Saat funding mengindikasikan kondisi ekstrem satu sisi, probabilitas keluar dari regime trend dapat dinaikkan (hingga batas aman) untuk mengurangi false confidence.

---

## 2. Regime-Aware Neural Predictor (MLP)

Setelah state pasar diperkirakan oleh HMM, prediktor arah harga tidak bekerja "buta".  
MLP diberi konteks regime agar interpretasi sinyal teknikal menyesuaikan kondisi pasar saat itu.

### A. Input Layer & Cross-Feature Embedding
Input vector $\mathbf{x}_t$ adalah penggabungan (*concatenation*) fitur teknikal $\mathbf{x}^{tech}$ dan *one-hot encoded* hidden state dari HMM $S_t$:
$$\mathbf{x}_t = [ RSI_t, MACD_{hist, t}, \Delta EMA_t, r_t, \sigma_{ATR, t}, \mathbb{1}_{S_t=1}, \dots, \mathbb{1}_{S_t=K} ]^T$$

Intuisi:
- Fitur teknikal menangkap dinamika lokal harga.
- One-hot regime memberi konteks global "pasar sedang mode apa".
- Kombinasi keduanya memungkinkan relasi non-linear: sinyal yang sama bisa bermakna berbeda di regime berbeda.

### B. Neural Architecture (Forward Pass)
Prediksi dilakukan melalui transformasi non-linear:
1. **Hidden Layer 1**: $\mathbf{h}^{(1)} = \phi(W^{(1)}\mathbf{x}_t + \mathbf{b}^{(1)})$
2. **Hidden Layer 2**: $\mathbf{h}^{(2)} = \phi(W^{(2)}\mathbf{h}^{(1)} + \mathbf{b}^{(2)})$
3. **Output Layer**: $\hat{y}_{t+1} = \text{Softmax}(W^{(3)}\mathbf{h}^{(2)} + \mathbf{b}^{(3)})$

Di mana $\phi$ adalah fungsi aktivasi **ReLU**: $\max(0, z)$. Output $\hat{y}_{t+1}$ memberikan probabilitas bersyarat $P(y_{t+1} = \text{UP} | \mathbf{x}_t)$.

Interpretasi:
- Output bukan "pasti naik/turun", tetapi probabilitas kondisional.
- Ini penting untuk risk engine karena ukuran posisi seharusnya proporsional terhadap tingkat keyakinan, bukan sekadar arah.

---

## 3. Directional Spectrum & Confluence Engine

Pada banyak sistem trading, keputusan akhir dipaksa menjadi sinyal biner terlalu dini.  
Di sini, keputusan dibentuk sebagai **spektrum keyakinan arah** agar informasi probabilistik tidak hilang.

### A. Normalized Confidence
Untuk layer prediktif (MLP), confidence dinormalisasi dari rentang $[0.5, 1.0]$ ke $[0, 1]$ agar memberikan kontribusi linear:
$$C_{MLP} = \frac{\max(0.5, P(y)) - 0.5}{0.5}$$

Artinya:
- Probabilitas 0.5 dianggap netral (tidak menambah keyakinan).
- Semakin jauh dari 0.5 ke atas, kontribusi confidence meningkat linier sampai 1.

### B. Total Directional Bias ($D_t$)
$$D_t = \text{Trend}_{side} \cdot \sum_{i=1}^L w_i \cdot \alpha_i \cdot C_i$$
Di mana:
- $\text{Trend}_{side} \in \{1, -1\}$: Arah tren EMA.
- $w_i$: Bobot statis layer $i$ ($\sum w = 1$).
- $\alpha_i \in \{0, 1\}$: Boolean alignment (apakah layer $i$ searah dengan tren).
- $C_i \in [0, 1]$: Confidence internal dari engine $i$.

Makna operasional:
- Tanda $D_t$ menunjukkan arah (long/short).
- Besar $|D_t|$ menunjukkan kekuatan conviction.
- Jika sinyal antar-layer tidak selaras, nilai $D_t$ otomatis mengecil, sehingga ukuran posisi ikut turun.

---

## 4. Manajemen Risiko Adaptif (ATR-Based)

Tahap ini menerjemahkan probabilitas menjadi parameter eksekusi yang bisa dipakai langsung di market.  
Sistem tidak hanya bertanya "arah mana?", tetapi juga "berapa besar risiko yang rasional untuk arah tersebut?".

### A. Dynamic Stop-Loss (SL) & Take-Profit (TP)
Penentuan level harga berdasarkan volatilitas yang disadari (*Realized Volatility*):
$$SL = P_{entry} \pm (1.5 \cdot ATR_{14, t})$$
$$TP_1 = P_{entry} \mp (1.5 \cdot \text{Risk}_{abs})$$
$$TP_2 = P_{entry} \mp (2.5 \cdot \text{Risk}_{abs})$$

Interpretasi:
- Jarak SL mengikuti ATR agar "nafas posisi" sesuai rezim volatilitas.
- TP bertingkat memungkinkan skema partial take-profit: mengunci profit lebih awal sambil tetap memberi ruang untuk ekstensi tren.

### B. Inverse Volatility Leverage
Leverage $L$ dihitung sebagai fungsi diskrit dari rasio volatilitas $R_v = \frac{ATR_t}{P_t}$:
$$L(R_v) = \begin{cases} 7, & R_v < 0.8\% \\ 5, & 0.8\% \le R_v < 1.2\% \\ 3, & 1.2\% \le R_v < 1.5\% \\ 2, & R_v \ge 1.5\% \end{cases}$$

Logika inti: semakin tinggi volatilitas relatif, semakin rendah leverage.  
Ini mencegah overexposure pada fase market yang secara statistik berisiko lebih besar.

### C. Position Sizing
Modal yang dialokasikan ($M_{trade}$) untuk satu posisi:
$$M_{trade} = M_{total} \times \text{BaseSize} \times |D_t|$$
Hal ini memastikan saat $D_t \to 0$ (pasar tidak pasti), eksposur modal juga menuju nol.

---
## 5. Alur End-to-End (Ringkas)

Urutan proses dalam satu siklus keputusan:
1. Data candle dan indikator diperbarui.
2. HMM menginferensi regime aktif dan probabilitas transisinya.
3. MLP memproduksi probabilitas arah bersyarat pada fitur + regime.
4. Semua engine dikonsolidasikan ke skor $D_t$.
5. Risk engine menetapkan SL/TP, leverage, dan ukuran posisi berbasis ATR serta $|D_t|$.
6. Jika syarat minimum kualitas sinyal terpenuhi, order dieksekusi.

Dengan desain ini, keputusan trading menjadi:
- **Probabilistik** (bukan deterministik kaku),
- **Kontekstual** (sadar regime),
- **Terukur risikonya** (position sizing dan leverage adaptif).

---
**Summary:** Sistem ini mentransformasikan ketidakpastian pasar (HMM + MLP) menjadi keputusan eksekusi yang disiplin (Directional Spectrum + ATR Risk Engine), sehingga keyakinan sinyal dan besaran risiko bergerak selaras.
