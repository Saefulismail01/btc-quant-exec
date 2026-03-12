# 📊 Proposal: Walk-Forward Full Pipeline (BCD + EMA + MLP Confluence)

**Tanggal:** 3 Maret 2026  
**Status:** PROPOSAL — belum diimplementasikan  
**Tujuan:** Membuktikan apakah confluence 3 layer menghasilkan WR dan return lebih baik daripada BCD standalone

---

## 1. Latar Belakang

### Baseline: BCD Standalone (sudah divalidasi)

| Metrik | Nilai |
|---|---|
| Win Rate | 64.4% |
| Daily Return (1×) | +0.78% |
| Max Drawdown | -24.8% |
| Profit Factor | 2.24 |

**Masalah:** Drawdown -24.8% terlalu besar untuk leverage 4-5×. Perlu **filter sinyal** yang mengurangi trade berkualitas rendah.

### Hipotesis

> Jika kita hanya trade saat **BCD + EMA + MLP setuju** (confluence), maka:
> - WR naik dari 64% → **68-72%**
> - Drawdown turun dari -24% → **-10 sampai -15%**
> - Jumlah trade berkurang 30-40%, tapi kualitasnya lebih tinggi
> - Dengan DD lebih rendah, leverage 4-5× menjadi aman → **3%+/hari tercapai**

---

## 2. Arsitektur Layer yang Akan Diuji

### Layer 1: BCD Regime (Sinyal Utama)

```
Output: "Bullish Trend" | "Bearish Trend" | "Sideways"
Fungsi: Menentukan ARAH dasar (long/short/skip)
Sudah divalidasi: ✅
```

### Layer 2: EMA Structure (Filter Tren)

```
Output: vote [-1.0 sampai +1.0]
Logika:
  Price > EMA20 > EMA50 → vote positif kuat (+0.7 sampai +1.0)
  Price < EMA20 < EMA50 → vote negatif kuat (-0.7 sampai -1.0)  
  Struktur tidak selaras  → vote lemah (×0.4)

Fungsi: FILTER — pastikan trend EMA sejalan dengan BCD regime
Contoh filter:
  BCD = "Bullish" tapi EMA vote < 0 → SKIP (harga di bawah EMA, kontra-trend)
  BCD = "Bullish" dan EMA vote > 0.3 → TRADE (konfirmasi struktur)
```

### Layer 3: MLP Confidence (Filter Conviction)

```
Output: (bias: "BULL"|"BEAR", confidence: 50-100%)
Logika: Neural network prediksi arah candle berikutnya
  dengan cross-feature dari BCD regime state

Fungsi: FILTER — hanya trade jika MLP setuju dan confidence cukup
Contoh filter:
  BCD = "Bullish", MLP bias = "BULL", confidence > 55% → TRADE
  BCD = "Bullish", MLP bias = "BEAR" → SKIP (neural net tidak setuju)
  BCD = "Bullish", MLP confidence < 55% → SKIP (conviction terlalu rendah)
```

---

## 3. Desain Confluence Filter

### Aturan Entry (yang akan diuji)

```
LONG jika SEMUA kondisi terpenuhi:
  ✅ BCD regime = "Bullish Trend"
  ✅ EMA vote > +0.3 (Price > EMA20 > EMA50, minimal partial alignment)
  ✅ MLP bias = "BULL" dan confidence > 55%

SHORT jika SEMUA kondisi terpenuhi:
  ✅ BCD regime = "Bearish Trend"
  ✅ EMA vote < -0.3
  ✅ MLP bias = "BEAR" dan confidence > 55%

SKIP jika salah satu gagal
```

### Variasi yang Akan Diuji

| Variasi | BCD | EMA Threshold | MLP Threshold | Deskripsi |
|---|---|---|---|---|
| **V0** (baseline) | Saja | — | — | BCD standalone (sudah ada) |
| **V1** | + EMA | vote > 0.3 | — | BCD + EMA saja |
| **V2** | + MLP | — | conf > 55% | BCD + MLP saja |
| **V3** (full) | + EMA + MLP | vote > 0.3 | conf > 55% | Full confluence |
| **V4** (ketat) | + EMA + MLP | vote > 0.5 | conf > 60% | Confluence ketat |

### Kenapa Variasi Penting?

Kita perlu tahu **layer mana yang paling berkontribusi** terhadap peningkatan kualitas sinyal:
- Jika V1 ≈ V3 → EMA sudah cukup, MLP tidak perlu
- Jika V2 ≈ V3 → MLP sudah cukup, EMA redundant
- Jika V3 >> V1 dan V3 >> V2 → kedua filter diperlukan
- Jika V4 >> V3 → threshold perlu diketatkan

---

## 4. Metrik yang Akan Diukur

| Metrik | Tujuan |
|---|---|
| **Win Rate** | Harus naik dari 64% baseline |
| **Daily Return (1×)** | Harus ≥ 0.78% baseline |
| **Max Drawdown** | HARUS turun — ini metrik utama |
| **Profit Factor** | Harus ≥ 2.24 baseline |
| **Trade Count** | Berapa banyak trade yang difilter |
| **Filter Rejection Rate** | Berapa % sinyal BCD yang di-skip |
| **Missed Opportunity Rate** | Berapa % trade profitable yang di-skip |

Metrik kunci bukan WR atau return — tapi **Drawdown / Return ratio**:

```
DD/Return Ratio = Max_Drawdown / Daily_Return

Baseline: -24.8% / 0.78% = -31.8  (butuh 32 hari untuk recover dari worst DD)
Target:   -10.0% / 0.80% = -12.5  (butuh 12.5 hari — lebih sehat)
```

---

## 5. Implementasi Walk-Forward

### Script yang akan dibuat: `scripts/walk_forward_confluence.py`

```python
# Pseudocode
for window in [2023, 2024_H2, 2025_2026]:
    
    # 1. Train BCD sekali per window (sudah ada)
    bcd.train_global(window_df)
    
    # 2. Hitung EMA untuk seluruh window (instant)
    df["EMA20"], df["EMA50"] = EMA
    
    # 3. Walk-forward MLP per step (seperti sebelumnya tapi hanya untuk inference)
    for candle in test_candles:
        
        # Layer 1: BCD regime
        regime = bcd.get_current_regime(context)
        
        # Layer 2: EMA vote  
        ema_vote = ema_model.get_directional_vote(context)
        
        # Layer 3: MLP confidence
        mlp_bias, mlp_conf = mlp.get_ai_confidence(context, bcd_states)
        
        # Confluence check
        if regime == "Bullish" and ema_vote > EMA_THRESHOLD and mlp_bias == "BULL" and mlp_conf > MLP_THRESHOLD:
            open_long()
        elif regime == "Bearish" and ema_vote < -EMA_THRESHOLD and mlp_bias == "BEAR" and mlp_conf > MLP_THRESHOLD:
            open_short()
        else:
            skip()  # ← ini yang mengurangi trade count dan drawdown
```

### Estimasi Waktu Eksekusi

| Komponen | Waktu (per window) |
|---|---|
| BCD training | ~20-30s (sudah ada) |
| EMA calculation | <1s |
| MLP walk-forward | ~5-10 menit (MLP retrain per step) |
| **Total** | ~5-11 menit per window |

**Masalah:** MLP retrain per step lambat. Opsi:
1. Retrain MLP setiap 24 candle (bukan setiap step) — sudah di-cache
2. Train MLP sekali per window (sama seperti BCD) — lebih cepat tapi less rigorous

---

## 6. Risiko dan Antisipasi

| Risiko | Dampak | Antisipasi |
|---|---|---|
| **Terlalu banyak filter** → terlalu sedikit trade | Daily return turun | Turunkan threshold (V3 → V1) |
| **MLP overfit** → confidence unreliable | False sense of security | Bandingkan V1 vs V3 — jika V1 ≈ V3, MLP tidak membantu |
| **EMA lag** → sinyal terlambat 2-3 candle | Missed entry di awal trend | Gunakan EMA threshold rendah (0.3 bukan 0.5) |
| **Walk-forward MLP terlalu lambat** | Tidak bisa test semua variasi | Train MLP sekali, bukan per step |

---

## 7. Success Criteria

Test dianggap **BERHASIL** jika salah satu variasi (V1-V4) mencapai:

| Metrik | Threshold |
|---|---|
| Win Rate | ≥ 66% (naik dari 64.4%) |
| Max Drawdown | **≤ -15%** (turun dari -24.8%) — INI YANG TERPENTING |
| Daily Return (1×) | ≥ 0.70% (boleh sedikit turun karena trade lebih sedikit) |
| DD/Return Ratio | **≤ -20** (turun dari -31.8) |
| Profit Factor | ≥ 2.3 |

Jika tercapai:
- Leverage 4× aman → DD = -15% × 4 = -60% (survivable)
- Daily return = 0.70% × 4 = **2.8%** + optimasi lain → **target 3% reachable**

---

## 8. Estimasi Timeline

| Step | Waktu | Output |
|---|---|---|
| Implementasi script | 1-2 jam | `walk_forward_confluence.py` |
| Run V0-V4 (5 variasi × 3 windows) | 1-3 jam | CSV results |
| Analisis dan laporan | 30 menit | `docs/reports/confluence_results.md` |
| **Total** | **3-5 jam** | Keputusan: variasi mana yang optimal |

---

*Menunggu persetujuan untuk mulai implementasi.*
