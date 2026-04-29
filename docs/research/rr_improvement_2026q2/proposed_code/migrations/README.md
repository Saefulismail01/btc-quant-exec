# Schema Migrations

**Target DB:** DuckDB (`btc-quant.db` atau path dari env `DB_PATH`)
**Reference:** `../../DESIGN_DOC.md` v0.3 §4.0.B & §4.0.C
**Engine compatibility:** DuckDB ≥ 0.9 (uses standard SQL DDL)

---

## Files & order

Run in numeric order. Each migration is **idempotent** (uses `IF NOT EXISTS`).

| # | File | Purpose | Reversible |
|---|------|---------|------------|
| 001 | `001_create_trades_lighter.sql` | Mirror dari Lighter — fakta trade (SOT) | Drop table |
| 002 | `002_create_signal_snapshots.sql` | Signal context per entry (write-once) | Drop table |
| 003 | `003_create_trade_snapshots.sql` | Polling MFE/MAE per trade | Drop table |
| 004 | `004_create_reconciliation_log.sql` | Audit log reconciliation worker | Drop table |
| 005 | `005_create_analytics_view.sql` | View join untuk analisis kondisional | Drop view |

---

## How to run (manual review first!)

**WAJIB:** review setiap file SQL sebelum eksekusi. Tidak ada framework migration yang otomatis di project ini saat ini.

```bash
# Backup DB dulu
cp backend/app/infrastructure/database/btc-quant.db btc-quant.db.bak.$(date +%Y%m%d-%H%M%S)

# Eksekusi (idealnya saat tidak ada bot live yang nulis)
duckdb backend/app/infrastructure/database/btc-quant.db < proposed_code/migrations/001_create_trades_lighter.sql
duckdb backend/app/infrastructure/database/btc-quant.db < proposed_code/migrations/002_create_signal_snapshots.sql
duckdb backend/app/infrastructure/database/btc-quant.db < proposed_code/migrations/003_create_trade_snapshots.sql
duckdb backend/app/infrastructure/database/btc-quant.db < proposed_code/migrations/004_create_reconciliation_log.sql
duckdb backend/app/infrastructure/database/btc-quant.db < proposed_code/migrations/005_create_analytics_view.sql

# Verify
duckdb backend/app/infrastructure/database/btc-quant.db -c "SHOW TABLES;"
```

---

## Rollback

```sql
DROP VIEW IF EXISTS analytics_trades;
DROP TABLE IF EXISTS reconciliation_log;
DROP TABLE IF EXISTS trade_snapshots;
DROP TABLE IF EXISTS signal_snapshots;
DROP TABLE IF EXISTS trades_lighter;
```

(Tidak menyentuh `live_trades` lama — tetap utuh.)

---

## Notes

- **`live_trades` lama tidak diubah** di migration ini. Akan jadi tabel "legacy" yang co-exist sementara, dipertahankan untuk historical reference.
- Setelah Tier 0b stabil + cukup data di `trades_lighter`, baru ada migration tambahan untuk deprecate `live_trades` dan rewrite konsumen.
- Semua tabel pakai `BIGINT` untuk timestamp (Unix milliseconds UTC) — konsisten dengan `live_trades` existing.
