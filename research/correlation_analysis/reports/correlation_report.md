# Correlation Analysis Report: BTC vs Altcoins

**Periode:** Jan 2022 - Mar 2026 | **Data:** Binance OHLCV | **Timeframes:** 4H, 1D
**Pairs:** BTC, ETH, DOGE, LINK, SOL, BNB (semua vs USDT)

---

## 0. Glosarium & Cara Baca

Sebelum masuk ke temuan, berikut istilah-istilah kunci yang dipakai di seluruh laporan ini:

| Istilah | Artinya |
|---------|---------|
| **Korelasi (correlation)** | Ukuran seberapa mirip dua aset bergerak bersamaan. Nilainya -1 sampai +1. Nilai +1 berarti keduanya selalu bergerak searah sempurna. Nilai 0 berarti tidak ada hubungan. Nilai -1 berarti selalu bergerak berlawanan. |
| **Pearson correlation** | Mengukur hubungan **linear** antara dua variabel. Cocok jika data terdistribusi normal. Sensitif terhadap outlier (lonjakan harga ekstrem bisa membesar-besarkan hasil). |
| **Spearman correlation** | Mengukur hubungan berdasarkan **urutan/ranking**, bukan nilai mentah. Lebih tahan terhadap outlier. Jika Pearson dan Spearman memberikan angka mirip, artinya korelasi tersebut genuine, bukan efek samping dari beberapa lonjakan harga ekstrem. |
| **Returns (% perubahan)** | Persentase perubahan harga dari candle ke candle. Kita mengkorelasikan returns, **bukan harga mentah**, karena harga BTC ($85K) dan DOGE ($0.17) tidak sebanding skalanya. Returns menormalisasi ini. Jika kita korelasikan harga mentah, dua aset yang sama-sama naik terus akan terlihat berkorelasi meski sebenarnya tidak related (spurious correlation). |
| **Rolling correlation** | Korelasi yang dihitung ulang secara bergulir (misal: setiap 30 candle terakhir). Ini menunjukkan bagaimana korelasi **berubah seiring waktu**, tidak hanya satu angka rata-rata. |
| **Regime** | "Kondisi pasar" saat itu. Kita definisikan 3 regime berdasarkan Moving Average: Bull (harga di atas tren naik), Bear (harga di bawah tren turun), Sideways (tidak jelas naik/turun). |
| **SMA50 / SMA200** | Simple Moving Average 50 dan 200 periode. Rata-rata harga 50 hari terakhir dan 200 hari terakhir. Dipakai untuk menentukan regime. Jika SMA50 > SMA200 dan harga di atas keduanya = bull market. |
| **Volatility (volatilitas)** | Seberapa "liar" harga bergerak. Diukur dari standar deviasi returns. Volatilitas tinggi = harga naik-turun tajam. Volatilitas rendah = harga relatif tenang. |
| **Contagion effect** | Fenomena di mana saat satu aset jatuh, aset lain ikut jatuh bersamaan. Dalam crypto, saat BTC crash, hampir semua altcoin ikut jatuh -- korelasi meningkat karena panic selling massal. |
| **Lead/Lag** | Apakah aset A bergerak duluan (lead) sebelum aset B mengikuti (lag)? Jika ETH bergerak 2 jam sebelum BTC, maka ETH "leads" BTC. Ini potensi sinyal prediktif. |
| **Cross-Correlation Function (CCF)** | Teknik untuk mengukur korelasi pada berbagai time shift (lag). Kita geser data satu aset maju/mundur beberapa candle, lalu hitung korelasi di setiap posisi geser. Posisi geser dengan korelasi tertinggi menunjukkan siapa yang bergerak duluan. |
| **Granger causality** | Tes statistik formal yang menjawab: "Apakah mengetahui data historis X membantu memprediksi Y lebih baik daripada hanya pakai data historis Y saja?" Ini bukan berarti X menyebabkan Y, tapi X mengandung informasi prediktif tentang Y. |
| **p-value** | Ukuran kepercayaan statistik. p < 0.05 artinya "hasil ini kemungkinan besar bukan kebetulan" (signifikan secara statistik). p > 0.05 artinya "tidak cukup bukti untuk menyimpulkan ada efek nyata." |
| **Std (standar deviasi)** | Ukuran sebaran data. Std rendah = data konsisten/stabil. Std tinggi = data berfluktuasi besar. Dalam konteks rolling correlation, std rendah berarti korelasi antar aset stabil dari waktu ke waktu. |
| **Skewness** | Ukuran "kemiringan" distribusi returns. Skew positif = ada ekor panjang ke kanan (kadang ada lonjakan naik besar). Skew negatif = ada ekor ke kiri (kadang ada crash besar). |
| **Kurtosis** | Ukuran "ketebalan ekor" distribusi. Kurtosis tinggi (>3) = distribusi returns punya "fat tails", artinya pergerakan ekstrem (crash/pump besar) terjadi lebih sering daripada distribusi normal. DOGE punya kurtosis 18 -- artinya pump/dump DOGE jauh lebih sering terjadi dibanding aset lain. |

### Cara Membaca Angka Korelasi

```
0.00 - 0.20  : Sangat lemah (hampir tidak berhubungan)
0.20 - 0.40  : Lemah
0.40 - 0.60  : Moderate (cukup berhubungan)
0.60 - 0.80  : Kuat (bergerak searah cukup sering)
0.80 - 1.00  : Sangat kuat (hampir selalu bergerak searah)
```

Contoh konkret: BTC-ETH = 0.84 artinya **84% dari waktu, ketika BTC naik, ETH juga naik (dan sebaliknya)**. Ini bukan angka presisi matematis, tapi cara intuitif memahami skalanya.

---

## 1. Executive Summary

Riset ini mengukur korelasi harga BTC terhadap 5 altcoin utama untuk menentukan apakah pergerakan altcoin bisa digunakan sebagai fitur tambahan pada signal engine BTC-QUANT.

**Kesimpulan utama:**
- Semua altcoin berkorelasi positif kuat dengan BTC (0.68-0.84)
- **ETH adalah proxy BTC terbaik** -- korelasi tertinggi (0.84) dan paling stabil di semua regime
- **BTC adalah price leader** -- altcoin mengikuti BTC, bukan sebaliknya (Granger causality)
- Korelasi **meningkat saat bear market** dan **menurun saat bull market**
- **Tidak ditemukan leading indicator** yang reliable dari altcoin ke BTC

---

## 2. Static Correlation

> **Apa yang diukur:** Satu angka korelasi untuk **seluruh periode** 2022-2026. Ini memberikan gambaran besar, tapi menyembunyikan perubahan dari waktu ke waktu.

### Pearson Correlation vs BTC (4H)

| Pair | Pearson | Spearman | Ranking |
|------|---------|----------|---------|
| BTC-ETH | **0.842** | **0.817** | #1 |
| BTC-SOL | 0.737 | 0.730 | #2 |
| BTC-BNB | 0.720 | 0.707 | #3 |
| BTC-LINK | 0.716 | 0.694 | #4 |
| BTC-DOGE | 0.683 | 0.722 | #5 |

**Interpretasi:**
- **BTC-ETH (0.84):** Korelasi "sangat kuat". Ini expected karena ETH adalah altcoin terbesar dan sering disebut sebagai "beta" terhadap BTC. Artinya: jika BTC naik 1%, ETH cenderung naik juga (meski tidak selalu sebesar 1%).
- **BTC-DOGE (0.68):** Korelasi paling lemah di antara 5 pair, tapi masih tergolong "kuat". DOGE dipengaruhi oleh faktor non-market seperti tweet Elon Musk dan hype retail, sehingga kadang bergerak independen dari BTC.
- **Pearson vs Spearman mirip untuk semua pair** -- ini konfirmasi bahwa korelasi ini genuine dan bukan terdistorsi oleh beberapa event outlier (misal satu hari crash besar yang membuat angka terlihat tinggi padahal biasanya tidak).
- Semua pair > 0.68 menunjukkan crypto market secara keseluruhan sangat terhubung -- saat BTC bergerak, seluruh pasar cenderung ikut.

---

## 3. Rolling Correlation (Time-Varying)

> **Apa yang diukur:** Korelasi dihitung ulang setiap 30 candle (= sekitar 5 hari di 4H, 1 bulan di 1D). Ini menunjukkan kapan korelasi menguat dan kapan melemah.

Window 30-period rolling Pearson:

| Pair | Mean | Std | Min | Max |
|------|------|-----|-----|-----|
| BTC-ETH | 0.839 | 0.116 | 0.002 | 0.986 |
| BTC-SOL | 0.752 | 0.142 | 0.057 | 0.959 |
| BTC-DOGE | 0.732 | 0.157 | 0.087 | 0.969 |
| BTC-BNB | 0.728 | 0.164 | -0.188 | 0.966 |
| BTC-LINK | 0.722 | 0.177 | -0.167 | 0.975 |

**Interpretasi:**
- **ETH paling stabil** -- std 0.116 (paling kecil) berarti korelasi BTC-ETH jarang berubah drastis. Bandingkan dengan LINK (std 0.177) yang bisa berfluktuasi lebar. Untuk signal engine, kita butuh pair yang **konsisten**, bukan yang kadang berkorelasi tinggi kadang rendah.
- **Min BTC-ETH = 0.002:** Pernah ada momen di mana BTC dan ETH hampir tidak berkorelasi, tapi ini sangat jarang dan sesaat. Mean tetap 0.84.
- **Min BTC-BNB = -0.188 dan BTC-LINK = -0.167:** Pernah berkorelasi negatif (bergerak berlawanan). Ini terjadi pada momen-momen khusus (misal: ada berita spesifik tentang BNB/LINK yang tidak mempengaruhi BTC). Pair yang bisa negatif **kurang reliable** sebagai sinyal konfirmasi.

---

## 4. Conditional Correlation

> **Apa yang diukur:** Apakah korelasi berubah tergantung BTC sedang naik atau turun? Data dipecah berdasarkan arah pergerakan BTC, lalu korelasi dihitung terpisah per kondisi.

| Kondisi | N (4H) | BTC-ETH | BTC-SOL | BTC-BNB |
|---------|--------|---------|---------|---------|
| All | 9,294 | 0.842 | 0.737 | 0.720 |
| BTC Up | 4,737 | 0.730 | 0.600 | 0.554 |
| **BTC Down** | **4,557** | **0.790** | **0.636** | **0.670** |
| BTC Pump (>1std) | 924 | 0.642 | 0.581 | 0.515 |
| BTC Crash (<-1std) | 911 | 0.704 | 0.540 | 0.615 |

> **Catatan:** "BTC Pump (>1std)" artinya candle di mana BTC naik lebih dari 1 standar deviasi di atas rata-rata -- yaitu kenaikan yang luar biasa besar (~1% per 4H candle). "BTC Crash (<-1std)" kebalikannya. N = jumlah candle dalam kategori tersebut.

**Interpretasi:**
- **BTC Down (0.790) > BTC Up (0.730) untuk ETH** -- fenomena klasik yang disebut **contagion effect** atau "korelasi asimetris". Saat pasar jatuh, investor panik dan menjual semua aset bersamaan, sehingga semuanya jatuh bersamaan (korelasi naik). Saat pasar naik, setiap aset punya alasan naik yang berbeda-beda, jadi pergerakannya lebih independen (korelasi turun).
- **BTC Pump punya korelasi TERENDAH (0.642 untuk ETH)** -- ini insight penting. Saat BTC pump besar, altcoin tidak selalu ikut. Mungkin karena: (a) BTC pump bisa dipicu oleh berita BTC-specific (misal ETF approval) yang tidak relevan untuk altcoin, atau (b) saat BTC pump, investor justru pindah dari altcoin ke BTC ("BTC dominance naik").
- **Implikasi praktis:** Sinyal konfirmasi dari altcoin paling berguna saat market **turun** (korelasi tinggi, lebih predictable). Saat market pump besar, jangan terlalu rely pada konfirmasi altcoin.

---

## 5. Regime-Specific Correlation

> **Apa yang diukur:** Korelasi dipecah berdasarkan "kondisi pasar" (regime). Regime ditentukan oleh posisi harga relatif terhadap SMA50 dan SMA200:
> - **Bull:** Harga > SMA50 dan SMA50 > SMA200 (uptrend jelas)
> - **Bear:** Harga < SMA50 dan SMA50 < SMA200 (downtrend jelas)
> - **Sideways:** Sisanya (tidak jelas arahnya)

### MA Regime (SMA50/SMA200)

| Regime | % Waktu | BTC-ETH | BTC-LINK | BTC-SOL | BTC-BNB | BTC-DOGE |
|--------|---------|---------|----------|---------|---------|----------|
| **Bear** | 19% | **0.892** | **0.820** | **0.751** | **0.808** | **0.774** |
| Sideways | 48% | 0.866 | 0.756 | 0.776 | 0.760 | 0.687 |
| Bull | 33% | 0.761 | 0.598 | 0.655 | 0.595 | 0.649 |

**Interpretasi:**
- **Bear market = korelasi tertinggi untuk SEMUA pair.** Ini memperkuat temuan dari Section 4 (conditional correlation). Selama bear market 2022 (LUNA crash, FTX collapse), semua crypto turun bersamaan karena kepanikan massal. Pola ini konsisten dan bisa diandalkan.
- **Bull market = korelasi terendah.** Saat bull, setiap altcoin punya "narrative" sendiri (DeFi season untuk ETH, meme coin hype untuk DOGE, Solana ecosystem growth untuk SOL). Masing-masing bergerak berdasarkan faktor idiosinkratik-nya, bukan semata-mata mengikuti BTC.
- **Sideways paling sering (48% waktu)** -- hampir separuh dari 4 tahun data, pasar tidak jelas arahnya. Korelasi moderate (0.69-0.87). Ini "kondisi default" yang paling sering dihadapi bot.
- **Delta bear vs bull sangat besar untuk LINK (0.82 vs 0.60) dan BNB (0.81 vs 0.60)** -- artinya LINK dan BNB hanya reliable sebagai sinyal konfirmasi saat bear. Saat bull, korelasi mereka drop ~0.2 poin -- cukup besar untuk jadi misleading.

### Combined Regime (MA x Volatility)

> Menggabungkan dua dimensi: arah pasar (bull/bear/sideways) DAN tingkat volatilitas (high/low). Ini memberikan gambaran paling granular.

| Regime | BTC-ETH | BTC-LINK | BTC-SOL |
|--------|---------|----------|---------|
| **Bear + High Vol** | **0.893** | **0.827** | **0.803** |
| Bear + Low Vol | 0.886 | 0.795 | 0.637 |
| Sideways + High Vol | 0.879 | 0.797 | 0.802 |
| Sideways + Low Vol | 0.838 | 0.695 | 0.734 |
| Bull + High Vol | 0.786 | 0.596 | 0.714 |
| **Bull + Low Vol** | **0.736** | **0.600** | **0.616** |

**Interpretasi:**
- **Bear + High Vol (0.893 untuk ETH)** = skenario "panic mode". Harga turun DAN bergerak sangat liar. Dalam kondisi ini, semua orang jual bersamaan, dan korelasi antar aset mendekati maksimum. Ini momen di mana konfirmasi altcoin paling bisa diandalkan.
- **Bull + Low Vol (0.736 untuk ETH)** = skenario "steady grind up". Pasar naik pelan-pelan tanpa volatilitas besar. Dalam kondisi ini, setiap aset bergerak lebih independen. Konfirmasi altcoin kurang bermakna di sini.
- **ETH tetap di atas 0.73 bahkan di kondisi terburuk (bull + low vol)** -- ini yang membuat ETH unggul: konsisten di semua skenario. Bandingkan dengan LINK yang turun ke 0.60 dan SOL ke 0.62.

---

## 6. Lead/Lag Analysis

> **Apa yang diukur:** Apakah ada altcoin yang bergerak **duluan** sebelum BTC? Jika ya, pergerakan altcoin tersebut bisa dijadikan "early warning" untuk memprediksi BTC.

### Cross-Correlation Function (CCF)

> CCF bekerja dengan "menggeser" data satu aset maju/mundur beberapa candle, lalu mengukur korelasi di setiap posisi. Lag negatif = altcoin bergerak duluan. Lag positif = BTC bergerak duluan. Lag 0 = bersamaan.

| Pair | Peak Lag (4H) | Peak Lag (1D) | Arti |
|------|--------------|--------------|------|
| ETH->BTC | -10 | -3 | ETH leads 10 candle (4H) / 3 hari (1D) |
| DOGE->BTC | -9 | -12 | DOGE leads |
| LINK->BTC | -11 | -11 | LINK leads |
| SOL->BTC | 0 | 0 | Bergerak bersamaan |
| BNB->BTC | -11 | -1 | BNB leads |

**TAPI -- ini bukan temuan yang actionable.** Berikut penjelasannya:

Jika kita lihat grafik CCF, korelasi di **setiap lag hampir sama tingginya**. Contoh BTC-ETH: korelasi di lag 0 = 0.8424, di lag -10 = 0.8425. Selisihnya hanya **0.0001** -- secara praktis tidak ada bedanya. Ini artinya CCF "flat", bukan ada puncak yang jelas. Peak lag -10 bukan berarti ETH benar-benar bergerak 10 candle lebih dulu dengan sinyal kuat -- ini hanya noise statistik.

**Kenapa CCF flat?** Karena korelasi antara BTC dan altcoin bersifat **contemporaneous** (terjadi di waktu yang sama), bukan lagged. Kedua aset bereaksi terhadap informasi yang sama hampir secara instan.

### Granger Causality (4H, p<0.05)

> Granger Causality bertanya: "Jika saya sudah tahu data historis BTC, apakah menambahkan data historis ETH membuat prediksi saya tentang BTC jadi lebih akurat?" Jika ya, maka ETH "Granger-causes" BTC. **Penting:** ini bukan causality sejati (ETH tidak "menyebabkan" BTC bergerak), tapi menunjukkan informasi prediktif.

| Direction | ETH | DOGE | LINK | SOL | BNB |
|-----------|-----|------|------|-----|-----|
| Alt -> BTC | no | no | no | no | no |
| **BTC -> Alt** | no | no | **YES** (p=0.002) | **YES** (p=0.004) | **YES** (p=0.010) |

**Interpretasi:**
- **Baris atas (Alt -> BTC): Semua "no"** -- Tidak ada satu pun altcoin yang secara statistik signifikan membantu memprediksi pergerakan BTC. Artinya: melihat data historis ETH/DOGE/SOL/dll **tidak memberikan informasi tambahan** untuk memprediksi ke mana BTC akan bergerak selanjutnya.
- **Baris bawah (BTC -> Alt): LINK, SOL, BNB "YES"** -- Sebaliknya, data historis BTC **membantu memprediksi** LINK (p=0.002), SOL (p=0.004), dan BNB (p=0.010). Ini konfirmasi bahwa **BTC adalah price leader** di pasar crypto. BTC bergerak duluan, altcoin mengikuti.
- **ETH dan DOGE "no" di kedua arah** -- ETH bergerak terlalu bersamaan dengan BTC (hampir simultan) sehingga tidak ada lag yang cukup untuk Granger causality. DOGE terlalu dipengaruhi faktor external (social media hype) yang tidak terkait BTC.

**Kesimpulan lead/lag:** Harapan awal bahwa altcoin bisa menjadi "early warning" untuk BTC **tidak terbukti**. BTC-lah yang memimpin pasar.

---

## 7. Rekomendasi untuk Signal Engine

### 7a. Pair yang paling berguna

1. **ETH** -- korelasi tertinggi (0.84), paling stabil (std 0.116), konsisten di semua regime (min 0.73 bahkan di bull+low vol). Wajib dipakai sebagai confirmation signal.
2. **SOL** -- korelasi #2 (0.74), bergerak simultan dengan BTC (lag=0). Bisa jadi secondary confirmation.
3. BNB, LINK, DOGE -- berguna tapi kurang stabil, terutama saat bull market (korelasi drop ke ~0.60).

### 7b. Fitur yang direkomendasikan

| Fitur | Deskripsi | Kenapa | Prioritas |
|-------|-----------|--------|-----------|
| **Correlation Filter** | Hanya ambil sinyal BTC jika ETH bergerak searah | ETH punya korelasi 0.84 -- jika ETH tidak konfirmasi, kemungkinan sinyal BTC adalah noise | Tinggi |
| **Regime-Aware Weight** | Bobot konfirmasi: bear=1.0, sideways=0.7, bull=0.4 | Korelasi bear 0.89 vs bull 0.76 -- di bear, konfirmasi altcoin jauh lebih reliable | Tinggi |
| **Divergence Alert** | Jika BTC & ETH diverge (korelasi rolling < 0.5) = warning | Rolling correlation BTC-ETH biasanya > 0.7. Jika turun < 0.5, ada sesuatu yang abnormal di pasar (mungkin event spesifik ETH/BTC). Saat diverge, model korelasi jadi tidak reliable -- lebih baik pause | Medium |
| ~~Leading Indicator~~ | ~~Altcoin sebagai predictor BTC~~ | ~~CCF flat, Granger causality semua non-signifikan. Tidak ada bukti~~ | ~~Ditolak~~ |

### 7c. Implementasi yang disarankan

```python
# Pseudo-code untuk Correlation Filter
def should_take_signal(btc_signal, eth_return, regime):
    # 1. Cek apakah ETH konfirmasi arah BTC
    #    Jika sinyal BTC = long, ETH harus juga sedang naik (return > 0)
    #    Jika sinyal BTC = short, ETH harus juga sedang turun (return < 0)
    eth_confirms = (btc_signal == "long" and eth_return > 0) or \
                   (btc_signal == "short" and eth_return < 0)

    # 2. Adjust confidence berdasarkan regime
    #    Bear: korelasi 0.89 -> bobot penuh, konfirmasi sangat bermakna
    #    Sideways: korelasi 0.87 -> bobot masih tinggi
    #    Bull: korelasi 0.76 -> bobot rendah, konfirmasi kurang bermakna
    regime_weight = {"bear": 1.0, "sideways": 0.7, "bull": 0.4}
    confidence = regime_weight[regime] if eth_confirms else 0.0

    # 3. Threshold: hanya ambil sinyal jika confidence > 0.5
    #    Artinya: di bull market, bahkan jika ETH konfirmasi (0.4),
    #    kita tetap TIDAK ambil sinyal -- karena korelasi terlalu rendah
    return confidence > 0.5
```

### 7d. Yang TIDAK perlu dilakukan

- **Jangan pakai altcoin sebagai leading indicator** -- CCF flat dan Granger causality non-signifikan. Tidak ada bukti statistik bahwa altcoin bergerak duluan.
- **Jangan pakai DOGE untuk konfirmasi** -- korelasi terendah (0.68), paling volatile (std 0.157), dan dipengaruhi faktor non-market (social media hype) yang membuat perilakunya unpredictable.
- **Jangan rely on korelasi saat bull market** -- korelasi turun signifikan (dari 0.89 ke 0.76 untuk ETH, dari 0.82 ke 0.60 untuk LINK). Sinyal konfirmasi jadi misleading.
- **Jangan asumsikan korelasi konstan** -- rolling correlation menunjukkan korelasi bisa drop mendekati 0 untuk waktu singkat. Selalu monitor korelasi real-time, jangan hardcode angka.

---

## 8. Deliverables

| # | File | Deskripsi |
|---|------|-----------|
| 1 | `scripts/01_fetch_data.py` | Data collection dari Binance |
| 2 | `scripts/02_preprocess.py` | Align, clean, hitung returns |
| 3 | `scripts/03_eda.py` | EDA: normalized prices, distributions, volatility, heatmap |
| 4 | `scripts/04_correlation.py` | Rolling & conditional correlation |
| 5 | `scripts/05_regime_detection.py` | MA & volatility regime detection |
| 6 | `scripts/06_regime_correlation.py` | Regime-specific correlation analysis |
| 7 | `scripts/07_lead_lag.py` | CCF & Granger causality |
| 8 | `reports/correlation_report.md` | Laporan ini |

### Visualisasi yang dihasilkan (di `reports/`)

| File | Konten |
|------|--------|
| `01_normalized_prices_{4h,1d}.png` | Semua aset dinormalisasi ke base 100 di awal periode. Memudahkan perbandingan performa relatif meski harga aslinya berbeda jauh. |
| `02_returns_distribution_{4h,1d}.png` | Histogram bentuk distribusi returns tiap aset. Menunjukkan apakah distribusi simetris, fat-tailed, atau skewed. |
| `03_rolling_volatility_{4h,1d}.png` | Volatilitas bergulir (annualized) tiap aset. Menunjukkan kapan pasar tenang vs liar. |
| `04_correlation_heatmap_{4h,1d}.png` | Matriks korelasi Pearson & Spearman semua pair. Snapshot "siapa mirip siapa". |
| `05_rolling_correlation_{4h,1d}.png` | Korelasi BTC vs tiap altcoin yang berubah seiring waktu (window 30/60/90). |
| `06_conditional_correlation_{4h,1d}.png` | Korelasi dipecah per kondisi: BTC naik, turun, pump, crash. |
| `07_ma_regime_{4h,1d}.png` | Overlay regime (warna hijau/merah/kuning) di atas harga BTC. |
| `08_vol_regime_{4h,1d}.png` | Rolling volatility + pembagian high/low vol regime. |
| `09_ma_regime_correlation_{4h,1d}.png` | Bar chart korelasi per regime (bull/bear/sideways). |
| `10_vol_regime_correlation_{4h,1d}.png` | Bar chart korelasi per volatility regime. |
| `11_combined_regime_heatmap_{4h,1d}.png` | Heatmap korelasi untuk setiap kombinasi MA regime x Vol regime (6 skenario). |
| `12_ccf_{4h,1d}.png` | Cross-correlation function: korelasi di berbagai lag. |
| `13_granger_{4h,1d}.png` | Hasil Granger causality test (-log10 p-value). Bar melewati garis merah = signifikan. |
