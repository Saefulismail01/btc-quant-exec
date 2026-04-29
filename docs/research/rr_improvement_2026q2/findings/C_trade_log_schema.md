# Trade log & telemetry — production schema

**Area:** C — Trade Log & Telemetry Schema  
**Status:** Complete (schema dari kode + verifikasi DuckDB lokal)  
**Updated:** 2026-04-24 (revisi: export Lighter root repo)

## TL;DR

Trade live persist ke **DuckDB** tabel `live_trades`, path default `backend/app/infrastructure/database/btc-quant.db` (override env `DB_PATH`). Kolom mencakup entry/exit, PnL, `exit_type`, dan **hanya** snapshot sinyal agregat (`signal_verdict`, `signal_conviction`). **Tidak** ada snapshot L1 regime, nilai L2, forecast vol, MFE/MAE, atau fee terpisah — ini gap utama untuk analisis retrospektif mendalam.

## Methodology

- Baca implementasi: `backend/app/adapters/repositories/live_trade_repository.py` (`CREATE TABLE`, `insert_trade`, `update_trade_on_close`).
- Verifikasi runtime: `DESCRIBE live_trades` + `SELECT count(*) WHERE status='CLOSED'` via `docs/research/rr_improvement_2026q2/scripts/_probe_db.py` dan `analyze_live_trades.py`.

## Findings

### C.1 Lokasi production

| Item | Nilai |
|------|--------|
| Engine | DuckDB |
| Path default | `backend/app/infrastructure/database/btc-quant.db` |
| Override | Environment variable `DB_PATH` (lihat `DEFAULT_DB_PATH` di `live_trade_repository.py` baris 29–31) |
| Tabel utama | `live_trades` |

### C.2 Schema `live_trades` (tipe dari `DESCRIBE` + definisi `CREATE`)

| Kolom | Tipe | Catatan |
|--------|------|---------|
| `id` | VARCHAR PK | ID trade (sering order id / hash dari exchange) |
| `timestamp_open` | BIGINT | Unix **milliseconds** |
| `timestamp_close` | BIGINT | Unix ms, NULL sampai close |
| `symbol` | VARCHAR | Contoh: `BTC/USDT` |
| `side` | VARCHAR | `LONG` \| `SHORT` |
| `entry_price` | DOUBLE | |
| `exit_price` | DOUBLE | NULL jika OPEN |
| `size_usdt` | DOUBLE | Margin notional (USDT) |
| `size_base` | DOUBLE | Kuantitas base (BTC) |
| `leverage` | INTEGER | |
| `sl_price`, `tp_price` | DOUBLE | Harga trigger |
| `sl_order_id`, `tp_order_id` | VARCHAR | Bisa berisi metadata SDK panjang (bukan murni id pendek) |
| `exit_type` | VARCHAR | Di-update saat close: mis. `SL` \| `TP` \| `TIME_EXIT` \| `MANUAL` (lihat docstring `update_trade_on_close`, baris 192) |
| `status` | VARCHAR | `OPEN` \| `CLOSED` |
| `pnl_usdt`, `pnl_pct` | DOUBLE | Diisi saat close |
| `signal_verdict` | VARCHAR | Dari `SignalResponse.confluence.verdict` saat open |
| `signal_conviction` | DOUBLE | `confluence.conviction_pct` |
| `candle_open_ts` | BIGINT | **Diharapkan** timestamp candle pemicu; **di `position_manager` saat ini diisi `time.time()` ms**, bukan candle — lihat temuan di bawah |
| `entry_filled_quote` | DOUBLE | USDC entry fill dari Lighter (opsional) |

Referensi DDL: ```76:99:backend/app/adapters/repositories/live_trade_repository.py
                    CREATE TABLE IF NOT EXISTS live_trades (
                        id                  VARCHAR PRIMARY KEY,
                        timestamp_open      BIGINT NOT NULL,
                        ...
                        entry_filled_quote  DOUBLE
                    )
```

### C.3 Field operasional (ya/tidak)

| Pertanyaan | Jawaban |
|------------|---------|
| Entry/exit timestamp | Ya (`timestamp_open`, `timestamp_close`) |
| Side, size, entry/exit price | Ya |
| Fees tersimpan eksplisit | **Tidak** di `live_trades` |
| Realized PnL | Ya (`pnl_usdt`, `pnl_pct`) |
| Exit reason | Ya (`exit_type`) |

### C.4 Snapshot signal state (L1–L4) saat entry

| Layer | Tersimpan? |
|-------|------------|
| L1 BOCPD regime / prob changepoint | **Tidak** |
| L2 indikator / vote | **Tidak** (hanya agregat via verdict jika terkait) |
| L3 MLP score mentah / prob kelas | **Tidak** — hanya `signal_conviction` + `signal_verdict` |
| L4 vol (Heston) forecast | **Tidak** |
| ATR pada entry | **Tidak** (bisa di-rekonstruksi dari OHLCV eksternal + `timestamp_open`) |

### C.5 MFE / MAE

**Tidak** tersimpan di `live_trades`.

### C.6 Audit tick-by-tick PnL intraday

**Tidak** di schema ini (hanya open/close).

### C.7 CSV export Lighter

Format umum (header): `Market,Side,Date,Trade Value,Size,Price,Closed PnL,Fee,Role,Type` — **fill-level** exchange (satu posisi bisa banyak baris), bukan baris 1:1 dengan `live_trades.id`. Untuk metrik per-posisi (streak, R:R) perlu **agregasi** (FIFO net size) atau memakai `live_trades` DuckDB.

| File | Baris data | Rentang `Date` (UTC) | Catatan |
|------|------------|----------------------|---------|
| `docs/reports/data/trade_export_2026-03-27.csv` | 118 | 2026-03-10 16:05 — 2026-03-27 05:33 | Arsip repo |
| `docs/reports/data/trade_export_2026-03-29.csv` | 140 | 2026-03-10 16:05 — 2026-03-29 02:29 | Arsip repo |
| **`lighter-trade-export-2026-04-24T01_03_31.715Z-UTC.csv`** (root repo) | **97** | **2026-04-02 08:00:46 — 2026-04-24 00:00:56** | Disuplai user 2026-04-24; cakupan Apr 2026 |

Distribusi sisi (file 2026-04-24): `Open Long` 36, `Close Long` 35, `Open Short` 11, `Close Short` 15 (hitung via `pandas.read_csv` + `value_counts` pada kolom `Side`).

### C.8 Jumlah trade / fill tersedia untuk analisis

- **`live_trades` (DuckDB lokal):** `SELECT count(*) FROM live_trades WHERE status='CLOSED'` → **2** (lihat `scripts/_probe_db.py`) — tidak cukup untuk D/E statistik.
- **Export Lighter 2026-04-24:** **97** baris fill (bukan 54 posisi agregat); cocok untuk rekonsiliasi PnL/fee di exchange dan analisis fill-level, bukan pengganti penuh `live_trades` + `exit_type` bot.
- Angka **54 posisi** di README (logbook Mar–Apr 2026) **tidak** terverifikasi di DuckDB lokal; bandingkan dengan agregasi dari CSV atau DB produksi jika tersedia.

### Sample 5 baris

Hanya 2 baris CLOSED tersedia lokal; contoh kolom terlihat di output `scripts/_probe_db.py` (trade TP, `WEAK BUY`, conviction 19.8).

## Gaps & Limitations

1. **Tidak ada** persistensi regime L1, fitur L2, probabilitas kelas MLP, atau label vol regime pada saat entry.
2. **`candle_open_ts` vs implementasi:** insert dari `position_manager` memakai `int(time.time() * 1000)` untuk `candle_open_ts`, bukan candle signal — ```920:923:backend/app/use_cases/position_manager.py
                signal_verdict=signal.confluence.verdict,
                signal_conviction=signal.confluence.conviction_pct,
                candle_open_ts=int(time.time() * 1000),
```
3. **Fees** tidak di `live_trades` (CSV Lighter punya kolom `Fee`).
4. Untuk **D/E** retrospektif kondisional terhadap L1/L3, perlu **replay pipeline** atau **instrumentasi** kolom baru (di luar scope sub-agent saat ini).

## Raw Sources

- `backend/app/adapters/repositories/live_trade_repository.py` baris 29–31, 71–214, 254–304  
- `backend/app/use_cases/position_manager.py` baris 906–924  
- `docs/reports/data/trade_export_2026-03-27.csv`, `trade_export_2026-03-29.csv`  
- `lighter-trade-export-2026-04-24T01_03_31.715Z-UTC.csv` (root workspace)  
- Script: `docs/research/rr_improvement_2026q2/scripts/_probe_db.py`, `analyze_live_trades.py`, `aggregate_lighter_roundtrips.py` (opsi `--episode-window-utc YYYY-MM-DD YYYY-MM-DD` untuk rentang **tanpa intervensi** 20–24 Apr)  
- Episode agregat (proxy posisi): `docs/research/rr_improvement_2026q2/data/episodes_lighter_2026-04-24.csv`
