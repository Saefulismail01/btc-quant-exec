"""DuckDB repository for the `signal_snapshots` table (Tier 0c)."""
from __future__ import annotations
import logging
import time
from typing import Optional
import duckdb
from .models import LinkStatus, SignalSnapshot

logger = logging.getLogger(__name__)
_NOW_MS = lambda: int(time.time() * 1000)

SIGNAL_SNAPSHOTS_DDL = """
CREATE TABLE IF NOT EXISTS signal_snapshots (
    snapshot_id VARCHAR PRIMARY KEY,
    ts_signal_ms BIGINT NOT NULL,
    candle_open_ts BIGINT NOT NULL,
    ts_order_placed_ms BIGINT,
    intended_side VARCHAR NOT NULL,
    intended_size_usdt DOUBLE NOT NULL,
    intended_entry_price DOUBLE,
    intended_sl_price DOUBLE,
    intended_tp_price DOUBLE,
    l1_regime VARCHAR,
    l1_changepoint_prob DOUBLE,
    l2_ema_vote DOUBLE,
    l2_aligned BOOLEAN,
    l3_prob_bear DOUBLE,
    l3_prob_neutral DOUBLE,
    l3_prob_bull DOUBLE,
    l3_class VARCHAR,
    l4_vol_regime VARCHAR,
    l4_current_vol DOUBLE,
    l4_long_run_vol DOUBLE,
    atr_at_signal DOUBLE,
    funding_at_signal DOUBLE,
    oi_at_signal DOUBLE,
    cvd_at_signal DOUBLE,
    htf_zscore_at_signal DOUBLE,
    signal_verdict VARCHAR,
    signal_conviction DOUBLE,
    lighter_order_id VARCHAR,
    link_status VARCHAR NOT NULL DEFAULT 'PENDING',
    created_at_ms BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snap_order ON signal_snapshots(lighter_order_id);
CREATE INDEX IF NOT EXISTS idx_snap_ts ON signal_snapshots(ts_signal_ms);
CREATE INDEX IF NOT EXISTS idx_snap_link ON signal_snapshots(link_status);
CREATE INDEX IF NOT EXISTS idx_snap_candle ON signal_snapshots(candle_open_ts);
"""


def ensure_schema(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(SIGNAL_SNAPSHOTS_DDL)


class SignalSnapshotRepository:
    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    def insert(self, snapshot: SignalSnapshot) -> str:
        try:
            self._conn.execute(
                """INSERT INTO signal_snapshots (
                    snapshot_id, ts_signal_ms, candle_open_ts, ts_order_placed_ms,
                    intended_side, intended_size_usdt, intended_entry_price,
                    intended_sl_price, intended_tp_price, l1_regime, l1_changepoint_prob,
                    l2_ema_vote, l2_aligned, l3_prob_bear, l3_prob_neutral, l3_prob_bull, l3_class,
                    l4_vol_regime, l4_current_vol, l4_long_run_vol, atr_at_signal,
                    funding_at_signal, oi_at_signal, cvd_at_signal, htf_zscore_at_signal,
                    signal_verdict, signal_conviction, lighter_order_id, link_status, created_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    snapshot.snapshot_id, snapshot.ts_signal_ms, snapshot.candle_open_ts, snapshot.ts_order_placed_ms,
                    snapshot.intended_side, snapshot.intended_size_usdt, snapshot.intended_entry_price,
                    snapshot.intended_sl_price, snapshot.intended_tp_price, snapshot.l1_regime, snapshot.l1_changepoint_prob,
                    snapshot.l2_ema_vote, snapshot.l2_aligned, snapshot.l3_prob_bear, snapshot.l3_prob_neutral,
                    snapshot.l3_prob_bull, snapshot.l3_class, snapshot.l4_vol_regime, snapshot.l4_current_vol,
                    snapshot.l4_long_run_vol, snapshot.atr_at_signal, snapshot.funding_at_signal, snapshot.oi_at_signal,
                    snapshot.cvd_at_signal, snapshot.htf_zscore_at_signal, snapshot.signal_verdict, snapshot.signal_conviction,
                    snapshot.lighter_order_id, snapshot.link_status.value, snapshot.created_at_ms,
                ],
            )
            logger.debug("[SnapshotRepo] inserted snapshot", extra={"snapshot_id": snapshot.snapshot_id})
            return snapshot.snapshot_id
        except Exception as exc:
            logger.error("[SnapshotRepo] insert failed", extra={"snapshot_id": snapshot.snapshot_id, "error": str(exc)}, exc_info=True)
            raise

    def update_linkage(self, snapshot_id: str, link_status: LinkStatus,
                       lighter_order_id: Optional[str] = None, ts_order_placed_ms: Optional[int] = None) -> None:
        try:
            self._conn.execute(
                """UPDATE signal_snapshots
                SET link_status = ?, lighter_order_id = COALESCE(?, lighter_order_id),
                    ts_order_placed_ms = COALESCE(?, ts_order_placed_ms)
                WHERE snapshot_id = ?""",
                [link_status.value, lighter_order_id, ts_order_placed_ms, snapshot_id],
            )
            logger.debug("[SnapshotRepo] updated linkage", extra={"snapshot_id": snapshot_id, "link_status": link_status.value})
        except Exception as exc:
            logger.error("[SnapshotRepo] update_linkage failed", extra={"snapshot_id": snapshot_id, "error": str(exc)}, exc_info=True)
            raise

    def mark_orphaned(self, older_than_ms: int, trades_lighter_ids: set[str]) -> int:
        if not trades_lighter_ids:
            rows = self._conn.execute(
                """SELECT snapshot_id FROM signal_snapshots
                WHERE link_status = 'ORDER_PLACED' AND ts_order_placed_ms IS NOT NULL
                AND ts_order_placed_ms < ? AND lighter_order_id IS NOT NULL""",
                [older_than_ms],
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT snapshot_id, lighter_order_id FROM signal_snapshots
                WHERE link_status = 'ORDER_PLACED' AND ts_order_placed_ms IS NOT NULL
                AND ts_order_placed_ms < ? AND lighter_order_id IS NOT NULL""",
                [older_than_ms],
            ).fetchall()
            rows = [r for r in rows if r[1] not in trades_lighter_ids]

        if not rows:
            return 0

        orphan_ids = [r[0] for r in rows]
        updated = 0
        for sid in orphan_ids:
            self._conn.execute(
                "UPDATE signal_snapshots SET link_status = 'ORPHANED' WHERE snapshot_id = ?",
                [sid],
            )
            updated += 1
        logger.warning("[SnapshotRepo] marked orphans", extra={"count": updated})
        return updated

    def get_by_order_id(self, lighter_order_id: str) -> Optional[SignalSnapshot]:
        try:
            row = self._conn.execute(
                "SELECT * FROM signal_snapshots WHERE lighter_order_id = ? LIMIT 1",
                [lighter_order_id],
            ).fetchone()
            if row is None:
                return None
            return _row_to_snapshot(row, self._conn)
        except Exception as exc:
            logger.error("[SnapshotRepo] get_by_order_id failed", extra={"lighter_order_id": lighter_order_id, "error": str(exc)}, exc_info=True)
            raise

    def get_by_snapshot_id(self, snapshot_id: str) -> Optional[SignalSnapshot]:
        try:
            row = self._conn.execute(
                "SELECT * FROM signal_snapshots WHERE snapshot_id = ?",
                [snapshot_id],
            ).fetchone()
            if row is None:
                return None
            return _row_to_snapshot(row, self._conn)
        except Exception as exc:
            logger.error("[SnapshotRepo] get_by_snapshot_id failed", extra={"snapshot_id": snapshot_id, "error": str(exc)}, exc_info=True)
            raise

    def count(self, link_status: Optional[str] = None) -> int:
        if link_status:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM signal_snapshots WHERE link_status = ?",
                [link_status],
            ).fetchone()
            return row[0] if row else 0
        row = self._conn.execute("SELECT COUNT(*) FROM signal_snapshots").fetchone()
        return row[0] if row else 0


def _row_to_snapshot(row: tuple, conn: duckdb.DuckDBPyConnection) -> SignalSnapshot:
    col_names = [desc[0] for desc in conn.description]
    d = dict(zip(col_names, row))
    return SignalSnapshot(
        snapshot_id=d["snapshot_id"],
        ts_signal_ms=d["ts_signal_ms"],
        candle_open_ts=d["candle_open_ts"],
        ts_order_placed_ms=d.get("ts_order_placed_ms"),
        intended_side=d["intended_side"],
        intended_size_usdt=d["intended_size_usdt"],
        intended_entry_price=d.get("intended_entry_price"),
        intended_sl_price=d.get("intended_sl_price"),
        intended_tp_price=d.get("intended_tp_price"),
        l1_regime=d.get("l1_regime"),
        l1_changepoint_prob=d.get("l1_changepoint_prob"),
        l2_ema_vote=d.get("l2_ema_vote"),
        l2_aligned=d.get("l2_aligned"),
        l3_prob_bear=d.get("l3_prob_bear"),
        l3_prob_neutral=d.get("l3_prob_neutral"),
        l3_prob_bull=d.get("l3_prob_bull"),
        l3_class=d.get("l3_class"),
        l4_vol_regime=d.get("l4_vol_regime"),
        l4_current_vol=d.get("l4_current_vol"),
        l4_long_run_vol=d.get("l4_long_run_vol"),
        atr_at_signal=d.get("atr_at_signal"),
        funding_at_signal=d.get("funding_at_signal"),
        oi_at_signal=d.get("oi_at_signal"),
        cvd_at_signal=d.get("cvd_at_signal"),
        htf_zscore_at_signal=d.get("htf_zscore_at_signal"),
        signal_verdict=d.get("signal_verdict"),
        signal_conviction=d.get("signal_conviction"),
        lighter_order_id=d.get("lighter_order_id"),
        link_status=LinkStatus(d["link_status"]),
        created_at_ms=d["created_at_ms"],
    )
