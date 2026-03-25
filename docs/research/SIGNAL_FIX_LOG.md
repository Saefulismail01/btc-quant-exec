# Signal Fix Log — BTC-QUANT v4.4

Dokumen ini mencatat semua perbaikan yang telah dilakukan pada signal engine,
execution layer, dan infrastruktur bot setelah forward test 15-25 Mar 2026.

---

## Status Keseluruhan

| Fix | File | Status | Tanggal |
|-----|------|--------|---------|
| Lighter auth token (SDK) | lighter_execution_gateway.py | ✅ DONE | 2026-03-25 |
| Exit price dari trigger_price | lighter_execution_gateway.py | ✅ DONE | 2026-03-25 |
| Startup position sync | data_ingestion_use_case.py | ✅ DONE | 2026-03-25 |
| Exit type dari order_type field | position_manager.py | ✅ DONE | 2026-03-25 |
| L2 weakening diperkuat | signal_service.py | ✅ DONE | 2026-03-25 |
| PR-1: 1H confirmation filter | - | ⏳ PENDING backtest | - |
| PR-2: Partial TP strategy | - | ⏳ PENDING backtest | - |
| Sprint 2: DD adaptive sizing | - | ⏳ PENDING | - |

---

## Fix Detail

---

### [FIX-EXEC-1] Lighter Auth Token via SDK
**Tanggal:** 2026-03-25
**File:** `backend/app/adapters/gateways/lighter_execution_gateway.py`
**Commit:** `e28c312`

**Masalah:**
- `_generate_auth_token()` membuat token format manual: `{expiry}:{account}:{key_index}:{random_hex}`
- Format ini tidak valid untuk Lighter API → 401 error pada semua query read endpoint
- Bot tidak bisa query balance, position, atau order history

**Root Cause:**
- Lighter API butuh token yang **ditandatangani** (signed) dengan API private key
- Token manual tidak punya signature → rejected

**Fix:**
```python
# Sebelum (BROKEN):
auth_token = f"{expiry_unix}:{account_index}:{api_key_index}:{random_hex}"

# Sesudah (FIXED):
token_result = client.create_auth_token_with_expiry(
    deadline=lighter_sdk.SignerClient.DEFAULT_10_MIN_AUTH_EXPIRY,
    api_key_index=self.api_key_index,
)
token = token_result[0]  # SDK returns tuple
```

**Impact:**
- ✅ Balance query berfungsi: $97.30
- ✅ Position query berfungsi
- ✅ Order history query berfungsi

---

### [FIX-EXEC-2] Exit Price dari trigger_price
**Tanggal:** 2026-03-25
**File:** `backend/app/adapters/gateways/lighter_execution_gateway.py`
**Commit:** `e28c312`

**Masalah:**
- `fetch_last_closed_order()` selalu return `filled_price = 0.0`
- Bot menghitung PnL berdasarkan harga 0 → corrupt data
- Risk manager membaca PnL salah → keputusan berikutnya cacat

**Root Cause:**
- Lighter SL/TP order adalah "reduce-only trigger order"
- `filled_base_amount = "0.00000"` karena order di-trigger bukan di-fill langsung
- Harga eksekusi sebenarnya ada di field `trigger_price` atau `price`

**Fix:**
```python
# Sebelum: hanya baca filled_base_amount (selalu 0 untuk SL/TP)
filled_price = float(last_order.get("filled_price", 0))  # WRONG

# Sesudah: fallback ke trigger_price untuk SL/TP orders
filled_base = float(last_order.get("filled_base_amount", 0) or 0)
if filled_base > 0:
    filled_price = filled_quote / filled_base  # actual fill
else:
    trigger_price = float(last_order.get("trigger_price", 0) or 0)
    filled_price = trigger_price if trigger_price > 0 else float(last_order.get("price", 0))
```

**Impact:**
- ✅ Exit price akurat: `$67,372.80` (TP trigger price)
- ✅ PnL calculation benar
- ✅ Risk manager data valid

---

### [FIX-EXEC-3] Startup Position Sync
**Tanggal:** 2026-03-25
**File:** `backend/app/use_cases/data_ingestion_use_case.py`
**Commit:** `861822f`

**Masalah:**
- Bot restart saat ada posisi open → DB tetap OPEN
- Bot kirain masih ada posisi → skip entry sinyal bagus
- Atau sebaliknya: bot tidak tahu posisi sudah closed → tidak buka posisi baru

**Fix:**
```python
# Saat daemon start: sync position status dulu
if position_manager:
    await position_manager.sync_position_status()
```

**Impact:**
- ✅ Bot tahu state posisi yang akurat saat restart
- ✅ Tidak ada lagi "stuck OPEN" setelah reboot

---

### [FIX-EXEC-4] Exit Type dari order_type Field
**Tanggal:** 2026-03-25
**File:** `backend/app/use_cases/position_manager.py`
**Commit:** `861822f`

**Masalah:**
- Exit type (SL/TP) ditentukan berdasarkan **jarak harga** (distance comparison)
- Tidak reliable: kalau harga ada di tengah SL dan TP, bisa salah klasifikasi

**Fix:**
```python
# Sebelum: distance comparison (tidak reliable)
if abs(exit_price - db_trade.sl_price) < abs(exit_price - db_trade.tp_price):
    exit_type = "SL"

# Sesudah: gunakan order_type field langsung
order_type_str = last_order.get("order_type", "").lower()
if "stop" in order_type_str:
    exit_type = "SL"
elif "take-profit" in order_type_str:
    exit_type = "TP"
```

**Impact:**
- ✅ SL freeze logic benar (PR-2: freeze setelah SL hit)
- ✅ Risk manager record PnL dengan label yang benar

---

### [FIX-SIGNAL-1] L2 EMA Weakening Diperkuat
**Tanggal:** 2026-03-25
**File:** `backend/app/use_cases/signal_service.py`
**Commit:** `8ab9b1b`

**Masalah:**
- L2 weakening sebelumnya hanya **reduce confidence** (dari 1.0 ke 0.3)
- Masih bisa berkontribusi positif ke conviction → WEAK BUY di kondisi ambiguous
- Kondisi weak: RSI >70, EMA distance <0.3 ATR
- Kondisi EMA ambiguous (EMA20 ≈ EMA50) tidak dicek

**Fix:**
```python
# Tambah kondisi baru: EMA ambiguous zone
ema_gap_ratio = abs(ema20_now - ema50_now) / ema50_now
if ema_gap_ratio < 0.001:  # EMA20 dan EMA50 hampir sama
    _l2_weakened = True

# Tightened thresholds: 70/30 → 68/32, distance 0.3 → 0.2 ATR

# Force l2=False (bukan hanya reduce confidence)
if _l2_weakened:
    l2 = False  # Full disable
```

**Impact:**
- ✅ Tidak ada contribution dari L2 di zona transisi/konsolidasi
- ✅ Signal lebih selektif di kondisi ambiguous
- ✅ Mengurangi false WEAK BUY di EMA crossover zone

---

## Masalah yang Belum Difix

### [PENDING-1] PR-1: 1H Confirmation Filter
**Priority:** High
**Masalah:** Signal 4H = 6x/hari, momentum sering terjadi di antara interval
**Plan:** Tambah 1H confirmation window sebelum entry
**Status:** Butuh backtest 6 bulan dulu

### [PENDING-2] PR-2: Partial TP Strategy
**Priority:** High
**Masalah:** TP fixed 0.71% terlalu konservatif, sering exit sebelum trend lanjut
**Plan:** 50% close @ TP1 (0.71%), 50% let run dengan trailing SL
**Status:** Butuh backtest 6 bulan dulu

### [PENDING-3] Sprint 2: DD Adaptive Sizing
**Priority:** Medium
**Masalah:** Drawdown protection belum ada di live execution
**Plan:** Graduated risk reduction saat DD naik (2% → 1.5% → 1.0% → 0.5%)
**Status:** Butuh Sprint 1 validated dulu

### [PENDING-4] Bear Market WR (47.1%)
**Priority:** Medium
**Masalah:** Bot kalah di bear market
**Root Cause:** MLP training bias ke bull data, EMA lag di bearish inflection
**Plan:** PR-1 (1H confirmation) diharapkan help, tapi butuh validasi

---

## Forward Test Baseline (Pre-Fix)

| Periode | Trades | PnL | Notes |
|---------|--------|-----|-------|
| 15-25 Mar 2026 | ~5-6 trades | -$2.85 | 1x SL fail (-$6.30), rest noise |

**Root causes forward test jelek:**
1. SL execution 18 Mar gagal → -$6.30 (execution bug, bukan signal)
2. Signal conviction rendah (19.8%) → entry dengan edge minimal
3. L2 weakening tidak agresif → false entry di ambiguous zone

---

*Last updated: 2026-03-25 23:55 UTC*
*Author: Richard (Feynman mode) 🔬*
