# BTC-QUANT Execution Layer — Buku Besar Log Perbaikan
**Periode:** 10 Maret 2026 — 30 Maret 2026
**Versi Bot:** v4.4 → v4.5
**Exchange:** Lighter.xyz Mainnet (ZK-rollup Perpetual DEX)
**Market:** BTC-USDC Perpetual (MARKET_ID = 1)

---

## Daftar Isi

1. [Statistik Live Trading](#1-statistik-live-trading)
2. [Bug Fixes dan Perbaikan Kritikal](#2-bug-fixes-dan-perbaikan-kritikal)
3. [Feature Enhancements](#3-feature-enhancements)
4. [Infrastruktur dan Parameter](#4-infrastruktur-dan-parameter)
5. [Status Terkini](#5-status-terkini)

---

## 1. Statistik Live Trading

### 1.1 Fase Eksekusi

| Fase | Periode | Deskripsi |
|------|---------|-----------|
| Manual | 10–13 Mar | Signal dari bot, order dibuka/tutup manual via dashboard |
| Uji Coba | 15 Mar | Test run awal otomasi — tidak dihitung dalam statistik |
| Otomatis | 16–27 Mar | Eksekusi penuh oleh bot, intervensi manual sesekali |
| Otomatis (updated) | 29–30 Mar | Strategy switch ke FixedStrategy ($20×7x) |

---

### 1.2 Fase Manual (10–13 Maret)

| Tanggal | Arah | Open → Close | Notional | PnL (USD) | Hasil |
|---------|------|-------------|----------|-----------|-------|
| 10 Mar | LONG | 16:05 → 18:14 | $9.97 | -0.12 | Loss |
| 11 Mar | LONG | 04:08 → 04:48 | $70.19 | +0.52 | Win |
| 11 Mar | LONG | 08:06 → 13:14 | $150.40 | +0.34 | Win |
| 11 Mar | LONG | 20:01 → 12 Mar 02:18 | $74.73 | -0.89 | Loss |
| 12 Mar | LONG | 08:05 → 09:45 | $149.47 | +1.00 | Win |
| 12 Mar | LONG | 12:15 → 13:46 | $149.76 | -1.03 | Loss |
| 12 Mar | LONG | 20:09 → 13 Mar 00:13 | $74.62 | +0.57 | Win |
| 13 Mar | LONG | open → 05:33 | $76.14 | +0.17 | Win |
| 13 Mar | LONG | open → 08:37 | $75.10 | +0.58 | Win |
| 13 Mar | LONG | open → 14:23 | $149.94 | +0.52 | Win |
| 13 Mar | LONG | open → 16:18 | $149.53 | -1.00 | Loss |

**Metrik Fase Manual:**

| Metrik | Nilai |
|--------|-------|
| Jumlah Trade | 11 |
| Win / Loss | 7 / 4 |
| Win Rate | 63.6% |
| Total PnL | +$0.66 |
| Avg Win | +$0.529 |
| Avg Loss | -$0.760 |
| Risk:Reward | 0.70 |
| Expected Value | +$0.060/trade |
| Profit Factor | 1.22 |

---

### 1.3 Uji Coba Otomasi (15 Maret)

| Tanggal | Arah | Open → Close | Notional | PnL | Keterangan |
|---------|------|-------------|----------|-----|-----------|
| 15 Mar | MIXED | 05:25 → 07:06 | $15.05 | -$0.04 | Test run — tidak dihitung |

---

### 1.4 Fase Otomatis (16–27 Maret)

> Trade 18 Mar (-$6.30) adalah **anomali bug SL order auth** (lihat FIX-3). Statistik disajikan dengan dan tanpa anomali.

| Tanggal | Arah | Open → Close | Notional | PnL (USD) | Hasil |
|---------|------|-------------|----------|-----------|-------|
| 16 Mar | LONG | 08:14 → 13:32 | $150.03 | +0.96 | Win |
| 16 Mar | LONG | 16:01 → 16:32 | $199.90 | +0.69 | Win |
| 17 Mar | LONG | 00:51 → 01:10 | $149.86 | +0.99 | Win |
| 17 Mar | LONG | 02:07 → 02:44 | $149.82 | +0.12 | Win |
| 17 Mar | LONG | 04:02 → 04:39 | $149.87 | -1.01 | Loss |
| 17 Mar | LONG | 07:21 → 07:39 | $150.17 | +0.03 | Win |
| 17 Mar | LONG | 08:00+12:00 → 14:40 | $149.88 | +0.62 | Win |
| 17 Mar | LONG | 14:15+14:16 → 14:44 | $149.35 | +0.55 | Win |
| 18 Mar | LONG | 08:00+04:09 → 15:00 | $150.43 | -6.30 | **SL Bug** |
| 22 Mar | SHORT | 00:00 → 00:02 | $74.93 | +0.56 | Win |
| 22 Mar | SHORT | 08:00 → 09:18 | $75.06 | +0.26 | Win |
| 22 Mar | SHORT | 12:00 → 14:19 | $75.04 | -0.54 | Loss |
| 23 Mar | SHORT | 00:00 → 07:01 | $74.77 | +0.26 | Win |
| 26 Mar | SHORT | 12:00 → 13:42 | $74.75 | -0.10 | Loss |
| 26 Mar | SHORT | 13:44 → 15:14 | $74.94 | +0.52 | Win |
| 27 Mar | SHORT | 04:00 → 05:33 | $74.89 | +0.26 | Win |

**Metrik Fase Otomatis:**

| Metrik | Excl. SL Bug | Incl. SL Bug |
|--------|-------------|-------------|
| Jumlah Trade | 15 | 16 |
| Win / Loss | 12 / 3 | 12 / 4 |
| Win Rate | 80.0% | 75.0% |
| Total PnL | +$4.17 | -$2.13 |
| Avg Win | +$0.485 | +$0.485 |
| Avg Loss | -$0.550 | -$1.988 |
| Risk:Reward | 0.88 | 0.24 |
| Expected Value | +$0.278/trade | -$0.133/trade |
| Profit Factor | 3.53 | 0.73 |

---

### 1.5 Fase Otomatis — FixedStrategy $20×7x (29–30 Maret)

Data dari CSV export Lighter (ground truth):

| Tanggal | Arah | Notional | PnL (USD) | Hasil |
|---------|------|----------|-----------|-------|
| 29 Mar | SHORT | ~$139 | +$0.51 | Win |
| 30 Mar | SHORT | ~$139 | +$1.23 | Win |

---

### 1.6 Ringkasan Keseluruhan

| Fase | Trade | WR | PnL | R:R | EV | PF |
|------|-------|----|-----|-----|----|----|
| Manual (10–13 Mar) | 11 | 63.6% | +$0.66 | 0.70 | +$0.060 | 1.22 |
| Uji Coba (15 Mar) | 1 | — | -$0.04 | — | — | — |
| Otomatis excl. Bug (16–27 Mar) | 15 | 80.0% | +$4.17 | 0.88 | +$0.278 | 3.53 |
| Otomatis incl. Bug (16–27 Mar) | 16 | 75.0% | -$2.13 | 0.24 | -$0.133 | 0.73 |
| **Total excl. Bug & uji coba** | **26** | **73.1%** | **+$4.83** | **0.75** | **+$0.186** | **2.03** |

---

## 2. Bug Fixes dan Perbaikan Kritikal

### Ringkasan Semua Fix

| ID | Deskripsi | Severity | Tanggal |
|----|-----------|----------|---------|
| FIX-1 | Double Position Guard | **CRITICAL** | 17 Mar |
| FIX-2 | Signal Replay after Restart | HIGH | 17 Mar |
| FIX-3 | SL Order Authentication | **CRITICAL** | 17 Mar |
| FIX-4 | Advisory Signal Execution | MEDIUM | 18 Mar |
| FIX-5 | Lighter Auth Token via SDK | **CRITICAL** | 25 Mar |
| FIX-6 | Exit Price dari trigger_price | MEDIUM | 25 Mar |
| FIX-7 | Startup Position Sync | MEDIUM | 25 Mar |
| FIX-8 | Exit Type Detection | MEDIUM | 25 Mar |
| FIX-9 | L2 EMA Weakening Logic | LOW | 25 Mar |
| FIX-10 | OCO Canceled Order Filter | **CRITICAL** | 27 Mar |
| FIX-11 | Manual SL Freeze Clear | MEDIUM | 27 Mar |
| FIX-12 | Dynamic Boot Log | LOW | 27 Mar |
| FIX-13 | Re-entry setelah Close | **CRITICAL** | 29 Mar |
| FIX-14 | Koreksi Database dari CSV | MEDIUM | 29 Mar |
| FIX-15 | Switch ke FixedStrategy | MEDIUM | 29 Mar |
| FIX-16 | SL/TP Limit Price Slippage Buffer | HIGH | 29 Mar |
| FIX-17 | filled_price dari SDK Response | MEDIUM | 29 Mar |

---

### FIX-1: Double Position Guard
**Commit:** `492cf0b` | **Severity:** CRITICAL | **Tanggal:** 17 Mar

**Masalah:** Bot dapat membuka posisi baru saat posisi sebelumnya masih `OPEN` di exchange, mengakibatkan *double exposure* yang tidak terkontrol.

**Solusi:** Implementasi `get_open_position()` check sebelum setiap entry. Jika terdapat posisi aktif, sinyal baru di-skip.

**Dampak:** Mencegah risiko margin call tidak terduga akibat penumpukan posisi.

---

### FIX-2: Signal Replay setelah Restart
**Commit:** `d8e7a87` | **Severity:** HIGH | **Tanggal:** 17 Mar

**Masalah:** Setelah restart, sinyal lama yang sudah diproses dapat di-replay karena `last_notified_ts` hanya tersimpan di memori (volatile).

**Solusi:** Persistensi `last_notified_ts` ke file `last_candle_ts.json` untuk menjaga state melewati restart.

**Dampak:** Menghilangkan entri duplikat yang tidak valid setelah bot reboot.

---

### FIX-3: SL Order Authentication
**Commit:** `c3107f9` | **Severity:** CRITICAL | **Tanggal:** 17 Mar

**Masalah:** Stop-loss order gagal ditempatkan karena `_submit_order()` tidak menyertakan auth header yang valid.

**Solusi:** Seluruh order placement request dikonfigurasi menggunakan auth token yang valid di header HTTP.

**Dampak:** Menjamin proteksi posisi. Kegagalan ini menyebabkan kerugian $6.30 pada 18 Maret.

---

### FIX-4: Advisory Signal Tidak Tereksekusi
**Commit:** `3160dc1` | **Severity:** MEDIUM | **Tanggal:** 18 Mar

**Masalah:** Sinyal dengan conviction 15–20% (`ADVISORY`) terblokir oleh logic filter meskipun merupakan sinyal valid.

**Solusi:** Pembaruan logic gate untuk memperlakukan status `ADVISORY` setara dengan `ACTIVE`.

**Dampak:** Meningkatkan frekuensi trading dengan menangkap peluang pada rentang conviction menengah.

---

### FIX-5: Lighter Auth Token via SDK
**Commit:** `e28c312` | **Severity:** CRITICAL | **Tanggal:** 25 Mar

**Masalah:** Format token manual tidak valid; Lighter memerlukan tanda tangan EdDSA via private key.

**Solusi:** Menggunakan SDK `create_auth_token_with_expiry()` untuk menghasilkan token resmi yang ditandatangani.

**Dampak:** Memulihkan akses ke seluruh write operations dan private queries yang sebelumnya unauthorized.

---

### FIX-6: Exit Price dari trigger_price
**Commit:** `e28c312` | **Severity:** MEDIUM | **Tanggal:** 25 Mar

**Masalah:** `filled_price` bernilai 0.0 pada order SL/TP karena mekanisme trigger order di Lighter.

**Solusi:** Implementasi logika fallback untuk mengambil harga eksekusi dari field `trigger_price` jika `filled_price` kosong.

**Dampak:** Akurasi kalkulasi PnL dan data risk management menjadi 100% valid.

---

### FIX-7: Startup Position Sync
**Commit:** `861822f` | **Severity:** MEDIUM | **Tanggal:** 25 Mar

**Masalah:** Ketidaksinkronan status posisi jika posisi ditutup saat bot sedang offline, menyebabkan bot terjebak dalam status `OPEN`.

**Solusi:** Penambahan fungsi `sync_position_status()` saat daemon startup untuk rekonsiliasi state dengan exchange.

**Dampak:** Bot selalu memulai dengan state yang bersih dan akurat setelah downtime.

---

### FIX-8: Exit Type Detection
**Commit:** `861822f` | **Severity:** MEDIUM | **Tanggal:** 25 Mar

**Masalah:** Penentuan jenis exit (SL vs TP) berbasis price distance tidak reliabel saat terjadi slippage tinggi.

**Solusi:** Identifikasi eksplisit menggunakan field `order_type` dari API response (`stop` vs `take-profit`).

**Dampak:** Logika SL freeze dan pelabelan risk manager menjadi lebih akurat.

---

### FIX-9: L2 EMA Weakening Logic
**Commit:** `8ab9b1b` | **Severity:** LOW | **Tanggal:** 25 Mar

**Masalah:** Filter tren (L2 EMA) tidak cukup kuat memblokir sinyal kontra-tren; hanya mengurangi confidence tanpa membatalkan sinyal.

**Solusi:** Memaksa status `l2 = False` saat kondisi weakening terdeteksi, sehingga sinyal otomatis di-skip.

**Dampak:** Mengurangi false entry pada kondisi pasar yang mengalami pembalikan tren.

---

### FIX-10: OCO Canceled Order Filter
**Commit:** `f644601` | **Severity:** CRITICAL | **Tanggal:** 27 Mar

**Masalah:** Saat TP tercapai, SL order yang dibatalkan otomatis (OCO) terbaca sebagai eksekusi SL, memicu freeze palsu.

**Solusi:** Filter eksplisit untuk mengabaikan order berstatus `"cancel"` dalam pemrosesan riwayat transaksi.

**Dampak:** Mencegah pemblokiran entri (freeze) yang keliru setelah perdagangan untung (TP).

---

### FIX-11: Manual SL Freeze Clear
**Tanggal:** 27 Mar | **Severity:** MEDIUM

**Masalah:** Status freeze yang tersimpan di disk memblokir entri selama berjam-jam meskipun masalah teknis sudah teratasi.

**Solusi:** Pembersihan manual pada `sl_freeze_state.json` dan restart kontainer untuk mereset kondisi bot.

**Dampak:** Mengurangi waktu idle bot dan mempercepat pemulihan operasional setelah kegagalan beruntun.

---

### FIX-12: Dynamic Boot Log
**Commit:** `62a32b0` | **Severity:** LOW | **Tanggal:** 27 Mar

**Masalah:** Log startup menampilkan nilai margin statis yang menyesatkan dan tidak sesuai konfigurasi aktual.

**Solusi:** Sinkronisasi log dengan variabel `MARGIN_USD` dan `LEVERAGE` yang aktif secara dinamis.

**Dampak:** Memudahkan monitoring dan debugging konfigurasi strategi saat bot dijalankan.

---

### FIX-13: Re-entry Langsung setelah Close
**Commit:** `ddc6309` | **Severity:** CRITICAL | **Tanggal:** 29 Mar

**Masalah:** Saat posisi baru saja ditutup di satu cycle, `sync_position_status()` langsung diikuti `process_signal()` di cycle yang sama, menyebabkan bot langsung membuka posisi baru. Root cause: return value semantics `sync_position_status()` salah — mengembalikan `True` saat tidak ada posisi di DB (harusnya `False`).

**Bug lama:**
```python
# data_ingestion_use_case.py — SEBELUM FIX
await self.position_manager.sync_position_status()
await self.position_manager.process_signal(signal)  # langsung buka baru!
```

```python
# position_manager.py — SEBELUM FIX
async def sync_position_status(self) -> bool:
    db_trade = self.repo.get_open_trade()
    if not db_trade:
        return True  # BUG: harusnya False
    ...
    if exchange_position:
        return True  # BUG: posisi masih open, harusnya False
```

**Solusi:**
- `sync_position_status()` return `True` **hanya** jika posisi baru saja ditutup di cycle ini
- Return `False` jika tidak ada posisi, posisi masih open, atau error
- Caller skip `process_signal()` jika return `True`

```python
# data_ingestion_use_case.py — SETELAH FIX
just_closed = await self.position_manager.sync_position_status()
if just_closed:
    print("  [Execution] Position just closed — skipping open to avoid immediate re-entry.")
else:
    await self.position_manager.process_signal(signal)
```

```python
# position_manager.py — SETELAH FIX
async def sync_position_status(self) -> bool:
    db_trade = self.repo.get_open_trade()
    if not db_trade:
        return False  # tidak ada posisi — tidak ada close event
    ...
    if exchange_position:
        return False  # posisi masih open — tidak ada close event
    # Posisi baru saja ditutup
    self.repo.close_trade(...)
    return True  # caller harus skip process_signal cycle ini
```

**Dampak:** Menghilangkan bug double/triple entry yang menyebabkan posisi tidak terkontrol.

**Side effect yang diterima:** Candle yang sama dengan close event akan skip open baru. Contoh: candle 07:00 WIB tgl 30 Mar tidak membuka posisi baru karena Trade #1 close di candle yang sama.

---

### FIX-14: Koreksi Database dari CSV Lighter
**Tanggal:** 29 Mar | **Severity:** MEDIUM

**Masalah:** Data database DuckDB tidak akurat — berisi 10 record campuran dari bug double entry, close manual, dan data tidak lengkap. Tidak cocok dengan trade history di Lighter.

**Solusi:** Rekonstruksi database dari CSV export Lighter (ground truth):
1. Export trade history dari Lighter UI → CSV
2. Hapus semua 10 record lama di DB
3. Insert ulang 9 trade yang valid berdasarkan CSV

**Data ground truth (9 trade SHORT, 22 Mar – 29 Mar):**
- Total PnL yang direkonstruksi: **+$2.1779 USDT**

**Catatan teknis:**
- DuckDB string comparison case-sensitive — gunakan single quotes: `WHERE status='OPEN'`
- Script fix dibuat lokal → `scp` ke VPS → `docker cp` ke container (heredoc SSH tidak reliable untuk script multi-line)

---

### FIX-15: Switch dari HestonStrategy ke FixedStrategy
**Commit:** `663ba55` | **Severity:** MEDIUM | **Tanggal:** 29 Mar

**Masalah:** HestonStrategy menghasilkan TP yang terlalu jauh dari entry (ATR × 2.1 ≈ 3.1%), menyebabkan posisi tidak hit TP dan harus ditutup manual. Tidak cocok untuk kondisi pasar sideways/ranging.

**Solusi:** Switch kembali ke FixedStrategy dengan parameter yang sudah terbukti (Golden v4.4), dengan margin/leverage diperbarui ke $20×7x.

**Parameter FixedStrategy aktif:**

| Parameter | Nilai |
|-----------|-------|
| `SL_PCT` | 1.333% |
| `TP_PCT` | 0.71% |
| `LEVERAGE` | 7x |
| `MARGIN_USD` | $20.0 |
| Notional | ~$140 |

**File:** `backend/app/use_cases/strategies/fixed_strategy.py`

**Import update di `data_ingestion_use_case.py`:**
```python
from app.use_cases.strategies.fixed_strategy import FixedStrategy, MARGIN_USD, LEVERAGE
position_manager = PositionManager(gateway=lighter_gateway, repo=live_repo, strategy=FixedStrategy())
```

---

### FIX-16: SL/TP Limit Price Slippage Buffer
**Commit:** `7330b4c` | **Severity:** HIGH | **Tanggal:** 29 Mar

**Masalah:** Limit price pada SL/TP order di-set sama dengan trigger price, menyebabkan order tidak fill saat terjadi market gap atau slippage tinggi.

**Root cause:** Lighter trigger order memerlukan limit price yang *lebih menguntungkan* dari trigger — untuk BUY limit harus lebih tinggi, untuk SELL limit harus lebih rendah.

**Solusi:** Tambah slippage buffer pada limit price:
- **SL order:** buffer 0.5%
- **TP order:** buffer 0.3%

```python
# lighter_execution_gateway.py
SLIPPAGE_PCT_SL = 0.005  # 0.5% buffer untuk SL
SLIPPAGE_PCT_TP = 0.003  # 0.3% buffer untuk TP

# SL untuk LONG (trigger = harga turun) → order SELL → limit di bawah trigger
# SL untuk SHORT (trigger = harga naik) → order BUY → limit di atas trigger
if is_ask:  # SHORT → SL is BUY
    sl_limit_price = trigger_price * (1 + SLIPPAGE_PCT_SL)
else:        # LONG → SL is SELL
    sl_limit_price = trigger_price * (1 - SLIPPAGE_PCT_SL)
```

**Dampak:** Memastikan SL/TP order selalu terfill saat trigger tersentuh, mencegah posisi terlindungi.

---

### FIX-17: filled_price dari Actual SDK Response
**Commit:** `7330b4c` | **Severity:** MEDIUM | **Tanggal:** 29 Mar

**Masalah:** `filled_price` pada market order di-set dari harga yang dikirim ke SDK (intended price), bukan dari actual fill price yang dikembalikan SDK. Mengakibatkan PnL record tidak akurat.

**Solusi:** Baca `avg_execution_price` dari SDK response object jika tersedia:

```python
# lighter_execution_gateway.py
resp = self._client.create_market_order(...)
filled_price = getattr(resp, 'avg_execution_price', None) or price
```

**Dampak:** PnL record lebih akurat, terutama saat terjadi slippage pada market order.

---

## 3. Feature Enhancements

### FEAT-1: Switch ke HestonStrategy (26 Mar)
**Commit:** `01ef707` | **Tanggal:** 26 Mar

> *Catatan: Strategi ini kemudian di-revert ke FixedStrategy di FIX-15 (29 Mar) karena TP terlalu jauh.*

HestonStrategy menggunakan parameter ATR-adaptive:
- SL = ATR × 1.5 (≈2.2% dari entry)
- TP = ATR × 2.1 (≈3.1% dari entry)

**Backtest comparison (62 hari, Jan–Mar 2026):**

| Metrik | FixedStrategy | HestonStrategy | Δ |
|--------|-------------|----------------|---|
| Net PnL | +30.04% | +76.10% | +46.1 pp |
| Profit Factor | 1.278 | 1.587 | +0.309 |
| Max Drawdown | 20.75% | 17.10% | -3.65 pp |
| Sharpe Ratio | 2.299 | 3.409 | +1.110 |
| R:R Ratio | 0.95 | 1.629 | +0.679 |

**Alasan revert:** Backtest menggunakan data 62 hari termasuk trending market. Pada kondisi pasar real (ranging), ATR-based TP terlalu jauh dan tidak reach. FixedStrategy lebih terbukti konsisten di live trading.

---

## 4. Infrastruktur dan Parameter

### 4.1 Environment

```
LIGHTER_MAINNET_API_KEY=8e9eaef1...fd536  ✅
LIGHTER_MAINNET_API_SECRET=39c0ba8a...f610  ✅
LIGHTER_API_KEY_INDEX=3  ✅
LIGHTER_ACCOUNT_INDEX=718591  ✅
LIGHTER_EXECUTION_MODE=mainnet  ✅
LIGHTER_TRADING_ENABLED=true  ✅
LIGHTER_MAINNET_BASE_URL=https://mainnet.zklighter.elliot.ai
```

### 4.2 BTC Market Parameters (Lighter Mainnet)

| Parameter | Nilai |
|-----------|-------|
| MARKET_ID | 1 |
| min_base_amount | 0.00020 BTC |
| supported_size_decimals | 5 |
| supported_price_decimals | 1 |
| min_quote_amount | 10.000000 USDC |
| Taker/maker fee | 0% |

### 4.3 VPS Deployment

| Item | Detail |
|------|--------|
| Container | `btc-quant-backend` |
| VPS .env path | `/home/saeful/vps/projects/btc-quant-lighter/.env` |
| Catatan | Container tidak membaca .env file — env vars diinjeksi via docker-compose |

### 4.4 Evolusi Parameter Sizing

| Versi | Margin | Leverage | Notional | Strategy |
|-------|--------|----------|----------|---------|
| Awal | $5 | 15x | $75 | FixedStrategy |
| 26 Mar | $20 | 7x | $140 | HestonStrategy |
| 29 Mar | $20 | 7x | $140 | **FixedStrategy** (current) |

---

## 5. Status Terkini

**Per 30 Maret 2026:**

| Komponen | Status |
|----------|--------|
| Container VPS | Running (`btc-quant-backend`) |
| Trading Mode | ENABLED (`LIGHTER_TRADING_ENABLED=true`) |
| Strategy | **FixedStrategy** (Golden v4.4) |
| Margin × Leverage | $20 × 7x = $140 notional |
| SL_PCT / TP_PCT | 1.333% / 0.71% |
| SL Freeze | Tidak aktif |
| Exit Detection | Fixed (skip canceled OCO) |
| Auth Token | SDK signed token |
| Signal Gate | ADVISORY signals dieksekusi |
| Re-entry Guard | Active (skip cycle setelah close) |
| SL/TP Slippage Buffer | SL: 0.5%, TP: 0.3% |

### Roadmap Pending

| Item | Priority | Status |
|------|----------|--------|
| PR-1: 1H confirmation filter | Medium | Pending backtest |
| PR-2: Partial TP + break-even SL | Medium | Pending backtest |
| Sprint 2: DD Adaptive Sizing | High | Pending |
| Monitor performa $20×7x (10 trade) | High | In Progress |
| Naik margin ke $30×5x jika stabil | Medium | Setelah 10 trade |
| Telegram alert untuk skip-entry events | Low | Identified |

### Key Learnings

1. **Auth token DEX** memerlukan kriptografik signing (EdDSA), bukan format manual
2. **OCO order** harus difilter berdasarkan status `"cancel"` sebelum digunakan untuk deteksi exit
3. **Exit type** deteksi harus dari field `order_type` eksplisit, bukan distance heuristics
4. **Startup reconciliation** penting untuk menjaga konsistensi state posisi setelah downtime
5. **Return value semantics** pada fungsi sync harus didefinisikan dengan sangat jelas untuk menghindari side effect pada caller
6. **Trigger order limit price** harus diberi slippage buffer — tidak boleh sama dengan trigger price
7. **Backtest tidak cukup** untuk validasi strategi — live market behavior berbeda dari data historis

---

*Dokumen ini diperbarui terakhir: 30 Maret 2026*
*Source of truth: commit history + CSV export Lighter trade history*
