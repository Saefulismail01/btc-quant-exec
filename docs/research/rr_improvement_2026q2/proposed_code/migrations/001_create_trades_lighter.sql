-- Migration 001 — trades_lighter
-- Mirror dari Lighter API (source of truth fakta trade)
-- Reference: DESIGN_DOC v0.3 §4.0.B.1
--
-- Idempotent: pakai IF NOT EXISTS

CREATE TABLE IF NOT EXISTS trades_lighter (
    -- Primary key — Lighter order_id entry market
    -- Frozen decision #2 (DESIGN_DOC v0.3 header table)
    trade_id                  VARCHAR PRIMARY KEY,

    -- Market identification
    symbol                    VARCHAR NOT NULL,                -- e.g. 'BTC/USDC'

    -- Direction & timing
    side                      VARCHAR NOT NULL,                -- 'LONG' | 'SHORT'
    ts_open_ms                BIGINT NOT NULL,                 -- Unix ms UTC, dari Lighter fill timestamp
    ts_close_ms               BIGINT,                          -- NULL while OPEN

    -- Prices
    entry_price               DOUBLE NOT NULL,
    exit_price                DOUBLE,                          -- NULL while OPEN

    -- Size (BTC native, bukan notional)
    size_base                 DOUBLE NOT NULL,

    -- P&L (USDT, signed; positive = profit)
    pnl_usdt                  DOUBLE,                          -- NULL while OPEN
    fee_usdt                  DOUBLE,                          -- separate from PnL untuk akurasi

    -- Status & exit classification
    status                    VARCHAR NOT NULL,                -- 'OPEN' | 'CLOSED'
    exit_type                 VARCHAR,                         -- 'TP' | 'SL' | 'TIME' | 'MANUAL' | 'UNKNOWN'
                                                                -- inferred via H.5 rule (stop-loss-limit / take-profit-limit / price tolerance)

    -- Reconciliation metadata
    last_synced_ms            BIGINT NOT NULL,                 -- Unix ms saat row di-sync dari Lighter
    source_checksum           VARCHAR,                         -- hash dari raw Lighter response payload (deteksi drift)
    reconciliation_lag_ms     BIGINT,                          -- ts_close_ms vs first time we saw CLOSED
                                                                -- NULL kalau ditemukan langsung CLOSED (no lag)

    -- Audit
    created_at_ms             BIGINT NOT NULL,
    updated_at_ms             BIGINT NOT NULL
);

-- Indexes untuk query pattern reconciliation worker & analytics
CREATE INDEX IF NOT EXISTS idx_trl_status        ON trades_lighter(status);
CREATE INDEX IF NOT EXISTS idx_trl_ts_close      ON trades_lighter(ts_close_ms);
CREATE INDEX IF NOT EXISTS idx_trl_ts_open       ON trades_lighter(ts_open_ms);
CREATE INDEX IF NOT EXISTS idx_trl_symbol_status ON trades_lighter(symbol, status);

-- Sanity comment
-- Query patterns:
--   1. Sweep open: SELECT trade_id FROM trades_lighter WHERE status='OPEN'
--   2. Recent closed: SELECT * FROM trades_lighter WHERE ts_close_ms > ? ORDER BY ts_close_ms DESC
--   3. Analytics join: ON trades_lighter.trade_id = signal_snapshots.lighter_order_id
