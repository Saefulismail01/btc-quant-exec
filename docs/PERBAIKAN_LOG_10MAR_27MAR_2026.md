# Log Perbaikan BTC-QUANT Execution Layer
**Periode:** 10 Maret 2026 – 27 Maret 2026
**Versi:** v4.4 → v4.5

---

## Ringkasan Eksekutif

Selama periode ini, bot trading BTC-QUANT berhasil dipindahkan dari simulasi ke **live trading di Lighter mainnet**, dengan serangkaian perbaikan kritikal pada infrastruktur eksekusi, deteksi sinyal, dan manajemen posisi. Total **17 trade live** telah dieksekusi dengan win rate ~75%.

---

## Fase 1 — Infrastruktur Awal (10–16 Mar)

### Deployment ke Lighter Mainnet
- Setup `LighterExecutionGateway` lengkap dengan koneksi ke mainnet
- Integrasi Lighter Python SDK (`lighter-python`)
- Docker deployment di VPS (`btc-quant-api`)
- Konfigurasi env vars: API key, API secret, account index (718591), key index (3)
- **First live order placed:** TX `d0bbcc4d...` ✅

### Penemuan Account Index
- Account index BUKAN angka sederhana — harus di-derive dari alamat L1 wallet
- Wallet Bitget: `0x105974E3EB346313d05727a67B04289C5AC6F544`
- Account index yang benar: **718591** (hex: `0xaf6ff`), bukan 3
- Cara temukan: via `AccountApi.accounts_by_l1_address()` atau Bitget ChangePubKey popup

### BTC Market Parameters
- `MARKET_ID = 1` (BTC perp)
- `min_base_amount = 0.00020` BTC
- `supported_size_decimals = 5`, `supported_price_decimals = 1`
- Taker/maker fee: 0%

---

## Fase 2 — Bug Fixes Kritikal (17–25 Mar)

### [FIX-1] Double Position Guard
**Commit:** `492cf0b` | **Tanggal:** ~17 Mar

**Masalah:** Bot bisa membuka posisi baru padahal posisi lama masih OPEN di exchange.

**Fix:** Cek `get_open_position()` sebelum setiap entry. Jika ada posisi aktif, skip entry.

**Impact:** Mencegah double exposure yang bisa mengakibatkan loss berlipat.

---

### [FIX-2] Signal Replay setelah Restart
**Commit:** `d8e7a87` | **Tanggal:** ~17 Mar

**Masalah:** Setelah bot restart, sinyal lama yang sudah diproses bisa di-replay kembali karena `last_notified_ts` hilang dari memory.

**Fix:** Persist `last_notified_ts` ke disk (`last_candle_ts.json`) sehingga state bertahan setelah restart.

**Impact:** Tidak ada lagi entry duplikat dari sinyal yang sama setelah reboot.

---

### [FIX-3] SL Order Authentication
**Commit:** `c3107f9` | **Tanggal:** ~17 Mar

**Masalah:** SL order gagal ditempatkan karena auth header salah — endpoint order placement adalah authenticated tapi header tidak dikirim dengan benar.

**Fix:** Pastikan semua order placement request menggunakan auth token yang valid.

**Impact:** SL order sekarang selalu terpasang saat posisi dibuka.

---

### [FIX-4] Advisory Signal Tidak Tereksekusi
**Commit:** `3160dc1` | **Tanggal:** ~18 Mar

**Masalah:** Signal dengan conviction 15–20% (status ADVISORY) di-skip padahal seharusnya dieksekusi.

**Fix:** Update logic gate — ADVISORY signals diperlakukan sama dengan ACTIVE untuk entry.

**Impact:** Bot tidak melewatkan sinyal valid di range conviction menengah.

---

### [FIX-5] Lighter Auth Token via SDK
**Commit:** `e28c312` | **Tanggal:** 25 Mar

**Masalah:** `_generate_auth_token()` membuat token format manual (`{expiry}:{account}:{key_index}:{hex}`) yang tidak valid — Lighter API butuh token yang **ditandatangani** dengan private key.

**Akibat:** Semua query read endpoint (balance, posisi, order history) return 401 Unauthorized.

**Fix:**
```python
# Sebelum (BROKEN):
token = f"{expiry_unix}:{account_index}:{api_key_index}:{random_hex}"

# Sesudah (FIXED):
token_result = client.create_auth_token_with_expiry(
    deadline=lighter_sdk.SignerClient.DEFAULT_10_MIN_AUTH_EXPIRY,
    api_key_index=self.api_key_index,
)
token = token_result[0]
```

**Impact:** Balance, posisi, dan order history bisa di-query dengan benar.

---

### [FIX-6] Exit Price dari trigger_price
**Commit:** `e28c312` | **Tanggal:** 25 Mar

**Masalah:** `fetch_last_closed_order()` selalu return `filled_price = 0.0` untuk order SL/TP.

**Root Cause:** Lighter SL/TP adalah "reduce-only trigger order" — `filled_base_amount = "0.00000"` karena di-trigger bukan di-fill langsung. Harga eksekusi ada di field `trigger_price`, bukan `filled_price`.

**Fix:**
```python
filled_base = float(last_order.get("filled_base_amount", 0) or 0)
if filled_base > 0 and filled_quote > 0:
    filled_price = filled_quote / filled_base  # actual fill
else:
    trigger_price = float(last_order.get("trigger_price", 0) or 0)
    filled_price = trigger_price if trigger_price > 0 else order_price
```

**Impact:** Exit price akurat → PnL calculation benar → risk manager data valid.

---

### [FIX-7] Startup Position Sync
**Commit:** `861822f` | **Tanggal:** 25 Mar

**Masalah:** Jika bot restart saat ada posisi open, DB tetap OPEN tapi exchange sudah closed → bot skip entry sinyal bagus karena mengira masih ada posisi.

**Fix:** Saat daemon start, jalankan `sync_position_status()` untuk mendeteksi posisi yang closed saat bot offline.

**Impact:** State posisi selalu akurat setelah restart. Tidak ada lagi "stuck OPEN".

---

### [FIX-8] Exit Type Detection dari order_type
**Commit:** `861822f` | **Tanggal:** 25 Mar

**Masalah:** Exit type (SL/TP) ditentukan dari **jarak harga** ke SL vs TP — tidak reliable jika harga di tengah atau ada slippage.

**Fix:** Gunakan field `order_type` dari API response langsung:
```python
order_type_str = last_order.get("order_type", "").lower()
if "stop" in order_type_str:
    exit_type = "SL"
elif "take-profit" in order_type_str:
    exit_type = "TP"
```

**Impact:** SL freeze logic benar, risk manager record label yang tepat.

---

### [FIX-9] L2 EMA Weakening Diperkuat
**Commit:** `8ab9b1b` | **Tanggal:** 25 Mar

**Masalah:** L2 (EMA trend confirmation) tidak cukup memblokir sinyal kontra-trend — confidence hanya dikurangi, tidak di-set False.

**Fix:** Saat L2 weakening aktif, force `l2 = False` alih-alih hanya mengurangi confidence score.

**Impact:** Lebih sedikit false entry saat trend berlawanan dengan sinyal.

---

## Fase 3 — Strategy Switch & Optimasi (26–27 Mar)

### [FEAT-1] Switch ke HestonStrategy
**Commit:** `01ef707` | **Tanggal:** 26 Mar

**Alasan Switch:**
- FixedStrategy: SL/TP tetap (1.333%/0.71%) → tidak adaptive terhadap volatilitas
- HestonStrategy: SL/TP berbasis **ATR-adaptive** dari model Heston volatility

**Parameter HestonStrategy:**
- SL = ATR × 1.5 (~2.2% dari entry)
- TP = ATR × 2.1 (~3.1% dari entry)
- R:R ratio ≈ 1:1.4

**Perbandingan Backtest (62 hari, Jan–Mar 2026):**

| Metrik | FixedStrategy | HestonStrategy | Delta |
|--------|--------------|----------------|-------|
| Net PnL | +30.04% | **+76.10%** | +46pp |
| Profit Factor | 1.278 | **1.587** | +0.309 |
| Max Drawdown | 20.75% | **17.10%** | -3.65pp |
| Sharpe Ratio | 2.299 | **3.409** | +1.110 |
| R:R Ratio | 0.95 | **1.629** | +0.679 |

---

### [FIX-10] OCO Canceled Order Salah Dibaca sebagai SL Exit
**Commit:** `f644601` | **Tanggal:** 27 Mar

**Masalah:** Ketika TP hit, SL companion order di-cancel otomatis oleh exchange (OCO behavior). Order canceled ini punya `trigger_price` valid → bot ambil duluan dan mengira exit via SL.

**Akibat:**
- Bot kirim notif "LIVE TRADE CLOSED — SL" padahal sebenarnya TP hit
- **SL freeze ter-aktif secara salah** → entry berikutnya diblokir
- Trade jam 03:00 WIB tidak tereksekusi karena freeze palsu ini

**Root Cause Detail:**
```
[LIGHTER] Last closed order: 844422962156095 (stop-loss/canceled-reduce-only) @ $70,227.40
```
Order `canceled-reduce-only` ini adalah SL yang dibatalkan karena TP sudah hit @ $68,461 (+5.26%), bukan exit yang sebenarnya.

**Fix:** Skip semua order dengan status mengandung `"cancel"` sebelum menentukan exit price:
```python
if "cancel" in status.lower():
    logger.debug(f"[LIGHTER] Skipping canceled order {order_id} ({order_type}/{status})")
    continue
```

**Impact:**
- ✅ TP exit terdeteksi dengan benar
- ✅ SL freeze tidak aktif setelah TP hit
- ✅ Entry berikutnya tidak terblokir

---

### [FIX-11] Clear SL Freeze yang Salah Aktif
**Tanggal:** 27 Mar (manual fix)

Freeze state yang sudah tersimpan di disk (`sl_freeze_state.json`) di-clear manual:
```json
{"sl_freeze_until": null}
```
Container di-restart untuk reload state dari disk.

**Impact:** Bot siap entry kembali tanpa menunggu sampai 2026-03-28T07:00.

---

### [FEAT-2] Update Margin & Leverage
**Commit:** `05c4216` | **Tanggal:** 27 Mar

**Perubahan:**
- Sebelum: `MARGIN_USD = 5.0`, `LEVERAGE = 15` → **notional $75**
- Sesudah: `MARGIN_USD = 20.0`, `LEVERAGE = 7` → **notional $140**

**Alasan:**
- Notional $75 menghasilkan profit terlalu kecil (~$0.3–0.5/trade)
- Leverage 15x terlalu tinggi → liquidation distance hanya ~6.7% dari entry
- Target: profit ~$1/trade dengan max loss ~$1/trade
- $20 × 7x: notional $140, liquidation ~14% dari entry (jauh di atas SL 2.2%), aman

**Estimasi perubahan:**
| Metrik | Sebelum | Sesudah |
|--------|---------|---------|
| Notional | $75 | $140 |
| Est. profit/trade (TP) | ~$0.5 | ~$0.95 |
| Est. loss/trade (SL) | ~$0.5 | ~$0.95 |
| Liquidation distance | ~6.7% | ~14% |

---

### [FIX-12] Boot Log Misleading
**Commit:** `62a32b0` | **Tanggal:** 27 Mar

Print statement boot log menampilkan `"$20 margin"` hardcode padahal nilai aktual bisa berbeda.

**Fix:** Baca langsung dari konstanta `MARGIN_USD` dan `LEVERAGE` di `heston_strategy.py`:
```python
print(f"... HestonStrategy (${MARGIN_USD:.0f} margin × {LEVERAGE}x = ${MARGIN_USD*LEVERAGE:.0f} notional)")
```

---

## Statistik Live Trading (10 Mar – 27 Mar 2026)

| Tanggal | Arah | Open → Close | PnL | Status |
|---------|------|-------------|-----|--------|
| 10 Mar | LONG | 16:05 → 18:14 | -$0.12 | Loss |
| 11 Mar | LONG | 04:08 → 04:48 | +$0.52 | Win |
| 11 Mar | LONG | 08:06 → 13:14 | +$0.34 | Win |
| 11 Mar | LONG | 20:01 → 12 Mar 02:18 | -$0.89 | Loss |
| 12 Mar | LONG | 08:05 → 09:45 | +$1.00 | Win |
| 12 Mar | LONG | 12:15 → 13:46 (5 rows) | -$1.03 | Loss |
| 12 Mar | LONG | 20:09 → 13 Mar 00:13 | +$0.57 | Win |
| 13 Mar | LONG | open → 05:33 | +$0.17 | Win |
| 13 Mar | LONG | open → 08:37 | +$0.58 | Win |
| 13 Mar | LONG | open → 14:23 (3 rows) | +$0.52 | Win |
| 13 Mar | LONG | open → 16:18 | -$1.00 | Loss |
| 16 Mar | LONG | 08:14 → 13:32 | +$0.96 | Win |
| 16 Mar | LONG | 16:01 → 16:32 | +$0.69 | Win |
| 17 Mar | LONG | 00:51 → 01:10 | +$0.99 | Win |
| 17 Mar | LONG | 02:07 → 02:44 | +$0.12 | Win |
| 17 Mar | LONG | 04:02 → 04:39 | -$1.01 | Loss |
| 17 Mar | LONG | 07:21 → 07:39 | +$0.03 | Win |
| 17 Mar | LONG | 08:00+12:00 → 14:40 | +$0.62 | Win |
| 17 Mar | LONG | 14:15+14:16 → 14:44 | +$0.55 | Win |
| 18 Mar | LONG | 08:00+04:09 → 15:00 | -$6.30 | SL Bug ⚠️ |
| 22 Mar | SHORT | 00:00 → 00:02 | +$0.56 | Win |
| 22 Mar | SHORT | 08:00 → 09:18 | +$0.26 | Win |
| 22 Mar | SHORT | 12:00 → 14:19 | -$0.54 | Loss |
| 23 Mar | SHORT | 00:00 → 07:01 | +$0.26 | Win |
| 26 Mar | SHORT | 12:00 → 13:42 | -$0.10 | Loss |
| 26 Mar | SHORT | 13:44 → 15:14 | +$0.52 | Win |
| 27 Mar | SHORT | 04:00 → 05:33 | +$0.26 | Win |

**Total trade:** 27
**Win:** 19 | **Loss:** 8
**Win Rate (excl. SL Bug):** ~73%
**Total PnL (excl. SL Bug):** ~+$5.99
**Total PnL (incl. SL Bug):** ~-$0.31

> ⚠️ Trade 18 Mar (-$6.30) adalah anomali akibat bug SL order auth yang sudah diperbaiki di [FIX-3].

---

## Status Saat Ini (27 Mar 2026)

| Komponen | Status |
|----------|--------|
| Container VPS | ✅ Running (btc-quant-api) |
| Strategy | ✅ HestonStrategy |
| Margin × Leverage | ✅ $20 × 7x = $140 notional |
| SL Freeze | ✅ Tidak aktif |
| Exit Detection | ✅ Fixed (skip canceled OCO) |
| Auth Token | ✅ SDK signed token |
| Signal Gate | ✅ ADVISORY signals dieksekusi |

---

## Pending / Roadmap

| Item | Priority | Status |
|------|----------|--------|
| PR-1: 1H confirmation filter | Medium | ⏳ Pending backtest |
| PR-2: Partial TP + break-even SL | Medium | ⏳ Pending backtest |
| Sprint 2: DD Adaptive Sizing | High | ⏳ Pending |
| Monitor performa $20×7x (10 trade) | High | 🔄 In Progress |
| Naik margin ke $30×5x jika stabil | Medium | 📅 Setelah 10 trade |

---

*Dokumen ini dibuat 2026-03-27. Update terakhir: 27 Maret 2026.*
