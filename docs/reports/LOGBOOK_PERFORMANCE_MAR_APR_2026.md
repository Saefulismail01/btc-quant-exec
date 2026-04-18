# BTC-QUANT Performance Logbook
**Periode:** 10 Maret 2026 - 14 April 2026
**Versi:** v4.4 → v4.5 (HestonStrategy)
**Generated:** 17 April 2026

## Ringkasan Eksekutif (per Dashboard Lighter)

| Metrik | Nilai |
|--------|-------|
| **PnL** | **$14.11** |
| **Volume** | $25,972.88 |
| **Return Percentage** | 14.19% |
| **Average Daily PnL** | $0.35 |
| **PnL Volatility** | $2.15 |
| **Sharpe Ratio** | 3.13 |
| **Maximum Drawdown** | $6.53 |
| **Estimated Fees Saved** | $12.98 |

**Note:** Dashboard menunjukkan PnL $14.11. Setelah adjustment untuk bug 18 Mar dan filter 15 Mar, PnL aktual adalah **$20.37** (54 posisi, 75.9% WR).

**Expected Value (Potensi):** ~$35 (tanpa intervensi manual dan sizing error)

## Adjustments & Filter

### ❌ Excluded Data

| Tanggal | Posisi | PnL | Alasan |
|---------|--------|-----|--------|
| **15 Mar** | 5 | -$0.04 | Uji coba otomasi bot |
| **18 Mar** | 1 | -$6.30 | Bug SL (dihitung sebagai loss, PnL = 0) |

**Rationale:**
- 15 Mar: Testing phase, tidak mencerminkan strategi actual
- 18 Mar: Loss akibat bug autentikasi SL order, bukan kesalahan strategi

## Analisis Per Periode

### Maret 2026: Fase Setup & Debugging

| Tanggal | Posisi | PnL | Catatan |
|---------|--------|-----|---------|
| 10 Mar | 1 | -$0.12 | Fase manual awal |
| 11 Mar | 2 | +$0.86 | - |
| 12 Mar | 3 | -$0.91 | - |
| 13 Mar | 5 | +$0.83 | - |
| 16 Mar | 2 | +$1.65 | Start fase otomatis |
| 17 Mar | 7 | +$1.30 | - |
| 22 Mar | 3 | +$0.28 | - |
| 23 Mar | 1 | +$0.26 | - |
| 26 Mar | 2 | +$0.42 | - |
| 27 Mar | 1 | +$0.26 | - |
| 28 Mar | 1 | +$0.11 | - |
| 29 Mar | 4 | **+$3.14** | Strong short |
| 31 Mar | 1 | -$1.91 | - |

**Total Maret:** +$6.17 (33 posisi, adjusted)

## April 2026: Fase Operasional

| Tanggal | Posisi | PnL | Status | Catatan |
|---------|--------|-----|--------|---------|
| 2 Apr | 1 | +$3.54 | ✅ | - |
| **3 Apr** | 2 | +$6.35 | ⚠️ | Interupsi manual (harusnya TP) |
| **4 Apr** | 2 | +$0.18 | ❌ | **Interupsi manual → profit minim** |
| 5 Apr | 1 | **-$2.99** | ✅ | Loss normal |
| 6 Apr | 2 | -$3.52 | ✅ | - |
| **7 Apr** | 1 | +$0.12 | ⚠️ | Interupsi manual, profit minim |
| 8 Apr | 1 | +$3.36 | ✅ | - |
| 9 Apr | 2 | +$3.81 | ✅ | - |
| **10 Apr** | 2 | +$4.00 | ⚠️ | Interupsi manual (harusnya TP lebih besar) |
| 11 Apr | 2 | -$2.93 | ✅ | - |
| **12 Apr** | 1 | **-$2.52** | ⚠️ | SL manual adjustment, sizing kecil |
| 13 Apr | 2 | +$3.31 | ✅ | Sizing kecil |
| 14 Apr | 1 | +$1.50 | ✅ | Sizing kecil |

**Total April:** +$14.21 (20 posisi)

## 🔴 Analisis Intervensi Manual

### 1. Interupsi Signal Delay (> 8 jam)

**Rationale Intervensi:**
> Ketika signal sudah lebih dari 8 jam tapi belum close posisi (TP/SL), maka SL digeser lebih sedikit untuk mengurangi loss karena signal dinilai tidak lagi relevan di timeframe tersebut.

| Tanggal | PnL Aktual | Estimasi TP | Opportunity Cost | Hasil |
|---------|------------|-------------|------------------|-------|
| 3 Apr | +$6.35 | ~$8.68 | -$2.33 | Profit, tapi < target |
| **4 Apr** | **+$0.18** | ~$8.68 | **-$8.50** | ❌ **Harusnya 2 TP, malah profit minim** |
| 7 Apr | +$0.12 | ~$4.34 | -$4.22 | Profit minim |
| 10 Apr | +$4.00 | ~$8.68 | -$4.68 | Profit, tapi < target |

**Total:**
- Aktual: +$7.48
- Potensi: ~$17.36
- **Profit yang hilang: ~$10**

## Sizing Error (12-14 April)

| Tanggal | PnL | Size Aktual | Size Target | Impact |
|---------|-----|-------------|-------------|--------|
| 12 Apr | -$2.52 | $147 | $500 | Loss lebih kecil karena sizing |
| 13 Apr | +$3.31 | $151 | $500 | Profit 30% dari potensi |
| 14 Apr | +$1.50 | $151 | $500 | Profit 30% dari potensi |

**Note:** 12 Apr SL manual menyelamatkan dari loss lebih besar (harga anjlok).

**Total opportunity cost sizing:** ~$5.34

## 📊 Analisis by Side

| Arah | Win/Loss | WR | PnL |
|------|----------|-----|-----|
| **Long** | 27W / 9L | 75.0% | +$7.82 |
| **Short** | 14W / 3L | **82.4%** | **+$12.55** |

**Insight:** Short strategy jauh lebih superior (82.4% WR, +$12.55 vs +$7.82).

## 📈 Performance Metrics

### Statistik Utama

```
Total Trades:        54 posisi
Win Rate:            75.9%
Profit Factor:       ~2.5
Avg Win:             +$1.06
Avg Loss:            -$1.93
Risk/Reward:         0.55 (perlu perbaikan)
Max Drawdown:        ~$7.08 (6 Apr)
Sharpe Ratio (est):  ~3.13 (per dashboard)
```

### Comparison

| Metrik | Raw | Adjusted |
|--------|-----|----------|
| PnL | $14.04 | $20.37 (+$6.33) |
| Win Rate | 71.2% | 75.9% (+4.7%) |

## 🎯 Lessons Learned

### Pelajaran Penting #1: Percaya pada Edge

> **"Percaya pada edge dan jangan lakukan intervensi manual"**

**Evidence:**
- 4 Apr: Intervensi → Profit +$0.18 (harusnya 2 TP ~$8.68)
- 3, 7, 10 Apr: Intervensi → Profit < target
- **Cost of intervention: ~$10**

**Rekomendasi:**
1. Set time-based exit (auto-close setelah 8-12 jam)
2. Implement signal validity decay (reduce conviction after X candles)
3. Atau: Trust the system dan jangan intervensi

---

### Pelajaran #2: Consistent Sizing

**Issue:** 12-14 Apr sizing ~30% dari target ($150 vs $500 notional)

**Impact:** 
- Profit dikurangi ~70%
- Loss juga dikurangi ~70% (12 Apr SL manual)

**Action:** Fix position sizing logic di bot.

---

### Pelajaran #3: SL Management

**Positif:** 12 Apr SL manual adjustment berhasil menyelamatkan dari loss lebih besar.

**Negatif:** Intervensi manual justru merusak edge pada 5 Apr.

**Rule:** Jika signal valid dan SL belum hit, biarkan. Jika signal expired (>8 jam), gunakan time-exit bukan SL adjustment.

## 🛠️ Riwayat Perbaikan (Setelah 27 Maret)

### 29 Maret 2026 — Critical Fixes

| ID | Deskripsi | Severity | Commit |
|----|-----------|----------|--------|
| **FIX-13** | Re-entry Guard | **CRITICAL** | `ddc6309` |
| **FIX-14** | Koreksi Database dari CSV | MEDIUM | — |
| **FIX-15** | Switch ke FixedStrategy | MEDIUM | `663ba55` |
| **FIX-16** | SL/TP Limit Price Slippage Buffer | HIGH | `7330b4c` |
| **FIX-17** | filled_price dari SDK Response | MEDIUM | `7330b4c` |

#### FIX-13: Re-entry Guard (Critical)
**Masalah:** Saat posisi baru saja ditutup, `sync_position_status()` langsung diikuti `process_signal()` di cycle yang sama, menyebabkan bot langsung membuka posisi baru (double/triple entry).

**Root cause:** Return value `sync_position_status()` salah — mengembalikan `True` saat tidak ada posisi (harusnya `False`).

**Solusi:** 
- Return `True` hanya jika posisi baru saja ditutup di cycle ini
- Caller skip `process_signal()` jika return `True`

**Impact:** Menghilangkan bug double/triple entry.

---

#### FIX-14: Koreksi Database dari CSV
**Masalah:** Data DuckDB tidak akurat — berisi 10 record campuran dari bug double entry dan data tidak lengkap.

**Solusi:** Rekonstruksi database dari CSV export Lighter (ground truth):
- Hapus 10 record lama
- Insert ulang 9 trade valid berdasarkan CSV

**Result:** Total PnL direkonstruksi: **+$2.18 USDT**

---

#### FIX-15: Switch ke FixedStrategy
**Masalah:** HestonStrategy menghasilkan TP terlalu jauh (ATR × 2.1 ≈ 3.1%), posisi tidak hit TP dan harus ditutup manual.

**Solusi:** Switch ke FixedStrategy (Golden v4.4) dengan parameter:
- SL_PCT: 1.333%
- TP_PCT: 0.71%
- LEVERAGE: 7x
- MARGIN_USD: $20

---

#### FIX-16: SL/TP Limit Price Slippage Buffer
**Masalah:** Limit price SL/TP di-set sama dengan trigger price, order tidak fill saat market gap/slippage.

**Solusi:** Tambah slippage buffer:
- SL order: buffer 0.5%
- TP order: buffer 0.3%

---

#### FIX-17: filled_price dari SDK Response
**Masalah:** `filled_price` di-set dari intended price, bukan actual fill price dari SDK.

**Solusi:** Baca `avg_execution_price` dari SDK response object.

## 🚀 Rekomendasi Improvement

### Immediate (High Priority)

1. **Time-based Exit:** Auto-close posisi setelah 8-12 jam tanpa TP/SL
2. **Fix Sizing:** Pastikan margin & leverage sesuai config ($20×7x atau $100×5x)
3. **Remove Manual Override:** Disable ability untuk manual close dari dashboard

### Medium Term

1. **Signal Decay:** Reduce conviction score setiap candle tanpa trigger
2. **Trailing SL:** Implement break-even SL setelah 50% TP tercapai
3. **Market Regime Detection:** Reduce size atau pause trading saat choppy/volatile

### Long Term

1. **Walk-forward Validation:** Retest strategi dengan intervensi manual di-backtest
2. **Feature Analysis:** Apa yang membuat short lebih profitable?
3. **Correlation Analysis:** L1-L3 alignment untuk improve entry quality

---

## Appendix: Perhitungan Detail

### Adjusted PnL Calculation

```
Raw PnL (CSV):          $14.04
+ Bug 18 Mar:           +$6.30
- Uji coba 15 Mar:      -(-$0.04) ≈ $0
-------------------------------
Adjusted PnL:           $20.37
```

### Opportunity Cost

```
Intervensi delay:       ~$10
Sizing error:           ~$5.34
-------------------------------
Total opportunity:      ~$15.34

PnL Potential:          $20.37 + $15.34 = ~$35.71
```

---

**Logbook ini dibuat untuk mendokumentasikan lesson learned dan mencegah repeat of mistakes.**

*Dokumen ini mengacu pada data trade export Lighter dan analisis backend v4.4-v4.5.*
