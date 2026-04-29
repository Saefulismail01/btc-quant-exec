**Tautan GitHub:** [Issue #1 — fondasi Tier 0](https://github.com/Saefulismail01/btc-quant-exec/issues/1) (dibuka 2026-04-24)  
*Isi di bawah ini = mirror; gunakan `gh issue edit` untuk menyamakan isu di GitHub.*

---

## Ringkasan

Isu ini men-track **Tier 0 — fondasi data trading**: **Lighter = sumber kebenaran** untuk fakta trade, **konteks sinyal yang tidak berubah** (L1–L4 + niat order) disimpan di DuckDB, **worker rekonsiliasi** menangani `stuck_open` dan mirror state, dan **analisis kondisional** (WR per regime, MFE/MAE, kalibrasi MLP) memungkinkan **setelah** telemetri dipercaya.

Ini **bukan** (belum) mengubah TP/SL, retrain MLP, atau menambah layer exhaustion. Itu mengandalkan Tier 0 + data Tier 1 (lihat `DESIGN_DOC.md`).

## Masalah yang kita selesaikan

- **Matematika eksekusi:** Win rate tinggi tapi **R:R ≈ 0.53** → EV tipis; butuh ukuran yang lebih jujur sebelum mengganti strategi.
- **Jarak telemetri:** Tidak ada **snapshot L1/L2/L3/L4 per entry** yang tahan lama → tidak bisa jawab “kenapa loss ini” secara retrospektif.
- **Selenis ledger:** DuckDB `live_trades` bisa **tidak sama** dengan Lighter (mis. `stuck_open`: di bursa sudah tutup, lokal masih OPEN) → analisis hanya dari baris lokal tidak andal.
- **Hipotesis horizon (divalidasi pasca Tier 0):** MLP dilatih **return maju 4H** mungkin tidak selaras **holding pendek / TP tetap** — butuh data, bukan tebak-tebakan.

## Yang sudah ada (proposal / dokumen)

- **Desain beku:** `docs/research/rr_improvement_2026q2/DESIGN_DOC.md` **v0.3**
- **Findings:** `docs/research/rr_improvement_2026q2/findings/` (A–H, SUMMARY)
- **Kode proposal + uji (bukan produksi):** `docs/research/rr_improvement_2026q2/proposed_code/`
  - Migrasi `001`–`005`, `reconciliation/`, `signal_snapshot/`, `INTEGRATION.md`
  - `pytest proposed_code` → **74 lulus** (DuckDB in-memory, tanpa `lighter` di tes)
- **Arsip proses:** `docs/research/rr_improvement_2026q2/PROCESS_DOCUMENTATION.md`

## Cakupan isu ini (implementasi)

1. **Branch:** mis. `refactor/reconciliation-pipeline` (nama final tim).
2. **Port** modul proposal dari `proposed_code/` ke `backend/` (atau layout paket yang disepakati); **tanpa** ubah perilaku strategi sampai feature flag mengizinkan.
3. **Jalankan migrasi SQL** `001`–`005` ke path DuckDB **yang benar** (`DB_PATH` / backup dulu).
4. **Sambungkan** `LighterReconciliationWorker` (atau ekuivalen) ke gateway sungguhan; patuhi rate limit / decision gate `INTEGRATION.md`.
5. **Hook** snapshot sinyal saat sinyal dibuat + order ditempatkan sesuai `signal_snapshot/signal_service_integration.md` + `INTEGRATION.md`.
6. **Deploy hanya** saat **tidak ada posisi terbuka** di Lighter (aturan aman di design doc).

## Di luar cakupan (isu terpisah / tier lanjut)

- Refresh penuh OHLCV / `market_metrics` + ingest **1m** (Tier 1)
- Retrain MLP / label baru (Tier 2)
- Exit asimetris / partial TP di produksi (Tier 3)
- Layer exhaustion mandiri (Tier 4)

## Kriteria penerimaan

- [ ] `trades_lighter` terisi / tetap sync; `stuck_open` bisa diselesaikan lewat sweep rekonsiliasi.
- [ ] `signal_snapshots` tertulis per sinyal baru; `candle_open_ts` dari **candle**, bukan `time.time()`.
- [ ] `analytics_trades` (atau ekuivalen) join dipakai untuk setidaknya beberapa trade nyata.
- [ ] `reconciliation_log` menunjukkan jalan periodik; metrik tercatat (lag, orphan rate).
- [ ] `PROCESS_DOCUMENTATION.md` / isu ini di-update dengan **nama branch** dan **tanggal deploy** saat selesai.

## Referensi

- `docs/research/rr_improvement_2026q2/PROCESS_DOCUMENTATION.md`
- `docs/research/rr_improvement_2026q2/DESIGN_DOC.md` §4.0
- `docs/research/rr_improvement_2026q2/proposed_code/INTEGRATION.md`
