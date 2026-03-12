# 📊 Riset: Trailing Stop vs Fixed SL/TP & Kelly Criterion vs Heston

**Tanggal:** 3 Maret 2026  
**Konteks:** BTC-QUANT Scalping Platform  
**Tujuan:** Evaluasi apakah trailing stop dan Kelly Criterion lebih optimal daripada sistem saat ini

---

## Bagian 1: Trailing Stop vs Fixed SL/TP

### 1.1 Cara Kerja Sistem SL/TP Saat Ini

Sistem saat ini menggunakan **Fixed SL/TP berbasis ATR** dengan multiplier adaptif dari Model Heston:

```
SL  = Price ± (ATR14 × sl_multiplier)
TP1 = Price ± (ATR14 × tp1_multiplier)
TP2 = Price ± (ATR14 × tp2_multiplier)
```

Multiplier ditentukan oleh gabungan dua modul:

| Komponen | Sumber | Fungsi |
|---|---|---|
| **Vol Regime** | Modul B: Heston `dv = -γ(v-η)dt + κ√v·dBv` | Klasifikasi: High / Normal / Low |
| **Halflife** | `T½ = ln(2) / γ` | Perkiraan kapan vol kembali normal |
| **Bias Score** | Modul A: Matriks Transisi Markov | Persistence rejim saat ini |

**4 Preset SL/TP yang Aktif:**

| Preset | Kondisi | SL× | TP1× | TP2× | Reward/Risk |
|---|---|---|---|---|---|
| HV-Fast-Revert | Vol tinggi, halflife < 15 | 2.2 | 0.8 | 1.2 | **0.36** |
| HV-Slow-Persist | Vol tinggi, halflife ≥ 15 | 2.0 | 1.0 | 1.5 | **0.50** |
| LV-Trend | Vol rendah | 1.2 | 1.2 | 1.8 | **1.00** |
| Normal | Default | 1.5 | 1.0 | 1.5 | **0.67** |

### 1.2 Apa Itu Trailing Stop?

Trailing stop adalah SL yang **bergerak mengikuti harga** saat posisi profitabel:

```
Trailing Stop Logic:
  IF side = LONG:
    trailing_sl = max(trailing_sl, highest_high - trail_distance)
  IF side = SHORT:
    trailing_sl = min(trailing_sl, lowest_low + trail_distance)
```

**Jenis trailing stop:**

| Tipe | Trail Distance | Cocok Untuk |
|---|---|---|
| **ATR Trailing** | N × ATR14 | Adaptif terhadap volatilitas |
| **Percentage** | N% dari harga | Sederhana tapi tidak adaptif |
| **Chandelier Exit** | 3 × ATR dari highest high | Classic trend-following |
| **Parabolic SAR** | Akselerasi progresif | Trend kuat |

### 1.3 Analisis: Cocokkan untuk BTC Scalping 4H?

#### ✅ Kelebihan Trailing Stop

1. **Menangkap pergerakan besar (fat tails).**
   BTC sering bergerak 5-10% dalam sehari saat trending. Fixed TP di 2× ATR (~2.6%) menutup posisi terlalu cepat. Trailing stop membiarkan profit berjalan.

2. **Eliminasi TP ceiling.**
   Dari data walk-forward, TP hit rate = 100% (semua TP tercapai dan langsung close). Ini berarti kita **never catch the full move** — trailing stop memungkinkan kita menangkap lebih dari 2× ATR saat trend kuat.

3. **Natural fit dengan BCD regime.**
   BCD regime bertahan 131+ candle (~22 hari) rata-rata. Dengan trailing stop, kita bisa ride seluruh regime Bullish/Bearish tanpa TP ceiling, dan trail SL mengunci profit secara progresif.

#### ⚠️ Kelemahan Trailing Stop

1. **Whipsaw di sideways.**
   BTC sering menunjukkan volatilitas tinggi + directionality rendah (High Volatility Sideways). Trailing stop akan sering ter-trigger oleh noise → lebih banyak losers.

2. **Kualitas exit terdegradasi.**
   Fixed TP memberi kontrol presisi atas reward/risk ratio. Trailing stop rata-rata menghasilkan exit di titik yang suboptimal (terlalu dekat saat trailing ketat, terlalu jauh saat trailing longgar).

3. **Lebih kompleks untuk backtest.**
   Trailing stop membutuhkan data intra-candle (high/low per candle minimum), bukan hanya close. Ini sudah tersedia di OHLCV kita, tapi simulasinya lebih rawan bias (tidak tahu mana yang terjadi duluan: high atau low).

### 1.4 Rekomendasi: Hybrid Approach

**Gunakan keduanya — Fixed SL + Trailing TP:**

```
ENTRY:
  SL = Fixed (1.5× ATR) → melindungi dari kerugian besar
  TP1 = Fixed (2.0× ATR) → take partial profit (50% posisi)

SETELAH TP1 HIT:
  SL yang tersisa → diubah ke Trailing Stop (1.0× ATR dari highest high)
  Sisa 50% posisi → biarkan berjalan sampai trailing stop ter-trigger
  ATAU sampai regime flip dari BCD
```

**Kenapa hybrid?**
- Fixed SL melindungi downside → kritis untuk leverage trading
- Fixed TP1 mengamankan profit minimum → memenuhi target per candle
- Trailing TP2 menangkap fat tails → bonus dari trending market
- BCD regime flip sebagai "macro trailing stop" → jangan long saat bearish dimulai

**Estimasi dampak (berdasarkan data walk-forward):**
- 213 trade TP di 2025-2026 mencapai TP1. Jika 50% posisi trail, dan BTC bergerak rata-rata 1.5× tambahan setelah TP1, maka:
  - Extra profit = 213 × 50% × 1.5 × avg_tp_pnl = +~167% tambahan
  - Daily return bisa naik dari +0.759% ke **~1.1-1.5%/day** di 1× leverage

---

## Bagian 2: Kelly Criterion vs Heston Position Sizing

### 2.1 Apa Itu Kelly Criterion?

Kelly Criterion adalah formula matematis yang menentukan **ukuran taruhan optimal** untuk memaksimalkan pertumbuhan modal jangka panjang.

**Formula dasar (binary outcome):**

```
f* = (b × p - q) / b

Di mana:
  f* = fraksi modal optimal untuk ditaruhkan
  b  = odds (rasio win/loss dalam ukuran, bukan frekuensi)
  p  = probabilitas menang
  q  = 1 - p = probabilitas kalah
```

**Contoh dari data kita (2025-2026):**

```
p = 0.645 (win rate 64.5%)
q = 0.355
b = avg_win / avg_loss = 2.569 / 2.052 = 1.252

f* = (1.252 × 0.645 - 0.355) / 1.252
f* = (0.808 - 0.355) / 1.252
f* = 0.362 → 36.2% modal per trade
```

### 2.2 Cara Kerja Position Sizing Saat Ini

Sistem saat ini menggunakan **Target ROE approach** (Module F di signal_service.py):

```python
TARGET_ROE = 0.04  # Target 4% return per trade

leverage = TARGET_ROE / (tp1_multiplier × vol_ratio)
leverage = clamp(leverage, 1, 20)

position_size = balance × (risk_pct / 100) × leverage
# risk_pct dari DirectionalSpectrum (5-15% base)
```

**Ini BUKAN Kelly Criterion**, tapi pendekatan "target return" yang kebalikannya:
- Kelly: "Berapa besar saya harus taruhkan berdasarkan edge saya?"
- Target ROE: "Berapa leverage yang saya butuhkan untuk mencapai return tertentu?"

### 2.3 Perbandingan Head-to-Head

| Aspek | Kelly Criterion | Sistem Heston Saat Ini |
|---|---|---|
| **Input** | Win rate + reward/risk ratio | Volatilitas regime + halflife + bias |
| **Output** | Fraksi modal (%) | SL/TP multiplier + leverage |
| **Adaptif terhadap** | Perubahan edge statistik | Perubahan kondisi volatilitas |
| **Asumsi** | Distribusi stabil, IID trades | Vol berubah (stochastic vol) |
| **Kekuatan** | Optimal secara matematis (MPT) | Adaptif terhadap market microstructure |
| **Kelemahan** | Tidak memperhitungkan vol clustering | Tidak memakai edge statistik langsung |
| **Risiko utama** | Over-betting jika edge terdegradasi | Under/over-leveraging jika Heston mis-estimate |

### 2.4 Analisis Mendalam

#### Kelly: Kekuatan
1. **Mathematically optimal** — Kelly memaksimalkan geometric growth rate. Ini terbukti secara teoritis (Shannon, 1956; Thorp, 1969).
2. **Self-correcting** — jika edge menurun (WR turun), Kelly otomatis mengurangi ukuran posisi.
3. **Tidak perlu model volatilitas** — hanya butuh historical win rate dan reward/risk ratio.

#### Kelly: Kelemahan untuk BTC Scalping
1. **Asumsi IID dilanggar.** Kelly mengasumsikan setiap trade independen. Tapi BTC regime membuat trade-trade berurutan sangat berkorelasi. Saat Bullish, semua LONG menang. Saat Bearish flip, semua LONG kalah bersamaan. Kelly pure akan over-bet di akhir regime.

2. **Full Kelly terlalu agresif.** f* = 36.2% artinya mempertaruhkan 36% modal per trade. Satu losing streak 5 trade = -82% drawdown. **Dalam praktik, bahkan hedge fund hanya menggunakan ½ Kelly atau ¼ Kelly.**

3. **Distribusi BTC bukan Gaussian.** BTC punya fat tails (kurtosis ~20-50). Kelly standar mengasumsikan distribusi normal. Fat tails membuat drawdown jauh lebih buruk daripada prediksi Kelly.

#### Heston: Kekuatan
1. **Mengerti bahwa volatilitas berubah.** Model Heston secara eksplisit memodelkan `dv = -γ(v-η)dt + κ√v·dBv`. Ini benar — vol BTC memang stokastik dan mean-reverting.
2. **SL/TP adaptif.** Saat vol tinggi, SL lebih lebar (menghindari noise). Saat vol rendah, SL lebih ketat. Ini secara implisit memproteksi dari regime volatilitas yang buruk.
3. **Halflife memberikan informasi temporal.** Kelly tidak tahu kapan vol akan berubah. Heston memprediksi "vol akan kembali normal dalam ~X candle".

#### Heston: Kelemahan
1. **Tidak menghitung edge.** Heston menentukan SL/TP berdasarkan kondisi vol, tapi **tidak memperhitungkan win rate atau reward/risk** dalam position sizing.
2. **Leverage formula terlalu sederhana.** `leverage = TARGET_ROE / (tp1 × vol_ratio)` tidak mempertimbangkan distribusi return yang sebenarnya.
3. **Tidak ada mekanisme auto-reduce.** Jika strategy edge menurun (WR turun dari 64% ke 50%), Heston tetap memberikan multiplier yang sama selama vol regime tidak berubah.

### 2.5 Rekomendasi: Kelly-Heston Hybrid

**Optimal approach = kombinasi keduanya:**

```
STEP 1 — Heston menentukan SL/TP (SUDAH ADA)
  → SL/TP multiplier adaptif terhadap volatilitas regime
  → Ini menentukan "berapa risiko per unit trade" (fixed dollar risk)

STEP 2 — Kelly menentukan POSITION SIZE (BELUM ADA)
  → Hitung rolling Kelly fraction dari 50-trade window terakhir
  → Gunakan ½ Kelly (half-Kelly) untuk keamanan
  → Input: recent win rate + recent avg_win/avg_loss ratio

STEP 3 — Heston OVERRIDE Kelly saat extreme
  → Jika vol_regime = "High" → cap Kelly di ¼ Kelly
  → Jika halflife < 5 → reduce Kelly 50% (vol akan swing keras)
```

**Formula position sizing yang direkomendasikan:**

```python
# Rolling Kelly dari 50 trade terakhir
rolling_wr = wins / total  # dari paper trading history
rolling_b  = avg_win / avg_loss
kelly_f = (rolling_b * rolling_wr - (1 - rolling_wr)) / rolling_b

# Safety: gunakan Half-Kelly, minimum 1%, maximum 15%
safe_f = max(0.01, min(0.15, kelly_f * 0.5))

# Vol regime override
if vol_regime == "High":
    safe_f *= 0.5  # Quarter Kelly di high vol
if halflife < 5:
    safe_f *= 0.75  # Reduce saat vol akan swing

position_size_pct = safe_f * 100  # → dikirim ke API response
```

### 2.6 Kesimpulan Perbandingan

| Pertanyaan | Jawaban |
|---|---|
| **Mana yang lebih adaptif?** | **Heston**, karena memodelkan perubahan volatilitas secara eksplisit. Kelly hanya melihat historical outcomes. |
| **Mana yang lebih optimal secara matematis?** | **Kelly**, karena memaksimalkan geometric growth rate. Tapi hanya jika asumsi IID terpenuhi (dan untuk BTC, tidak terpenuhi). |
| **Mana yang lebih aman?** | **Heston**, karena SL/TP adaptif mencegah kerugian besar saat vol spike. Kelly pure bisa sangat agresif. |
| **Mana yang harus dipakai?** | **Keduanya (hybrid)**. Heston untuk SL/TP + risk per trade. Kelly untuk position sizing. |

---

## Ringkasan Rekomendasi

### Prioritas Implementasi

| # | Rekomendasi | Impact | Effort |
|---|---|---|---|
| 1 | **Naikkan TP1 ke ≥ 1.5× ATR** di semua preset | HIGH | LOW |
| 2 | **Tambahkan Trailing TP** setelah TP1 hit (partial close) | HIGH | MEDIUM |
| 3 | **Implementasi Half-Kelly** position sizing | MEDIUM | LOW |
| 4 | Heston override Kelly di extreme vol | MEDIUM | LOW |

### Estimasi Dampak Gabungan

```
Baseline (sistem saat ini, 1× leverage):
  Daily return = +0.782%

Setelah TP1 naik + Trailing TP:
  Daily return = ~+1.1-1.5%

Setelah + Half-Kelly position sizing:
  Lebih konsisten, drawdown lebih kecil
  Compound growth rate optimal

Target 3%/hari di 5× leverage:
  1.1% × 5 = 5.5% → MELAMPAUI TARGET ✅
```

---

## Bagian 3: Justifikasi Prioritas — Mana yang Benar-Benar Perlu?

### Penilaian Jujur Per Rekomendasi

#### ✅ #1: Naikkan TP1 ke ≥ 1.5× ATR — **WAJIB, dampak terbesar**

**Kenapa sangat disarankan:**
- Ini bukan optimasi — ini **bug fix**. Preset saat ini punya TP1 = 0.8× ATR (HV-Fast-Revert) dan 1.0× ATR (Normal). Reward/risk ratio-nya cuma 0.36–0.67. Artinya kamu harus menang **73% trade di HV** hanya untuk breakeven. Itu tidak realistis.
- Walk-forward sudah **membuktikan** bahwa TP 2.0× / SL 1.5× menghasilkan 64.7% WR dan PF 2.26. Ini data, bukan teori.
- Effort-nya sangat rendah — cukup ubah 4 angka di `get_sl_tp_multipliers()`.

**Risiko jika tidak dilakukan:**
- Profit per trade terlalu kecil → butuh WR sangat tinggi yang unrealistic
- Sistem sudah punya edge 64.7% tapi reward/risk ratio saat ini **menggerus edge tersebut**

> **Verdict: HARUS dilakukan. Ini item paling kritis.**

---

#### 🤔 #2: Trailing TP setelah TP1 — **BAGUS tapi BISA DITUNDA**

**Kenapa disarankan:**
- Secara teori, trailing TP menangkap fat tails → return lebih tinggi saat trending
- Dari data: 213 TP hit, semua close di TP1. Kita tidak tahu berapa banyak yang sebenarnya terus bergerak setelah TP1

**Kenapa bisa ditunda / mungkin tidak perlu:**
- **Belum ada data** berapa banyak trade yang punya sisa move besar setelah TP1. Estimasi "+167% tambahan" itu asumsi kasar, bukan data.
- Trailing TP memperkenalkan **kompleksitas baru** yang harus di-backtest ulang secara menyeluruh
- Sistem 4H timeframe = **1 candle per 4 jam**. Trailing stop di 4H kurang presisi — harga bisa bergerak jauh dalam 1 candle sebelum trail ter-update
- **Partial close** (50% di TP1, sisanya trail) membutuhkan perubahan di `paper_trade_service.py` yang tidak trivial — logic posisi harus support split

**Yang perlu divalidasi dulu:**
- Backtest: berapa % trade yang punya move > 2× ATR setelah TP1 hit?
- Jika < 30%, trailing TP hampir tidak memberi tambahan — cost implementasinya tidak worth it

> **Verdict: NICE TO HAVE. Tunda sampai #1 sudah jalan dan tervalidasi. Bisa jadi tidak perlu jika data menunjukkan mayoritas trade memang optimal di 2× ATR.**

---

#### 🤔 #3: Half-Kelly Position Sizing — **BERGUNA tapi BELUM MENDESAK**

**Kenapa disarankan:**
- Kelly menambahkan dimensi yang saat ini **tidak ada**: position sizing berdasarkan actual edge
- Sistem saat ini menggunakan `TARGET_ROE = 0.04` yang statis — tidak peduli apakah strategi sedang dalam winning streak atau losing streak
- Kelly secara otomatis mengurangi ukuran posisi saat edge menurun → perlindungan alami

**Kenapa mungkin belum perlu sekarang:**
- **Kelly butuh data trade history** yang cukup (minimum 50 trade). Kalau paper trading baru jalan, belum ada data. Kelly dengan data sedikit = unreliable.
- **Sistem Heston sudah cukup aman** untuk tahap ini. SL adaptif + leverage cap 20× sudah memberikan perlindungan basic.
- Kelly paling berguna saat **scaling up ke real money** — di tahap paper trading / validasi, position sizing exact belum kritis.
- Bahaya utama Kelly: jika dihitung dari data in-sample yang bias, bisa menghasilkan over-betting. Perlu walk-forward Kelly juga.

**Kapan harus diimplementasi:**
- Setelah paper trading mengumpulkan ≥50 trade
- Sebelum transisi ke live trading dengan uang sungguhan

> **Verdict: BERGUNA NANTI. Implementasi setelah paper trading berjalan cukup lama. Bukan prioritas sekarang.**

---

#### ⬜ #4: Heston Override Kelly di Extreme Vol — **TIDAK PERLU SEKARANG**

**Kenapa disarankan awalnya:**
- Mencegah Kelly over-bet saat vol spike

**Kenapa sebenarnya tidak urgent:**
- Ini **tergantung #3** (Kelly). Kalau Kelly belum diimplementasi, override-nya juga tidak perlu.
- Heston SL/TP adaptif **sudah secara implisit** melakukan ini — SL lebih lebar di high vol = risiko per trade sudah dikurangi otomatis.
- Ini lebih ke "belt and suspenders" — asuransi tambahan yang baik punya tapi bukan kebutuhan.

> **Verdict: SKIP untuk sekarang. Implementasi otomatis bersamaan dengan #3 jika/saat Kelly diimplementasi.**

---

### Ringkasan Prioritas yang Sudah Direvisi

| # | Rekomendasi | Status | Alasan |
|---|---|---|---|
| 1 | **Naikkan TP1 ke ≥ 1.5×** | 🔴 **WAJIB** | Bug fix, bukan fitur baru. Data walk-forward sudah membuktikan |
| 2 | Trailing TP | 🟡 Tunda | Butuh data dulu. Kompleksitas tinggi, benefit belum terukur |
| 3 | Half-Kelly | 🟡 Nanti | Butuh 50+ trade history. Berguna saat scale ke live |
| 4 | Heston override Kelly | ⚪ Skip | Depends on #3, dan Heston sudah cover secara implisit |

**Kesimpulan: Yang benar-benar perlu dikerjakan sekarang cuma #1.** Sisanya bisa ditambahkan bertahap setelah sistem berjalan dan ada data real.

---

*Dokumen ini akan diupdate setelah implementasi dan backtest.*
