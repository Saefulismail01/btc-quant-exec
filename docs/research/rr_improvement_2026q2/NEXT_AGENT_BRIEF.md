# Brief untuk agen berikutnya — BTC scalping R:R & fondasi data

**Tanggal:** 2026-04-24  
**Bahasa kerja:** Indonesia (utama) atau Inggris teknis bila perlu.  
**Repo:** `btc-scalping-execution_layer` (execution layer + riset di `docs/research/rr_improvement_2026q2/`).

---

## 1. Peran yang diharapkan

Kamu adalah **agen implementasi / riset lanjutan** yang:

- Membaca konteks yang sudah dibekukan di `DESIGN_DOC.md` v0.3 dan ringkasan proses di `PROCESS_DOCUMENTATION.md`.
- Menjalankan **prioritas** yang user pilih (lihat §4); tidak mengubah scope besar tanpa konfirmasi.
- Menghormati **akun live Lighter (mainnet)**: jangan probe API riskan saat posisi terbuka; backup DB sebelum migrasi; ikuti `proposed_code/INTEGRATION.md`.

---

## 2. Konteks bisnis (ringkas)

- Bot scalping BTC: **WR tinggi (~75%)**, tapi **R:R struktural ~0,53** (TP 0,71% / SL 1,333%) → EV tipis.
- Hipotesis utama desain: **mismatch horizon** (MLP dilatih target mirip *forward return 4H*, eksekusi jauh lebih pendek) + **telemetri minim** + **ledger lokal DuckDB** kadang tidak selaras Lighter (`stuck_open`).
- User pernah menolak menunggu proyek **reconciliasi penuh** lama; jalur pendek **tanpa recon** tetap valid: studi label + data Binance + CSV Lighter.

---

## 3. Status artefak (apa yang sudah ada)

| Area | Lokasi | Status |
|------|--------|--------|
| Desain beku Tier 0 | `DESIGN_DOC.md` | v0.3 — Lighter SOT, `trades_lighter`, `signal_snapshots`, worker, view analitik |
| Proposed code (belum merge prod) | `proposed_code/` | SQL 001–005, repo + worker + tes, `INTEGRATION.md` §7 decision gate; **74 pytest** lulus (mock) |
| Isu tracking | `GITHUB_ISSUE_tier0_foundation.md` + [GitHub #1](https://github.com/Saefulismail01/btc-quant-exec/issues/1) | Isi bahasa Indonesia |
| Studi empirik “label eksekusi” | `experiments/execution_aligned_label_study/run_study.py` | 1m Binance fapi, resample 4H, bandingkan label MLP 3-kelas vs TP-sebelum-SL; `--synthetic`, `--eval walkforward`, unduh paralel (`--fetch-workers`) — **baca** `README.md` di folder itu |
| Findings A–H | `findings/` | Referensi; OHLCV lokal sempat stale (cek ulang) |

**Belum (umum):** port Tier 0 ke `backend/`, branch `refactor/reconciliation-pipeline`, migrasi ke DuckDB produksi, hook snapshot di `use_cases/`.

---

## 4. Langkah ke depan (pilih prioritas; urut jika all-in)

### A. Implementasi Tier 0 (fondasi ledger + telemetri)

1. Baca `proposed_code/INTEGRATION.md` §7 (decision gate).  
2. Buat branch; pindahkan/modularisasikan kode proposal ke `backend/` (sesuai tim).  
3. Backup DB; jalankan migrasi 001–005; wire gateway + worker; hook snapshot.  
4. **Deploy hanya** saat **tidak ada posisi** di Lighter.  
5. **Verifikasi:** `reconciliation_log`, `analytics_trades` berisi data nyata, orphan rate wajar.

### B. Studi R:R / MLP (bisa paralel / tanpa A)

1. Di mesin dengan jaringan stabil: `run_study.py` dengan data Binance (`--days 90+`), `--cache-dir`, coba `--eval walkforward`.  
2. (Opsional) join fitur CVD/funding/OI jika tersedia pipeline ingest.  
3. Dokumentasikan: apakah **label “TP sebelum SL”** cukup diprediksi vs label 3-kelas 4H — dasar keputusan **retrain** atau **bukan** (selaras `DESIGN_DOC` §Tier 2).

### C. Tier 1 data

- Refresh `btc_ohlcv_*` + `market_metrics` sampai mutakhir; rencanakan 1m jika mau simulasi exit/ path halus (lihat findings E/F).

### D. Setelah A+B cukup matang

- Asymmetric exit / retrain MLP dengan label *execution-aligned* — **hanya** setelah bukti data; ikuti guardrail di `DESIGN_DOC`.

---

## 5. Larangan & peringatan

- Jangan asumsi **testnet** = prod; gateway prod = sumber arsitektur.  
- Skrip `run_study.py` memakai `verify=False` pada request Binance (selaras backfill) — pahami risiko MITM; di CI gunakan `--synthetic`.  
- Jangan hapus / overwrite DuckDB produksi tanpa backup.  
- Jangan melebihi rate limit Lighter (lihat `findings/H`).

---

## 6. File wajib dibaca dulu (urutan)

1. `DESIGN_DOC.md` — §3 root cause, §4 road map, frozen decisions.  
2. `PROCESS_DOCUMENTATION.md`  
3. `proposed_code/INTEGRATION.md` (jika kerjaan = Tier 0)  
4. `experiments/execution_aligned_label_study/README.md` (jika kerjaan = studi label)  
5. `findings/SUMMARY.md` untuk arsip cepat

---

## 7. Definisi “selesai” per paket

| Paket | Selesai bila |
|--------|----------------|
| Tier 0 port | Tabel + worker + hook jalan; issue #1 / checklist dicontek | 
| Studi `run_study` | Setidaknya satu run **Binance nyata** tersimpan (output/log) + 1 paragraf simpulan | 
| Tier 1 | `max(timestamp)` OHLCV ≥ hari hari terakhir trade / analisis |

---

**Pesan untuk user:** serahkan file ini + branch/issue ke agen baru; batasi satu prioritas (A **atau** B) bila waktu sempit.
