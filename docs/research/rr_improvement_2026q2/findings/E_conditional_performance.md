# Conditional performance vs exhaustion proxies

**Area:** E — Conditional Performance  
**Status:** Partial / Blocked untuk beberapa proxy (data waktu tidak selaras)  
**Updated:** 2026-04-24

## TL;DR

**E.1 (funding):** join ASOF `market_metrics.funding_rate` ke `ts_open` episode → nilai hampir konstan **-0.000032** pada sampel DB lokal → **quintile tidak terbentuk** (varians nol). **E.2 (HTF stretch):** OHLCV DuckDB **berakhir 2026-03-18** sedangkan episode April 2026 — **TIDAK VALID** memakai stretch dari candle terakhir DB untuk April. **E.3–E.4:** butuh deret OI/CVD resolusi tinggi selaras entry → **TIDAK TERSEDIA** pada join ini. **E.5:** proxy streak sisi per hari UTC (sampel kecil). **E.6:** output layer vol **TIDAK** di-log per trade; join ke candle terakhir DB sama-sama bias untuk April.

## Methodology

- Episode: sama seperti Area D (`aggregate_lighter_roundtrips.py`, `complete=True`).  
- Funding join: DuckDB `ASOF LEFT JOIN market_metrics` pada `ts_open_ms` (lihat sesi Python 2026-04-24).  
- Stretch HTF: rencana `(close - ema50) / atr14` pada `btc_ohlcv_4h` — **dibatalkan** untuk April karena `max(timestamp)` OHLCV < tanggal buka episode.

## Findings per sub-area

### E.1 Funding rate bucket

| Bucket | n | WR | avg PnL USD |
|--------|---|-----|----------------|
| (varians nol) | 27 | 0.741 | +0.231 |

`funding_rate` hasil ASOF untuk 27 episode: **-3.2e-5** (semua baris identik pada probing). `pd.qcut(..., q=5)` gagal / kosong.

### E.2 HTF z-score (price vs EMA50 dalam unit ATR 4H)

**TIDAK TERSEDIA (valid)** untuk episode **2026-04-02 … 2026-04-22** karena:

```text
Query: SELECT max(timestamp) FROM btc_ohlcv_4h  → 1773835200000 = 2026-03-18 12:00 UTC
Sumber: DuckDB btc-quant.db (sesi probing)
```

Merge ASOF ke April hanya mengulang candle **2026-03-18** → **look-ahead / stale snapshot** — **dilarang** dipakai sebagai bukti E.2.

### E.3 OI delta vs price delta (24h)

**TIDAK TERSEDIA** — tidak ada deret OI 24h per titik entry episode di artefak analisis ini (hanya snapshot `market_metrics` tanpa join temporal valid untuk April).

### E.4 CVD divergence (1h window)

**TIDAK TERSEDIA** — tidak ada OHLCV 1h di DuckDB inti + tidak ada CVD 1h terpisah.

### E.5 Streak posisi (arah sama dalam hari UTC)

Definisi operasional: urut episode **`t_open`**; dalam satu `day` (UTC), naikkan indeks streak setiap episode dengan **`side`** sama dengan episode sebelumnya di hari itu; reset saat sisi berganti.

| streak_idx | n | WR |
|------------|---|-----|
| 1 | 16 | 0.875 |
| 2 | 10 | 0.600 |
| 3 | 1 | 0.000 |

**n=1** pada streak 3 → **tidak signifikan**.

### E.6 Volatility regime

**TIDAK TERSEDIA** per episode dari log — harus replay `VolatilityRegimeEstimator` pada OHLCV yang mencakup tanggal entry; OHLCV DB tidak mencakup April → **blocked** untuk rentang CSV ini.

## Gaps & Limitations

- Perlu **sinkronisasi**: refresh `btc_ohlcv_4h` + `market_metrics` hingga ≥ akhir periode export, atau gunakan API historis exchange/Coinglass sesuai kebijakan lead analyst.  
- Tanpa itu, **E.1–E.2–E.6** tidak bisa menguji hipotesis exhaustion dengan kuat.

## Raw Sources

- `backend/app/infrastructure/database/btc-quant.db` — `SELECT max(timestamp) FROM btc_ohlcv_4h`  
- `market_metrics` schema: `market_repository.py`  
- Script episode: `scripts/aggregate_lighter_roundtrips.py`
