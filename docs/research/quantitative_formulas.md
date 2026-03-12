# Formulasi Matematis BTC-QUANT-BTC Quant Scalper

Dokumen ini merangkum dasar-dasar matematis dan logika kuantitatif yang menggerakkan platform BTC-QUANT-BTC setelah pembaruan **Phase 1-8**.

---

## 1. Feature Engineering (Observasi Tersembunyi)

Sistem mentransformasi data OHLCV mentah menjadi vektor fitur $X_t$ untuk model HMM dan MLP.

### a. Log Return
Digunakan untuk normalisasi deret waktu agar stasioner:
$$r_t = \ln\left(\frac{P_t}{P_{t-1}}\right)$$
Dimana $P_t$ adalah harga penutupan pada waktu $t$.

### b. Realized Volatility
Mengukur dispersi harga dalam jendela waktu $\tau = 14$:
$$\sigma_t = \sqrt{\frac{1}{\tau} \sum_{i=0}^{\tau-1} (r_{t-i} - \bar{r}_t)^2}$$

### c. Volume Z-Score
Mendeteksi anomali volume relatif terhadap rata-rata bergerak ($\mu_{vol}$) dan standar deviasi ($\sigma_{vol}$) jendela 20 candle:
$$Z_{vol, t} = \frac{V_t - \mu_{vol, t}}{\sigma_{vol, t}}$$

---

## 2. Layer 1: Hidden Markov Model (HMM)

HMM mengasumsikan pasar berada dalam *hidden state* $S_t \in \{1, \dots, N\}$ yang tidak terlihat langsung.

### a. Pemilihan Jumlah State Optimal (BIC)
Sistem menggunakan *Bayesian Information Criterion* untuk memilih $N$ state terbaik (2-6):
$$BIC = \ln(n)k - 2\ln(\hat{L})$$
Dimana:
- $n$: jumlah observasi
- $k$: jumlah parameter bebas ($N^2 + 2N \cdot dims$)
- $\hat{L}$: Likelihood maksimum dari model.

### b. Non-Homogeneous Transition (NHHM Bias)
Probabilitas transisi $A_{ij} = P(S_{t+1}=j | S_t=i)$ dimodifikasi secara dinamis berdasarkan Funding Rate ($f_t$):
$$A'_{ij} = \text{softmax}(A_{ij} + \beta \cdot f_t)$$
Jika $f_t > 0.01\%$, sistem meningkatkan probabilitas transisi keluar dari regime Bullish untuk mengantisipasi *Long Squeeze*.

---

## 3. Layer 3: Regime-Aware MLP

Prediksi arah harga candle berikutnya ($y_{t+1} \in \{0, 1\}$) menggunakan integrasi fitur silang.

### a. One-Hot Regime Encoding
Output HMM ($S_t$) diubah menjadi vektor biner:
$$\mathbf{h}_t = [ \mathbb{1}(S_t=1), \mathbb{1}(S_t=2), \dots, \mathbb{1}(S_t=N) ]$$

### b. MLP Forward Pass
Vektor input gabungan $\mathbf{x}^{total}_t = [\mathbf{x}^{tech}_t, \mathbf{h}_t]$ diproses melalui jaringan saraf:
$$z_1 = \text{ReLU}(W_1 \mathbf{x}^{total}_t + b_1)$$
$$\hat{y}_{t+1} = \sigma(W_2 z_1 + b_2)$$
Dimana $\sigma$ adalah fungsi sigmoid untuk probabilitas arah.

---

## 4. Directional Spectrum Scoring

Menggantikan skor biner dengan spektrum kontinu $D \in [-1, 1]$.

### a. Weighted Confluence
$$D_t = \text{side}_t \times \sum_{i=1}^{4} (w_i \cdot \mathbb{1}_{aligned, i} \cdot C_i)$$
Dimana:
- $\text{side}_t$: $+1$ (Bullish) atau $-1$ (Bearish).
- $w_i$: Bobot layer ($w_{HMM}=0.3, w_{MLP}=0.35$, dll).
- $C_i$: Confidence layer tersebut ($MLP_{prob}$ atau $HMM_{posterior}$).

---

## 5. Risk Management Berbasis ATR

### a. Dinamis Position Sizing
Besar posisi ($Size$) disesuaikan dengan keyakinan sistem:
$$Size = \text{BaseSize} \times |D_t|$$

### b. Adaptive Leverage
Leverage ($L$) berbanding terbalik dengan volatilitas relatif ($ATR/P$):
$$L \propto \frac{1}{ATR_t / P_t}$$
Semakin bergejolak pasar, semakin rendah leverage yang diizinkan untuk menjaga jarak Stop Loss tetap aman.

---
**Catatan:** Formulasi ini memastikan bahwa keputusan tidak hanya diambil berdasarkan indikator teknikal tunggal, melainkan melalui konsensus probabilitas antar berbagai dimensi pasar (regime, momentum, psikologi, dan risiko).
