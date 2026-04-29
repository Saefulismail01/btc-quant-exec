# Design Doc — R:R Improvement & Exhaustion Awareness

**Version:** 0.3 (FROZEN — implementation-ready)
**Updated:** 2026-04-24
**Owner:** Lead analyst (diskusi user ↔ Claude)
**Status:** ✅ FROZEN — siap untuk Tier 0b/0c implementation
**Dokumen pendukung:** `findings/A`–`findings/H`, `findings/SUMMARY.md`, `proposed_code/`

## Changelog

- **v0.3** — Freeze design dengan default decisions dari `findings/H_lighter_sdk_capabilities.md`. Live runtime validation (Tier 0a-validation) **di-skip** karena: (a) tidak ada read-only API key, (b) ada posisi aktif di Lighter yang harus dihindari interferensi. Asumsi runtime akan divalidasi via implementation Tier 0b di branch terpisah, bukan via standalone probing. Section 8 di-restructure: "open assumptions to validate during impl" menggantikan "open questions". Schema SQL + code skeleton dibangun di `proposed_code/` (proposal-grade, belum git branch).
- **v0.2** — User mengonfirmasi DuckDB `live_trades` tidak reliable (pattern `stuck_open`: trade closed di Lighter masih ter-flag OPEN di DuckDB). Strategi telemetri di-rework: Lighter = source of truth fakta trade, DuckDB jadi signal context store terpisah. Tier 0 di-restructure dengan reconciliation pipeline + signal snapshot table baru. Tambah Section 3.6 (ledger reliability gap) dan Section 4.0 (Lighter SDK reconnaissance) sebagai prerequisite.
- **v0.1** — Draft awal sintesis findings sub-agent.

## Frozen decisions (v0.3)

Ringkasan keputusan default yang diadopsi tanpa runtime validation:

| # | Keputusan | Default v0.3 | Confidence | Validasi nanti |
|---|-----------|---------------|------------|----------------|
| 1 | Lighter host | `mainnet.zklighter.elliot.ai/api/v1` (sesuai gateway prod) | High (kode jelas) | Smoke test di Tier 0b branch |
| 2 | SOT `trade_id` | `order_id` entry market | Medium-High | Verify saat implement reconciliation worker |
| 3 | Mirror granularity | Per order (bukan per fill) | Medium | Re-evaluate kalau >30% multi-fill ditemukan saat impl |
| 4 | Backfill source | `OrderApi.export` (CSV download) untuk one-time, `accountInactiveOrders` cursor untuk delta | Medium | Verify response struktur saat first call |
| 5 | `exit_type` inference | Match `Order.type` (`stop-loss-limit`/`take-profit-limit`) + price tolerance vs `signal_snapshots.intended_sl/tp_price` | Medium | Verify enum aktual saat first probing data nyata |

Semua "validasi nanti" akan terjadi natural saat sub-agent Tier 0b/0c menulis & test kode dengan response Lighter yang real (di branch terpisah, **dengan akun saat tidak ada posisi terbuka**).

---

## 1. Executive summary

Sistem scalping BTC saat ini punya **win rate ~75% tapi R:R = 0.53** (TP 0.71% / SL 1.333%), menghasilkan EV tipis ~+0.22% per trade. User memahami ada problem struktural "bot masih buy di puncak" dan ingin tahu layer apa yang perlu ditambah/diperbaiki.

**Hasil riset discovery** (sub-agent, 2026-04-24) + klarifikasi user:

1. **Hipotesis awal "semua layer lagging" ditolak sebagian.** L3 MLP sudah memakai fitur microstructure (CVD, funding, OI). Masalahnya bukan ketiadaan layer exhaustion, tapi kemungkinan **horizon mismatch** antara label MLP (4H forward return) dan eksekusi aktual (TP realistis kena 1-2H).
2. **Hipotesis "loss cluster di puncak streak win" belum didukung data.** Distribusi `wins_before_loss` pada 27 episode April: `[5, 1, 7, 0, 4, 1, 2]` — relatif tersebar.
3. **Gap telemetri serius.** Snapshot signal state (L1/L2/L3/L4) tidak disimpan per trade → analisis conditional WR retrospektif tidak mungkin tanpa replay atau instrumentasi baru.
4. **Bug `candle_open_ts`** — diisi `time.time()`, bukan timestamp candle signal.
5. **Engine eksekusi tidak native support partial TP / trailing**, harus emulasi client-side.
6. **Ledger reliability gap (klarifikasi v0.2):** DuckDB `live_trades` tidak reliable vs Lighter — pattern `stuck_open` (trade closed di Lighter masih flag OPEN di DuckDB). Konsekuensi: tidak cukup hanya "menambah kolom" — butuh re-arsitektur source of truth + reconciliation pipeline.

**Rekomendasi utama (urutan ROI):**

| Tier | Inisiatif | Effort | ROI (qualitatif) | Risiko |
|------|-----------|--------|------------------|--------|
| 0a | Lighter SDK reconnaissance (prerequisite) | 0.5-1 hari | Enabling semua di bawah | Rendah |
| 0b | Reconciliation pipeline (Lighter → DuckDB) + fix `stuck_open` | 3-4 hari | Foundational reliability | Sedang |
| 0c | Signal snapshot store baru + fix `candle_open_ts` | 2-3 hari | Enabling semua analisis kondisional | Rendah |
| 1 | Sync data OHLCV/metrics + 1m ingest | 1-2 hari | Unblock Area D/E/F | Rendah |
| 2 | **MLP horizon refactor** (label = TP_hit_before_SL) | 3-5 hari | Tinggi — langsung target root cause | Sedang (perlu A/B) |
| 3 | Asymmetric exit (paper trade forward test) | 2-3 hari | Tinggi — perbaiki R:R | Rendah (dry-run) |
| 4 | Exhaustion layer (veto/sizing modifier) | 1-2 minggu | Menengah — bergantung Tier 1/2 | Menengah |

**Rekomendasi:** Tier 0 (a→b→c) jalan **dulu**, kemudian Tier 1 paralel dengan Tier 2/3. Tier 0b jadi prerequisite mutlak karena tanpa reconciliation, telemetri yang kita capture pun bisa jadi "stuck OPEN" tidak pernah ter-resolve.

---

## 2. Problem statement

### 2.1 Dari sudut matematika eksekusi

Dengan config sekarang (Golden v4.4):

```
TP = 0.71%
SL = 1.333%
R:R = TP/SL = 0.533

EV per trade = WR × TP − (1−WR) × SL
            = 0.759 × 0.71% − 0.241 × 1.333%
            = 0.539% − 0.321%
            = +0.218% per trade
```

EV positif tapi tipis. Sensitivitas:
- Drop WR ke 70% → EV = +0.097% (jatuh 55%)
- Drop WR ke 65% → EV = −0.005% (break-even)

Sistem **fragile** terhadap degradasi WR. Margin of safety bergantung pada asumsi WR stabil.

### 2.2 Dari sudut naratif user

> "Bot ga tau kapan harga itu pucuk karena BCD dan teknikal akan ada di bias long. Sudah streak win beberapa kali tapi di pucuk dia masih buy dan akhirnya SL."

**Temuan data:** pola "loss setelah streak panjang" **belum** teridentifikasi di 27 episode April (sample kecil, belum decisive). Pola loss **relatif acak** berdasarkan posisi streak.

**Tapi masalah user tetap valid** — cuma kemungkinan root cause-nya bukan "buta exhaustion" melainkan **struktur R:R** + **mismatch MLP**.

### 2.3 Pertanyaan inti yang harus dijawab

1. Kenapa MLP (yang punya fitur CVD/funding/OI) masih bias long di puncak?
2. Apakah rightward tail winner terpotong oleh TP 0.71%?
3. Apakah SL 1.333% masuk akal secara volatility-adjusted, atau terlalu lebar?
4. Kalau asymmetric exit diadopsi, berapa degradasi WR yang dapat ditoleransi?

---

## 3. Root cause analysis

### 3.1 R:R struktural (confidence: tinggi)

R:R 0.53 memang sengaja dipilih untuk optimize WR (Golden v4.4 analysis di logbook evolusi v4). **Trade-off eksplisit:** WR tinggi vs winner magnitude terbatas.

Masalahnya bukan "salah desain" — tapi di trend market, winner seharusnya bisa lebih besar dari 0.71%. Dengan fixed TP, **trend continuation capacity tidak dimanfaatkan**.

### 3.2 MLP horizon mismatch (confidence: sedang — butuh verifikasi)

Dari `A_architecture_inventory.md` §A.3:

```
MLP_FORWARD_RETURN_WINDOW = 1 (default)  → 1 candle 4H = 4 jam horizon
Threshold label: 0.5 × norm_atr × √W
```

Artinya MLP dilatih untuk prediksi: "apakah harga 4 jam ke depan lebih dari 0.5×ATR dari sekarang?"

Bandingkan dengan eksekusi:
- TP 0.71% — dalam low-vol BTC, ini << 0.5×ATR
- Median holding winner: 4.81 jam (dari D.2)

**Implikasi:** MLP bilang "bull 4H ahead" pada kondisi yang sebenarnya TP 0.71% sudah kena dalam 1-2 jam lalu harga reverse. MLP-nya secara teknis "benar" (prediksi 4H mungkin masih bull), tapi eksekusi bot sudah kena TP lalu mungkin re-entry di posisi lebih tinggi.

**Inilah mekanisme yang bisa menyebabkan "buy di puncak":** bukan karena layer buta, tapi karena MLP optimize untuk horizon yang lebih panjang dari yang bot eksekusikan.

**Status validasi:** Hipotesis ini **belum diverifikasi dengan data**. Butuh:
- Compare distribusi MLP probability bull di trade winner vs loser
- Compare MLP probability di kondisi "harga sudah 1 ATR di atas EMA50 4H" vs baseline

### 3.3 Telemetry blindness (confidence: sangat tinggi)

Dari `C_trade_log_schema.md`: `live_trades` hanya simpan `signal_verdict` + `signal_conviction`. **Tidak bisa** rekonstruksi:
- MLP prob per kelas pada saat entry
- L1 regime aktual
- ATR / vol regime
- MFE/MAE selama hold

Akibatnya: tidak ada feedback loop dari live ke training. Model training tidak tahu "di kondisi seperti apa prediksi sayamu salah di live". Ini **silent degradation risk**.

### 3.4 Data pipeline gap (confidence: tinggi)

- OHLCV di DB stop di 2026-03-18 (diakses 2026-04-24)
- Trade April 2026 tidak bisa di-cross-reference ke indicator context
- 1m OHLCV tidak ada → simulasi intraday not feasible

### 3.5 Engine execution limitation (confidence: tinggi)

- Gateway hanya support **full close**, tidak native partial
- Trailing stop tidak ada sebagai first-class citizen
- Ada `test_sl_freeze_logic.py` yang mengakui skenario "SL + profit" — artinya trailing SL ada secara ad-hoc, tapi tidak terstruktur

### 3.6 Ledger reliability gap (confidence: tinggi — dari user)

**Pattern teridentifikasi:** Trade closed di Lighter, tapi DuckDB `live_trades` masih `status='OPEN'`. Tidak ada update timestamp_close, exit_price, pnl_usdt, atau exit_type.

**Root cause hipotesis:**
- Gateway mengandalkan callback/event setelah order fill, tapi callback bisa miss (network drop, restart bot, race condition)
- Tidak ada **periodic reconciliation worker** yang query Lighter "list of open positions" dan force-resolve diff
- TP/SL yang trigger di Lighter side (server-side stop order) tidak otomatis post-back ke `position_manager.update_trade_on_close`

**Konsekuensi untuk telemetri Tier 0 (revisi v0.2):**

Tidak cukup hanya menambah kolom snapshot di `live_trades`. Kalau row tersebut "stuck OPEN" selamanya, snapshot signal-nya juga tidak akan punya outcome label (TP/SL/PnL). Akibatnya **dataset analisis kondisional tetap bolong** meskipun instrumentasi sudah dipasang.

**Implikasi arsitektur:**

Pisahkan dua concern:
1. **Signal context** — write-once saat signal dibuat. Tidak bergantung pada outcome trade. **Selalu utuh** meski exchange callback miss.
2. **Trade ledger** — mirror dari Lighter, di-sync periodic via reconciliation pipeline. Lighter = source of truth.

Linkage: signal context ↔ trade ledger via `lighter_order_id` yang di-issue Lighter saat order placed.

**Bukti dari findings:**
- Sub-agent menemukan hanya 2 baris CLOSED di DuckDB lokal vs 54 trade di logbook — **konsisten dengan teori bahwa banyak trade tidak ter-update closure-nya** (entah karena DB bukan produksi, atau karena `stuck_open` pattern).
- CSV Lighter (97 fill) tetap reliable dan punya semua data exit (PnL, fee).

---

## 4. Solution roadmap

### TIER 0 — Pondasi (source-of-truth + telemetri reliable)

**Filosofi v0.2:** **Lighter = SOT untuk fakta trade, DuckDB = SOT untuk signal context.** Tidak ada lagi "trade ledger DuckDB" yang berdiri sendiri tanpa reconciliation.

#### 4.0.A — Lighter SDK reconnaissance (prerequisite, 0.5-1 hari)

Sebelum desain reconciliation, harus tahu apa yang Lighter SDK Python sediakan. Action items:

1. Audit `backend/app/adapters/gateways/lighter_execution_gateway.py` — method apa saja yang sudah dipakai
2. Inventory dari Lighter SDK dokumentasi:
   - `get_open_positions()` / `get_positions()` — fetch posisi yang masih open
   - `get_trade_history(start, end)` — fetch closed trades historis
   - `get_order_status(order_id)` — query status spesifik order
   - WebSocket events untuk fill/close notification (real-time path)
   - Rate limit untuk masing-masing endpoint

**Output:** `findings/H_lighter_sdk_capabilities.md` (file baru di folder yang sama). Ini dikerjakan oleh sub-agent berikutnya.

#### 4.0.B — Reconciliation pipeline (3-4 hari)

##### 4.0.B.1 Tabel mirror `trades_lighter`

```sql
CREATE TABLE trades_lighter (
  trade_id           VARCHAR PRIMARY KEY,    -- order_id Lighter (authoritative)
  symbol             VARCHAR NOT NULL,
  side               VARCHAR NOT NULL,       -- LONG / SHORT
  ts_open_ms         BIGINT NOT NULL,        -- dari Lighter fill timestamp
  ts_close_ms        BIGINT,                 -- NULL jika OPEN
  entry_price        DOUBLE NOT NULL,
  exit_price         DOUBLE,
  size_base          DOUBLE NOT NULL,
  pnl_usdt           DOUBLE,                 -- closed_pnl dari Lighter
  fee_usdt           DOUBLE,                 -- fee dari Lighter (terpisah)
  status             VARCHAR NOT NULL,       -- OPEN / CLOSED
  exit_type          VARCHAR,                -- TP / SL / TIME / MANUAL (inferred)
  -- Reconciliation metadata
  last_synced_ms     BIGINT NOT NULL,
  source_checksum    VARCHAR,                -- hash dari raw Lighter response
  reconciliation_lag_ms BIGINT               -- ts_close_ms vs first time we saw CLOSED
);

CREATE INDEX idx_trl_status ON trades_lighter(status);
CREATE INDEX idx_trl_ts_close ON trades_lighter(ts_close_ms);
```

##### 4.0.B.2 Reconciliation worker

Background task yang jalan periodic. Dua mode:

**Mode A — Open positions sweep (interval: 60-120 detik)**
```python
async def reconcile_open_positions():
    duckdb_open = SELECT trade_id FROM trades_lighter WHERE status = 'OPEN'
    lighter_open = await gateway.get_open_positions()  # set of order_id

    # Stuck OPEN — closed di Lighter, OPEN di DuckDB
    stuck = duckdb_open - lighter_open
    for trade_id in stuck:
        details = await gateway.get_trade_details(trade_id)
        upsert_trade_closed(trade_id, details)
        log.warn("reconciled stuck_open", trade_id=trade_id, lag_ms=...)

    # Missing — open di Lighter, ga ada di DuckDB
    missing = lighter_open - duckdb_open
    for trade_id in missing:
        details = await gateway.get_open_position_details(trade_id)
        upsert_trade_open(trade_id, details)
        log.warn("reconciled missing_open", trade_id=trade_id)
```

**Mode B — History backfill (interval: 1 jam)**
```python
async def reconcile_history():
    last_24h = await gateway.get_trade_history(now - 24h, now)
    for trade in last_24h:
        upsert_from_lighter(trade)  # idempotent
```

##### 4.0.B.3 Migration strategy

- Tidak hapus `live_trades` lama (preserve history)
- Tambah `trades_lighter` sebagai tabel baru
- One-time migration: rebuild `trades_lighter` dari Lighter API (last 90 days history) + dari CSV export sebagai gap-filler
- Sediakan VIEW kompatibilitas `live_trades_compat` untuk konsumen lama (sementara)

##### 4.0.B.4 Observability

Tabel reconciliation log:
```sql
CREATE TABLE reconciliation_log (
  ts_ms BIGINT NOT NULL,
  mode VARCHAR NOT NULL,           -- 'sweep' / 'history'
  stuck_resolved INT NOT NULL,
  missing_resolved INT NOT NULL,
  duration_ms INT NOT NULL,
  errors TEXT
);
```

Dashboard metric: `reconciliation_lag_ms` p50/p95/p99 — kalau lag naik berarti ada degradasi sync.

#### 4.0.C — Signal snapshot store + fix `candle_open_ts` (2-3 hari)

##### 4.0.C.1 Tabel baru `signal_snapshots`

```sql
CREATE TABLE signal_snapshots (
  snapshot_id            VARCHAR PRIMARY KEY,    -- UUID generated saat signal
  ts_signal_ms           BIGINT NOT NULL,        -- saat signal generated
  candle_open_ts         BIGINT NOT NULL,        -- candle 4H yang trigger (FIXED dari bug v0.1)
  ts_order_placed_ms     BIGINT,                 -- saat kirim ke Lighter
  -- Intent
  intended_side          VARCHAR NOT NULL,
  intended_size_usdt     DOUBLE NOT NULL,
  intended_entry_price   DOUBLE,
  intended_sl_price      DOUBLE,
  intended_tp_price      DOUBLE,
  -- Layer snapshots
  l1_regime              VARCHAR,
  l1_changepoint_prob    DOUBLE,
  l2_ema_vote            DOUBLE,
  l2_aligned             BOOLEAN,
  l3_prob_bear           DOUBLE,
  l3_prob_neutral        DOUBLE,
  l3_prob_bull           DOUBLE,
  l3_class               VARCHAR,
  l4_vol_regime          VARCHAR,
  l4_current_vol         DOUBLE,
  l4_long_run_vol        DOUBLE,
  -- Market context at signal
  atr_at_signal          DOUBLE,
  funding_at_signal      DOUBLE,
  oi_at_signal           DOUBLE,
  cvd_at_signal          DOUBLE,
  htf_zscore_at_signal   DOUBLE,                  -- (close - ema50_4h) / atr14_4h
  -- Aggregate (existing)
  signal_verdict         VARCHAR,
  signal_conviction      DOUBLE,
  -- Linkage to trade ledger (filled in setelah order placed)
  lighter_order_id       VARCHAR,
  link_status            VARCHAR NOT NULL DEFAULT 'PENDING'
                          -- PENDING / ORDER_PLACED / ORDER_FILLED
                          -- / ORDER_REJECTED / ORPHANED
);

CREATE INDEX idx_snap_order ON signal_snapshots(lighter_order_id);
CREATE INDEX idx_snap_ts ON signal_snapshots(ts_signal_ms);
CREATE INDEX idx_snap_link ON signal_snapshots(link_status);
```

**Karakteristik penting:**
- **Write-once:** snapshot ditulis pas signal generated, tidak pernah di-update kecuali field linkage (`lighter_order_id`, `link_status`)
- **Independen dari order outcome:** snapshot tetap utuh meski order rejected atau ledger sync gagal
- **Schema eksplisit (bukan JSON):** trade-off chosen for query performance + indexability. Schema migration lebih ribet, tapi DuckDB OLAP-friendly untuk aggregation.

**Alternatif yang ditolak (vs v0.1):** Schema JSON-flexible (`kv_json TEXT`) — ditolak karena kita sudah tahu field-field yang dibutuhkan (predictable schema), dan agregasi `WHERE l3_prob_bull > 0.7` jauh lebih cepat di kolom native vs JSON parsing.

##### 4.0.C.2 Integration di `signal_service` & `position_manager`

Flow yang baru:

```python
# Di signal_service, saat signal generated:
snapshot = build_signal_snapshot(
    candle_open_ts=df.iloc[-1].timestamp,   # FIX: dari candle, bukan time.time()
    l1=l1_output, l2=l2_output, l3=l3_output, l4=l4_output,
    market_context=metrics_at_signal,
    intended=intended_order
)
snapshot_id = signal_snapshot_repo.insert(snapshot)
# snapshot_id passed downstream

# Di position_manager, saat order ditempatkan ke Lighter:
order_response = await gateway.place_order(...)
signal_snapshot_repo.update_linkage(
    snapshot_id=snapshot_id,
    lighter_order_id=order_response.order_id,
    link_status='ORDER_PLACED'
)

# Reconciliation worker juga update link_status saat fill terdeteksi:
# ORDER_PLACED → ORDER_FILLED ketika trades_lighter row appears
```

##### 4.0.C.3 Fix bug `candle_open_ts`

Now bagian dari snapshot flow di atas, bukan field di trade ledger. Bug originalnya (`time.time()` di `position_manager.py:922`) di-deprecate karena field `candle_open_ts` pindah ke `signal_snapshots`.

##### 4.0.C.4 Orphan detection

Worker harian (atau on-demand):

```sql
-- Snapshot dengan link_status = ORDER_PLACED tapi tidak punya match di trades_lighter
-- setelah X menit → kemungkinan order rejected tanpa callback, atau orphan
UPDATE signal_snapshots
SET link_status = 'ORPHANED'
WHERE link_status = 'ORDER_PLACED'
  AND ts_order_placed_ms < (now_ms - 10*60*1000)
  AND lighter_order_id NOT IN (SELECT trade_id FROM trades_lighter);
```

Orphan rate jadi metric kualitas pipeline.

#### 4.0.D — Tabel intraday `trade_snapshots` (MFE/MAE polling)

(Sama seperti v0.1, tapi sekarang FK ke `trades_lighter.trade_id`, bukan `live_trades.id`)

```sql
CREATE TABLE trade_snapshots (
  trade_id      VARCHAR NOT NULL,         -- FK trades_lighter
  timestamp_ms  BIGINT NOT NULL,
  price         DOUBLE NOT NULL,
  pnl_usdt      DOUBLE NOT NULL,
  pnl_pct       DOUBLE NOT NULL,
  PRIMARY KEY (trade_id, timestamp_ms)
);
CREATE INDEX idx_tsnap_trade ON trade_snapshots(trade_id);
```

**Polling frequency:** 30 detik. Background task di reconciliation worker juga (single goroutine pattern).

**Derive MFE/MAE on-the-fly:**
```sql
SELECT trade_id, MAX(pnl_pct) AS mfe, MIN(pnl_pct) AS mae
FROM trade_snapshots GROUP BY trade_id;
```

(Tidak perlu maintain running max kolom — overhead di-defer ke query time.)

#### 4.0 — Final analytics view

Setelah Tier 0 selesai, view utama untuk analisis:

```sql
CREATE VIEW analytics_trades AS
SELECT
  t.trade_id,
  t.symbol, t.side,
  t.ts_open_ms, t.ts_close_ms,
  t.entry_price, t.exit_price,
  t.pnl_usdt, t.fee_usdt,
  t.exit_type, t.status,
  s.candle_open_ts,
  s.l1_regime, s.l1_changepoint_prob,
  s.l2_ema_vote, s.l2_aligned,
  s.l3_prob_bull, s.l3_prob_bear, s.l3_class,
  s.l4_vol_regime, s.l4_current_vol,
  s.atr_at_signal, s.funding_at_signal, s.oi_at_signal, s.cvd_at_signal,
  s.htf_zscore_at_signal,
  s.signal_conviction,
  -- MFE/MAE on-the-fly
  (SELECT MAX(pnl_pct) FROM trade_snapshots WHERE trade_id = t.trade_id) AS mfe_pct,
  (SELECT MIN(pnl_pct) FROM trade_snapshots WHERE trade_id = t.trade_id) AS mae_pct
FROM trades_lighter t
LEFT JOIN signal_snapshots s ON s.lighter_order_id = t.trade_id
WHERE t.status = 'CLOSED';
```

Ini view yang nantinya jadi input untuk Area D/E investigation berikutnya.

---

### TIER 1 — Data sync

#### 4.1.1 Refresh DB OHLCV + market_metrics

Jalankan ingestion script sampai ≥ tanggal trade terakhir. Verifikasi `max(timestamp)` >= NOW().

#### 4.1.2 Dump `live_trades` produksi

Bergantung jawaban user di pertanyaan klarifikasi (DB ada di mana).

#### 4.1.3 Ingest 1m OHLCV periode trade

Buat tabel `btc_ohlcv_1m` untuk periode April-ongoing. Ini wajib untuk simulasi asymmetric exit yang akurat.

---

### TIER 2 — MLP horizon refactor (kandidat solusi utama)

Ini investigasi yang paling aku rekomendasikan berdasarkan findings. Hipotesis: **MLP mis-optimize karena objective-nya beda dari eksekusi.**

#### 4.2.1 Fase investigasi (2 hari)

- Ambil data 3 bulan historis dengan telemetri (after Tier 0)
- Compute 3 label alternatif per trade:
  - **L_old**: forward return 4H > threshold (current)
  - **L_new1**: TP_hit_before_SL given current TP/SL config (direct execution label)
  - **L_new2**: forward return 1H > 0.5% (match realistis holding)
- Train 3 MLP dengan label berbeda, sama feature set
- Compare test-set performance:
  - Precision/recall per kelas
  - Calibration (reliability diagram)
  - Confusion matrix per regime BOCPD
  - **Live trade simulator**: run prediksi dengan tiap model vs actual outcome

#### 4.2.2 Fase A/B test (1 minggu paper)

Kalau L_new1 atau L_new2 jelas lebih baik:
- Deploy paralel di paper mode
- Hitung EV per signal setelah 100+ sinyal
- Keputusan: promote ke live atau rollback

#### 4.2.3 Risk

- **Overfitting risk:** label baru bisa overfit ke period training
- **Regime dependency:** hasil di bull-trend bisa beda dari chop
- Mitigasi: walk-forward validation eksplisit (bukan sklearn internal), minimum 3 bulan test window

---

### TIER 3 — Asymmetric exit (kandidat solusi paralel)

#### 4.3.1 Config proposal

**Skenario A (conservative):** TP1 @ 0.4% close 60%, move SL to BE, trail remaining 40% with 2×ATR chandelier
**Skenario B (aggressive):** TP1 @ 0.4% close 40%, TP2 @ 1.2% close 30%, trail remaining 30%
**Skenario C (pure trail):** No fixed TP, initial SL 1.333%, trail with 3×ATR once profit > 0.3%

#### 4.3.2 Engine changes needed

- Emulasi partial close: modify `close_position_market` untuk support `quantity` parameter (bukan full position)
- Trailing logic: polling-based di `PositionManager.manage_open_positions()`
- State machine: trade dalam state `ENTRY → TP1_HIT → TRAILING → EXIT`
- Test coverage: unit tests untuk partial close + trailing amend

#### 4.3.3 Success metric

- Avg winner pct naik ≥ 50% (dari 0.71% ke ≥1.07%)
- WR drop diterima: max −10 pp (dari 75% ke ≥65%)
- Net EV naik ≥ 2× baseline
- Max drawdown tidak memburuk > 25%

#### 4.3.4 Rollout

1. Paper mode 2 minggu → collect 50+ signal
2. Production 50% sizing 2 minggu
3. Full sizing setelah metric tercapai

---

### TIER 4 — Exhaustion layer terpisah (conditional, deferred)

Hanya justified kalau Tier 2 + Tier 3 tidak cukup menaikkan EV **dan** data post-instrumentation menunjukkan loss memang cluster di exhaustion zone.

**Placeholder design:**
- Output: scalar `exhaustion_score ∈ [0, 1]`
- Komponen:
  - Funding z-score rolling 30 hari
  - HTF (4H) price stretch vs EMA50 (dalam unit ATR)
  - CVD divergence flag (1h window)
  - OI/price divergence (24h)
- Pemakaian: **modifier**, bukan signal generator:
  - `exhaustion_score > 0.7` → veto entry
  - `0.5 < score ≤ 0.7` → reduce size 50%, tighten TP 50bps
- Kalibrasi: backtest di 6+ bulan historis dengan walk-forward

**Defer sampai ada bukti empiris** bahwa layer ini punya signal.

---

## 5. Implementation roadmap (timeline indikatif, revisi v0.2)

```
Week 1:
  [Tier 0a] Lighter SDK reconnaissance         ← 0.5-1 day (sub-agent)
  [Tier 0c] Schema migration review           ← 1 day (user review)
  [Tier 0b] Reconciliation pipeline impl      ← 3 days (mulai paralel setelah recon)
  [Tier 1]  Data refresh scripts              ← paralel

Week 2:
  [Tier 0b] Reconciliation worker deploy + observe stuck_open metric
  [Tier 0c] Signal snapshot store implement   ← 2-3 days
  [Tier 0d] trade_snapshots polling worker    ← 1 day
  [Tier 1]  1m OHLCV ingest                   ← 2 days

Week 3:
  [Tier 0]  Verify analytics_trades view berisi data nyata (>10 trade lengkap)
  [Tier 2]  MLP horizon investigation kickoff ← 5 days
  [Tier 3]  Asymmetric exit design + engine   ← 3 days (parallel)

Week 4-5:
  [Tier 3]  Paper trading asymmetric exit (forward test)
  [Tier 2]  A/B MLP variants paper

Week 6+:
  Decision point: promote winners, evaluasi Tier 4 (exhaustion layer)
```

**Critical path:** Tier 0a → 0b → 0c. Tier 1 paralel. Tier 2/3 dimulai setelah ada data telemetri minimal 1-2 minggu (Week 3-4 paling cepat realistis untuk hasil meaningful).

---

## 6. Success metrics (fase keseluruhan)

**Primary:**
- Net EV per trade naik dari +0.22% → target ≥+0.50%
- Sharpe ratio (rolling 30 hari) naik dari 3.13 → target ≥4.0
- Max drawdown tidak memburuk > 25%

**Secondary:**
- Avg winner pct naik ≥50%
- Profit factor ≥ 2.0 (dari ~1.5 current estimated)
- Telemetri coverage: 100% trade punya snapshot lengkap

**Guardrail (abort trigger):**
- WR drop > 12 pp dari baseline
- Dua minggu berturut-turut negative PnL
- Drawdown > $15 single period

---

## 7. Risk analysis

| Risiko | Prob | Impact | Mitigasi |
|---|---|---|---|
| Migration corrupt existing `live_trades` | Rendah | Tinggi | Backup sebelum migrate, rollback script. v0.2: tabel baru dibuat *terpisah*, `live_trades` lama tidak di-touch |
| Reconciliation worker over-fetch Lighter API | Sedang | Sedang | Rate limit per endpoint, exponential backoff |
| One-time history backfill miss order_id | Sedang | Sedang | Cross-check dengan CSV export sebagai gap-filler |
| Snapshot signal tidak match fill (race) | Rendah | Sedang | UUID di snapshot, linkage update saat order_id confirmed; metric orphan_rate |
| MLP label baru worse OOS | Sedang | Sedang | Walk-forward validation, paper A/B |
| Asymmetric exit turunkan WR > 12pp | Sedang | Sedang | Gradual rollout, guardrail monitoring |
| Trailing logic bug → order spam | Rendah | Tinggi | Rate limit, idempotency check |
| Data refresh introduce look-ahead bug | Sedang | Tinggi | Temporal audit sebelum training |
| Polling MFE/MAE overwhelm exchange API | Rendah | Sedang | 30s interval, batch queries |

---

## 8. Open assumptions to validate during implementation

**Resolved di v0.2:**
- ~~Telemetri schema kolom vs JSON~~ → Pilih kolom eksplisit di tabel `signal_snapshots` baru (rationale di §4.0.C.1)
- ~~"DB produksi" location~~ → Tidak relevan setelah pivot SOT ke Lighter. Sub-agent berikutnya tetap perlu konfirmasi `DB_PATH` env aktif buat menjamin tabel baru dibuat di tempat yang benar.

**Resolved di v0.3:**
- ~~Lighter SDK endpoint discovery~~ → `findings/H_lighter_sdk_capabilities.md` complete
- ~~5 keputusan teknis (host/trade_id/granularity/backfill/exit_type)~~ → default frozen di "Frozen decisions" table di header
- ~~Standalone runtime validation~~ → di-skip; validasi via implementation
- ~~Lighter testnet URL contradiction~~ → user confirm: bot live di mainnet, dokumentasi outdated; kode gateway = source of truth

**Yang akan divalidasi natural saat coding (Tier 0b/0c di branch):**

1. **[Multi-fill rate]** Asumsi >90% single-fill di akun ini. Kalau ternyata multi-fill umum → reconsider per-fill granularity (re-evaluate setelah 100 trade pertama ter-mirror).
2. **[`OrderApi.export` async lag]** Asumsi `data_url` tersedia segera. Kalau ada delay (export job async) > 1 menit → adjust backfill chunk strategy.
3. **[Field semantics]** Mapping di `findings/H §H.5` belum diverifikasi runtime. Setiap field nullable/missing yang ditemukan saat first parse harus di-handle defensively.
4. **[Rate limit aktual]** Asumsi premium-tier (24k weighted/min). Kalau akun standard (60/min) → drastis turunkan polling frequency atau upgrade tier.
5. **[Auth token TTL]** Belum jelas berapa lama token dari `create_auth_token_with_expiry` valid. Worker harus refresh token preemptively.

**Yang masih butuh keputusan lead analyst (di luar reconciliation):**

6. **[Retrain MLP]** Apakah boleh retrain dengan label baru di environment dedicated? Atau harus buat pipeline terpisah dulu? (Relevan saat Tier 2 dimulai).
7. **[Paper mode]** Apakah infrastruktur paper trading sudah ada, atau perlu dibangun? (Relevan saat Tier 3 dimulai).
8. **[Prioritas Tier 2 vs Tier 3]** Kalau harus pilih satu dulu, MLP refactor atau asymmetric exit?
9. **[Migration timing]** Reconciliation pipeline harus deploy ke production saat **tidak ada posisi terbuka**. Window mana yang biasanya bot idle (untuk safe deploy)?

---

## 9. Appendix — referensi findings

| Claim di dokumen ini | Sumber |
|---|---|
| Fitur MLP 8 kolom + 4 regime | `A_architecture_inventory.md §A.3` |
| `candle_open_ts` bug | `C_trade_log_schema.md` Gaps §2 |
| Distribusi `wins_before_loss` | `D_loss_pattern_analysis.md §D.1` |
| DB OHLCV stop 2026-03-18 | `B_data_inventory.md §B.1` |
| `live_trades` schema | `C_trade_log_schema.md §C.2` |
| Gateway no partial close | `F_asymmetric_exit_simulation.md §F.1` |
| MLP artifact tidak ada | `G_mlp_deep_dive.md` |
| R:R calculation | logbook `performance_logbook_mar_apr_2026.qmd` |
| `stuck_open` pattern | User confirmation, sesi 2026-04-24 chat |
| Lighter CSV reliability vs DuckDB | User confirmation, sesi 2026-04-24 chat |

---

**End of design doc v0.3 — FROZEN, ready for implementation.**

## Implementation artifacts (next deliverables)

Di folder `proposed_code/` (proposal-grade, belum git branch):

```
proposed_code/
├── README.md                    ← overview & how to deploy
├── migrations/                  ← SQL files siap di-execute
│   ├── 001_create_trades_lighter.sql
│   ├── 002_create_signal_snapshots.sql
│   ├── 003_create_trade_snapshots.sql
│   ├── 004_create_reconciliation_log.sql
│   └── 005_create_analytics_view.sql
├── reconciliation/              ← Tier 0b reconciliation worker
│   ├── lighter_reconciliation_worker.py
│   ├── trades_lighter_repository.py
│   └── tests/
└── signal_snapshot/             ← Tier 0c signal context store
    ├── signal_snapshot_repository.py
    ├── signal_service_integration.md   ← how to hook ke signal_service
    └── tests/
```

**Catatan penting:** Code di `proposed_code/` adalah **proposal**, bukan production code. Setelah review user → pindah ke proper branch (`refactor/reconciliation-pipeline`) → review kode lebih dalam → deploy saat akun **tanpa posisi terbuka**.
