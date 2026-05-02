# PRD & DoD: Backtest Engine Next Generation

## Konteks: Kondisi Algoritma Saat Ini

### Apa yang Sudah Ada (Current State)

Backtest engine saat ini (`pullback_v44_same_engine.py`) adalah **single-layer 4H OHLC engine** yang mengintegrasikan sinyal v4.4 (BCD + AI + EMA + DirectionalSpectrum) dengan simulasi eksekusi dalam satu pipeline. Detail:

| Komponen | Status | File:Baris |
|---|---|---|
| Signal generation (v4.4 layer 1-4) | **Berfungsi** — panggil BCD, AI, EMA, Spectrum service | `:140-227` |
| Market entry simulation | **Berfungsi** — entry di close price sinyal | `:264-299` |
| Pullback limit entry | **Berfungsi** — cari candle berikutnya yang touch limit price | `:302-374` |
| Exit logic (SL/TP/TIME_EXIT) | **Berfungsi** — hold max 6 candle, SL/TP cek per candle | `:230-261` |
| Metrics (Sharpe, DD, Win Rate) | **Berfungsi** — dihitung otomatis per konfigurasi | `:400-562` |
| File output (CSV/JSON) | **Berfungsi** — trades, equity curve, daily, summary | `:565-573` |
| Comparison summary | **Berfungsi** — semua konfigurasi dibandingkan | `:633-675` |

**Data source:** DuckDB `btc_ohlcv_4h` + `market_metrics` (2022-11-18 → 2026-03-04, ~14,400 candles)

### Masalah yang Teridentifikasi

Setelah investigasi kode, ditemukan **7 bias** yang membuat hasil backtest tidak sepenuhnya valid:

| # | Masalah | Bias | Dampak | Kode |
|---|---|---|---|---|
| 1 | **OHLC 4H approximation** — `Low ≤ limit_px` dianggap FILLED, padahal harga cuma sentuh tipis | Positif | ↑ Fill rate, ↑ Profit | `:321-326` |
| 2 | **Tidak cek candle T** — loop mulai dari `i+1`, candle sinyal itu sendiri tidak dicek | Negatif | ↓ Fill rate | `:319` |
| 3 | **SL priority over TP** — dalam satu candle, SL dicek duluan | Negatif | ↓ Profit, ↓ Win Rate | `:85-96` |
| 4 | **Sharpe dari hari dengan trade saja** — hari tanpa trade tidak dimasukkan | Positif | ↑ Sharpe 20-40% | `:495-498` |
| 5 | **Drawdown tanpa MTM** — equity curve hanya dicatat saat exit | Positif | ↓ Max DD 20-50% | `:484-487` |
| 6 | **Skip_until konservatif** — posisi aktif skip sinyal baru | Negatif | ↓ Jumlah trade | `:306-312`, `:372` |
| 7 | **TRAIL_TP terminologi** — exit di close saat TP attain, bukan trailing stop | Minimal | Terminologi | `:89-90`, `:94-95` |

### Keterbatasan Data

| Data | Periode | Resolusi | Tersedia |
|---|---|---|---|
| 4H OHLC (DuckDB) | 2022-11 → 2026-03 | 4 jam | ✅ Full |
| 1H OHLC (parquet) | 2025-10 → 2026-03 | 1 jam | ⚠️ 6 bulan |
| 15s bars (parquet) | 2025-10 → 2026-03 | 15 detik | ⚠️ 6 bulan |
| Tick raw (parquet) | 2026-04-03 (6 jam) | Tick | ❌ Tidak cukup |

---

## PRD: Product Requirements Document

### 1. Problem Statement

Backtest engine saat ini menggunakan **4H OHLC approximation** untuk simulasi limit order entry dan exit. Ini menghasilkan bias positif signifikan karena asumsi "harga touch = order filled" tidak akurat untuk strategi pullback. Risk metrics (Sharpe, DD) juga overestimated karena metodologi perhitungan yang tidak memasukkan hari tanpa trade dan mark-to-market.

**Tujuan:** Bangun dual-layer backtest engine yang memisahkan signal layer (4H) dan execution layer (15s/tick) untuk menghasilkan hasil yang valid, akurat, dan bebas bias struktural.

### 2. Functional Requirements

#### FR-1: Dual-Layer Architecture

- **Signal Layer** (4H): Generate sinyal menggunakan engine v4.4 yang sudah ada (BCD + AI + EMA + Spectrum). Identik dengan yang sekarang.
- **Execution Layer** (15s/tick): Simulasi limit order placement, fill validation, dan exit (SL/TP/TIME_EXIT) dengan resolusi 15 detik.
- Kedua layer harus dari **data source terpisah** — tidak boleh satu DataFrame.

#### FR-2: Tick-by-Tick Execution

- Limit order dipasang di setiap bar 15s setelah sinyal
- Fill terjadi **hanya jika harga benar-benar attain limit price** pada bar 15s tertentu
- No more "sentuh = filled" assumption
- Dukungan partial fill (opsional, fase 2)

#### FR-3: Correct SL/TP Priority

- Dalam 15s execution, urutan SL/TP diketahui persis — tidak ada lagi "SL selalu menang"
- Setiap bar 15s dicek: entry dulu → setelah entry, cek exit
- Exit cek: manapun yang attain duluan (SL atau TP), itu yang dieksekusi

#### FR-4: Batasi Hold Time — Bukan Skip Sinyal

- Ganti `skip_until` dengan pencatatan sinyal terlewat (BLOCKED)
- Catat: berapa banyak sinyal yang terlewat karena posisi aktif
- Tidak perlu concurrent positions — tetap 1 posisi, tapi catat opportunity cost

#### FR-5: Mark-to-Market Harian

- Equity curve dengan MTM harian: equity = cash + mark-to-market posisi terbuka
- MTM = position_notional × (close_today / entry_price - 1)
- Resample ke daily, forward-fill

#### FR-6: Correct Risk Metrics

- Sharpe ratio: semua hari dalam periode (hari tanpa trade = return 0%)
- Max drawdown: dari equity curve harian dengan MTM
- Sortino ratio, Calmar ratio, VaR 95%

#### FR-7: Walk-Forward Validation

- Window: 6 bulan train → 3 bulan test (OOS)
- Geser 3 bulan setiap window
- Minimal 4 window untuk periode 2022-11 → 2026-03
- **Syarat:** Semua metrik harus konsisten antar OOS window

#### FR-8: Verifikasi Engine Baru

Empat tes yang harus lulus sebelum digunakan untuk pengambilan keputusan:
1. **Market entry di engine baru harus identical** dengan engine lama (±1%)
2. **Pullback 0% (pb=0) harus sama dengan market entry**
3. **Fill rate menurun monoton** seiring kenaikan pullback %
4. **Random seed berbeda → variasi < 5%**

### 3. Non-Functional Requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-1 | Execution time | < 30 menit untuk full periode |
| NFR-2 | Reproducibility | Deterministik (seed-based random) |
| NFR-3 | Data isolation | Signal data ≠ execution data |

### 4. Data Requirements

| Data | Sumber | Untuk | Required |
|---|---|---|---|
| 4H OHLC | DuckDB `btc_ohlcv_4h` | Signal generation | ✅ Yes |
| Market metrics | DuckDB `market_metrics` | Signal generation | ✅ Yes |
| 15s bars | `bars15s_2025-*.parquet` | Execution layer | ⚠️ 6 bulan saja |
| 1H OHLC | `ohlcv_1h_6bulan.parquet` | Fallback execution | ⚠️ Alternatif |

**Catatan:** Karena 15s data hanya tersedia untuk Oktober 2025 - Maret 2026, walk-forward hanya bisa dilakukan di periode tersebut. Untuk periode penuh 2022-2025, engine baru bisa fallback ke 1H atau 4H dengan metodologi yang lebih baik dari sekarang (misal: intrabar randomness).

---

## DoD: Definition of Done

### DoD-1: Dual-Layer Architecture

- [ ] `backtest/core/signal_layer.py` — signal generation, identik dengan `capture_signals()` yang sekarang
- [ ] `backtest/core/execution_layer_15s.py` — execution engine dengan 15s bars
- [ ] `backtest/core/execution_layer_4h.py` — fallback execution engine untuk periode tanpa 15s
- [ ] Kedua layer bisa berjalan independen
- [ ] Output sinyal dari signal_layer bisa langsung dimasukkan ke execution_layer

### DoD-2: Tick-by-Tick Execution (15s)

- [ ] Limit order simulation: pasang limit price, cek setiap bar 15s
- [ ] Fill validation: `LONG: price ≤ limit_px` pada bar tertentu → FILLED di bar itu
- [ ] Exit monitoring: setelah FILLED, cek SL/TP setiap bar 15s
- [ ] TIME_EXIT: jika melebihi max_wait (dalam satuan waktu, bukan candle), exit di close price
- [ ] MISS: jika limit tidak attain dalam max_wait
- [ ] Output: entry_price, exit_price, exit_type, hold_time, pnl

### DoD-3: SL/TP Priority Correct

- [ ] Tidak ada prioritas buatan — SL dan TP dicek pada bar yang sama secara sekuensial
- [ ] Yang attain duluan dalam timeline 15s yang dieksekusi
- [ ] Verifikasi: bandingkan dengan tick data (6 jam) untuk sample

### DoD-4: Opportunity Cost Recording

- [ ] Sinyal yang muncul saat posisi aktif dicatat sebagai BLOCKED
- [ ] Statistik: total BLOCKED, potensi PnL yang terlewat
- [ ] Tidak ada sinyal yang di-skip tanpa dicatat

### DoD-5: MTM Harian

- [ ] Fungsi `calculate_daily_equity(trades, daily_ohlcv, initial_capital)`
- [ ] Equity curve dengan resample harian, forward-fill
- [ ] MTM untuk posisi terbuka: `notional * (close_today / entry_price - 1)`
- [ ] Output: DataFrame dengan index date, kolom equity

### DoD-6: Risk Metrics

- [ ] Sharpe ratio: `mean(daily_returns) / std(daily_returns) * sqrt(365)` — **semua hari**
- [ ] Sortino ratio: hanya downside deviation
- [ ] Calmar ratio: CAGR / max drawdown
- [ ] Max drawdown: dari equity curve harian (MTM)
- [ ] Value at Risk 95%: percentile daily returns
- [ ] Profit factor: gross profit / gross loss
- [ ] Average hold time: dalam jam, bukan candle

### DoD-7: Walk-Forward Validation

- [ ] Framework walk-forward: 6 bulan train, 3 bulan test, geser 3 bulan
- [ ] Semua konfigurasi pullback di-test di setiap window
- [ ] Report: metrik per window + rata-rata + standar deviasi
- [ ] **Gate:** Jika ranking pullback config berbeda antara train dan test → warning overfitting

### DoD-8: Verification Tests

- [ ] **Test 1:** Market entry engine baru ≈ engine lama (±1%)
- [ ] **Test 2:** Pullback 0% (pb=0, max_wait=1) ≈ market entry
- [ ] **Test 3:** Fill rate pb=0.1% > pb=0.2% > pb=0.3% > ... (monotonik)
- [ ] **Test 4:** 3 run dengan random seed berbeda → variasi final equity < 5%

### DoD-9: Reporting & Output

- [ ] File output: trades.csv, equity.csv, daily.csv, summary.json (sama seperti sekarang)
- [ ] Tambahan: missed_signals.csv (sinyal BLOCKED)
- [ ] Tambahan: walkforward_report.md (auto-generated)
- [ ] Tambahan: validation_report.md (hasil 4 verification tests)

---

## Perbandingan: Old vs New Engine

| Aspek | Old Engine | New Engine |
|---|---|---|
| **Signal Layer** | 4H, inlined di script utama | 4H, module terpisah `signal_layer.py` |
| **Execution Layer** | 4H, same DataFrame | 15s, data terpisah, module terpisah |
| **Fill Validation** | `Low ≤ limit_px` = filled | Bar-by-bar 15s: price attain limit |
| **SL/TP Priority** | SL always wins | Actual sequence in 15s timeline |
| **Hold Time** | Skip_until = i + hold | Catat sinyal BLOCKED |
| **Equity Curve** | Exit points only | Daily MTM |
| **Sharpe Ratio** | Hanya hari dengan trade | Semua hari (return 0 untuk non-trade day) |
| **Max Drawdown** | Dari equity exit points | Dari equity harian MTM |
| **Validation** | Single window (full period) | Walk-forward multi-window |
| **Data Coverage** | 2022-11 → 2026-03 (4H) | 2025-10 → 2026-03 (15s) + fallback |
| **File Output** | 4 files per config | 4 files + missed log + validation report |

---

## Implementasi Bertahap

| Fase | Apa | Data | Durasi | DoD Check |
|---|---|---|---|---|
| **Fase 1** | Pisahkan signal & execution layer | 4H + 15s | 1-2 hari | DoD-1 |
| **Fase 2** | Tick-by-tick execution engine | 15s | 2-3 hari | DoD-2, DoD-3, DoD-4 |
| **Fase 3** | MTM harian + risk metrics | 1H | 0.5 hari | DoD-5, DoD-6 |
| **Fase 4** | Walk-forward framework | 4H + 15s | 1 hari | DoD-7 |
| **Fase 5** | Verification + reporting | - | 0.5 hari | DoD-8, DoD-9 |
| **Total** | | | **~5-7 hari** | |

---

## Referensi

- Script utama: `backtest/scripts/experiments/pullback_v44_same_engine.py`
- Validitas analisis: `backtest/results/pullback_v44_compare/VALIDITY_ANALYSIS.md`
- Data 4H: DuckDB `btc_ohlcv_4h`
- Data 15s: `Projects/Paper/data/data_historis/bars15s_*.parquet`
- Hasil sekarang: `backtest/results/pullback_v44_compare/`

*Dokumen dibuat: 2026-05-02*
