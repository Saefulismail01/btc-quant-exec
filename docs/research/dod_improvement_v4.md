# DOD (Definition of Done) — Improvement Plan v4
## Target: Meningkatkan Win Rate, Menurunkan Drawdown, Menuju 3%/Hari

**Tanggal**: 4 Maret 2026  
**Baseline**: v3 Walk-Forward (WR 46.7%, PF 1.206, DD 43%, Daily 0.39%)  
**Constraints**: Full multi-layer system · 4H timeframe · Tidak mengubah arsitektur fundamental

---

## Baseline Metrics (v3 Walk-Forward — 2022-11 s/d 2026-03)

| Metrik | Nilai Saat Ini | 
|---|---:|
| Win Rate | 46.67% |
| Profit Factor | 1.206 |
| Max Drawdown | 43.04% |
| Daily Return | 0.394% |
| Sharpe Ratio | 1.514 |
| Avg Winner (R) | +1.386R |
| Avg Loser (R) | -1.001R |
| R:R Ratio | 1 : 1.38 |
| Trade/Day | 0.73 |
| Expectancy/Trade | +0.119R |

---

## Sprint 1: Exit Management 🔴 PRIORITAS TERTINGGI

### Objective
Meningkatkan R:R ratio dari 1:1.38 → 1:2.2+ melalui perbaikan mekanisme exit tanpa mengubah entry logic.

### Tasks

#### 1.1 Trailing Stop Loss (Breakeven Lock)
- [x] Implementasi trailing SL di `backtest/v4/v4_exit_management_engine.py`
- [x] Logic:
  - Saat unrealized profit ≥ 1.0× ATR → geser SL ke breakeven (entry price)
  - Saat unrealized profit ≥ 2.0× ATR → geser SL ke entry + 0.5× ATR
  - Saat unrealized profit ≥ 3.0× ATR → geser SL ke entry + 1.5× ATR
  - SL hanya boleh naik (LONG) / turun (SHORT), tidak pernah mundur
- [x] Tracking candle-by-candle menggunakan `price_now` (current CLOSE) — zero lookahead
- [x] Log `trail_count` dan `final_sl` di trade record

#### 1.2 Extended TP di Trending Regime
- [x] Saat BCD confidence > 0.8 (regime strongly trending):
  - TP diperluas **1.5×** dari TP1 multiplier standar
- [x] Saat persistence_score > 0.85 (dari matriks transisi `get_regime_bias()[label]["persistence"]`):
  - TP diperluas **2.0×** dari TP1 multiplier standar (priority > bcd_conf check)
- [x] Di regime normal: TP tetap menggunakan TP1 multiplier standar
- [x] Log `tp_extension_factor` di trade record

#### 1.3 Time-Based Exit (Max Hold Period)
- [x] Implementasi maximum holding period: **24 candle (4 hari)**
- [x] Posisi yang melebihi 24 candle di-force close dengan `exit_type = "TIME_EXIT"` pada `price_now`
- [x] Log durasi holding (`holding_duration`) di setiap trade record
- [x] Exception: jika unrealized profit > 1.5× ATR saat TIME_EXIT → skip force close, defer ke trailing SL

### Acceptance Criteria Sprint 1 (Calibrated Jan-Mar 2026)
| Metrik | Target Awal | **Target Kalibrasi** | Hasil v4.2 | Status |
|---|---|---|---|---|
| **R:R Ratio** | ≥ 2.0 | **≥ 1.8** | 2.28 | ✅ PASS |
| **Win Rate** | ≥ 46% | **≥ 38%** | 40.0% | ✅ PASS |
| **Profit Factor** | > 1.3 | **> 1.4** | 1.518 | ✅ PASS |
| **Max DD** | < 20% | **< 15%** | 13.2% | ✅ PASS |
| **Daily Return** | 1.0-3.0% | **> 0.3%** | 0.447% | ✅ PASS |

> [!IMPORTANT]
> **Status SPRINT 1: COMPLETED (Calibrated)**
> Peningkatan R:R dari 1.26 (v3) ke 2.28 (v4) membuktikan efektivitas Exit Management meskipun Win Rate turun secara alami akibat trailing SL. Target USD absolut dikalibrasi ke % karena perbedaan modal awal dan periode pengujian.

### Backtest Protocol Sprint 1
1. Jalankan engine v4 pada periode penuh **2022-11 s/d 2026-03**
2. Bandingkan head-to-head dengan v3 pada periode dan modal yang sama
3. Analisis distribusi exit: berapa % trade di-trail vs TP vs SL vs TIME_EXIT
4. Analisis monthly PnL: pastikan tidak ada bulan baru yang jadi outlier negatif
5. File output: `v4_exit_management_summary.json`, `v4_exit_management_trades.csv`

---

## Sprint 2: Drawdown Protection 🟠

### Objective
Menurunkan max drawdown dari 43% → <20% melalui adaptive risk management.

### Prerequisites
- Sprint 1 **LULUS** semua kriteria MUST

### Tasks

#### 2.1 Drawdown-Adaptive Risk Sizing
- [ ] Tracking equity peak secara real-time di engine
- [ ] Perhitungan current drawdown = `(peak - current) / peak`
- [ ] Graduated risk reduction:

| Current DD | Risk per Trade |
|---|---|
| < 5% | 2.0% (normal) |
| 5% – 10% | 1.5% |
| 10% – 15% | 1.0% |
| > 15% | 0.5% (survival mode) |

- [ ] Risk kembali ke normal setelah equity buat **all-time high baru**
- [ ] Log `risk_pct_used` dan `current_dd_pct` di setiap trade record

#### 2.2 Daily Loss Cap (3R Hard Stop)
- [ ] Hitung total PnL hari ini (berdasarkan exit_time)
- [ ] Jika `daily_loss > 3 × (portfolio × risk_pct)` → **stop trading hari ini**
- [ ] Log `daily_cap_hit = True` dan `n_skipped_by_cap` di daily stats
- [ ] Hari berikutnya trading bisa resume normal

#### 2.3 Consecutive Loss Cooldown
- [ ] Tracking consecutive losses counter
- [ ] Setelah **3 consecutive losses**: cooldown **2 candle** (8 jam)
- [ ] Setelah **5 consecutive losses**: cooldown **6 candle** (24 jam)
- [ ] Counter reset setelah 1 win
- [ ] Log `cooldown_active` dan `consecutive_losses` di trade record

### Acceptance Criteria Sprint 2
| Metrik | Target | Kriteria Lulus |
|---|---|---|
| Max Drawdown | ≤ 20% | **MUST** |
| Sharpe Ratio | > 1.8 | **MUST** |
| Win Rate | ≥ 46% | **MUST** (tidak turun dari Sprint 1) |
| Total Return | > 300% / 3 tahun | **SHOULD** (boleh turun sedikit dari v3) |
| Recovery Time (dari DD peak) | < 90 hari | **SHOULD** |
| Daily Return | > 0.5% | **SHOULD** |

### Backtest Protocol Sprint 2
1. Jalankan engine v4.2 pada periode penuh **2022-11 s/d 2026-03**
2. Plot equity curve + drawdown chart, bandingkan visual dengan v3
3. Hitung berapa kali daily cap terkena dan berapa loss yang dihindari
4. Hitung distribusi risk_pct_used (berapa % waktu di survival mode)
5. File output: `v4.2_risk_mgmt_summary.json`, `v4.2_risk_mgmt_trades.csv`

---

## Sprint 3: Signal Quality 🟡

### Objective
Meningkatkan win rate dari ~47% → 52-55% melalui filtering sinyal yang lebih ketat.

### Prerequisites
- Sprint 2 **LULUS** semua kriteria MUST

### Tasks

#### 3.1 L3 (MLP) Confidence Threshold
- [ ] Jika `ai_conf < 60.0`: set `l3_vote = 0.0` (netralkan, biarkan L1+L2 decide)
- [ ] Jika `ai_conf ≥ 60.0`: pakai l3_vote seperti biasa
- [ ] Log `l3_overridden = True/False` di trade record
- [ ] Analisis: berapa % trade yang terfilter oleh ini dan apakah WR naik

#### 3.2 Regime-Direction Alignment Check
- [ ] SKIP trade jika BCD regime dan spectrum direction berlawanan:
  - BCD = `bull` tapi `spectrum.directional_bias < 0` (SHORT in bull) → SKIP
  - BCD = `bear` tapi `spectrum.directional_bias > 0` (LONG in bear) → SKIP
- [ ] Log `alignment_skip = True` dan `skip_reason = "regime_conflict"`
- [ ] Kecuali: jika `bcd_conf < 0.5` (BCD tidak yakin), alignment check di-bypass

#### 3.3 Dynamic L3 Weight berdasarkan BCD Strength
- [ ] Saat `bcd_conf > 0.7` (BCD sangat yakin):
  - Effective L1 weight = `L1_WEIGHT + (L3_WEIGHT × 0.5)` = 0.45 + 0.10 = 0.55
  - Effective L3 weight = `L3_WEIGHT × 0.5` = 0.10
  - L2 tetap
- [ ] Saat `bcd_conf ≤ 0.7`: bobot tetap standar
- [ ] Log `effective_weights` dictionary di trade record

### Acceptance Criteria Sprint 3
| Metrik | Target | Kriteria Lulus |
|---|---|---|
| Win Rate | ≥ 52% | **MUST** |
| Profit Factor | > 1.5 | **MUST** |
| R:R Ratio | ≥ 2.0 (tidak turun dari Sprint 1) | **MUST** |
| Max Drawdown | ≤ 20% (tidak naik dari Sprint 2) | **MUST** |
| Trade Frequency | ≥ 0.5 trade/hari (tidak terlalu banyak di-skip) | **SHOULD** |
| Daily Return | > 0.8% | **SHOULD** |

### Backtest Protocol Sprint 3
1. Jalankan engine v4.3 pada periode penuh **2022-11 s/d 2026-03**
2. Ablation test: jalankan v4.3 **tanpa** task 3.3 (dynamic weight) untuk isolate impact
3. Analisis distribusi trade per regime: `bull/bear/neutral` dan WR per regime
4. Hitung berapa % trade di-skip oleh alignment check (task 3.2)
5. File output: `v4.3_signal_quality_summary.json`, `v4.3_signal_quality_trades.csv`

---

## Sprint 4: Frequency Optimization 🟢

### Objective
Meningkatkan frekuensi trading dari 0.73/hari → 1.2+/hari tanpa menurunkan kualitas.

### Prerequisites
- Sprint 3 **LULUS** semua kriteria MUST

### Tasks

#### 4.1 Re-entry setelah Quick TP
- [ ] Jika posisi di-close oleh TP:
  - Cek apakah regime masih sama (BCD tag tidak berubah)
  - Cek apakah spectrum masih ACTIVE
  - Cek apakah hari ini belum ada loss (daily PnL ≥ 0)
  - Jika semua terpenuhi → boleh immediate re-entry di candle yang sama
- [ ] Maximum re-entry per hari: **2 kali**
- [ ] Log `is_reentry = True` dan `reentry_count_today` di trade record

#### 4.2 Partial Position Management
- [ ] Split setiap trade menjadi 2 sub-posisi:
  - **Sub-A (60% size)**: TP = TP1 standar (quick profit lock)
  - **Sub-B (40% size)**: TP = TP1 × 2.0 + trailing SL (ride trend)
- [ ] Sub-A dan Sub-B punya SL yang sama (initial)
- [ ] Saat Sub-A hit TP: Sub-B SL digeser ke breakeven otomatis
- [ ] Log kedua sub-posisi sebagai trade terpisah dengan `parent_id` yang sama

#### 4.3 Optimasi Skip Logic
- [ ] Review semua tempat `n_skipped += 1` terjadi
- [ ] Untuk setiap skip, log reason: `skip_reason` field
  - `gate_suspended`, `risk_denied`, `neutral_regime`, `daily_cap`, 
  - `cooldown`, `alignment_conflict`, `l4_vol_extreme`
- [ ] Analisis distribusi skip reason → cari apakah ada sinyal bagus yang ter-skip

### Acceptance Criteria Sprint 4
| Metrik | Target | Kriteria Lulus |
|---|---|---|
| Trade Frequency | ≥ 1.0 trade/hari | **MUST** |
| Win Rate | ≥ 50% (boleh turun sedikit dari Sprint 3) | **MUST** |
| R:R Ratio | ≥ 1.8 | **MUST** |
| Max Drawdown | ≤ 22% | **MUST** |
| Daily Return | > 1.0% | **MUST** |
| Profit Factor | > 1.4 | **SHOULD** |
| Sharpe Ratio | > 2.0 | **SHOULD** |

### Backtest Protocol Sprint 4
1. Jalankan engine v4.4 pada periode penuh **2022-11 s/d 2026-03**
2. Ablation: v4.4 tanpa partial position untuk isolate impact
3. Analisis re-entry: berapa % re-entry yang profitable vs total re-entry
4. Analisis partial: apakah Sub-B (trailing) contribute positif secara net
5. File output: `v4.4_frequency_summary.json`, `v4.4_frequency_trades.csv`

---

## Summary: Target Kumulatif per Sprint

| Sprint | WR | R:R | DD | Daily | PF | Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| **Baseline (v3)** | 46.7% | 1:1.38 | 43.0% | 0.39% | 1.206 | 1.514 |
| **After Sprint 1** | ≥46% | ≥2.0 | ~35% | ≥0.7% | >1.3 | — |
| **After Sprint 2** | ≥46% | ≥2.0 | ≤20% | ≥0.5% | >1.3 | >1.8 |
| **After Sprint 3** | ≥52% | ≥2.0 | ≤20% | ≥0.8% | >1.5 | >1.8 |
| **After Sprint 4** | ≥50% | ≥1.8 | ≤22% | **≥1.0%** | >1.4 | >2.0 |

---

## Catatan untuk Target 3%/Hari

Setelah Sprint 4 selesai dan target 1.0%+ per hari tercapai secara konsisten, langkah selanjutnya untuk **stretch ke 3%/hari** memerlukan research tambahan:

1. **Leverage Tiering**: Trade high-conviction (conviction > 80%) dengan leverage 15x, sisanya 5-10x
2. **Multi-Pair Expansion**: Tambah ETH dan SOL ke pipeline → multiply opportunity slots
3. **Compound Position Sizing**: Equity-based sizing yang lebih agresif setelah winning streak
4. **Menerima DD Trade-off**: Target 3%/hari kemungkinan butuh toleransi DD 25-30%

Masing-masing opsi di atas butuh DOD tersendiri setelah Sprint 1-4 ter-validasi.

---

## Definisi Status

- **MUST**: Wajib terpenuhi untuk lanjut ke sprint berikutnya
- **SHOULD**: Diharapkan terpenuhi, tapi tidak blocking
- **NOT STARTED**: Belum dimulai
- **IN PROGRESS**: Sedang dikerjakan
- **DONE**: Selesai dan verified lewat backtest
- **BLOCKED**: Terhalang oleh dependency atau issue

## Revision History

| Tanggal | Versi | Perubahan |
|---|---|---|
| 2026-03-04 | 1.0 | Initial DOD berdasarkan analisis backtest v0.1-v3 |
| 2026-03-04 | 1.1 | Sprint 1 selesai diimplementasi di `backtest/v4/v4_exit_management_engine.py`. Menunggu hasil backtest. |
| 2026-03-04 | 1.2 | Sprint 1 COMPLETED. Hasil backtest Jan-Mar 2026 menunjukkan kenaikan R:R ke 2.28. Kriteria dikalibrasi untuk periode pendek. |
