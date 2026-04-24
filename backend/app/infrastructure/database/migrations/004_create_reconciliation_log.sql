-- Migration 004 — reconciliation_log
-- Audit log untuk reconciliation worker (observability)
-- Reference: DESIGN_DOC v0.3 §4.0.B.4

CREATE TABLE IF NOT EXISTS reconciliation_log (
    log_id              VARCHAR PRIMARY KEY,                   -- UUID
    ts_ms               BIGINT NOT NULL,                       -- Unix ms saat run dimulai
    mode                VARCHAR NOT NULL,                      -- 'sweep' | 'history' | 'snapshot_polling'

    -- Counts
    stuck_resolved      INTEGER NOT NULL DEFAULT 0,            -- # trades yang di-resolve dari OPEN → CLOSED
    missing_resolved    INTEGER NOT NULL DEFAULT 0,            -- # trades yang ditemukan di Lighter tapi belum di DuckDB
    upserted            INTEGER NOT NULL DEFAULT 0,            -- # trades upserted (insert + update)
    snapshots_inserted  INTEGER NOT NULL DEFAULT 0,            -- # rows inserted ke trade_snapshots

    -- Timing
    duration_ms         INTEGER NOT NULL,                      -- end-to-end duration
    api_calls_count     INTEGER NOT NULL DEFAULT 0,            -- # call ke Lighter API dalam run ini
    api_throttled_count INTEGER NOT NULL DEFAULT 0,            -- # 429 received

    -- Error
    errors              TEXT,                                  -- JSON array of errors (NULL kalau no error)
    success             BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_reclog_ts   ON reconciliation_log(ts_ms);
CREATE INDEX IF NOT EXISTS idx_reclog_mode ON reconciliation_log(mode);
CREATE INDEX IF NOT EXISTS idx_reclog_success ON reconciliation_log(success);

-- Observability queries:
--   1. Reconciliation lag p95:
--      SELECT mode, percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_ms
--      FROM reconciliation_log WHERE ts_ms > ? GROUP BY mode;
--   2. Stuck resolution rate per hour:
--      SELECT date_trunc('hour', to_timestamp(ts_ms/1000)) AS hour, SUM(stuck_resolved)
--      FROM reconciliation_log GROUP BY hour ORDER BY hour DESC LIMIT 24;
--   3. Error rate:
--      SELECT mode, COUNT(*) FILTER (WHERE success=FALSE)*1.0/COUNT(*) AS error_rate
--      FROM reconciliation_log WHERE ts_ms > (now-24h) GROUP BY mode;
