"""DuckDB repository for the `trades_lighter` table (Tier 0b)."""
from __future__ import annotations
import hashlib
import json
import logging
import time
from typing import Optional
import duckdb
from .models import ExitType, LighterClosedOrder, LighterPosition, LighterTradeMirror, TradeStatus

logger = logging.getLogger(__name__)
_NOW_MS = lambda: int(time.time() * 1000)

TRADES_LIGHTER_DDL = """
CREATE TABLE IF NOT EXISTS trades_lighter (
    trade_id                  VARCHAR PRIMARY KEY,
    symbol                    VARCHAR NOT NULL,
    side                      VARCHAR NOT NULL,
    ts_open_ms                BIGINT NOT NULL,
    ts_close_ms               BIGINT,
    entry_price               DOUBLE NOT NULL,
    exit_price                DOUBLE,
    size_base                 DOUBLE NOT NULL,
    pnl_usdt                  DOUBLE,
    fee_usdt                  DOUBLE,
    status                    VARCHAR NOT NULL,
    exit_type                 VARCHAR,
    last_synced_ms            BIGINT NOT NULL,
    source_checksum           VARCHAR,
    reconciliation_lag_ms     BIGINT,
    created_at_ms             BIGINT NOT NULL,
    updated_at_ms             BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trl_status        ON trades_lighter(status);
CREATE INDEX IF NOT EXISTS idx_trl_ts_close      ON trades_lighter(ts_close_ms);
CREATE INDEX IF NOT EXISTS idx_trl_ts_open       ON trades_lighter(ts_open_ms);
CREATE INDEX IF NOT EXISTS idx_trl_symbol_status ON trades_lighter(symbol, status);
"""

RECONCILIATION_LOG_DDL = """
CREATE TABLE IF NOT EXISTS reconciliation_log (
    log_id              VARCHAR PRIMARY KEY,
    ts_ms               BIGINT NOT NULL,
    mode                VARCHAR NOT NULL,
    stuck_resolved      INTEGER NOT NULL DEFAULT 0,
    missing_resolved    INTEGER NOT NULL DEFAULT 0,
    upserted            INTEGER NOT NULL DEFAULT 0,
    snapshots_inserted  INTEGER NOT NULL DEFAULT 0,
    duration_ms         INTEGER NOT NULL,
    api_calls_count     INTEGER NOT NULL DEFAULT 0,
    api_throttled_count INTEGER NOT NULL DEFAULT 0,
    errors              TEXT,
    success             BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS idx_reclog_ts      ON reconciliation_log(ts_ms);
CREATE INDEX IF NOT EXISTS idx_reclog_mode    ON reconciliation_log(mode);
CREATE INDEX IF NOT EXISTS idx_reclog_success ON reconciliation_log(success);
"""


def ensure_schema(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(TRADES_LIGHTER_DDL)
    conn.execute(RECONCILIATION_LOG_DDL)


class TradesLighterRepository:
    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self._conn = conn

    def get_open_trade_ids(self) -> set[str]:
        try:
            rows = self._conn.execute(
                "SELECT trade_id FROM trades_lighter WHERE status = 'OPEN'"
            ).fetchall()
            return {row[0] for row in rows}
        except Exception as exc:
            logger.error("[TradesLighterRepo] get_open_trade_ids failed", extra={"error": str(exc)}, exc_info=True)
            raise

    def get_trade(self, trade_id: str) -> Optional[LighterTradeMirror]:
        try:
            row = self._conn.execute(
                """SELECT trade_id, symbol, side, ts_open_ms, ts_close_ms,
                    entry_price, exit_price, size_base, pnl_usdt, fee_usdt,
                    status, exit_type, last_synced_ms, source_checksum,
                    reconciliation_lag_ms, created_at_ms, updated_at_ms
                FROM trades_lighter WHERE trade_id = ?""",
                [trade_id],
            ).fetchone()
            if row is None:
                return None
            return _row_to_mirror(row)
        except Exception as exc:
            logger.error("[TradesLighterRepo] get_trade failed", extra={"trade_id": trade_id, "error": str(exc)}, exc_info=True)
            raise

    def count(self, status: Optional[str] = None) -> int:
        if status:
            return self._conn.execute(
                "SELECT COUNT(*) FROM trades_lighter WHERE status = ?", [status]
            ).fetchone()[0]
        return self._conn.execute("SELECT COUNT(*) FROM trades_lighter").fetchone()[0]

    def upsert_trade(self, trade: LighterTradeMirror) -> None:
        now = _NOW_MS()
        trade.updated_at_ms = now
        trade.last_synced_ms = now
        try:
            self._conn.execute(
                """INSERT INTO trades_lighter (
                    trade_id, symbol, side, ts_open_ms, ts_close_ms,
                    entry_price, exit_price, size_base, pnl_usdt, fee_usdt,
                    status, exit_type, last_synced_ms, source_checksum,
                    reconciliation_lag_ms, created_at_ms, updated_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (trade_id) DO UPDATE SET
                    ts_close_ms = excluded.ts_close_ms,
                    exit_price = excluded.exit_price,
                    pnl_usdt = excluded.pnl_usdt,
                    fee_usdt = excluded.fee_usdt,
                    status = excluded.status,
                    exit_type = excluded.exit_type,
                    last_synced_ms = excluded.last_synced_ms,
                    source_checksum = excluded.source_checksum,
                    reconciliation_lag_ms = excluded.reconciliation_lag_ms,
                    updated_at_ms = excluded.updated_at_ms""",
                [
                    trade.trade_id, trade.symbol, trade.side, trade.ts_open_ms,
                    trade.ts_close_ms, trade.entry_price, trade.exit_price,
                    trade.size_base, trade.pnl_usdt, trade.fee_usdt,
                    trade.status.value, trade.exit_type.value if trade.exit_type else None,
                    trade.last_synced_ms, trade.source_checksum, trade.reconciliation_lag_ms,
                    trade.created_at_ms, trade.updated_at_ms,
                ],
            )
            logger.debug("[TradesLighterRepo] upserted trade", extra={"trade_id": trade.trade_id, "status": trade.status.value})
        except Exception as exc:
            logger.error("[TradesLighterRepo] upsert_trade failed", extra={"trade_id": trade.trade_id, "error": str(exc)}, exc_info=True)
            raise

    def upsert_from_open_position(self, pos: LighterPosition) -> None:
        mirror = LighterTradeMirror(
            trade_id=pos.order_id, symbol=pos.symbol, side=pos.side,
            ts_open_ms=pos.ts_open_ms, entry_price=pos.entry_price,
            size_base=pos.size_base, status=TradeStatus.OPEN,
        )
        self.upsert_trade(mirror)

    def mark_closed(self, trade_id: str, closed_order: LighterClosedOrder, exit_type: Optional[ExitType] = None) -> None:
        now = _NOW_MS()
        existing = self.get_trade(trade_id)
        lag_ms: Optional[int] = None
        if existing and existing.ts_open_ms and closed_order.ts_close_ms:
            lag_ms = now - closed_order.ts_close_ms
        checksum = _checksum(closed_order)
        try:
            self._conn.execute(
                """UPDATE trades_lighter
                SET ts_close_ms = ?, exit_price = ?, pnl_usdt = ?, fee_usdt = ?,
                    status = 'CLOSED', exit_type = ?, last_synced_ms = ?,
                    source_checksum = ?, reconciliation_lag_ms = ?, updated_at_ms = ?
                WHERE trade_id = ?""",
                [
                    closed_order.ts_close_ms, closed_order.exit_price,
                    closed_order.pnl_usdt, closed_order.fee_usdt,
                    exit_type.value if exit_type else ExitType.UNKNOWN.value,
                    now, checksum, lag_ms, now, trade_id,
                ],
            )
            logger.warning("[TradesLighterRepo] reconciled stuck_open -> CLOSED", extra={"trade_id": trade_id, "lag_ms": lag_ms})
        except Exception as exc:
            logger.error("[TradesLighterRepo] mark_closed failed", extra={"trade_id": trade_id, "error": str(exc)}, exc_info=True)
            raise

    def write_reconciliation_log(self, log_id: str, mode: str, ts_ms: int, stuck_resolved: int,
                                  missing_resolved: int, upserted: int, snapshots_inserted: int,
                                  duration_ms: int, api_calls_count: int, api_throttled_count: int,
                                  errors: list[str], success: bool) -> None:
        errors_json = json.dumps(errors) if errors else None
        try:
            self._conn.execute(
                """INSERT INTO reconciliation_log (
                    log_id, ts_ms, mode, stuck_resolved, missing_resolved, upserted,
                    snapshots_inserted, duration_ms, api_calls_count, api_throttled_count,
                    errors, success
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    log_id, ts_ms, mode, stuck_resolved, missing_resolved, upserted,
                    snapshots_inserted, duration_ms, api_calls_count, api_throttled_count,
                    errors_json, success,
                ],
            )
        except Exception as exc:
            logger.error("[TradesLighterRepo] write_reconciliation_log failed", extra={"log_id": log_id, "error": str(exc)}, exc_info=True)
            raise


def _row_to_mirror(row: tuple) -> LighterTradeMirror:
    (trade_id, symbol, side, ts_open_ms, ts_close_ms, entry_price, exit_price,
     size_base, pnl_usdt, fee_usdt, status_str, exit_type_str, last_synced_ms,
     source_checksum, reconciliation_lag_ms, created_at_ms, updated_at_ms) = row
    return LighterTradeMirror(
        trade_id=trade_id, symbol=symbol, side=side, ts_open_ms=ts_open_ms,
        ts_close_ms=ts_close_ms, entry_price=entry_price, exit_price=exit_price,
        size_base=size_base, pnl_usdt=pnl_usdt, fee_usdt=fee_usdt,
        status=TradeStatus(status_str),
        exit_type=ExitType(exit_type_str) if exit_type_str else None,
        last_synced_ms=last_synced_ms, source_checksum=source_checksum,
        reconciliation_lag_ms=reconciliation_lag_ms,
        created_at_ms=created_at_ms, updated_at_ms=updated_at_ms,
    )


def _checksum(obj: object) -> str:
    payload = json.dumps(obj.__dict__, default=str, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]
