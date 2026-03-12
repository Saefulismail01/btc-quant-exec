# 📊 Riset: Leverage, Drawdown, dan Jalur Menuju 3%/Hari

**Tanggal:** 3 Maret 2026  
**Konteks:** BTC-QUANT Scalping — daily return saat ini +0.78% di 1× leverage  
**Pertanyaan:** Bagaimana cara aman mencapai target 3%/hari?

---

## 1. Kondisi Saat Ini

| Metrik | Nilai (1× leverage) |
|---|---|
| Win Rate | 64.4% |
| Daily Return | +0.78% |
| Max Drawdown | -24.8% |
| Profit Factor | 2.24 |
| Avg Win | +2.6% |
| Avg Loss | -2.1% |

**Target: 3%/hari → butuh ~3.8× leverage jika edge tetap.**

---

## 2. Masalah: Leverage × Drawdown

Leverage adalah **pengali dua arah** — memperbesar profit DAN loss:

| Leverage | Daily Return | Max Drawdown | Apakah Survive? |
|---|---|---|---|
| 1× | +0.78% | -24.8% | ✅ Aman |
| 2× | +1.56% | -49.6% | ✅ Sakit tapi survive |
| 3× | +2.34% | -74.4% | ⚠️ Margin call territory |
| 4× | +3.12% | -99.2% | ❌ Akun hampir habis |
| 5× | +3.90% | -124% | ❌ Likuidasi total |

> **Kesimpulan brutal: leverage 4-5× dengan drawdown 24.8% = bunuh akun.**

Ini kenapa leverage BUKAN solusi utama. Yang perlu diselesaikan dulu: **kurangi drawdown.**

---

## 3. Tiga Jalur Menuju 3%/Hari

### Jalur A: Kurangi Drawdown → Leverage Lebih Aman

**Logika:** Jika max DD turun dari -24% ke -10%, maka leverage 5× = DD -50% (survivable).

**Cara menurunkan drawdown:**

| Metode | Deskripsi | Estimasi DD Reduction | Effort |
|---|---|---|---|
| **Confluence Filter** | Hanya trade jika BCD + EMA + MLP setuju | DD -30~50% | MEDIUM |
| **FGI Guard** | Skip trade saat FGI > 80 (extreme greed) atau < 20 (extreme fear) | DD -10~20% | LOW |
| **Regime Duration Filter** | Skip trade di 3 candle pertama setelah regime flip (sering false signal) | DD -15~25% | LOW |
| **Dynamic SL Tightening** | Geser SL ke breakeven setelah profit 1× ATR | DD -20~30% | MEDIUM |

**Jika gabungkan Confluence + FGI Guard:**
- DD estimasi: -24% × 0.5 × 0.85 = **~-10%**
- Leverage aman: 5× → DD = -50% (survivable)
- Daily return: 0.78% × 5 = **3.9%** ✅

**Trade-off:** Confluence filter akan **mengurangi jumlah trade** (hanya ambil trade berkualitas tinggi). Estimasi: trade berkurang 30-40%, tapi WR naik dari 64% ke 70%+.

---

### Jalur B: Tambah Frekuensi Trade (Multi-Timeframe)

**Logika:** Dari 1× leverage, 0.78%/hari datang dari rata-rata 0.78%/6 trades = 0.13%/trade. Jika bisa ambil lebih banyak trade berkualitas per hari, return naik tanpa leverage.

| Timeframe | Trades/Hari | Return/trade | Daily Return (1×) |
|---|---|---|---|
| 4H (sekarang) | ~6 candles, ~0.5 trade aktif | 0.13% | 0.78% |
| 1H (tambahan) | ~24 candles, ~2 trade aktif | ~0.05-0.08% | +0.10-0.16% |
| **4H + 1H** | **~2.5 trade aktif** | ~0.10% avg | **~1.0%** |

**Tapi ada masalah:**
- BCD di 1H belum divalidasi — BOCPD bisa terlalu sensitif di timeframe kecil
- Lebih banyak noise → WR kemungkinan turun
- Butuh riset + walk-forward terpisah untuk 1H
- **Belum direkomendasikan sekarang**

---

### Jalur C: Leverage Moderat + Risk Per Trade Rendah (PALING PRAGMATIS)

**Logika:** Gunakan leverage moderat (3×) bersama risk management ketat.

```
Konfigurasi yang direkomendasikan:
  Leverage      = 3× (fixed, tidak dinamis dulu)
  Risk per trade = 2% dari modal (max loss per trade)
  Max positions  = 1 (satu posisi pada satu waktu)
  Max daily loss = 5% → stop trading hari itu
```

| Metrik | Tanpa Leverage | Leverage 3× + Risk Cap |
|---|---|---|
| Daily Return | +0.78% | **+2.34%** |
| Max Drawdown | -24.8% | -24.8% × (2%/avg_loss) = **~-15%** |
| Worst Day | -4.2% | **-5%** (capped) |

**Kenapa ini pragmatis:**
- Leverage 3× memberi 2.34%/hari — belum 3%, tapi **sudah mendekati**
- Risk cap 2% + max daily loss 5% mencegah likuidasi
- Tidak butuh perubahan kode engine — hanya parameter di paper_trade_service
- Bisa dijalankan minggu depan, bukan bulan depan

**Kekurangan:**
- Return 2.34% < target 3%
- Masih perlu Jalur A (confluence filter) untuk menutup gap 0.66% sisanya

---

## 4. Rekomendasi: Jalur C Dulu, Lalu A

### Tahap 1: Sekarang (Minggu ini)
- **Leverage 3× fixed** di paper trading
- **Risk per trade 2%**, max daily loss 5%
- Target realistis: **+2.0-2.5%/hari**

### Tahap 2: Minggu depan
- **Confluence filter** (BCD + EMA harus setuju)
- Estimasi: WR naik dari 64% → 68-72%, DD turun 30%
- Dengan DD lebih rendah, **naikkan leverage ke 4×**
- Target: **+3.0-3.5%/hari**

### Tahap 3: Bulan depan
- Validasi confluence filter di walk-forward
- Implementasi FGI guard
- Half-Kelly position sizing dari 50+ trade data
- Target final: **+3-5%/hari dengan DD < -15%**

---

## 5. Sistem Leverage Saat Ini vs Rekomendasi

### Saat Ini (Module F — Target ROE)

```python
TARGET_ROE = 0.04  # 4% return per trade
leverage = TARGET_ROE / (tp1_multiplier × vol_ratio)
# Menghasilkan leverage 5-15× tergantung vol!
```

**Masalah:** Ini menghasilkan leverage yang **terlalu tinggi** di vol rendah:
- Vol rendah (vol_ratio = 0.005, tp1 = 1.8): leverage = 0.04 / (1.8 × 0.005) = **4.4×** ← OK
- Vol rendah (vol_ratio = 0.003, tp1 = 1.8): leverage = 0.04 / (1.8 × 0.003) = **7.4×** ← terlalu tinggi
- Vol normal (vol_ratio = 0.008, tp1 = 2.0): leverage = 0.04 / (2.0 × 0.008) = **2.5×** ← OK

### Yang Direkomendasikan

```python
# Leverage moderat + risk cap
MAX_LEVERAGE = 3      # Hard cap
RISK_PER_TRADE = 0.02  # 2% dari modal
MAX_DAILY_LOSS = 0.05  # 5% → stop trading

# Hitung leverage dari risk budget
sl_distance_pct = sl_multiplier * vol_ratio  # berapa % harga bisa turun ke SL
leverage = RISK_PER_TRADE / sl_distance_pct
leverage = min(leverage, MAX_LEVERAGE)  # cap
```

**Ini lebih aman karena:**
- Leverage dihitung dari **berapa yang siap hilang** (risk-first), bukan **berapa yang mau dapat** (greed-first)
- Hard cap 3× mencegah overleveraging
- Daily loss cap mencegah tilt trading

---

## 6. Ringkasan

| Pertanyaan | Jawaban |
|---|---|
| Kenapa daily return 0.78%? | Karena di 1× leverage — ini pure edge dari BCD |
| Apakah leverage solusi? | Sebagian. Tapi leverage tanpa DD kontrol = bunuh akun |
| Berapa leverage aman? | **3× sekarang**, naikkan ke 4× setelah confluence filter |
| Bagaimana capai 3%/hari? | Leverage 3× + confluence filter + risk cap |
| Apa yang perlu dikerjakan? | Confluence filter (BCD+EMA setuju) → baru naikkan leverage |

> **Bottom line:** BCD edge-nya solid (64.4% WR, PF 2.24). Masalahnya bukan signal quality — masalahnya adalah **risk management belum cukup ketat untuk support leverage tinggi.** Fix risk management dulu, leverage menyusul.

---

*Referensi: Walk-forward validation BCD v3, Module F signal_service.py*
