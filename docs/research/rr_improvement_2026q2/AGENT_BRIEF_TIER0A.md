# Sub-Agent Brief — Tier 0a: Lighter SDK Reconnaissance

**Parent doc:** `DESIGN_DOC.md` v0.2 (§4.0.A)
**Status:** Ready for execution
**Owner (lead analyst):** Claude (chat parent)
**Owner (executor):** Sub-agent (kamu yang membaca file ini)
**Estimated effort:** 0.5–1 sesi panjang
**Created:** 2026-04-24

---

## 1. Konteks singkat

Tim sedang merancang **reconciliation pipeline** untuk mengatasi pattern `stuck_open` (trade yang sudah closed di Lighter masih flag `OPEN` di DuckDB lokal). Sebelum design pipeline-nya bisa di-freeze, kita butuh **catalog lengkap kapabilitas Lighter SDK** yang sudah dipakai di repo + endpoint apa saja yang available untuk:

1. Query open positions (sweep mode)
2. Query trade history / fill history (backfill mode)
3. Query order status spesifik (force resolution)
4. Real-time event subscription (websocket — kalau ada)

**Tugasmu fokus 100% di area ini.** Jangan kerjakan Tier 0b/0c/1/2/3/4 atau modifikasi production code.

---

## 2. Mission

Hasilkan **satu file** `findings/H_lighter_sdk_capabilities.md` yang berisi inventory lengkap, sample code, rate limit, dan rekomendasi konkret cara implement reconciliation worker. Output harus cukup detail sehingga design pipeline di DESIGN_DOC §4.0.B bisa langsung di-implement tanpa research tambahan.

---

## 3. Investigation areas

### Area H.1 — Inventory pemakaian SDK saat ini

**Pertanyaan:**
- File-file apa saja di `backend/app/adapters/gateways/` yang call Lighter SDK?
- Method/endpoint apa yang sudah dipakai di production code?
- Versi SDK Lighter yang dipakai (cek `pyproject.toml` / `requirements.txt`)
- Pattern auth (API key, signer, dll) — cukup deskripsi, **JANGAN** dump credentials

**Hint lokasi awal:**
- `backend/app/adapters/gateways/lighter_execution_gateway.py`
- Mungkin ada juga `lighter_market_gateway.py` atau sejenis untuk market data
- Search: `import lighter` atau `from lighter`
- Search di docs: `docs/lighter_gateway.md`, `docs/deployment/LIGHTER_*`

### Area H.2 — Endpoint discovery (yang BELUM dipakai)

Ini bagian terpenting. Untuk reconciliation kita butuh tahu method-method berikut **available atau tidak** di SDK:

| Use case | Method yang dicari | Pertanyaan |
|---|---|---|
| Sweep open positions | `get_open_positions()` / `list_positions()` / `get_account_positions()` | Apakah return semua open posisi user dalam satu call? Format response? |
| Backfill closed trades | `get_trade_history()` / `get_fills()` / `get_closed_orders()` | Pagination? Time range filter? Maksimum range per call? |
| Order status query | `get_order_status(order_id)` / `get_order(order_id)` | Bisa query order yang sudah filled/canceled? |
| Order detail (closed) | `get_order_details(order_id)` | Termasuk fill price, fee, timestamps? |
| Account state | `get_account()` / `get_balance()` | Cara cross-check P&L total? |
| WebSocket events | Subscribe ke fill / order_update events | Channel name? Auth flow? Reconnect behavior? |

**Untuk setiap method yang ditemukan, dokumentasikan:**

```
Method: [nama]
Available di SDK version: [versi]
Signature: async def foo(arg1: T1, ...) -> ReturnType
Sample call: [snippet pendek]
Sample response (struktur): [field penting]
Rate limit: [requests/sec, atau "tidak terdokumentasi"]
Pagination: [yes/no, mekanisme]
Latency observed: [kalau bisa diuji, otherwise N/A]
```

**Sumber dokumentasi:**
- README / dokumentasi SDK Lighter (kalau pip-installed, cek site-packages atau GitHub repo SDK)
- Lighter API docs publik (web)
- Source code SDK langsung (paling reliable)

### Area H.3 — Rate limit & quota

- Berapa request/sec/IP atau /account?
- Apakah ada burst allowance?
- Penalty kalau over (banned IP, soft throttle)?
- Best practice retry/backoff dari dokumentasi
- Apakah ada websocket alternative untuk hindari REST polling?

### Area H.4 — Testnet vs mainnet

- Apakah Lighter punya testnet/sandbox?
- URL/endpoint testnet?
- Apakah API yang sama bisa pakai key testnet?
- Ini penting untuk **safe testing reconciliation worker tanpa risiko ke akun live**

**Hint:** `docs/deployment/LIGHTER_TESTNET_VS_MAINNET.md`, `docs/deployment/LIGHTER_TESTNET_TESTING.md` mungkin sudah ada konteks.

### Area H.5 — Field semantics di response

Untuk method `get_open_positions()` dan `get_trade_history()` (atau ekuivalen), **dokumentasikan setiap field response** yang relevan untuk schema `trades_lighter` di DESIGN_DOC §4.0.B.1:

| Field DuckDB target | Field Lighter | Tipe | Catatan |
|---|---|---|---|
| `trade_id` | ? | ? | Order ID, Position ID, atau Fill ID? |
| `symbol` | ? | ? | Format `BTC-USDT` atau market_id integer? |
| `side` | ? | ? | LONG/SHORT atau BUY/SELL? Net position vs fill side? |
| `ts_open_ms` | ? | ? | Unit (ms/s/ns)? UTC? |
| `ts_close_ms` | ? | ? | Field name? |
| `entry_price` | ? | ? | Avg entry untuk multi-fill? |
| `exit_price` | ? | ? | Field name? |
| `size_base` | ? | ? | BTC quantity, atau notional? |
| `pnl_usdt` | ? | ? | Realized PnL net atau gross? Termasuk fee? |
| `fee_usdt` | ? | ? | Field terpisah? Maker/taker breakdown? |
| `exit_type` | ? | ? | Apakah Lighter ekspos "TP filled" vs "SL filled" vs "manual close"? |

**Field `exit_type` paling tricky** — kalau Lighter tidak ekspos langsung, kita perlu **inference logic** (compare exit_price vs sl_price/tp_price dari signal_snapshots). Dokumentasikan ini sebagai catatan.

### Area H.6 — Idempotency & deduplication

- Apakah `get_trade_history()` bisa return duplicate kalau dipanggil 2x dengan range overlap?
- Field unik untuk dedup di sisi kita: `order_id`? `fill_id`? `position_id`?
- Bagaimana SDK menangani retry pada order placement (idempotency key)?

### Area H.7 — Reconciliation pattern recommendation

Setelah H.1-H.6 selesai, rekomendasikan **pattern eksekusi konkret** untuk dua mode di DESIGN_DOC §4.0.B.2:

**Mode A — Open positions sweep:**
- Method yang dipakai
- Polling interval optimal (mempertimbangkan rate limit + freshness requirement)
- Error handling
- Bagaimana mendeteksi "stuck_open" (positions yang ada di DuckDB tapi tidak ada di Lighter response)

**Mode B — History backfill:**
- Method yang dipakai
- Time range chunking (misal 24h per call)
- Cara handle pagination
- Strategi awal one-time backfill (last 30/60/90 days)

**Mode C — Real-time (kalau websocket available):**
- Apakah feasible jadi pengganti polling?
- Trade-off vs polling (latency, complexity, reconnect)

---

## 4. Output format

File: `findings/H_lighter_sdk_capabilities.md`

Struktur:

```markdown
# Lighter SDK Capabilities — Reconciliation Discovery

**Area:** H — Lighter SDK Reconnaissance (DESIGN_DOC §4.0.A)
**Status:** [Complete / Partial / Blocked]
**Updated:** YYYY-MM-DD
**SDK version probed:** [versi]

## TL;DR
[2-3 kalimat: method utama yang available untuk reconciliation, dan rekomendasi pattern]

## H.1 Inventory pemakaian saat ini
[Tabel + path file]

## H.2 Endpoint discovery
[Per method: signature, sample, response shape, rate limit]

## H.3 Rate limits
[Tabel ringkas + sumber]

## H.4 Testnet
[URL, perbedaan dengan mainnet, cara akses]

## H.5 Field semantics
[Tabel mapping Lighter field → schema target DuckDB]

## H.6 Idempotency
[Field unik, behavior duplicate]

## H.7 Reconciliation pattern recommendation
### Mode A — Open positions sweep
[Method + interval + error handling]
### Mode B — History backfill
[Method + chunking + pagination]
### Mode C — WebSocket alternative (kalau ada)
[Trade-off]

## Gaps & blockers
[Apa yang TIDAK bisa diverifikasi dan kenapa]

## Action items untuk DESIGN_DOC §4.0.B revisi
[Bullet list konkret apa yang perlu di-update di parent design doc]

## Raw sources
[Path file SDK, URL docs, snippet output]
```

---

## 5. Constraints

### ❌ Yang TIDAK boleh dilakukan
- ❌ **Jangan kirim order ke Lighter** (mainnet maupun testnet) — tugasmu read-only research
- ❌ **Jangan modifikasi kode produksi** (`backend/app/adapters/gateways/*.py` dll)
- ❌ **Jangan dump credentials / API keys** ke file output
- ❌ **Jangan implement reconciliation worker** — itu Tier 0b, di luar scope brief ini
- ❌ **Jangan modifikasi schema DuckDB** — itu Tier 0c
- ❌ **Jangan retrain model** atau jalankan analisis Area D/E baru

### ✅ Yang boleh dilakukan
- ✅ Read source code SDK Lighter (di `site-packages` atau GitHub)
- ✅ Read public dokumentasi Lighter (web)
- ✅ Read kode existing di `backend/app/adapters/gateways/`
- ✅ Tulis script eksperimental di `scripts/H_*.py` untuk **read-only** test (mis. `get_open_positions()` di testnet)
- ✅ Buat snippet/sample code di output markdown
- ✅ Tulis di `docs/research/rr_improvement_2026q2/findings/H_*.md` dan `scripts/`

### ⚠️ Hati-hati
- Kalau perlu test endpoint nyata (Area H.2 latency observation), **gunakan testnet saja**, jangan mainnet
- Kalau testnet tidak available dan kamu butuh test mainnet, **tanya lead analyst dulu** (tulis di `PROGRESS.md` section "Blocked")
- Kalau menemukan bug/anomali di SDK, dokumentasikan tapi jangan fix

---

## 6. Eskalasi ke lead analyst

Stop dan minta klarifikasi (tulis di `PROGRESS.md`) kalau:

1. SDK Lighter tidak punya endpoint untuk salah satu use case kritis (sweep / history / order_status)
2. Rate limit terlalu ketat untuk reconciliation pattern yang dibayangkan
3. Field semantics ambigu atau kontradiktif dengan dokumentasi
4. Testnet tidak available dan kamu butuh confirm sebelum test mainnet
5. SDK version di repo terlalu lama dan endpoint yang dibutuhkan hanya ada di versi baru (perlu keputusan upgrade)

---

## 7. Definition of Done

Brief ini selesai kalau:

- ✅ File `findings/H_lighter_sdk_capabilities.md` terisi lengkap sesuai template
- ✅ Setiap method di tabel H.5 terisi (atau eksplisit ditulis "TIDAK TERSEDIA" + alasan)
- ✅ Section H.7 berisi rekomendasi konkret yang bisa langsung jadi spec untuk pipeline implementer
- ✅ `PROGRESS.md` di-update dengan progress sesi
- ✅ Kalau ada script eksperimental, ada di `scripts/H_*.py` dengan README pendek di header

---

## 8. Referensi yang harus dibaca dulu

Sebelum mulai eksekusi, baca berurutan:

1. **`DESIGN_DOC.md` v0.2 §3.6 dan §4.0** — konteks kenapa reconciliation dibutuhkan
2. **`findings/A_architecture_inventory.md` §A.5** — pemakaian gateway saat ini
3. **`findings/C_trade_log_schema.md`** — schema target untuk reconciliation
4. **`docs/lighter_gateway.md`** — dokumentasi internal kalau ada
5. **`docs/deployment/LIGHTER_*`** — konteks deployment & testnet

---

**End of brief.** Mulai dengan baca referensi di Section 8, lalu update `PROGRESS.md` dengan section baru `## YYYY-MM-DD HH:MM — Tier 0a kickoff`.
