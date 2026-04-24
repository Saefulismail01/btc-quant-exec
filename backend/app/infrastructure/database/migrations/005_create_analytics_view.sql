-- Migration 005 — analytics_trades view
-- Final analytics view: join trades_lighter + signal_snapshots + MFE/MAE on-the-fly
-- Reference: DESIGN_DOC v0.3 §4.0 (Final analytics view)
--
-- Idempotent: pakai CREATE OR REPLACE VIEW (DuckDB ≥0.9 support)
-- Filter: WHERE t.status = 'CLOSED' — only closed trades enter analytics

CREATE OR REPLACE VIEW analytics_trades AS
SELECT
    -- Trade ledger (source of truth from Lighter)
    t.trade_id,
    t.symbol,
    t.side,
    t.ts_open_ms,
    t.ts_close_ms,
    t.entry_price,
    t.exit_price,
    t.pnl_usdt,
    t.fee_usdt,
    t.exit_type,
    t.status,
    t.reconciliation_lag_ms,

    -- Signal context (write-once at signal time)
    s.candle_open_ts,
    s.l1_regime,
    s.l1_changepoint_prob,
    s.l2_ema_vote,
    s.l2_aligned,
    s.l3_prob_bull,
    s.l3_prob_bear,
    s.l3_prob_neutral,
    s.l3_class,
    s.l4_vol_regime,
    s.l4_current_vol,
    s.atr_at_signal,
    s.funding_at_signal,
    s.oi_at_signal,
    s.cvd_at_signal,
    s.htf_zscore_at_signal,
    s.signal_conviction,
    s.signal_verdict,
    s.intended_sl_price,
    s.intended_tp_price,

    -- MFE/MAE derived on-the-fly from trade_snapshots (no running-max column needed)
    (SELECT MAX(pnl_pct) FROM trade_snapshots WHERE trade_id = t.trade_id) AS mfe_pct,
    (SELECT MIN(pnl_pct) FROM trade_snapshots WHERE trade_id = t.trade_id) AS mae_pct,
    (SELECT MAX(price)   FROM trade_snapshots WHERE trade_id = t.trade_id) AS price_high,
    (SELECT MIN(price)   FROM trade_snapshots WHERE trade_id = t.trade_id) AS price_low

FROM trades_lighter t
LEFT JOIN signal_snapshots s
    ON s.lighter_order_id = t.trade_id
WHERE t.status = 'CLOSED';

-- Rollback: DROP VIEW IF EXISTS analytics_trades;

-- Sample queries:
--   Conditional WR by L1 regime:
--     SELECT l1_regime,
--            COUNT(*) FILTER (WHERE exit_type = 'TP') * 1.0 / COUNT(*) AS win_rate,
--            COUNT(*) AS n
--     FROM analytics_trades
--     GROUP BY l1_regime ORDER BY n DESC;
--
--   MFE distribution by L3 class:
--     SELECT l3_class, percentile_cont(0.5) WITHIN GROUP (ORDER BY mfe_pct) AS mfe_p50
--     FROM analytics_trades GROUP BY l3_class;
--
--   HTF z-score vs exit_type:
--     SELECT exit_type, AVG(htf_zscore_at_signal), COUNT(*)
--     FROM analytics_trades GROUP BY exit_type;
