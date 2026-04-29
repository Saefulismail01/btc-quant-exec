# Dokumentasi proses — R:R improvement & Tier 0 foundation (rr_improvement_2026q2)

**Versi:** 1.0  
**Tanggal arsip:** 2026-04-24  
**Tracking implementasi:** [GitHub Issue #1 — Tier 0 (bahasa Indonesia)](https://github.com/Saefulismail01/btc-quant-exec/issues/1)  
**Handoff agen baru:** [`NEXT_AGENT_BRIEF.md`](./NEXT_AGENT_BRIEF.md) — peran, status artefak, langkah A–D, larangan.  
**Cakupan:** Inisiatif penelitian dan desain sejak diskusi awal (performa live, R:R, layer exhaustion) hingga artefak proposal Tier 0b/0c dan langkah port ke produksi.  
**Bukan** transcript chat — ringkasan keputusan, artefak, dan state proses agar orang baru bisa melanjutkan tanpa konteks obrolan.

---

## 1. Tujuan inisiatif

| Tujuan | Keterangan |
|--------|------------|
| **Diagnosa** | Memahami mengapa win rate tinggi tapi EV tipis: R:R struktural, kemungkinan mismatch horizon MLP (4H) vs eksekusi scalping, dan narasi "buy di puncak". |
| **Data & ledger** | Mengatasi kebutuhan bukti empiris: telemetri L1–L4 per trade, MFE/MAE, join ke kondisi pasar; serta **ketidakreliabelan** DuckDB `live_trades` vs fakta Lighter (`stuck_open`). |
| **Fondasi** | Mendesain **Tier 0**: Lighter = source of truth trade; DuckDB = signal context + mirror + reconciliation. |
| **Jangka menengah** | Setelah fondasi: Tier 1 (refresh OHLCV/metrics, 1m), Tier 2 (refit/label MLP), Tier 3 (asymmetric exit), Tier 4 (exhaustion layer) — sesuai `DESIGN_DOC.md` v0.3. |

---

## 2. Kronologi singkat (fase)

1. **Diskusi + logbook** — Referensi performa: `docs/reports/live_trading/performance_logbook_mar_apr_2026.qmd` (WR, TP/SL, R:R, isu operasional).  
2. **Brief riset** — `README.md` (mission sub-agent, Area A–G).  
3. **Pengumpulan findings** — Sub-agent: `findings/A` … `findings/G`, `findings/SUMMARY.md` (arsitektur, data, skema trade, pola loss, kondisional, simulasi exit, MLP).  
4. **Recon Lighter** — `findings/H_lighter_sdk_capabilities.md` (endpoint, rate limit, mapping ke `trades_lighter`).  
5. **Desain beku** — `DESIGN_DOC.md` **v0.3 FROZEN** (SOT, reconciliation, `signal_snapshots`, view analitik; **skip** standalone live validation Tier0a; alasan: mainnet, posisi terbuka, tanpa read-only key).  
6. **Artefak kode proposal** — `proposed_code/` + `AGENT_BRIEF_TIER0BC.md` (satu SOT instruksi untuk sub-agent coding).  
7. **Implementasi proposal-grade** — Sub-agent: migrasi `001`–`005`, paket `reconciliation/` + `signal_snapshot/`, `INTEGRATION.md`, `requirements-dev.txt`, `pytest` (74 passed, Windows, tanpa `import lighter` di test).  
8. **Decision gate** — Dikunci di `proposed_code/INTEGRATION.md` (§7): MLP/strategi prob, threading `snapshot_id`, TTL, rate limit tier, kolom `analytics_trades`, multi-fill, `DB_PATH`.  
9. **Status saat arsip** — **Belum** di-port ke branch produksi; **next**: port `refactor/reconciliation-pipeline`, migrate DB (backup), deploy saat akun tanpa posisi terbuka.  
10. **Studi empirik jalur pendek (tanpa recon)** — `experiments/execution_aligned_label_study/run_study.py`: membandingkan label MLP 3-kelas (4H) vs label biner “TP sebelum SL” pada harga 1m Binance (fitur 8, micro=0). Mode `--synthetic` untuk CI; `--eval walkforward` = `TimeSeriesSplit`; unduh 1m paralel opsi `--fetch-workers>1` + `--fetch-chunk-days`.

---

## 3. Peran: lead vs sub-agent

| Peran | Tanggung jawab |
|--------|-----------------|
| **Lead analyst** | Sintesis, `DESIGN_DOC`, freeze v0.3, brief `AGENT_BRIEF_TIER0BC.md`, batasan (lead tidak ngoding file produksi; fokus desain/ekstraksi). |
| **Sub-agent riset** | Findings A–H, skrip bantu di `docs/.../scripts/`, analisis data (read-only kode produksi). |
| **Sub-agent coding** | Skeleton + SQL + test di `proposed_code/` saja, patuh brief; tidak sentuh DB produksi / tidak commit. |

---

## 4. Keputusan yang dibekukan (v0.3) — inti

Lihat tabel penuh di `DESIGN_DOC.md` header "Frozen decisions". Intinya:

- Host Lighter mengikuti gateway prod.  
- `trade_id` mirror = `order_id` (granularity per order, bukan per fill; revisit jika multi-fill > ambang).  
- Backfill: `OrderApi.export` + cursor inactive orders sesuai H.  
- `exit_type`: infer dari tipe order + toleransi harga vs `intended_sl/tp` di snapshot.  
- Validasi runtime standalone **ditiadakan**; validasi saat implementasi di branch, idealnya **tanpa posisi terbuka**.

---

## 5. Peta file (index)

| Jalan | Isi |
|--------|-----|
| `README.md` | Mission awal sub-agent, Area A–G, kendala. |
| `PROGRESS.md` | Log kronologis per sesi. |
| `DESIGN_DOC.md` | SOT desain: masalah, akar, roadmap Tier 0–4, skema, view `analytics_trades`. |
| `findings/` | Bukti & analisis per area. |
| `AGENT_BRIEF_TIER0A.md` | Recon Lighter (Tier 0a). |
| `AGENT_BRIEF_TIER0BC.md` | Instruksi lengkap Tier 0b+0c (mission, DoD, constraints). |
| `proposed_code/README.md` | Overview artefak kode proposal. |
| `proposed_code/INTEGRATION.md` | Urutan deploy, dependensi, **Decision gate** §7. |
| `proposed_code/migrations/` | `001`–`005` SQL (idempotent). |
| `proposed_code/reconciliation/` | Worker, repo, `exit_type_inference`, tests. |
| `proposed_code/signal_snapshot/` | Repo, model, `signal_service_integration.md`, tests. |
| `experiments/execution_aligned_label_study/` | Uji cek tabel MLP 4H vs simulasi TP/SL 1m (README + `run_study.py`). |

**Catatan:** `AGENT_BRIEF_TIER0A_VALIDATION.md` (validasi live terpisah) **dibatalkan** per v0.3 — tidak digunakan.

---

## 6. Verifikasi kualitas (artefak proposal)

- **Tes:** `pytest docs/research/rr_improvement_2026q2/proposed_code -q` → **74 passed** (in-memory DuckDB, mock gateway, bukan Lighter mainnet).  
- **Batasan disengaja:** tidak import SDK `lighter` di test suite Windows; kode produksi nanti memakai gateway sungguhan di environment yang didukung.

---

## 7. Apa yang *belum* selesai (jangan disalahartikan)

| Item | Status |
|------|--------|
| Port kode & migrasi ke `backend/` + branch `refactor/reconciliation-pipeline` | Belum |
| Worker reconciliation terpasang & jalan di proses app | Belum |
| Hook snapshot di `use_cases/signal_service.py` / `position_manager.py` (sesuai integration doc) | Belum |
| Backtest strategi baru dengan bar 1m + label eksekusi | **Belum** — butuh Tier 0 hidup + Tier 1 data |
| Bukti final "satu akar per trade" untuk setiap loss | **Belum** — butuh join snapshot + `trades_lighter` cukup lama |

---

## 8. Langkah paling andal setelah arsip (ringkas)

1. Review `proposed_code/INTEGRATION.md` §7 (decision gate).  
2. Port artefak → branch; backup DB; jalankan migrasi; wire worker + snapshot.  
3. Kumpulkan 1–2 minggu data nyata.  
4. Paralel: refresh OHLCV/metrics (+ 1m jika perlu backtest exit).  
5. Baru: eksperimen MLP / exit asimetris / exhaustion sesuai `DESIGN_DOC`.

---

## 9. Referensi performa (angka awal diskusi)

- TP/SL, R:R, WR, EV: `performance_logbook_mar_apr_2026.qmd` + `findings/SUMMARY.md`.  
- Angka dapat berubah; sumber periode Mar–Apr 2026.

---

*Dokumen ini disimpan sebagai arsip proses resmi folder `rr_improvement_2026q2/`. Perbarui `PROGRESS.md` ketika ada milestone baru.*
