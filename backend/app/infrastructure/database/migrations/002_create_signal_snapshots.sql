-- Migration 002 — signal_snapshots
-- Signal context per entry (write-once, not bergantung outcome trade)
-- Reference: DESIGN_DOC v0.3 §4.0.C.1
--
-- Karakteristik:
--   - Insert sekali saat signal generated (sebelum order placed ke Lighter)
--   - Field linkage (lighter_order_id, link_status) di-update setelah order placed
--   - Tidak pernah delete (audit trail)

CREATE TABLE IF NOT EXISTS signal_snapshots (
    -- Primary key — UUID generated saat signal
    snapshot_id               VARCHAR PRIMARY KEY,

    -- Timing
    ts_signal_ms              BIGINT NOT NULL,                 -- saat signal generated
    candle_open_ts            BIGINT NOT NULL,                 -- candle 4H yang trigger
                                                                -- FIXED dari bug position_manager.py:922
                                                                -- (sebelumnya time.time() salah)
    ts_order_placed_ms        BIGINT,                          -- saat kirim order ke Lighter (NULL kalau belum placed)

    -- Intent (apa yang bot mau lakukan)
    intended_side             VARCHAR NOT NULL,                -- 'LONG' | 'SHORT'
    intended_size_usdt        DOUBLE NOT NULL,                 -- notional intent
    intended_entry_price      DOUBLE,
    intended_sl_price         DOUBLE,
    intended_tp_price         DOUBLE,

    -- Layer 1 — Bayesian Changepoint Detection
    l1_regime                 VARCHAR,                         -- regime label string
    l1_changepoint_prob       DOUBLE,                          -- 0..1

    -- Layer 2 — Technical (EMA structure)
    l2_ema_vote               DOUBLE,                          -- [-1, 1] continuous vote
    l2_aligned                BOOLEAN,                         -- alignment boolean

    -- Layer 3 — MLP (3-class classifier)
    l3_prob_bear              DOUBLE,                          -- 0..1
    l3_prob_neutral           DOUBLE,                          -- 0..1
    l3_prob_bull              DOUBLE,                          -- 0..1
    l3_class                  VARCHAR,                         -- 'BULL' | 'BEAR' | 'NEUTRAL'

    -- Layer 4 — Volatility (Heston-style)
    l4_vol_regime             VARCHAR,                         -- 'low' | 'mid' | 'high'
    l4_current_vol            DOUBLE,
    l4_long_run_vol           DOUBLE,

    -- Market context at signal moment
    atr_at_signal             DOUBLE,
    funding_at_signal         DOUBLE,                          -- funding rate (decimal, e.g. 0.0001)
    oi_at_signal              DOUBLE,                          -- open interest
    cvd_at_signal             DOUBLE,                          -- cumulative volume delta
    htf_zscore_at_signal      DOUBLE,                          -- (close - ema50_4h) / atr14_4h

    -- Aggregate (existing field di live_trades, dipertahankan untuk continuity)
    signal_verdict            VARCHAR,                         -- dari SignalResponse.confluence.verdict
    signal_conviction         DOUBLE,                          -- conviction_pct

    -- Linkage to trade ledger (filled in setelah order placed)
    lighter_order_id          VARCHAR,                         -- FK ke trades_lighter.trade_id
    link_status               VARCHAR NOT NULL DEFAULT 'PENDING',
                                                                -- PENDING (snapshot ditulis, order belum placed)
                                                                -- ORDER_PLACED (order sent ke Lighter)
                                                                -- ORDER_FILLED (matched dengan trades_lighter row)
                                                                -- ORDER_REJECTED (Lighter reject)
                                                                -- ORPHANED (placed tapi tidak ditemukan di trades_lighter setelah X menit)

    -- Audit
    created_at_ms             BIGINT NOT NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_snap_order        ON signal_snapshots(lighter_order_id);
CREATE INDEX IF NOT EXISTS idx_snap_ts           ON signal_snapshots(ts_signal_ms);
CREATE INDEX IF NOT EXISTS idx_snap_link         ON signal_snapshots(link_status);
CREATE INDEX IF NOT EXISTS idx_snap_candle       ON signal_snapshots(candle_open_ts);

-- Query patterns:
--   1. Recent signals: SELECT * FROM signal_snapshots WHERE ts_signal_ms > ? ORDER BY ts_signal_ms DESC
--   2. Linkage check: SELECT * FROM signal_snapshots WHERE lighter_order_id = ?
--   3. Orphan detection: WHERE link_status = 'ORDER_PLACED' AND ts_order_placed_ms < (now - 10 min)
--                       AND lighter_order_id NOT IN (SELECT trade_id FROM trades_lighter)
--   4. Conditional WR: JOIN trades_lighter ON trade_id = lighter_order_id, GROUP BY l1_regime
