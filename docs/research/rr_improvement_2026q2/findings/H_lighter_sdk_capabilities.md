# Lighter SDK Capabilities — Reconciliation Discovery

**Area:** H — Lighter SDK Reconnaissance (`DESIGN_DOC.md` §4.0.A, `AGENT_BRIEF_TIER0A.md`)  
**Status:** **Partial** — inventory kode + model OpenAPI + rate limit publik **lengkap**; latensi runtime & respons live **tidak** diuji (import SDK gagal di environment Windows probe karena `libc`; uji read-only disarankan di **Linux executor** atau testnet dari container).  
**Updated:** 2026-04-24  
**SDK version probed (package metadata):** `lighter` PyPI package **`1.0.0`** (`site-packages/lighter/__init__.py` `__version__`); constraint repo: `lighter-sdk>=1.0.0` (`backend/requirements.txt`, `backend/requirements.executor.txt`).

## TL;DR

Reconciliation **tanpa** menambah dependency baru bisa memakai **REST yang sudah dipakai gateway** (`/account`, `/accountOrders`, `/accountInactiveOrders`, `/nextNonce`, `/orderBookDetails`, `/orderBooks`) + pola auth **SignerClient.create_auth_token_with_expiry** + header `Authorization`. Untuk **backfill massal** dan **cursor**, SDK OpenAPI menyediakan **`OrderApi.account_inactive_orders`** (sama path REST), **`OrderApi.trades`** → `GET /api/v1/trades` (cursor, `account_index`, limit ≤100), dan **`OrderApi.export`** → export terjadwal dengan **`data_url`** (CSV). **WebSocket:** `lighter.ws_client.WsClient` subscribe `account_all/{account_index}` + `order_book/{market_id}` — cocok sebagai **Mode C** pengurang polling, dengan trade-off kompleksitas reconnect. **Rate limit:** `accountInactiveOrders` **sangat berat** (weight **100**); autentikasi menggeser limit ke bucket L1 (premium/builder) per [dokumentasi publik](https://apidocs.lighter.xyz/docs/rate-limits).

## H.1 Inventory pemakaian saat ini

| File | Peran |
|------|--------|
| `backend/app/adapters/gateways/lighter_execution_gateway.py` | Gateway utama: REST `aiohttp` + token via **SignerClient**; order via **async** `create_market_order`, `create_order`, `create_sl_order`, `create_tp_order`. |
| `execution_layer/lighter/*.py`, `backend/scripts/*.py` | Skrip / executor lain yang `import lighter` (bukan gateway produksi utama). |

**REST endpoint yang sudah dipanggil dari kode (path relatif terhadap `base_url` yang berakhiran `/api/v1`):**

| Endpoint | Metode | Auth? | Pemakaian di gateway |
|----------|--------|-------|------------------------|
| `/orderBooks` | GET | Tidak | Metadata market (decimals) |
| `/orderBookDetails` | GET | Tidak | Last price, order book |
| `/account` | GET | Ya | Posisi terbuka, balance (`_fetch_account`, `get_open_position`, `get_account_balance`) |
| `/accountOrders` | GET | Ya | `fetch_open_orders`, SL/TP aktif |
| `/accountInactiveOrders` | GET | Ya | `fetch_last_closed_order`, `fetch_entry_fill_quote` (limit default 10) |
| `/nextNonce` | GET | Ya | `fetch_account_nonce` |

**Auth:** `SignerClient` dari `lighter.signer_client` — `create_auth_token_with_expiry(..., api_key_index=...)`. Kredensial: env `LIGHTER_*_API_KEY` / `*_API_SECRET`, `LIGHTER_API_KEY_INDEX`, `LIGHTER_ACCOUNT_INDEX` — **tidak didokumentasikan nilai konkret di file ini.**

**Catatan implementasi vs deployment doc:** `LighterExecutionGateway` untuk `testnet` memakai default `base_url` **`https://mainnet.zklighter.elliot.ai/api/v1`** dengan komentar *"Lighter doesn't have a separate testnet endpoint"* (```94:105:backend/app/adapters/gateways/lighter_execution_gateway.py```), sedangkan `docs/deployment/LIGHTER_TESTNET_VS_MAINNET.md` menyebut host **`testnet.zklighter.elliot.ai`**. **Kontradiksi** — freeze design harus memilih sumber kebenaran (env override vs dokumentasi).

**WebSocket di gateway:** `self.ws_url` diset, `_ws` state ada, tetapi **tidak** ditemukan loop subscribe aktif di file gateway yang di-audit (hanya `close()`). Integrasi WS real-time **belum** di production gateway ini.

---

## H.2 Endpoint discovery (belum / sebagian dipakai)

Sumber tambahan: **`lighter.api.order_api.OrderApi`** (OpenAPI generator), path resource absolut `/api/v1/...` (ApiClient biasanya menggabungkan dengan host Configuration).

### Sweep open positions

| Aspek | Temuan |
|--------|--------|
| **Method REST setara** | `GET /account?by=index&value={account_index}` — sudah dipakai. Response: `positions[]` per `market_id`, `size` (scaled int), `entry_price`, `opened_at`, `sl_order_id`, `tp_order_id`, dll. |
| **SDK wrapper** | `AccountApi.account(by, value)` → `DetailedAccounts`. |
| **Satu call semua market?** | Ya, lewat **account** — filter `market_id == 1` (BTC) di klien. |
| **Sample call (REST)** | `GET {base}/account?by=index&value=0` + header `Authorization: <token>`. |
| **Rate limit (dok publik)** | Bucket “other” **300** kecuali terdaftar lain; **`account`** tidak tercantum eksplisit di tabel weight → perlakukan sebagai **300** sampai diverifikasi lewat support. |

### Backfill closed trades / fills

| Method | Available | REST path (dari serializer SDK) | Catatan |
|--------|-----------|----------------------------------|---------|
| **`OrderApi.account_inactive_orders`** | Ya | `/api/v1/accountInactiveOrders` | Params: `account_index`, `limit` (1–100), opsional `market_id`, `cursor`, `between_timestamps` (string). Pagination **cursor**. Sama dengan yang gateway pakai; **perluas** limit + cursor untuk backfill. |
| **`OrderApi.trades`** | Ya | `/api/v1/trades` | Params wajib: `sort_by` (`timestamp` \| `trade_id` \| `block_height`), `limit` 1–100; opsional `account_index`, `cursor`, `var_from`, `type`, `aggregate`, dll. Return model **`Trades`**: `trades[]`, **`next_cursor`**. **Fill-level** on-chain style (`Trade` model), bukan sama persis dengan “order CSV export”. |
| **`OrderApi.export`** | Ya | (serialize: cek `_export_serialize` — tipe `type` wajib `funding` \| `trade`) | Response **`ExportData`**: `code`, `message`, **`data_url`** — unduhan file (polanya mirip CSV dashboard). Cocok **one-time migration** 30/60/90 hari (`start_timestamp` / `end_timestamp` ms, range valid di model). |
| **`OrderApi.account_active_orders`** | Ya | `/api/v1/accountActiveOrders` | Ekuivalen `/accountOrders` yang dipakai gateway (nama berbeda di OpenAPI vs path manual). |

**Tidak ditemukan** di SDK yang di-inspeksi: method bernama persis `get_order_status(order_id)` — status order tersedia sebagai objek **`Order`** di daftar `accountInactiveOrders` / `accountOrders` dengan field `status` (enum string: `filled`, `canceled`, `open`, …).

**Sample (pseudo, async OrderApi):**

```python
# Trades — butuh ApiClient dikonfigurasi host + auth sama seperti produksi
resp = await order_api.trades(
    sort_by="timestamp",
    limit=100,
    auth=token_str,
    account_index=account_index,
    market_id=1,
    cursor=None,
)
# resp.trades: list[Trade]; resp.next_cursor untuk halaman berikutnya
```

**Rate limit (dok publik):** `trades` weight **600**; `accountInactiveOrders` weight **100** (mahal).

### Order status / detail (closed)

| Aspek | Temuan |
|--------|--------|
| Query by `order_id` | Filter client-side dari hasil `accountInactiveOrders` / `accountOrders` (gateway: `fetch_entry_fill_quote`). |
| Field harga / fee | Model **`Order`**: `filled_base_amount`, `filled_quote_amount`, `trigger_price`, `price`, `type` (`stop-loss-limit`, `take-profit-limit`, `market`, …), `status`, `timestamp`, `transaction_time`, `order_id`. |

### Account state / PnL

| Aspek | Temuan |
|--------|--------|
| Balance | `available_balance` di objek account (sudah dipakai). |
| Realized PnL per posisi | Field di posisi dari `/account` (lihat docstring `AccountApi.account` di SDK: **Realized PnL** disebutkan untuk position). |

### WebSocket

| Aspek | Temuan |
|--------|--------|
| Class | `lighter.ws_client.WsClient` |
| URL | `wss://{host}/stream` default; host dari `Configuration.get_default().host` tanpa `https://`. |
| Channel | `subscribe` → `order_book/{market_id}`, `account_all/{account_id}`. |
| Event types | `connected`, `subscribed/order_book`, `update/order_book`, `subscribed/account_all`, `update/account_all`, `ping` / `pong`. |
| Reconnect | Dok publik: deployments bisa putus koneksi — perlu **reconnect + ping/pong** (sudah ada handler pong). |

**Latency observed:** **N/A** (tidak diuji live di sesi ini).

---

## H.3 Rate limits

Ringkasan dari [Lighter — Rate Limits](https://apidocs.lighter.xyz/docs/rate-limits) (2026-04-24):

| Konteks | Ringkasan |
|---------|-----------|
| REST base | `https://mainnet.zklighter.elliot.ai/api/v1/` |
| Standard (unauthenticated / IP) | **60 requests / rolling minute** (unweighted). |
| Premium (L1-authenticated) | **24,000 weighted requests / rolling minute** (angka weight per endpoint). |
| Builder | **240,000 weighted / minute** untuk read REST (kecuali sendTx). |
| **Weights relevan** | `nextNonce`: **6**; `accountInactiveOrders`: **100**; `trades`, `recentTrades`: **600**; endpoint tidak terdaftar: **300**. |
| Kelebihan | HTTP **429** atau **405**; WS bisa ikut throttled; backoff disarankan. |
| WS | Max koneksi, subscription, pesan/menit — lihat dokumen yang sama. |

**Rekomendasi implementer:** autentikasi setiap request reconciliation; backoff eksponensial pada 429; **jangan** poll `accountInactiveOrders` dengan frekuensi tinggi pada akun standard.

---

## H.4 Testnet vs mainnet

| Sumber | Pernyataan |
|--------|------------|
| `LIGHTER_TESTNET_VS_MAINNET.md` | Dashboard testnet `lighter.elliot.ai`, API `testnet.zklighter.elliot.ai`; mainnet `lighter.xyz`, `api.lighter.xyz`. |
| `LighterExecutionGateway` (kode) | Default testnet **base_url** = `https://mainnet.zklighter.elliot.ai/api/v1` (override env `LIGHTER_TESTNET_BASE_URL`). |
| **Kesimpulan** | Operator harus menyelaraskan **env** dengan kebijakan Lighter terkini; untuk **uji read-only** reconciliation, prefer **akun paper / key read-only** atau host testnet resmi jika API memang terpisah. |

**TIDAK dijalankan** di sesi ini: koneksi testnet aktual (brief: no orders; read-only boleh — blocked oleh libc di Windows dev).

---

## H.5 Field semantics — mapping ke `trades_lighter` (`DESIGN_DOC` §4.0.B.1)

| Field DuckDB target | Sumber Lighter yang masuk akal | Tipe / catatan |
|----------------------|---------------------------------|----------------|
| `trade_id` | **`order_id`** (string) dari order entry / posisi; atau **`tx_hash`** dari fill — **putuskan satu SOT**: untuk kompatibilitas dengan `live_trades.id` sekarang, **order_id** entry market yang dipakai bot. |
| `symbol` | `market_id` → map ke `BTC/USDC` (gateway `MARKET_ID=1`). |
| `side` | Posisi: tanda `size` di `/account` → LONG/SHORT; order: `is_ask` + `reduce_only` atau field `side` (model masih ada `side` “TODO remove”). |
| `ts_open_ms` | `opened_at` posisi (ms) atau `timestamp`/`created_at` order entry. |
| `ts_close_ms` | `transaction_time` / `updated_at` order **filled** penutup; atau waktu fill terakhir dari `trades` stream. |
| `entry_price` | `entry_price` posisi (scaled) → unscaling seperti gateway (`/ 10**price_decimals`). |
| `exit_price` | Dari order tutup: `filled_quote/filled_base` atau `trigger_price` untuk SL/TP (sudah di `fetch_last_closed_order`). |
| `size_base` | `filled_base_amount` atau `position.quantity` (unscale). |
| `pnl_usdt` | **TIDAK** selalu field langsung di Order — CSV export menyimpan **Closed PnL**; REST order mungkin perlu hitung dari fill atau pakai **`export`** / laporan. Untuk posisi: unrealized/realized di blok account (detail field name di `DetailedAccount` perlu cek response sample live). |
| `fee_usdt` | `taker_fee` / `maker_fee` di model **`Trade`** (integer scaled); alokasi ke akun: `ask_account_pnl` / `bid_account_pnl` string di `Trade` — **perlu normalisasi** ke USDT. |
| `status` | Derive: posisi `size!=0` → OPEN; else CLOSED. |
| `exit_type` | **Tidak ada** field enum “TP” vs “SL” eksplisit di model Order; inferensi: cocokkan `type` (`take-profit-limit`, `stop-loss-limit`) + `filled_price` vs batas dari **`signal_snapshots`** / `live_trades.sl_price`/`tp_price`; jika tidak ada: `MANUAL` / `UNKNOWN`. |

---

## H.6 Idempotency & deduplication

| Pertanyaan | Jawaban |
|------------|---------|
| Duplikat saat range overlap? | **Cursor + upsert** pada kunci stabil (`order_id` atau `trade_id`+`timestamp`) mengurangi duplikat; perilaku server **tidak** diuji. |
| Kunci unik disarankan | **`order_id`** untuk lifecycle order; **`trade_id`** (int) untuk baris `Trade` di endpoint `trades` — beda granularitas; pipeline harus definisi apakah mirror per **order** atau per **fill**. |
| Idempotency order placement | Nonce sequential (`nextNonce`) — retry harus hati-hati agar tidak double-send. |

---

## H.7 Reconciliation pattern recommendation

### Mode A — Open positions sweep (60–120 s)

1. **Sumber kebenaran posisi:** `GET /account` → jika `positions` untuk `market_id=1` kosong atau `size=0`, tidak ada posisi terbuka di Lighter.  
2. **Bandingskan** dengan `SELECT trade_id FROM trades_lighter WHERE status='OPEN'`.  
3. **Stuck OPEN:** ada di DuckDB, tidak ada posisi di Lighter → panggil **`accountInactiveOrders`** (limit besar + **cursor** jika perlu) untuk menemukan order penutup terbaru yang cocok `trade_id` / waktu; lalu `upsert` ke CLOSED + `exit_price` dari logika `fetch_last_closed_order`.  
4. **Missing OPEN:** ada di Lighter, tidak di DuckDB → insert OPEN dari posisi + order entry id jika tersedia.  
5. **Polling:** 60–120 s; pada 429 → backoff **≥ cooldown** dokumen (`weight/(totalWeight/60)` contoh ~750ms untuk weight 300).  
6. **Auth:** selalu kirim `Authorization` agar limit premium/L1.

### Mode B — History backfill (±1 jam)

1. **Utama:** `accountInactiveOrders` dengan **`between_timestamps`** + **`cursor`** (tersedia di OpenAPI) untuk chunk waktu (mis. 24h).  
2. **Pelengkap fill-level:** `OrderApi.trades` dengan `account_index`, `market_id`, `sort_by=timestamp`, `cursor` — limit 100 per call.  
3. **Bulk / CSV parity dengan dashboard:** `OrderApi.export` `type='trade'`, `start_timestamp`, `end_timestamp`, `account_index`, `market_id` → unduh `data_url` → parse CSV (sama semantik dengan export manual).  
4. **One-time 90 hari:** segmentasi timestamp non-overlap + upsert idempotent per `order_id`/`trade_id`.

### Mode C — WebSocket alternative

1. Subscribe **`account_all/{account_index}`** untuk perubahan posisi/order.  
2. **Feasible** sebagai **suplemen** untuk mengurangi polling berat (`accountInactiveOrders`).  
3. **Trade-off:** kompleksitas reconnect, state diff, tetap perlu **REST “truth”** periodik (heartbeat) untuk recovery setelah downtime.

---

## Gaps & blockers

1. **Import `lighter` gagal** di satu environment Windows (`libc` / C standard library) — SignerClient tidak bisa diinstansiasi; **executor Linux** atau container harus jadi referensi untuk smoke test.  
2. **Kontradiksi URL testnet** antara deployment doc vs `LighterExecutionGateway` default.  
3. **`pnl_usdt` / fee** agregat per posisi dari REST murni: perlu **satu contoh response JSON** dari produksi/testnet untuk mem-finalkan mapping (tanpa menampilkan secret).  
4. Gateway **tidak** memakai `OrderApi` class — hanya string path; implementer reconciliation bisa pilih **tetap aiohttp** (konsisten) atau **OrderApi** (typed).

---

## Action items untuk `DESIGN_DOC` §4.0.B revisi (v0.3)

- Tetapkan **SOT `trade_id`**: `order_id` entry vs `tx_hash` vs `trade_id` numerik `trades`.  
- Perbarui diagram alur: **Mode B** memakai kombinasi **`inactive_orders` + cursor** dan/atau **`export`** untuk parity CSV.  
- Cantumkan **weight rate limit** per call dan requirement **auth** untuk worker.  
- Sesuaikan **testnet base URL** dengan keputusan operasi (env vs doc).  
- Tambahkan sub-bab **exit_type inference** (mapping `type` order + toleransi harga).  
- Referensikan file ini sebagai **Tier 0a complete** setelah lead review.

---

## Raw sources

- `backend/app/adapters/gateways/lighter_execution_gateway.py` (baris ~50–246, 750–1170)  
- `backend/requirements.txt` (pin `lighter-sdk>=1.0.0`)  
- `C:\Users\ThinkPad\AppData\Local\Programs\Python\Python312\Lib\site-packages\lighter\__init__.py` (`__version__`)  
- `.../lighter/api/order_api.py` — `account_inactive_orders`, `trades`, `export` serializers  
- `.../lighter/models/order.py`, `trade.py`, `export_data.py`, `trades.py`  
- `.../lighter/ws_client.py`  
- `.../lighter/signer_client.py` (header + `create_*` signatures)  
- `docs/lighter_gateway.md` (tabel endpoint)  
- `docs/deployment/LIGHTER_TESTNET_VS_MAINNET.md`, `LIGHTER_TESTNET_TESTING.md`  
- https://apidocs.lighter.xyz/docs/rate-limits  
- `docs/research/rr_improvement_2026q2/DESIGN_DOC.md` §4.0.B.1–B.2  
- `docs/research/rr_improvement_2026q2/AGENT_BRIEF_TIER0A.md`  
