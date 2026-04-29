# Proposed Code — Tier 0b/0c Implementation

**Status:** PROPOSAL — implementasi selesai (Tier 0b + 0c skeleton + tests). Belum dijadwalkan deploy. Review oleh user dulu.
**Reference:** `../DESIGN_DOC.md` v0.3
**Updated:** 2026-04-24 (Tier 0b/0c implementation — coding-specialist subagent)

---

## Overview

Folder ini berisi **rancangan kode dan schema** untuk:

- **Tier 0b** — Reconciliation pipeline (Lighter API → DuckDB mirror)
- **Tier 0c** — Signal snapshot store + integration ke `signal_service`

Code di sini bersifat **proposal-grade**:
- Belum di-merge ke main branch
- Schema SQL belum di-execute terhadap DB produksi
- Reconciliation worker belum di-deploy
- Tujuan: dapat di-review oleh user/maintainer sebelum jadi production change

---

## Struktur folder

```
proposed_code/
├── README.md                              ← file ini
├── INTEGRATION.md                         ← deploy sequence + Tier 1+ dependencies
├── conftest.py                            ← pytest sys.path setup
├── pytest.ini                             ← asyncio_mode=auto
├── requirements-dev.txt                   ← duckdb, pytest, pytest-asyncio
├── migrations/
│   ├── README.md                          ← migration ordering & rollback
│   ├── 001_create_trades_lighter.sql
│   ├── 002_create_signal_snapshots.sql
│   ├── 003_create_trade_snapshots.sql
│   ├── 004_create_reconciliation_log.sql
│   └── 005_create_analytics_view.sql      ← analytics_trades view (NEW)
├── reconciliation/                        ← Tier 0b
│   ├── __init__.py
│   ├── models.py                          ← dataclasses: LighterTradeMirror, ReconciliationResult, enums
│   ├── trades_lighter_repository.py       ← DuckDB: upsert_trade, get_open_trade_ids, mark_closed
│   ├── exit_type_inference.py             ← pure function: infer TP/SL/MANUAL/UNKNOWN
│   ├── lighter_reconciliation_worker.py   ← async worker (sweep + history); Protocol gateway
│   └── tests/
│       ├── __init__.py
│       ├── test_exit_type_inference.py    ← pure unit tests (no DB)
│       ├── test_repository.py             ← in-memory DuckDB tests
│       └── test_reconciliation_worker.py  ← AsyncMock gateway tests
└── signal_snapshot/                       ← Tier 0c
    ├── __init__.py
    ├── models.py                          ← SignalSnapshot dataclass, LinkStatus enum
    ├── signal_snapshot_repository.py      ← insert, update_linkage, mark_orphaned, get_by_order_id
    ├── signal_service_integration.md      ← detailed diff / hook instructions
    └── tests/
        ├── __init__.py
        └── test_signal_snapshot_repository.py
```

---

## Cara review (urutan disarankan)

1. **Schema dulu** — baca `migrations/*.sql`. Pastikan tipe data + nullable + indeks sesuai ekspektasi.
2. **Trades repository** — `reconciliation/trades_lighter_repository.py` (upsert idempotent)
3. **Signal snapshot repository** — `signal_snapshot/signal_snapshot_repository.py` (write-once)
4. **Reconciliation worker** — `reconciliation/lighter_reconciliation_worker.py` (orchestration)
5. **Integration patch** — `signal_snapshot/signal_service_integration.md` (where to hook)

---

## Cara test (offline, tanpa Lighter)

Semua test pakai **mocked Lighter response** — tidak ada call API real.  
Semua DB pakai **`:memory:` DuckDB** — tidak menyentuh `btc-quant.db` produksi.  
Windows compatible (tidak ada libc / C import dari lighter SDK).

### Install dev deps

```bash
pip install -r docs/research/rr_improvement_2026q2/proposed_code/requirements-dev.txt
```

### Run dari repo root (cara yang disarankan)

```bash
pytest docs/research/rr_improvement_2026q2/proposed_code -q
```

### Run per modul (verbose)

```bash
pytest docs/research/rr_improvement_2026q2/proposed_code/reconciliation/tests/ -v
pytest docs/research/rr_improvement_2026q2/proposed_code/signal_snapshot/tests/ -v
```

### Expected output

```
... passed in X.XXs
```

Total test cases: ~45+ (exit_type: 16, repository: 13, worker: 12, snapshot: 16+)

---

## Deployment plan (saat siap)

**WAJIB DILAKUKAN SAAT TIDAK ADA POSISI TERBUKA DI LIGHTER.**

1. Backup `btc-quant.db` (full snapshot)
2. Run migrations 001 → 005 di order
3. Verify tabel ter-create dengan `DESCRIBE` queries
4. Deploy reconciliation worker dengan feature flag `RECONCILIATION_ENABLED=false` (dry-run mode logging only)
5. Monitor 24 jam — verify response Lighter parse sukses
6. Toggle `RECONCILIATION_ENABLED=true` untuk write mode
7. Monitor `reconciliation_log` table untuk `stuck_resolved` count
8. Setelah stable: integrate signal snapshot ke `signal_service` (Tier 0c)

---

## Open items / TODOs di proposal

- Lokasi DB target — perlu konfirmasi `DB_PATH` env aktif (lihat DESIGN_DOC §8 resolved)
- Auth token refresh strategy — assume 5 menit TTL, refresh setiap 4 menit (validate saat first call)
- Rate limit handler — backoff exponential dengan jitter, perlu tune saat tahu tier akun
- Feature flag mekanisme — pakai env var atau tabel config? Default: env var
