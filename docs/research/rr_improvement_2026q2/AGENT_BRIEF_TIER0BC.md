# Agent Brief — Tier 0b + Tier 0c (single source of instruction)

**Single source of truth:** Sub-agent **hanya** mengikuti dokumen ini + artefak yang dirujuk di §2. Jangan menggabungkan instruksi dari chat parent kecuali untuk eskalasi yang ditulis di `PROGRESS.md`.

**Created / updated:** 2026-04-24  
**Owner (lead analyst):** User ↔ Claude (parent)  
**Audience:** Sub-agent (**coding-specialist**)  
**Status:** Ready to dispatch  
**Estimated effort:** 1–2 sesi panjang (skeleton + tests + docs; **bukan** deploy)

---

## 1. Mission (Tier 0b + 0c, lengkap)

Implement **proposal-grade** artefak untuk:

| Tier | Isi | Deliverable utama |
|------|-----|---------------------|
| **0b** | Reconciliation pipeline (Lighter → DuckDB mirror) | SQL `trades_lighter` + `reconciliation_log` + **worker skeleton** (mock gateway) + **tests** + catatan observabilitas |
| **0c** | Signal snapshot store + perbaikan semantik `candle_open_ts` | SQL `signal_snapshots` + **repository skeleton** + **tests** + **integration doc** (diff terhadap kode produksi — **tanpa** mengedit produksi) |

Semua path output: **`docs/research/rr_improvement_2026q2/proposed_code/**` saja.

---

## 2. Required reading (urut, wajib)

1. **`DESIGN_DOC.md` v0.3** — §3.6, **§4.0.B** (reconciliation), **§4.0.C** (snapshots), **§4.0.D** (`trade_snapshots`), **§4.0** analytics view, **§8** (asumsi terbuka).
2. **`findings/H_lighter_sdk_capabilities.md`** — kontrak gateway abstrak, field order/posisi, rate limit (untuk komentar di worker, bukan import SDK).
3. **`findings/C_trade_log_schema.md`** — `live_trades` legacy (konteks `stuck_open`).
4. **`proposed_code/README.md`** — struktur proposal.
5. **`proposed_code/migrations/README.md`** — urutan migration & rollback.
6. **Starter SQL (keep as starter, review & lanjutkan):**  
   `proposed_code/migrations/001_create_trades_lighter.sql` … `004_create_reconciliation_log.sql`  
   - Boleh **edit** jika drift vs DESIGN_DOC; setiap ubahan wajib komentar `-- Changed by sub-agent (Tier0bc): <reason>`.
7. **Referensi baca saja (jangan ubah file ini):**  
   - `backend/app/adapters/gateways/lighter_execution_gateway.py`  
   - `backend/app/use_cases/signal_service.py`  
   - `backend/app/use_cases/position_manager.py`  

---

## 3. Starter context (`keep_as_starter`)

File **001–004** sudah ada sebagai draf lead analyst. Tugas sub-agent:

- **Review** konsistensi dengan DDL / pseudocode di `DESIGN_DOC` v0.3.
- **Lanjutkan** dengan **`005_create_analytics_view.sql`** (belum ada) — isi persis pola `CREATE VIEW analytics_trades` di DESIGN_DOC §4.0 (nama view / kolom harus match keputusan freeze).
- Update **`migrations/README.md`** jika urutan atau rollback berubah.

---

## 4. Deliverables (checklist)

### 4.1 SQL — `proposed_code/migrations/`

- [ ] Verify / fix `001` … `004` (dengan komentar jika diubah).
- [ ] **Create** `005_create_analytics_view.sql` (view `analytics_trades` + `WHERE t.status = 'CLOSED'` sesuai doc).

### 4.2 Reconciliation — `proposed_code/reconciliation/`

- [ ] `__init__.py`
- [ ] `models.py` — dataclasses (`LighterTradeMirror`, `ReconciliationResult`, enum mode sweep/history, dll.)
- [ ] `trades_lighter_repository.py` — DuckDB: `upsert_trade`, `get_open_trade_ids`, `get_trade`, `mark_closed`, idempotent writes.
- [ ] `lighter_reconciliation_worker.py` — `async` worker; **dependency injection** `Protocol` untuk “gateway” ( **`get_open_position_ids()`**, **`fetch_inactive_orders_page(...)`**, dll.) — **tanpa** `import lighter`.
- [ ] `exit_type_inference.py` — pure function sesuai frozen decision DESIGN_DOC (match `order.type` + toleransi harga vs `intended_sl` / `intended_tp` dari snapshot bila tersedia).
- [ ] `tests/` — `test_repository.py`, `test_reconciliation_worker.py` (AsyncMock), `test_exit_type_inference.py`; DB **`:memory:`** DuckDB.
- [ ] Opsional: `README.md` di folder ini — cara jalankan test.

### 4.3 Signal snapshot — `proposed_code/signal_snapshot/`

- [ ] `__init__.py`, `models.py` (`SignalSnapshot` align kolom §4.0.C.1).
- [ ] `signal_snapshot_repository.py` — `insert`, `update_linkage`, `mark_orphaned`, `get_by_order_id`.
- [ ] `tests/test_signal_snapshot_repository.py`.
- [ ] **`signal_service_integration.md`** — diff / urutan hook ke `signal_service` + `position_manager` (termasuk bug `candle_open_ts` ~922 → ganti sumber ke snapshot), diagram alur teks atau mermaid ringkas.

### 4.4 Integration doc agregat (wajib)

- [ ] **`proposed_code/INTEGRATION.md`** — satu halaman: urutan deploy (migration → worker → snapshot), dependensi ke Tier 1, link ke `signal_service_integration.md`, **tidak** menyentuh produksi sampai branch terpisah.

### 4.5 Dev deps & top-level README

- [ ] **`proposed_code/requirements-dev.txt`** — `duckdb`, `pytest`, `pytest-asyncio` (+ opsional minimal).
- [ ] Update **`proposed_code/README.md`** — status implementasi, perintah pytest dari **repo root**.

---

## 5. Constraints (keras)

| # | Aturan |
|---|--------|
| C1 | **Jangan** mengubah file di luar `docs/research/rr_improvement_2026q2/proposed_code/**` (termasuk `backend/`, `src/`, migration ke DB produksi). |
| C2 | **Jangan** `import lighter` atau memanggil API Lighter nyata — **mock / Protocol** saja (alasan: Windows + kebijakan v0.3: validasi runtime dialihkan ke impl di branch idle). |
| C3 | **Jangan** `git commit` / merge / push — hanya tulis file; user yang stage. |
| C4 | Tests harus **lolos di Windows** (tanpa libc signer Lighter). |
| C5 | **Jangan** mengeksekusi SQL ke file `btc-quant.db` produksi — hanya `:memory:` di pytest. |
| C6 | Tiap path write: **idempotent** + log konteks pada error (tanpa secrets). |

---

## 6. Definition of done

Sub-agent selesai bila:

1. Semua file di §4 ada dan isinya mengisi kontrak (bukan file kosong).  
2. Dari **root repo**:  
   `pytest docs/research/rr_improvement_2026q2/proposed_code -q`  
   (atau path setara yang didaftarkan di `proposed_code/README.md`) → **semua hijau**.  
3. Return message ke parent mengikuti **§7** persis.

---

## 7. Output format (return message ke parent)

Gunakan Markdown berikut:

```markdown
## Files created
- …

## Files modified (existing under proposed_code/)
- …: reason

## SQL changes (vs starter 001–004)
- …

## Tests
- Command: …
- Result: … (e.g. 12 passed)

## Open questions for lead analyst
1. …

## Estimated remaining effort to production
- …
```

---

## 8. Out of scope (eksplisit)

- Deploy / menjalankan migration ke DuckDB produksi.  
- Panggilan Lighter live / WebSocket produksi.  
- Mengedit `signal_service.py` / `position_manager.py` / gateway **di repo utama** (hanya dokumentasi di `*.md` under `proposed_code/`).  
- Tier **1** (OHLCV refresh), **2** (MLP label), **3** (asymmetric exit), **4** (exhaustion).  
- `live_trades_compat` VIEW kecuali diminta tambahan di iterasi berikutnya.  
- Commit git.

---

## 9. Eskalasi

Jika konflik DESIGN_DOC vs starter SQL: **DESIGN_DOC v0.3 menang**, catat di “Open questions” jika ambigu fatal.

---

## 10. Dispatch

Parent akan memanggil sub-agent **coding-specialist** dengan prompt satu baris pertama:

> Baca dan patuhi sepenuhnya `docs/research/rr_improvement_2026q2/AGENT_BRIEF_TIER0BC.md` sebagai single source of instruction. Kerjakan hingga Definition of done §6; kembalikan output format §7.

**End of brief.**
