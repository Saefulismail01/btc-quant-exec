# Executive summary — R:R improvement discovery (2026 Q2)

**Updated:** 2026-04-24  
**Audience:** Lead analyst  
**Maks:** ~2 halaman

## 0. Konteks laporan live & intervensi manusia

**Dibaca:** `docs/reports/live_trading/performance_logbook_mar_apr_2026.qmd` (dan ringkasannya di `docs/reports/LOGBOOK_PERFORMANCE_MAR_APR_2026.md`). Di sana **intervensi manual** didefinisikan sebagai menggeser SL/TP atau menutup posisi lewat dashboard, mengesampingkan otomasi — dengan dampak terdokumentasi (mis. **3, 4, 7, 10 Apr** interupsi signal delay; **12 Apr** penyesuaian SL manual + isu **sizing** ~\$150 vs target \$500; opportunity cost tersirat ~\$15 vs jalur TP penuh).

**Catatan operasional (bukan dari file logbook):** per operator, **tanpa intervensi manual = 20–24 April 2026** (inklusif). Periode sebelum **20 Apr** pada export yang sama masih bisa tercampur perilaku / catatan intervensi di logbook (mis. 3, 4, 7, 10, 12 Apr).

**Implikasi analisis:** filter **ketat** (episode lengkap sepenuhnya di jendela UTC): **`--episode-window-utc 2026-04-20 2026-04-24`** pada `aggregate_lighter_roundtrips.py` → **n=5** episode, WR **60%**, total PnL **-\$2.21** pada export CSV saat ini (`findings/D_loss_pattern_analysis.md`, subset). **n sangat kecil**; tanggal **20 Apr** tidak memiliki episode close dalam file ini.

## 1. Hipotesis vs bukti saat ini

**Hipotesis (README):** layer trailing (L1/L2/L3) membuat sistem buta exhaustion → banyak win kecil lalu loss besar di reversal.

**Bukti numerik saat ini:** **Tidak cukup** untuk mengonfirmasi atau menyangkal. Proxy dari **27** episode round-trip (agregasi FIFO fill Lighter Apr 2026) menunjukkan WR **~74%** dan total PnL **+$6.23**, dengan **7** loss dan variasi “wins sebelum loss” (0–7). **n kecil** dan **bukan** log bot `live_trades` + `exit_type` → hanya indikasi awal, bukti lemah untuk klaim struktural.

**Data DuckDB `live_trades` lokal:** hanya **2** baris CLOSED — tidak memadai untuk regresi streak/conditional WR.

## 2. Top 3 actionable insight (denga angka)

1. **Gap telemetri:** `live_trades` menyimpan `signal_verdict` / `signal_conviction` saja; **tidak** ada snapshot L1/L2/L4, MLP prob, atau MFE/MAE — analisis kondisional historis membutuhkan **instrumentasi** atau **replay** (`findings/C_trade_log_schema.md`).

2. **Desinkronisasi data:** `btc_ohlcv_4h.max(timestamp)` = **2026-03-18** pada DB yang diprobe, sedangkan export Lighter **April 2026** — join proxy (funding/stretch/vol) ke April **tidak valid** (`findings/B_data_inventory.md`, `findings/E_conditional_performance.md`).

3. **Asymmetric exit:** Gateway saat ini = **full** close market + SL/TP reduce-only; **partial TP / trailing native** tidak ada di `lighter_execution_gateway.py` — butuh emulasi klien atau perluasan SDK (`findings/F_asymmetric_exit_simulation.md`).

## 3. Top 3 gap data / tooling

1. **`live_trades` dump produksi** (54+ trade seperti logbook) atau backup DB identik dengan produksi.  
2. **OHLCV & metrics** yang mencakup **seluruh** rentang live + resolusi **≤1m** untuk sim exit.  
3. **Artefak + log training MLP** (atau pipeline evaluasi OOS) — `mlp_*.joblib` tidak ada di workspace; kalibrasi tidak terukur.

## 4. Rekomendasi prioritas (untuk lead analyst)

1. **Tutup gap data dulu** (refresh DuckDB / pipeline ingestion sampai ≥ akhir periode trading + dump `live_trades`). Tanpa itu, **E.2 / F.2 / kalibrasi** tidak layak dipakai untuk keputusan.  
2. **Paralel rendah risiko:** desain **instrumentasi** minimal pada `insert_trade` (regime label, funding snapshot, ATR) — hanya setelah persetujuan arsitek (di luar brief sub-agent “no prod code change” yang sudah diikuti).  
3. **Urutan solusi:** setelah data siap, ulangi **D.1 + E.1/E.2/E.5**; baru bandingkan ROI investigasi **exhaustion layer** vs **asymmetric exit** (yang juga butuh intraday untuk simulasi).

## Referensi cepat

| File | Isi |
|------|-----|
| `findings/A_architecture_inventory.md` | Alur L1–L5 + path kode |
| `findings/B_data_inventory.md` | Sumber DuckDB + limit OHLCV |
| `findings/C_trade_log_schema.md` | Schema + CSV Lighter |
| `findings/D_loss_pattern_analysis.md` | Pola loss proxy episode |
| `findings/E_conditional_performance.md` | Funding / HTF / streak |
| `findings/F_asymmetric_exit_simulation.md` | Kapabilitas + F.2 blocked |
| `findings/G_mlp_deep_dive.md` | Label, fitur, gap artefak |
| `findings/H_lighter_sdk_capabilities.md` | Tier 0a — SDK + REST + WS + reconciliation pattern |
| `scripts/aggregate_lighter_roundtrips.py` | FIFO episode dari CSV |
| `data/episodes_lighter_2026-04-24.csv` | Output episode |
