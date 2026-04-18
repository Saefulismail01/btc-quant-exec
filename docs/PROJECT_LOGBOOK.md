# 📓 BTC-QUANT: Project Logbook & Evolution

Dokumen ini berfungsi sebagai *single source of truth* untuk melacak progres, keputusan arsitektur, dan update terbaru dalam pengembangan BTC-QUANT.

---

## 🚀 Status Saat Ini: v4.8 + Trailing SL & Order ID Tracking
**Update Terakhir:** 12 April 2026
**Status Eksekusi:** Live di Lighter Mainnet ✅
**Strategy Aktif:** Signal Executor + Intraday Monitor (Trailing SL 15m)
**Execution Mode:** Signal Executor (API hanya generate signal)

### 🔝 Key Updates (v4.8 — 12 April 2026)

**Root Cause:** Bot masih kena SL 2x dalam satu hari karena SL freeze tidak bekerja di signal executor. SL freeze logic ada di API (PositionManager) tapi signal executor eksekusi langsung ke Lighter tanpa cek freeze state.

**Implementasi Order ID Tracking & Trailing SL:**

1. **Order ID Tracking** (`signal_executor.py`)
   - Tambah `ORDER_IDS_FILE` path: `execution_layer/lighter/order_ids.json`
   - Implement `load_order_ids()`, `save_order_ids()`, `clear_order_ids()`
   - Simpan order IDs (entry, SL, TP) setelah eksekusi trade
   - Clear order IDs ketika posisi close atau tidak ada posisi

2. **SL Order Update Logic** (`trailing_sl.py`)
   - Implement `cancel_order(order_id, nonce)` untuk cancel SL order by transaction hash
   - Implement `update_sl_order(position, new_sl_price)` dengan pattern cancel + create:
     - Load SL order ID dari file
     - Cancel existing SL order
     - Create new SL order dengan harga trailing
     - Update order IDs di file
   - Implement trailing SL logic: trail jika profit > 1%, lock minimal 0.5% profit

3. **Intraday Monitor Integration** (`intraday_monitor.py`)
   - Add order ID clearing ketika posisi close
   - Add `clear_order_ids()` function
   - Clear order IDs di monitoring cycle ketika tidak ada posisi
   - Clear order IDs setelah manual close position

4. **Unit Tests** (`tests/test_order_id_tracking.py`)
   - 8 unit tests untuk order ID tracking logic
   - Test save/load/clear dan error handling
   - Semua tests pass (95/95 total tests including trailing SL & SL freeze tests)

5. **SL Freeze di Signal Executor** (`signal_executor.py`)
   - Implement SL freeze check di `run_cycle()` sebelum entry
   - Load freeze state dari `sl_freeze_state.json` (shared dengan API)
   - Block entry jika freeze aktif sampai 07:00 WIB besok

**Deployment & Architecture Change:**

6. **Disable PositionManager Execution**
   - Set `LIGHTER_TRADING_ENABLED=false` di `.env` VPS
   - API (PositionManager) hanya generate signal, tidak eksekusi trade
   - Mencegah double entry antara API dan signal executor

7. **Enable Signal Executor + Intraday Monitor**
   - Enable `signal-executor` service di docker-compose.yml
   - Enable `intraday-monitor` service di docker-compose.yml
   - Set `LIGHTER_TRADING_ENABLED=true` untuk signal executor (override .env)
   - Deploy ke VPS dengan LIVE TRADING mode

8. **Bug Fix: Intraday Monitor Minute Overflow**
   - Fix error `ValueError: minute must be in 0..59` di perhitungan next check time
   - Handle overflow ketika next_quarter >= 60 (tambah 1 jam dan reset minute ke 0)

**Perubahan file:**
1. `execution_layer/lighter/signal_executor.py` - Order ID tracking + SL freeze check
2. `execution_layer/lighter/trailing_sl.py` - SL order update (cancel + create) + trailing logic
3. `execution_layer/lighter/intraday_monitor.py` - Order ID clearing + minute overflow fix
4. `execution_layer/lighter/tests/test_order_id_tracking.py` - Unit tests baru
5. `docker-compose.yml` - Enable signal-executor & intraday-monitor services
6. `.env` (VPS) - Set `LIGHTER_TRADING_ENABLED=false` untuk API

**Setup Baru:**
- API (btc-quant-api) = Generate signal only (PositionManager execution disabled)
- Signal Executor = Eksekusi trade ke Lighter + SL freeze check + Order ID tracking
- Intraday Monitor = Trailing SL 15m cycle + Early exit detection
- SL Freeze State = Shared file `sl_freeze_state.json` antara API dan signal executor
- Order ID State = File `order_ids.json` untuk tracking SL/TP orders

**Commits:**
- `f4bcf62` - Disable signal-executor, intraday-monitor, lighter-executor
- `6880c6a` - Enable intraday-monitor for trailing SL
- `79e2066` - Update TRAILING_SL_README.md with deployment status
- `9264d02` - Enable signal executor with LIVE TRADING mode + fix intraday monitor bug

### 🔝 Key Updates (v4.7 — 08 April 2026)

**Root Cause:** Tanggal 7 April 2026 jam 03:00 WIB, bot tidak entry padahal ada signal BUY. Investigasi docker logs menemukan dua bug:

**Bug 1: SL Freeze salah trigger saat SL = breakeven**
- SL dipindah manual ke breakeven setelah trade >8 jam
- SL hit di $68,870 (di atas entry $68,570) → PnL sebenarnya hampir 0
- Bot tetap trigger SL freeze sampai 07:00 WIB berikutnya → signal jam 03:00 WIB di-block
- **Fix:** SL freeze sekarang hanya aktif kalau `pnl_usdt < 0`. SL breakeven/profit tidak freeze.

**Bug 2: PnL calculation salah (formula lokal vs data Lighter)**
- `_calculate_pnl` pakai `TAKER_FEE_RATE = 0.0002` (0.02%) tapi Lighter charge jauh lebih tinggi
- Hasil: bot lapor +$1.84 padahal Lighter show -$0.12 (selisih ~$2)
- **Fix:** PnL sekarang diambil langsung dari fill amount Lighter (`exit_filled_quote - entry_filled_quote`). Formula lokal hanya sebagai fallback jika data fill tidak tersedia.

**Perubahan file:**
1. `lighter_execution_gateway.py`
   - `fetch_last_closed_order` sekarang return `filled_quote` dan `filled_base`
   - Tambah method `fetch_entry_fill_quote()` — dipanggil setelah `place_market_order`
2. `live_trade_repository.py`
   - Tambah field `entry_filled_quote` (USDC yang dibayar saat entry)
   - Migration aman: `ALTER TABLE` yang silent-fail untuk DB existing
3. `position_manager.py`
   - Setelah market order fill → `fetch_entry_fill_quote()` dan simpan ke DB
   - Saat close → `pnl = exit_filled_quote - entry_filled_quote` (Lighter fills)
   - SL freeze: `if exit_type == "SL" and pnl_usdt < 0` (bukan any SL)

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

- **[2026-04-12]** Session: Order ID Tracking & Trailing SL Implementation (v4.8).
    - **Root Cause:** Bot kena SL 2x dalam satu hari karena SL freeze tidak bekerja di signal executor. SL freeze logic ada di API tapi signal executor eksekusi langsung tanpa cek freeze state.
    - **Implementasi Order ID Tracking:** Tambah `load_order_ids()`, `save_order_ids()`, `clear_order_ids()` di `signal_executor.py` untuk tracking SL/TP order IDs ke file `order_ids.json`.
    - **SL Order Update Logic:** Implement `cancel_order()` dan `update_sl_order()` di `trailing_sl.py` dengan pattern cancel + create untuk update SL order secara dinamis.
    - **Trailing SL Logic:** Trail SL jika profit > 1%, lock minimal 0.5% profit. Step size 0.25% per trailing update.
    - **Intraday Monitor Integration:** Add order ID clearing di `intraday_monitor.py` untuk clear order IDs ketika posisi close.
    - **SL Freeze di Signal Executor:** Implement SL freeze check di signal executor untuk block entry setelah SL hit sampai 07:00 WIB besok.
    - **Unit Tests:** 8 unit tests untuk order ID tracking, total 95/95 tests pass (termasuk trailing SL & SL freeze tests).
    - **Architecture Change:** Disable PositionManager execution (`LIGHTER_TRADING_ENABLED=false`), enable signal executor untuk eksekusi trade + SL freeze + order ID tracking.
    - **Deployment:** Deploy signal executor + intraday monitor ke VPS dengan LIVE TRADING mode. Fix intraday monitor minute overflow bug.
    - **Commits:** `f4bcf62`, `6880c6a`, `79e2066`, `9264d02`.

- **[2026-04-11]** Session: Exchange-First Architecture Fix & Cloud Core Research Engine.
    - **Exchange-First Architecture:** Implementasi architecture baru di mana Lighter exchange adalah source of truth untuk position status (bukan database). Triple-check sebelum close position di DB.
    - **False Position Closure Bug Fix:** Tambah timestamp validation di `fetch_last_closed_order` untuk mengabaikan order lama. Tambah `position_open_time` parameter untuk mencegah matching pre-position orders.
    - **Position Status Notification:** Implement `notify_position_status` untuk notifikasi status posisi yang sudah terbuka.
    - **SL Freeze Trailing SL Fix:** Perbaikan SL freeze logic untuk trailing SL di backend.
    - **Telegram Blocked Entry Notifications:** Implement notifikasi Telegram ketika entry diblok (SL freeze, dll).
    - **Cloud Core Research Engine:** Implementasi `cloud_core/` sebagai mini core engine untuk research (L1-L4 only, tanpa executor).
        - Layer 1: BCD (Bayesian Changepoint Detection)
        - Layer 2: EMA (Exponential Moving Average)
        - Layer 3: MLP/XGBoost/RandomForest/LightGBM/LSTM/Logistic/Advanced/Rules (alternatives)
        - Layer 4: Risk Management
        - Spectrum Engine: Ensemble voting
        - Live/Paper Executor untuk testing
    - **Self-Contained Testing System:** Cloud core bisa berjalan independent di cloud VMs tanpa dependency ke backend.
    - **Colab Core Notebook:** Implementasi `colab_core.ipynb` untuk research di Google Colab.
    - **Directory Cleanup:** Reorganisasi directory structure - pindahkan old stuff ke `archive/`, docs ke `docs/`, scripts ke `archive/scripts/`.
    - **Docker Fixes:**
        - Fix Docker numpy<2 dependency conflict untuk lighter-sdk
        - Fix executor-specific requirements tanpa pandas-ta untuk lighter-sdk compatibility
        - Fix Python path untuk executor containers - copy backend ke /app dan set PYTHONPATH
    - **Backtest Research Scripts:** Multiple scripts untuk evaluasi BCD confidence, precision filter, layer accuracy, meta classifier.
    - **Commits:** `cb88781`, `dfad4e5`, `64ffb55`, `e424772`, `9259f8d`, `0f4dd35`, `ed09709`, `59e3617`, `56c0b9b`.

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

## 🎯 Fokus Saat Ini: Monitoring Trailing SL & Order ID Tracking (v4.8)

### Status Lighter Execution
| Task | Status | Note |
|---|---|---|
| Riset Dokumentasi API Lighter | ✅ DONE | |
| Phase 1-4: API Client, Nonce, Execution | ✅ DONE | Live di mainnet sejak 17 Mar |
| Auth Token Fix | ✅ DONE | 25 Mar — SDK signed token |
| Exit Price Fix | ✅ DONE | 25 Mar — trigger_price fallback |
| Startup Sync | ✅ DONE | 25 Mar |
| HestonStrategy Live | ✅ DONE | 26 Mar — $5 margin, ATR-adaptive |
| Exchange-First Architecture | ✅ DONE | 11 Apr — Exchange sebagai source of truth, triple-check |
| False Position Closure Fix | ✅ DONE | 11 Apr — Timestamp validation, position_open_time |
| Position Status Notification | ✅ DONE | 11 Apr — Notify status posisi terbuka |
| SL Freeze Trailing SL Fix | ✅ DONE | 11 Apr — Perbaikan SL freeze untuk trailing SL |
| Telegram Blocked Entry Notifications | ✅ DONE | 11 Apr — Notifikasi ketika entry diblok |
| Cloud Core Research Engine | ✅ DONE | 11 Apr — Mini core engine untuk research (L1-L4) |
| Colab Core Notebook | ✅ DONE | 11 Apr — Single-file notebook untuk Google Colab |
| Directory Cleanup | ✅ DONE | 11 Apr — Reorganisasi struktur direktori |
| Docker Fixes (numpy, pandas-ta, PYTHONPATH) | ✅ DONE | 11 Apr — Perbaikan dependency dan path |
| Backtest Research Scripts | ✅ DONE | 11 Apr — Evaluasi BCD, layer accuracy, meta classifier |
| Order ID Tracking | ✅ DONE | 12 Apr — Track SL/TP order IDs untuk trailing SL |
| SL Order Update (Cancel+Create) | ✅ DONE | 12 Apr — Update SL order secara dinamis |
| Trailing SL Logic | ✅ DONE | 12 Apr — Trail jika profit > 1%, lock 0.5% |
| Intraday Monitor | ✅ DONE | 12 Apr — 15m monitoring cycle untuk trailing SL |
| SL Freeze di Signal Executor | ✅ DONE | 12 Apr — Block entry setelah SL hit |
| Architecture Change (Signal Executor) | ✅ DONE | 12 Apr — Signal executor eksekusi, API hanya generate signal |

### Next Action (Priority)
1. **Monitor Trailing SL** — validasi trailing SL bekerja dengan baik pada live trading
2. **Monitor SL Freeze** — pastikan SL freeze bekerja di signal executor (block entry setelah SL hit)
3. **Validasi Order ID Tracking** — pastikan order IDs tersimpan dengan benar dan SL update berhasil
4. **Monitor Intraday Monitor** — pastikan 15m cycle berjalan smooth tanpa error
5. **Analisis Performa Trailing SL** — bandingkan performa dengan vs tanpa trailing SL setelah 10-20 trades

---

## ⚠️ Tantangan & Risiko (Watchlist)
- **Bear Market WR**: Win Rate di bear market (47.1%) perlu ditingkatkan agar lebih stabil.
- **Data Leakage Check**: Memastikan tidak ada lookahead bias pada model MLP v4.4.
- **Lighter Nonce Sensitivity**: Sistem nonce Lighter sangat ketat, butuh manajemen state yang presisi.
- **Trailing SL Gap Risk**: Cancel + create SL order ada jeda tanpa proteksi (meskipun singkat, ~3 detik).
- **Order ID State Consistency**: Pastikan order IDs selalu sinkron antara signal executor dan intraday monitor.
- **SL Freeze Sync**: Freeze state shared antara API dan signal executor perlu dipastikan konsisten.

---
*Log ini diperbarui setiap kali ada perubahan signifikan pada arsitektur atau status proyek.*
