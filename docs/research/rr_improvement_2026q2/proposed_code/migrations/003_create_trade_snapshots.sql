-- Migration 003 — trade_snapshots
-- Polling intraday untuk MFE/MAE per trade
-- Reference: DESIGN_DOC v0.3 §4.0.D
--
-- Polling frequency: 30 detik (di reconciliation worker)
-- Untuk trade scalping median 5h × 2/min = ~600 rows/trade
-- Estimasi storage: < 1 MB per 100 trade

CREATE TABLE IF NOT EXISTS trade_snapshots (
    trade_id          VARCHAR NOT NULL,                        -- FK trades_lighter.trade_id
    timestamp_ms      BIGINT NOT NULL,                         -- Unix ms UTC saat snapshot
    price             DOUBLE NOT NULL,                         -- mark price dari Lighter
    pnl_usdt          DOUBLE NOT NULL,                         -- unrealized PnL pada saat snapshot
    pnl_pct           DOUBLE NOT NULL,                         -- pnl_usdt / size_usdt * 100

    PRIMARY KEY (trade_id, timestamp_ms)
);

-- Index untuk query MFE/MAE per trade
CREATE INDEX IF NOT EXISTS idx_tsnap_trade ON trade_snapshots(trade_id);

-- Derive MFE/MAE on-the-fly (tidak perlu maintain running max kolom):
--   SELECT trade_id,
--          MAX(pnl_pct) AS mfe_pct,
--          MIN(pnl_pct) AS mae_pct,
--          MAX(price)   AS price_high,
--          MIN(price)   AS price_low
--   FROM trade_snapshots
--   GROUP BY trade_id;

-- Retention policy (manual / cron, tidak built-in DuckDB):
--   Bisa di-archive trade_snapshots untuk trade yang sudah CLOSED > 30 hari
--   Statement: DELETE FROM trade_snapshots WHERE trade_id IN
--                (SELECT trade_id FROM trades_lighter WHERE status='CLOSED'
--                 AND ts_close_ms < (now - 30*86400*1000))
