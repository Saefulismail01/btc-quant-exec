# Laporan Walk-Forward & Ablation

Tanggal laporan: 2026-03-03  
Periode uji: 2022-11-01 s/d 2026-03-03 (hasil trade mulai aktif dari 2023-01-24)  
Modal awal: USD 10,000

## Ringkasan Hasil Utama

| Skenario | Final Equity (USD) | Net PnL % | Net PnL (USD) | Trades |
|---|---:|---:|---:|---:|
| Layer 1 | 37,211.13 | 272.11% | 27,211.13 | 506 |
| Layer 1+2 | 64,448.17 | 544.48% | 54,448.17 | 405 |
| Full Layer | 69,789.39 | 597.89% | 59,789.39 | 989 |

### Insight Ablation
- Full vs Layer 1: equity akhir lebih tinggi 87.55% (69,789 vs 37,211).
- Full vs Layer 1+2: equity akhir lebih tinggi 8.29% (69,789 vs 64,448).
- Layer 1+2 vs Layer 1: equity akhir lebih tinggi 73.20%.
- Estimasi CAGR (1218 hari):
  - Layer 1: 48.30%/tahun
  - Layer 1+2: 74.85%/tahun
  - Full Layer: 79.07%/tahun

## Detail Performa Full Layer

### KPI Inti
- Total trade: 989
- Win/Loss: 461 / 528
- Win rate: 46.61%
- Profit factor: 1.209
- Sharpe ratio: 1.568
- Daily return %: 0.4909% per hari
- Max drawdown: -45.38%
- Expectancy: +USD 60.45/trade
- Rata-rata winner: +USD 749.83
- Rata-rata loser: -USD 541.44

### Distribusi Exit
| Exit Type | Jumlah | Win Rate | Total PnL (USD) | Avg PnL (USD) |
|---|---:|---:|---:|---:|
| TP | 461 | 100.0% | 345,669.36 | 749.83 |
| SL | 528 | 0.0% | -285,879.94 | -541.44 |

### Distribusi Gate
| Gate | Jumlah | Win Rate | Total PnL (USD) | Avg PnL (USD) |
|---|---:|---:|---:|---:|
| ACTIVE | 895 | 47.0% | 62,911.20 | 70.29 |
| ADVISORY | 94 | 42.6% | -3,121.78 | -33.21 |

### Distribusi Side
| Side | Jumlah | Win Rate | Total PnL (USD) | Avg PnL (USD) |
|---|---:|---:|---:|---:|
| LONG | 449 | 49.0% | 29,701.98 | 66.15 |
| SHORT | 540 | 44.6% | 30,087.44 | 55.72 |

### Distribusi Regime
| Regime | Jumlah | Win Rate | Total PnL (USD) | Avg PnL (USD) |
|---|---:|---:|---:|---:|
| bull | 449 | 49.0% | 29,701.98 | 66.15 |
| bear | 325 | 45.8% | 32,062.41 | 98.65 |
| neutral | 215 | 42.8% | -1,974.97 | -9.19 |


### Distribusi Tahunan
| Tahun | Jumlah | Win Rate | Total PnL (USD) | Avg PnL (USD) |
|---|---:|---:|---:|---:|
| 2023 | 287 | 44.25% | 2,408.81 | 8.39 |
| 2024 | 321 | 48.60% | 19,703.92 | 61.38 |
| 2025 | 323 | 45.51% | 19,448.98 | 60.21 |
| 2026 (YTD s/d 2026-03-03) | 58 | 53.45% | 18,227.71 | 314.27 |

### Analisa Performa Seluruh Periode Pengujian

- Performa tahunan menunjukkan pola berikut:
  - 2023: fase adaptasi sistem, PnL tipis (+USD 2,408.81) dengan win rate 44.25%.
  - 2024-2025: fase ekspansi edge, PnL tahunan stabil tinggi (sekitar +USD 19k per tahun).
  - 2026 (YTD s/d 2026-03-03): awal tahun sangat kuat (+USD 18,227.71), tetapi belum comparable dengan tahun penuh.
- Sumber variasi performa utama selama seluruh periode adalah **cluster loss bulanan**, bukan hilangnya edge jangka panjang:
  - Bulan terbaik: 2025-11 (+USD 21,066.67).
  - Bulan terburuk: 2025-12 (-USD 26,439.67).
  - Ini menandakan distribusi hasil bersifat lumpy, sehingga kontrol sizing lebih penting daripada mengejar win rate semata.
- Driver struktural yang konsisten sepanjang data:
  - `ACTIVE` menghasilkan edge positif (895 trade, +USD 62,911.20; +USD 70.29/trade).
  - `ADVISORY` cenderung menggerus hasil (94 trade, -USD 3,121.78; -USD 33.21/trade).
  - Regime `neutral` negatif secara agregat (215 trade, -USD 1,974.97), sementara `bull` dan `bear` positif.
- Kesimpulan analitis periode penuh:
  - Sistem profitable lintas rezim waktu, tetapi kualitas entry tidak merata.
  - Stabilitas hasil paling bergantung pada disiplin filter gate dan pembatasan eksposur di regime `neutral`.

### Risk Profile & Drawdown
- Periode trading aktual (berdasarkan trade log): 2023-01-24 00:00 UTC s/d 2026-03-02 16:00 UTC (1133 hari kalender).
- Total trade: 989 dengan win rate total 46.61%.
- Durasi trade:
  - Rata-rata 30.47 jam
  - Median 16 jam
  - P90 72 jam
  - Maksimum 304 jam
- Risk per trade:
  - Risk fraction terhadap equity: mean 1.985%, median 2.000%, p95 2.000% (sangat konsisten di sekitar 2%).
  - Risk nominal (`risk_usd`): min USD 148.13, median USD 389.60, p90 USD 1,167.29, max USD 1,691.44.
- Win rate vs size (berdasarkan kuartil `risk_usd`):
  - Q1 (size terkecil): 45.16%
  - Q2: 47.37%
  - Q3: 47.77%
  - Q4 (size terbesar): 46.15%
- Win rate pada size terbesar (top 10% `risk_usd`):
  - 99 trade, win rate 43.43%, total PnL +USD 2,912.05, avg +USD 29.41/trade.
- Trade dengan size maksimum:
  - Entry 2025-11-21 04:00 UTC, exit 2025-11-23 12:00 UTC, side SHORT.
  - Risk USD 1,691.44, hasil -USD 1,692.79, exit type `SL`.
- R-multiple & Risk:Reward Ratio:
  - Avg Winner: **+1.386R** (Profit rata-rata 1.38x dari nilai risiko per trade).
  - Avg Loser: **-1.001R** (Loss rata-rata sesuai dengan mandat risk 2%).
  - Realized Risk:Reward Ratio: **1 : 1.38**
  - Expectancy Score: **+0.112R per trade** (Sistem menghasilkan profit bersih 0.112x risk untuk setiap trade yang diambil).
- Episode max DD:
  - Peak equity: USD 21,967.25 (2024-03-05 12:00 UTC)
  - Valley: USD 11,999.03 (2024-06-12 16:00 UTC)
  - Recovery ke high sebelumnya: 2024-10-01 20:00 UTC
  - Longest underwater period: 180 trade (2024-03-05 s/d 2024-10-01)

### Musiman PnL (Exit-time basis)
- Best month: 2025-11 = +USD 21,066.67
- Worst month: 2025-12 = -USD 26,439.67
- Sinyal performa bersifat lumpy, jadi sizing harus memperhitungkan cluster loss.

## Metodologi

### 1) Setup Backtest
- Walk-forward confluence menggunakan pipeline multi-layer.
- Trade dieksekusi ketika bias spektrum lolos gate minimal.
- Fee round-trip: 0.04% x 2 sisi.
- Satu posisi aktif pada satu waktu.

### 2) Struktur Layer (berdasarkan engine confluence)
- L1 (BCD): vote arah regime.
- L2 (EMA structure): vote tren struktural.
- L3 (MLP AI): vote confidence arah.
- L4 (volatility filter): multiplier risiko, bukan vote arah.

### 2.1) Detail Masing-Masing Layer

#### L1 (BCD): Vote Arah Regime
- Menggunakan Bidirectional Commodity Channel Index (BCD), sebagai vote arah regime.
- Efek dampak: dilakukan deteksi regime bull/bear, sehingga memungkinkan pengontrolan trading menurut arah regime.

#### L2 (EMA structure): Vote Trend Struktural
- Menggunakan Exponential Moving Average (EMA) pada harga, sebagai vote trend struktural.
- Efek dampak: memberikan prediksi trend dan memberikan kemampuan pada sistem untuk melakukan trade pada saat trend berubah.

#### L3 (MLP AI): Vote Confidence Arah
- Menggunakan Multi-Layer Perceptron (MLP) sebagai vote confidence arah.
- Efek dampak: memberikan kemampuan dalam memberikan keterangan kepercayaan sistem akan arah yang diberikan.

#### L4 (volatility filter): Multiplier Risiko
- Menggunakan volatility filter sebagai multiplier risiko.
- Efek dampak: memberikan kemampuan dalam memberikan risiko yang lebih besar atau lebih rendah terhadap trade tergantung pada volatility saat itu.


### 3) Agregasi Sinyal (Spectrum)
- Bobot vote: L1=0.30, L2=0.25, L3=0.45.
- Bias = (0.30*L1 + 0.25*L2 + 0.45*L3) x L4_multiplier.
- Gate:
  - ACTIVE jika |bias| >= 0.20
  - ADVISORY jika 0.10 <= |bias| < 0.20
  - SUSPENDED jika |bias| < 0.10

### 4) Aturan Entry/Exit
- Entry LONG/SHORT mengikuti arah regime + arah bias spektrum.
- Stop Loss dan Take Profit berbasis ATR dengan multiplier adaptif dari estimator volatilitas.
- Exit oleh salah satu kondisi: TP, SL, atau regime flip.

### 5) Catatan Interpretasi
- Walau win rate < 50%, sistem tetap profit karena average winner > average loser.
- Kontribusi ADVISORY negatif di periode ini, sehingga kualitas sinyal ACTIVE lebih baik.
- Regime neutral memberi expectancy negatif, perlu filter tambahan untuk menekan noise trade.

## Trade Plan (Operasional)

### A. Mode Eksekusi
- Default mode: eksekusi hanya saat gate ACTIVE.
- ADVISORY mode: opsional, maksimal 50% size dari ACTIVE atau skip total.

### B. Position Sizing
- Risk dasar: 2.0% equity per trade (sesuai profil backtest Full Layer).
- Saat drawdown > 20% dari equity peak: turunkan risk ke 1.0-1.25% sampai recovery.
- Hard stop harian: berhenti trading jika loss harian mencapai 3R.

### C. Filter Kualitas Setup
- Prioritaskan setup pada regime bull/bear; hindari neutral kecuali bias sangat kuat.
- Jika 3 loss beruntun: cooldown minimal 1 sesi (atau 1 hari) untuk reset.
- Jika volatilitas ekstrem (L4 multiplier rendah), skip sinyal walau arah benar.

### D. Manajemen Posisi
- Tetap gunakan SL/TP ATR adaptif (jangan dipersempit manual saat entry buruk).
- Dilarang averaging loser.
- Setelah equity membuat high baru pasca DD, sizing bisa kembali ke 2%.

### E. KPI Monitoring Mingguan
- Win rate rolling 50 trade
- Profit factor rolling 50 trade
- PnL ACTIVE vs ADVISORY
- Persentase trade pada regime neutral
- Max drawdown berjalan


## Peran Implementasi Ekonofisika (Asimetrik)

Implementasi sistem ini melampaui analisis teknikal tradisional dengan mengadopsi kerangka kerja **Ekonofisika**, yang memandang pasar sebagai sistem stokastik non-linear dengan distribusi return yang memiliki *fat-tails*. Fokus utama adalah pada pemodelan volatilitas dan kegigihan (*persistence*) regime secara asimetris untuk meningkatkan kualitas manajemen risiko.

### 1) Dinamika Volatilitas Stokastik (Model Heston) — Modul B
Sistem menggunakan pendekatan yang terinspirasi dari **Model Heston (1993)** untuk mengestimasi parameter volatilitas yang tidak konstan. Berbeda dengan indikator standar, sistem memodelkan variansi ($v_t$) sebagai proses *mean-reverting* melalui persamaan diferensial stokastik:

$$dv_t = -\gamma(v_t - \eta)dt + \kappa\sqrt{v_t} dW_t^v$$

Di mana:
- **$\gamma$ (Gamma)**: Kecepatan *mean-reversion*. Menentukan seberapa cepat pasar kembali ke level "tenang" setelah lonjakan volatilitas.
- **$\eta$ (Eta)**: *Long-run variance*. Merupakan level "volatilitas wajar" BTC dalam jangka panjang.
- **$\kappa$ (Kappa)**: *Vol-of-vol*. Mengukur volatilitas dari volatilitas itu sendiri (ketidakpastian lapis kedua).

**Dampak Operasional:**  
Sistem menghitung *half-life* volatilitas ($T_{1/2} = \ln(2) / \gamma$) untuk memprediksi durasi ketidakteraturan pasar. Jika volatilitas saat ini jauh di atas $\eta$ (Regime High Vol), sistem secara otomatis melonggarkan Stop Loss sebesar **2.0x ATR** untuk menghindari *noise*, sementara pada regime normal tetap pada **1.5x ATR**.

### 2) Matriks Transisi & Kegigihan Regime — Modul A
Pasar menunjukkan efek memori (*memory effect*) yang dimodelkan melalui **Matriks Transisi Markov** empiris:

$$P = \begin{pmatrix} p_{11} & p_{12} \\ p_{21} & p_{22} \end{pmatrix}$$

Di mana $p_{ij}$ adalah probabilitas transisi dari regime $i$ ke regime $j$. Sistem mengukur **Persistence Score** ($p_{ii}$):
- Jika $p_{ii} > 0.8$, sistem menganggap regime sangat stabil dan memperluas target Take Profit (TP2).
- Jika probabilitas transisi ke regime berlawanan meningkat, sistem mengaktifkan mekanisme *Soft Exit* lebih awal untuk mengamankan profit sebelum pembalikan arah total terjadi.

### 3) Analisis Distribusi Return Asimetrik — Modul C
Ekonofisika mengakui adanya asimetri risiko (pergerakan harga turun biasanya memiliki volatilitas lebih tinggi dibanding naik). Validasi ini memastikan sistem tetap memiliki **Expectancy positif** ($E > 0$) bahkan jika *Win Rate* secara statistik di bawah 50%:

$$E = (P_{win} \times \text{AvgWin}) - (P_{loss} \times \text{AvgLoss})$$

Hasil walk-forward menunjukkan bahwa integrasi filter volatilitas asimetris ini berhasil menjaga rasio **Avg Winner (+$749.83)** jauh lebih besar dibanding **Avg Loser (-$541.44)**, yang merupakan kunci utama profitabilitas jangka panjang sistem ini.

### 4) Status Integrasi vs Roadmap
- **Terimplementasi**: Estimasi parameter Heston secara *real-time*, perhitungan matriks transisi regime BCD, dan penyesuaian SL/TP berbasis profil risiko asimetris.
- **Optimalisasi Mendatang**: Penggunaan parameter $\rho$ (korelasi antara return harga dan perubahan variansi) untuk mendeteksi *crash* lebih dini, serta penguatan filter pada regime *neutral* yang saat ini masih memiliki *expectancy* negatif.



## Kesimpulan
- Full Layer memberikan hasil terbaik pada data yang diberikan: +597.89% dengan final equity USD 69,789.39.
- Penambahan Layer 2 sudah meningkatkan performa signifikan dibanding Layer 1; Layer penuh memberi tambahan edge lanjutan.
- Trade plan paling selaras dengan hasil ini adalah fokus pada gate ACTIVE, risk 2% adaptif, dan kontrol ketat saat fase drawdown.
