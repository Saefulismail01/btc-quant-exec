# Integration Guide — Tier 0b + Tier 0c

**Version:** 0.1 (Proposal — not yet applied to production)  
**Reference:** `../DESIGN_DOC.md` v0.3 §4.0.B, §4.0.C  
**Detail:** See `signal_snapshot/signal_service_integration.md` for hook-level diff

---

## 1. Deploy sequence

**CRITICAL:** All steps below must execute when **no positions are open in Lighter**.

```
Step 1: Backup DB
  cp backend/app/infrastructure/database/btc-quant.db btc-quant.db.bak.$(date +%Y%m%d)

Step 2: Run SQL migrations (numeric order, idempotent)
  duckdb <db_path> < proposed_code/migrations/001_create_trades_lighter.sql
  duckdb <db_path> < proposed_code/migrations/002_create_signal_snapshots.sql
  duckdb <db_path> < proposed_code/migrations/003_create_trade_snapshots.sql
  duckdb <db_path> < proposed_code/migrations/004_create_reconciliation_log.sql
  duckdb <db_path> < proposed_code/migrations/005_create_analytics_view.sql

Step 3: Verify tables created
  duckdb <db_path> -c "SHOW TABLES;"
  duckdb <db_path> -c "DESCRIBE trades_lighter;"
  duckdb <db_path> -c "DESCRIBE signal_snapshots;"
  duckdb <db_path> -c "SELECT * FROM analytics_trades LIMIT 0;"

Step 4: One-time history backfill (Tier 0b)
  - Use LighterReconciliationWorker.reconcile_history() with RECONCILIATION_ENABLED=false (dry-run)
  - Review reconciliation_log for parse errors
  - Toggle RECONCILIATION_ENABLED=true after confirming dry-run clean

Step 5: Deploy reconciliation worker (Tier 0b)
  - Feature flag: RECONCILIATION_ENABLED=false initially
  - Monitor reconciliation_log.stuck_resolved metric
  - Watch for reconciliation_lag_ms p95 < 300s

Step 6: Integrate signal snapshot hook (Tier 0c)
  - Apply changes per signal_snapshot/signal_service_integration.md
  - Deploy to staging (paper mode) first
  - Verify signal_snapshots.link_status transitions PENDING → ORDER_PLACED → ORDER_FILLED
  - Verify candle_open_ts matches expected 4H candle boundary (not time.time())

Step 7: Monitor 1 week
  - Orphan rate < 5% (signal placed, order never filled)
  - reconciliation_lag_ms p95 < 300s
  - analytics_trades view has linked rows
```

---

## 2. Dependencies

| Component | Depends on | Notes |
|-----------|-----------|-------|
| `trades_lighter` table | migration 001 | Must exist before worker starts |
| `signal_snapshots` table | migration 002 | Must exist before signal_service hooks |
| `trade_snapshots` table | migration 003 | Tier 0d (MFE/MAE polling, separate sprint) |
| `reconciliation_log` table | migration 004 | Must exist before worker starts |
| `analytics_trades` view | migrations 001+002+003 | All three tables must exist |
| `LighterReconciliationWorker` | `TradesLighterRepository` | Inject same DuckDB conn |
| `SignalSnapshotRepository` | `signal_snapshots` table | Inject into signal_service |
| Tier 1 (OHLCV refresh) | Independent | Can run in parallel with Tier 0b/0c |
| Tier 2 (MLP refactor) | `analytics_trades` view | Needs ≥2 weeks of snapshot data |

---

## 3. Rollback procedure

```sql
-- Emergency rollback (tables only, NOT touching live_trades):
DROP VIEW IF EXISTS analytics_trades;
DROP TABLE IF EXISTS reconciliation_log;
DROP TABLE IF EXISTS trade_snapshots;
DROP TABLE IF EXISTS signal_snapshots;
DROP TABLE IF EXISTS trades_lighter;
```

`live_trades` is **not touched** by any of these migrations.
The old system remains fully functional after rollback.

---

## 4. Production code changes (Tier 0c)

Detailed diff instructions: [`signal_snapshot/signal_service_integration.md`](signal_snapshot/signal_service_integration.md)

Summary:
- `backend/app/schemas/signal.py` — add `snapshot_id: Optional[str]`
- `backend/app/use_cases/signal_service.py` — insert snapshot, expose MLP class probs
- `backend/app/use_cases/position_manager.py` — update linkage, remove `time.time()` bug
- `backend/app/use_cases/ai_service.py` — expose per-class MLP probabilities

**None of these changes are applied in this proposal.** This `proposed_code/` folder
is for review only. Apply changes in git branch `refactor/reconciliation-pipeline`.

---

## 5. Link to Tier 1+

Once `analytics_trades` view contains ≥ 2 weeks of data with full signal snapshots:

- **Tier 2 (MLP refactor):** Use `analytics_trades` to label `TP_hit_before_SL`
  as alternative training target. Query: `WHERE l3_class='BULL' AND exit_type IN ('TP', 'SL')`.
- **Tier 3 (Asymmetric exit):** Use `mfe_pct` and `mae_pct` from `analytics_trades`
  to calibrate TP1/TP2 levels. Query: `SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY mfe_pct)`.
- **Tier 4 (Exhaustion layer):** Use `htf_zscore_at_signal`, `funding_at_signal`,
  `cvd_at_signal` for exhaustion score calibration.

---

## 6. Open questions (for lead analyst before branch deploy)

1. **Auth token refresh TTL** — `create_auth_token_with_expiry` TTL unknown; worker
   assumes 5-min TTL with 4-min refresh. Validate on first real call.
2. **Rate limit tier** — Worker assumes premium (24k weighted/min). If account is
   standard (60/min), `accountInactiveOrders` sweep frequency must drop to < 0.6/min.
3. **Multi-fill handling** — DESIGN_DOC default: per-order granularity (single fill
   assumption). If >30% of trades have multiple fills, re-evaluate to per-fill
   in `trades_lighter`.
4. **DB_PATH env** — Confirm which `DB_PATH` value the production bot reads at runtime.
   Worker and bot must write to the same DuckDB file.
5. **`snapshot_id` in `SignalResponse`** — Chosen threading mechanism. Alternative:
   short-lived in-memory dict keyed by signal hash if schema change is blocked.

---

## 7. Decision gate (parent synthesis, 2026-04-24)

Status: **APPROVED FOR PORT TO `refactor/reconciliation-pipeline`** with the following decisions.

1. **MLP probabilities (Tier 0c hook)**
   - Decision: add explicit API in `ai_service` to return per-class probabilities
     (`bull`, `bear`, `neutral`) and stop overloading `get_confidence()`.
   - Reason: keeps signal snapshot write deterministic and avoids ambiguous tuple unpacking.

2. **`snapshot_id` threading**
   - Decision: keep `snapshot_id: Optional[str]` in `SignalResponse` as canonical path.
   - Fallback (only if schema blocker): temporary in-memory map keyed by signal hash, TTL <= 10 minutes.

3. **Auth token TTL strategy**
   - Decision: keep current conservative defaults (assume 5 min TTL, refresh at 4 min)
     but make both values configurable via env when porting to branch.
   - Required check on first live call: log observed expiry and adjust config (not code logic).

4. **Rate-limit tier**
   - Decision: default to safe cadence until tier is confirmed; do not assume premium at startup.
   - Operational rule: if account is standard tier, keep `accountInactiveOrders` polling below
     0.6 calls/min as documented.

5. **`analytics_trades` extra columns in migration 005**
   - Decision: keep extra columns (`reconciliation_lag_ms`, `intended_sl_price`,
     `intended_tp_price`, `l3_prob_neutral`) because all are already present in base tables.
   - Reason: improves Tier 2/3 analysis without changing source-of-truth semantics.

6. **Multi-fill trade granularity**
   - Decision: keep per-order granularity for Tier 0b as frozen in DESIGN_DOC v0.3.
   - Trigger to revisit: if observed multi-fill ratio > 30% in reconciliation logs.

7. **DB path alignment**
   - Decision: worker and bot must read the exact same `DB_PATH`; add startup assert during
     branch integration (out of scope for `proposed_code/`).
