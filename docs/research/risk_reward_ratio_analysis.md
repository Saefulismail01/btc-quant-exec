# 📊 Risk to Reward Ratio — Analisis SL/TP Preset

**Tanggal:** 3 Maret 2026  
**Konteks:** Update SL/TP multiplier di `layer1_volatility.py` berdasarkan data walk-forward

---

## Preset Setelah Update (3 Maret 2026)

| Preset | Kondisi | SL× | TP1× | TP2× | R:R (TP1) | R:R (TP2) | Breakeven WR |
|---|---|---|---|---|---|---|---|
| **HV-Fast-Revert** | Vol tinggi, halflife < 15 | 2.0 | 1.5 | 2.0 | 1 : 0.75 | 1 : 1.0 | 57.1% |
| **HV-Slow-Persist** | Vol tinggi, halflife ≥ 15 | 2.0 | 1.5 | 2.5 | 1 : 0.75 | 1 : 1.25 | 57.1% |
| **LV-Trend** | Vol rendah | 1.2 | 1.8 | 2.5 | 1 : 1.50 | 1 : 2.08 | 40.0% |
| **Normal** | Default | 1.5 | 2.0 | 3.0 | 1 : 1.33 | 1 : 2.0 | 42.9% |

---

## Perbandingan Lama vs Baru

| Preset | TP1 Lama | TP1 Baru | R:R Lama | R:R Baru | BEP WR Lama | BEP WR Baru |
|---|---|---|---|---|---|---|
| HV-Fast-Revert | 0.8× | **1.5×** | 1:0.36 | **1:0.75** | 73.3% ❌ | 57.1% ✅ |
| HV-Slow-Persist | 1.0× | **1.5×** | 1:0.50 | **1:0.75** | 66.7% ⚠️ | 57.1% ✅ |
| LV-Trend | 1.2× | **1.8×** | 1:1.00 | **1:1.50** | 50.0% ✅ | 40.0% ✅ |
| Normal | 1.0× | **2.0×** | 1:0.67 | **1:1.33** | 60.0% ⚠️ | 42.9% ✅ |

---

## Cara Baca Risk:Reward

- **R:R = SL : TP = Risiko : Reward**
- Contoh **1 : 1.33** → setiap 1 unit risiko menghasilkan 1.33 unit reward jika menang
- Semakin tinggi reward, semakin rendah WR yang dibutuhkan untuk profitable

## Breakeven Win Rate

```
Breakeven WR = SL / (SL + TP1)
```

Jika WR aktual > Breakeven WR → **profitable** (positive edge)

- WR aktual kita (walk-forward): **64.7%**
- Semua preset sekarang punya breakeven WR **di bawah 57.1%**
- Margin of safety: **+7.6% hingga +24.7%** di atas breakeven

---

## Expectancy Per Preset (WR = 64.7%)

```
Expectancy = (WR × Reward) - ((1-WR) × Risk)
```

| Preset | Rumus | Expectancy / Trade |
|---|---|---|
| **HV-Fast-Revert** | (0.647 × 0.75) - (0.353 × 1.0) | **+0.132** ✅ |
| **HV-Slow-Persist** | (0.647 × 0.75) - (0.353 × 1.0) | **+0.132** ✅ |
| **LV-Trend** | (0.647 × 1.50) - (0.353 × 1.0) | **+0.618** ✅✅ |
| **Normal** | (0.647 × 1.33) - (0.353 × 1.0) | **+0.507** ✅✅ |

> **Semua preset positif.** LV-Trend dan Normal punya expectancy tertinggi karena reward > risk.

---

## Catatan Kritis

1. **Preset HV-Fast-Revert lama (TP1 = 0.8×)** membutuhkan WR 73.3% untuk breakeven — dengan WR 64.7% kita, itu **guaranteed loss** di high vol. Ini sekarang sudah diperbaiki.

2. **Preset Normal** adalah yang paling sering aktif (mayoritas waktu BTC di vol normal). Update dari 1.0× ke 2.0× ATR berarti setiap trade normal sekarang punya expectancy +0.507 per unit risiko, naik dari +0.078.

3. **Semua preset** sekarang berada jauh di bawah WR aktual — memberikan buffer keamanan bahkan jika WR turun dari 64.7% ke ~58%.

---

*Sumber: Walk-forward validation BCD v3 (2023, 2024 H2, 2025-2026)*  
*File terkait: `backend/engines/layer1_volatility.py` → `get_sl_tp_multipliers()`*
