# 📓 BTC-QUANT: Project Logbook & Evolution

Dokumen ini berfungsi sebagai *single source of truth* untuk melacak progres, keputusan arsitektur, dan update terbaru dalam pengembangan BTC-QUANT.

---

## 🚀 Status Saat Ini: v4.6 + Exchange-to-DB Sync + Lighter Live
**Update Terakhir:** 06 April 2026
**Status Eksekusi:** Live di Lighter Mainnet ✅
**Strategy Aktif:** FixedStrategy (Golden v4.4) — ($99 margin, 5x leverage, No LLM)

### 🔝 Key Updates (v4.6 — 06 April 2026)

1. **Telegram Bot Enhancements** — Menambahkan command `/signal` (detail konfluensi) dan `/balance` (query saldo exchange rill).
2. **Neutral Regime Guard Fix** — Perbaikan bug `l1_vote` di mana kondisi neutral terbaca sebagai bearish.
3. **Architecture Cleanup** — Sinkronisasi penuh dokumen (LEDGER) dengan kode rill v4.6 (Tabel Arsitektur & Risk Rules).
4. **Shadow Logging Improvement** — Peningkatan detail log untuk monitoring *Shadow Trades*.

### 🔝 Key Updates (v4.5 — 25-26 Maret 2026)

**Execution Layer Fixes (semua di commit 2026-03-25):**
1. **Lighter Auth Token** — Fix 401 error: ganti manual token format ke SDK `create_auth_token_with_expiry()`. Balance/position query sekarang berfungsi.
2. **Exit Price Fix** — `filled_price` selalu 0.0 karena SL/TP Lighter adalah reduce-only trigger order. Fix: gunakan `trigger_price` sebagai fallback.
3. **Startup Position Sync** — Bot restart tidak lagi stuck dengan DB OPEN saat posisi sudah closed di exchange.
4. **Exit Type Detection** — Ganti distance comparison ke `order_type` field langsung (stop-loss/take-profit). SL freeze logic sekarang akurat.

**Signal Quality Fix:**
5. **L2 EMA Weakening Diperkuat** — Force `l2 = False` (bukan sekadar reduce confidence) saat:
   - RSI > 68 (BULL) atau RSI < 32 (BEAR)
   - EMA distance < 0.2 ATR
   - EMA20 ≈ EMA50 (gap < 0.1%) → ambiguous zone

**Strategy Upgrade:**
6. **Switch ke HestonStrategy** — FixedStrategy (SL 1.333% / TP 0.71% fixed, R:R ~1:0.5) diganti HestonStrategy (ATR-adaptive SL/TP, R:R Normal 1:1.33). Margin $5, leverage 15x untuk live testing.

**Dokumentasi baru:**
- `docs/research/SIGNAL_FIX_LOG.md` — log lengkap semua fix dengan before/after

---

### 🔝 Key Updates (v4.4)
1.  **Fix #1: L3 Disagreement Logic** - MLP NEUTRAL sekarang menjadi counter-signal (-0.3) terhadap BCD BULL/BEAR.
2.  **Fix #2: Weight Calibration** - Mengembalikan bobot ke standar emas: **L1=0.30, L2=0.25, L3=0.45**.
3.  **Fix #3: Momentum Exhaustion** - Implementasi RSI & Proximity filter pada Layer 2.
4.  **OPT-A (1-Candle Target)** - Perpindahan target MLP ke 4H (1 candle) untuk presisi scalping yang lebih tinggi.

### 🎯 Code Quality Improvements (13 Maret 2026)
**Status:** Execution Layer Hardened ✅

**Review Findings**: 39 issues identified across 3 critical files
- **Critical Issues Fixed**: 7/7 ✅
- **High Priority Issues Fixed**: 3/3 ✅
- **Medium Improvements**: 5/5 ✅

**Key Fixes Implemented**:
1. **Gateway Resource Leak** - Try-finally blocks prevent connection exhaustion
2. **Signal Handler Race** - asyncio.Event ensures thread-safe shutdown
3. **Position Exit Detection** - Heuristic + API query fallback for accurate tracking
4. **PnL Fee Deduction** - Now accounts for 0.04% taker fees (entry+exit)
5. **SL Failure Recording** - Emergency closes properly recorded to DB
6. **Risk Manager Balance** - Uses actual account equity instead of fixed margin
7. **Paper Executor Safeguards** - Position limits (5 max), signal timeout (30s), loss tracking

**TODO Items Implemented**:
1. ✅ `fetch_account_nonce()` - Server nonce synchronization
2. ✅ `fetch_last_closed_order()` - Accurate exit detection from actual fills
3. ✅ `close_all_positions()` - Graceful shutdown with position closure

**Commits**:
- `edd8ff5` - Fix 10 critical code review issues
- `439d12a` - Implement 3 TODO items from review

---

## 🛠️ Riwayat Implementasi (Timeline)

### April 2026

- **[2026-04-06]** Session: Fix "Inconsistency" & Real-time Exchange Sync (v4.6).
    - Implementasi `fetch_open_orders` dan `get_active_sl_tp` di `LighterExecutionGateway`.
    - Implementasi `update_trade_params` di `LiveTradeRepository` untuk sinkronisasi harga.
    - Sinkronisasi otomatis SL/TP di `PositionManager.sync_position_status()` agar bot tidak lagi "buta" terhadap perubahan manual di dashboard bursa.
    - Audit label notifikasi: Menemukan konflik di mana status `ADVISORY` (10-20% conviction) memberikan sinyal "WAIT" di Telegram namun tetap dilakukan "ENTRY" oleh bot.

- **[2026-04-01]** Session: Execution Robustness Optimization.
    - **Re-entry Prevention**: Menambahkan proteksi di `data_ingestion_use_case.py` agar bot tidak langsung masuk ke posisi baru (re-entry) di *candle* yang sama setelah sebuah posisi tertutup. Mengurangi risiko *churn* pada volatilitas tinggi.
    - **Shadow Monitoring Integration**: Menambahkan modul `shadow_monitor.py` untuk melacak performa teoretis sinyal bot terhadap performa riil (manual) untuk audit reliabilitas.

### Maret 2026

- **[2026-03-26]** Session: Strategy Heston Adaptive & Mainnet Optimization.
    - **HestonStrategy Deployment**: Mengganti `FixedStrategy` dengan `HestonStrategy`. SL/TP kini bersifat dinamis berdasarkan ATR-Adaptive dan volatilitas stokastik model Heston.
    - **Risk Manager Balance Sync**: `PositionManager` kini mengambil saldo riil dari bursa untuk menghitung *position sizing* yang lebih akurat, bukan lagi berdasarkan nilai margin statis.

- **[2026-03-25]** Session: Critical Lighter Gateway Fixes.
    - **Auth Token Fix**: Migrasi ke SDK native `create_auth_token_with_expiry()`. Menghilangkan error 401 Unauthorized secara permanen.
    - **OCO Cancel Handling**: Perbaikan `fetch_last_closed_order` untuk otomatis mengabaikan (skip) order yang berstatus "Canceled" saat mendeteksi *exit price*. Menghindari kesalahan pencatatan harga keluar saat salah satu kaki OCO (SL atau TP) terpicu.
    - **Startup Sync Robustness**: Perbaikan logika sinkronisasi saat bot baru menyala; bot sekarang memprioritaskan status bursa daripada status database yang mungkin *stale*.

- **[2026-03-17]** Session: Mainnet live trading + bug fixes + PR-2 + diskusi PR-1 & exit strategy.

  **Walk-Forward Test (Confluence Spectrum v2)**
  - Dijalankan ulang karena ada perubahan BCD, EMA direction fix, dan BOCPD posterior fix
  - Data: 8000 candles (2022–2026), 3 window (2023 Full, 2024 H2, 2025–2026)
  - Hasil rata-rata per variasi:
    | Var | WR | Daily | DD | PF |
    |-----|-----|-------|-----|-----|
    | V0 (BCD only) | 66.7% | +0.619% | -16.8% | 2.29 |
    | V1 (BCD+EMA, production) | 66.2% | +0.575% | -13.3% | 2.18 |
    | V2 (BCD+EMA+MLP) | 65.2% | +0.467% | -15.0% | 2.12 |
    | V3 (EMA+MLP) | 67.1% | +0.561% | -17.1% | 2.33 |
    | V4 (All layers, ACTIVE gate) | 66.5% | +0.350% | -12.5% | 2.23 |
  - **Best by PF**: V3. **Best DD**: V4. **Production (V1)**: balance antara DD dan return.

  **Deployment Lighter Mainnet**
  - Container di-deploy ulang dengan `LIGHTER_TRADING_ENABLED=true`
  - CRLF issue pada `.env` di VPS menyebabkan API key kosong → fix: `sed -i 's/\r$//' .env`
  - Order pertama berhasil live: LONG BTC, SL & TP placed via SDK native methods
  - Beberapa fix gateway: endpoint `/orderBooks`, `/orderBookDetails`, auth header removal, SDK URL strip `/api/v1`

  **PR-2: Entry Position Guard** ✅ DEPLOYED
  - Commit: `492cf0b`
  - Logika:
    1. Posisi terbuka → skip entry baru
    2. SL hit → freeze entry sampai 07:00 WIB keesokan harinya (persist ke disk `sl_freeze_state.json`)
    3. TP hit → freeze di-clear, boleh entry berikutnya segera
  - Sudah live di VPS

  **Diskusi: Trailing Stop**
  - Lighter SDK tidak punya native trailing stop
  - Manual trailing (cancel+replace SL) berisiko: ada jeda tanpa proteksi
  - **Keputusan: tidak implement** untuk sistem scalping ini

  **Diskusi: TP terlalu cepat (harga lanjut naik setelah TP hit)**
  - Root cause: TP fixed 0.71% terlalu konservatif saat momentum kuat
  - Solusi yang diusulkan: **Partial TP** (TP1 50% @ 0.71%, TP2 50% @ ~1.5-2%, SL geser ke breakeven setelah TP1)
  - **Status: belum diputuskan** — perlu analisis data historis dulu

  **Diskusi: PR-1 (1H Confirmation)**
  - Masalah: entry di close 4H = sering beli di pucuk
  - Solusi: 4H signal = "permission window" (4 jam), entry baru saat 1H konfirmasi (pullback ke EMA20_1H + bullish close)
  - Alasan valid secara trading: better RR, hindari FOMO entry, multi-TF confluence
  - **Status: belum implement** — disarankan backtest simulasi dulu sebelum production

- **[2026-03-13]** Code Review & Quality Hardening (COMPLETED).
    - Comprehensive code review: 39 issues identified
    - Fixed 10 critical/high priority issues in execution layer
    - Implemented 3 TODO items (nonce fetch, order query, shutdown)
    - Project structure refactoring: cleaned root, organized docs, standardized paths
    - Ready for testnet validation

- **[2026-03-13]** Inisialisasi proyek **Lighter Execution Layer**.
    - Selesai melakukan riset dokumentasi API Lighter (Nonce, Scaling, SDK).
    - Pembuatan PRD & DoD awal untuk integrasi Lighter.

- **[2026-03-12]** Validasi Bear Market (Jan 2023 - Des 2023).
    - Hasil: Win Rate 57.14% secara keseluruhan, namun Bear Regime masih di 47.1%.

- **[2026-03-11]** Penyelesaian Phase 3 Binance Live Execution.
    - Implementasi Emergency Stop, Telegram Notifications, dan Status API.

### Februari 2026
- **[2026-02-27]** Re-training model MLP dengan input Cross-Feature HMM.
- **[2026-02-25]** Migrasi dari HMM tradisional ke **Bayesian Changepoint Detection (BCD)** sebagai Layer 1.

---

## 📅 Next Steps (Per 2026-03-17)

| Priority | Item | Status |
|----------|------|--------|
| 1 | Backtest PR-1: simulasi 1H confirmation filter pada sinyal historis | ⏳ PENDING |
| 2 | Analisis Partial TP: berapa % trade lanjut >1.5% setelah TP1 hit | ⏳ PENDING |
| 3 | Implement PR-1 jika backtest hasilnya positif | 📅 BACKLOG |
| 4 | Implement Partial TP jika analisis mendukung | 📅 BACKLOG |

---

## 🔬 Riwayat Pengujian Terakhir (Validation Metrics)

### 1. Robustness Validation: Bear Market (2022-11-18 sd 2023-12-31)
*   **Metode**: Walk-forward backtest menggunakan data historical 4H yang belum pernah dilihat model (Out-of-Sample).
*   **Parameter**: Bobot 0.3/0.25/0.45, Margin $1,000, Leverage 15x.
*   **Hasil Performa**:
    *   **Total Return**: +49.2%
    *   **Win Rate (Overall)**: 57.14% (455 trades)
    *   **Sharpe Ratio**: 1.267
    *   **Max Drawdown**: -17.73% (Improvement dari v3 yang -22.48%)
*   **Metrik Operasional Tambahan**:
    *   **Profit Factor**: **1.296** (Setiap $1 kerugian tertutup oleh $1.29 keuntungan).
    *   **Avg Trade PnL**: +$48.70 per trade (Mencerminkan "edge" positif setelah biaya).
    *   **Exit Distribution**:
        *   **SL (Stop Loss)**: 32.5%
        *   **TP (Take Profit)**: 29.2%
        *   **TRAIL_TP (Trailing)**: 24.8% (Penjaga profit saat trend kuat).
        *   **TIME_EXIT (24h)**: 13.4% (Safety net jika market stagnant).
    *   **Avg Duration**: 8.5 jam (Sesuai dengan target scalping 2-candle cycles).
*   **Analisa Performa per Regime**:
    *   **Bull Regime**: 58.8% WR (Profit memuaskan)
    *   **Neutral Regime**: 64.2% WR (Performa terbaik, bot sangat stabil di sideways)
    *   **Bear Regime**: 47.1% WR (**Weak Spot**, win rate di bawah 50% menunjukkan model masih butuh tuning untuk kondisi crash agresif).

### 2. Bull Market Benchmarking (2024-01-01 sd 2026-03-04)
*   **Metode**: Perbandingan Fix #1 (L3 Counter-Signal) vs Baseline.
*   **Analisa Performa**:
    *   **Win Rate**: Naik dari 58.1% menjadi **60.1%** (+2.0%).
    *   **Sharpe Ratio**: Naik signifikan dari 2.248 menjadi **2.712** (+20.6%).
    *   **Kesimpulan**: Fix #1 berhasil mengurangi "fake entries" dengan menggunakan L3 sebagai rem saat terjadi ketidakcocokan data teknikal dengan rezim pasar.

---

## 🎯 Fokus Saat Ini: Stabilisasi Live + Sprint 2-4

### Status Lighter Execution
| Task | Status | Note |
|---|---|---|
| Riset Dokumentasi API Lighter | ✅ DONE | |
| Phase 1-4: API Client, Nonce, Execution | ✅ DONE | Live di mainnet sejak 17 Mar |
| Auth Token Fix | ✅ DONE | 25 Mar — SDK signed token |
| Exit Price Fix | ✅ DONE | 25 Mar — trigger_price fallback |
| Startup Sync | ✅ DONE | 25 Mar |
| HestonStrategy Live | ✅ DONE | 26 Mar — $5 margin, ATR-adaptive |

### Roadmap Sprint (dari DOD v4)
| Sprint | Target | Status | Blocking? |
|--------|--------|--------|-----------|
| Sprint 1: Exit Management | R:R ≥ 1.8, DD ≤ 15% | ✅ DONE (backtest) | — |
| Sprint 2: DD Adaptive Sizing | DD ≤ 20%, Sharpe ≥ 1.8 | ⏳ PENDING | Butuh equity tracking live |
| Sprint 3: Signal Quality | WR ≥ 52%, Bear WR ≥ 52% | ⏳ PENDING | Setelah Sprint 2 |
| Sprint 4: Frequency | ≥ 1 trade/hari | ⏳ PENDING | Setelah Sprint 3 |

### Next Action (Priority)
1. **Monitor HestonStrategy** — validasi 5-10 trade live ($5 margin)
2. **Naikkan margin** ke $10-20 kalau 5 trade pertama profitable
3. **Implement Sprint 2** — DD adaptive sizing (graduated risk reduction)
4. **Leverage 3-5x** — setelah Sprint 2 deployed dan DD terkontrol

---

## ⚠️ Tantangan & Risiko (Watchlist)
- **Bear Market WR**: Win Rate di bear market (47.1%) perlu ditingkatkan agar lebih stabil.
- **Data Leakage Check**: Memastikan tidak ada lookahead bias pada model MLP v4.4.
- **Lighter Nonce Sensitivity**: Sistem nonce Lighter sangat ketat, butuh manajemen state yang presisi.

---

## 📅 Rencana Langkah Berikutnya (Action Items)
1.  **Phase 1 Lighter**: Setup `LighterExecutionGateway` yang mendukung Testnet.
2.  **MLP Deep-dive**: Analisis *feature importance* untuk memahami mengapa Bear Market WR rendah.
3.  **Cross-Validation**: Implementasi Walk-Forward kembali untuk memvalidasi bobot 0.3/0.25/0.45 di data 2022.

---
*Log ini diperbarui setiap kali ada perubahan signifikan pada arsitektur atau status proyek.*
