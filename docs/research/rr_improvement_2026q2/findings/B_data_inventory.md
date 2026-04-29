# Data availability — DuckDB & feeds

**Area:** B — Data Availability  
**Status:** Partial (schema + path diverifikasi; kedalaman real-time vs historis sebagian inferensi dari kode)  
**Updated:** 2026-04-24

## TL;DR

Data harga & metrik terpusat di **DuckDB** (`btc_ohlcv_4h`, `market_metrics`) dengan **ASOF join** ke candle 4H. **CVD** ada di kolom OHLCV dan di snapshot `market_metrics`. **OI, funding, liquidations, OBI, FGI** ada di `market_metrics`. **Tidak** ada tabel Coinglass terpisah di repo; kedalaman historis konkret = isi file DB lokal (contoh: OHLCV sampai **2026-03-18** pada probing ini — query di bawah).

## Methodology

- Inspeksi DDL: `backend/app/adapters/repositories/market_repository.py` (`_init_tables`, `get_ohlcv_with_metrics`).
- Query: `SELECT min(timestamp), max(timestamp), count(*) FROM btc_ohlcv_4h` dan analog untuk `market_metrics` (dijalankan saat sesi riset).

## Findings (format README B)

### B.1 OHLCV BTC perpetual (4H)

```
Source: btc_ohlcv_4h
Provider/exchange: Binance futures (via pipeline data_engine / backfill scripts — verifikasi deployment)
Path/connector di codebase: MarketRepository, data_engine.py
Granularity: 4H (satu tabel; bukan multi-TF terpisah di DuckDB ini)
Historical depth: contoh DB lokal — min ts 1568332800000, max ts 1773835200000 (= 2026-03-18 12:00 UTC), n=14270
Real-time available: update saat proses ingestion jalan (bukan query langsung dari sini)
Storage: DuckDB table btc_ohlcv_4h
Sample query: SELECT * FROM btc_ohlcv_4h ORDER BY timestamp DESC LIMIT 5
```

Catatan: **1m / 5m / 15m / 1h** seperti daftar di README **tidak** muncul sebagai tabel terpisah di `market_repository.py` — **TIDAK TERSEDIA** di DuckDB layer ini kecuali ada pipeline lain di luar file yang diperiksa.

### B.2 CVD

```
Source: cumulative volume delta
Provider: sama dengan feed OHLCV (tersimpan per bar)
Path: kolom cvd di btc_ohlcv_4h; juga cvd di market_metrics (snapshot)
Granularity: 4H bar + snapshot metrics
Historical depth: mengikuti baris OHLCV / metrics
Real-time available: via ingestion (inferensi)
Storage: DuckDB
Sample query: SELECT timestamp, cvd FROM btc_ohlcv_4h ORDER BY timestamp DESC LIMIT 5
```

### B.3 Order book snapshot / L2

```
Source: order book imbalance
Path: market_metrics.order_book_imbalance (aggregate), bukan full L2
Granularity: per-row metrics (timestamp)
Historical depth: mengikuti market_metrics
Real-time available: inferensi dari insert_metrics callers
Storage: DuckDB
```

Full **L2 book** depth: **TIDAK TERSEDIA** di schema DuckDB yang diinventaris.

### B.4 Open interest

```
Source: open_interest
Path: market_metrics.open_interest
Granularity: snapshot per timestamp metrics
Storage: DuckDB
Sample: SELECT timestamp, open_interest FROM market_metrics ORDER BY timestamp DESC LIMIT 5
```

### B.5 Funding rate

```
Source: funding_rate
Path: market_metrics.funding_rate
Storage: DuckDB
```

### B.6 Liquidations

```
Source: liquidations_buy, liquidations_sell
Path: market_metrics (kolom DOUBLE)
Storage: DuckDB
```

### B.7 Spot vs perp basis

**TIDAK TERSEDIA** sebagai kolom eksplisit di `market_repository` DDL yang dibaca — mungkin derivatif dari feed lain; tidak diverifikasi di sesi ini.

### B.8 BTC dominance / total market cap

`global_mcap_change` ada di `market_metrics` (perubahan % global mcap, bukan dominance mentah). Field **dominance** eksplisit: **TIDAK TERSEDIA** di DDL ini.

### B.9 News / event calendar (FOMC, CPI)

**TIDAK TERSEDIA** di DuckDB schema; kemungkinan manual / feed eksternal (tidak di-repo).

## Gaps & Limitations

- Rentang **OHLCV di DB lokal** bisa tertinggal vs periode **export Lighter April 2026** — join ASOF untuk proxy HTF pada April akan **salah** (memakai candle terakhir yang tersedia).
- **Multi-timeframe OHLCV** (1m untuk sim trailing) tidak terbukti di tabel DuckDB inti.

## Raw Sources

- `backend/app/adapters/repositories/market_repository.py` baris 38–133  
- Query sesi: `max(timestamp)` dari `btc_ohlcv_4h` → `1773835200000` (2026-03-18 UTC)
