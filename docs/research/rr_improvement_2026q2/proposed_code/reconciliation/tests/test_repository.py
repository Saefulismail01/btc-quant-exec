"""
Tests for TradesLighterRepository — uses in-memory DuckDB (:memory:).

Covers:
  - upsert_trade (insert new, update existing)
  - upsert_from_open_position
  - mark_closed (stuck-open resolution)
  - get_open_trade_ids
  - get_trade (fetch by PK)
  - write_reconciliation_log
  - count helpers
"""

import time

import duckdb
import pytest

from reconciliation.models import (
    ExitType,
    LighterClosedOrder,
    LighterPosition,
    LighterTradeMirror,
    TradeStatus,
)
from reconciliation.trades_lighter_repository import (
    TradesLighterRepository,
    ensure_schema,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def conn():
    """Fresh in-memory DuckDB connection with schema applied."""
    c = duckdb.connect(":memory:")
    ensure_schema(c)
    yield c
    c.close()


@pytest.fixture
def repo(conn):
    return TradesLighterRepository(conn)


def _make_mirror(trade_id: str = "order_001", status: TradeStatus = TradeStatus.OPEN) -> LighterTradeMirror:
    now = int(time.time() * 1000)
    return LighterTradeMirror(
        trade_id=trade_id,
        symbol="BTC/USDC",
        side="LONG",
        ts_open_ms=now - 3600_000,
        entry_price=95_000.0,
        size_base=0.01,
        status=status,
    )


def _make_closed_order(order_id: str = "order_001") -> LighterClosedOrder:
    now = int(time.time() * 1000)
    return LighterClosedOrder(
        order_id=order_id,
        symbol="BTC/USDC",
        side="LONG",
        entry_price=95_000.0,
        exit_price=95_675.0,
        size_base=0.01,
        pnl_usdt=6.75,
        fee_usdt=0.19,
        ts_open_ms=now - 7200_000,
        ts_close_ms=now - 60_000,
        order_type="take-profit-limit",
    )


# ── upsert_trade ──────────────────────────────────────────────────────────────

class TestUpsertTrade:
    def test_insert_new_open(self, repo):
        mirror = _make_mirror("t1", TradeStatus.OPEN)
        repo.upsert_trade(mirror)
        assert repo.count() == 1
        assert repo.count("OPEN") == 1

    def test_upsert_updates_status(self, repo):
        mirror = _make_mirror("t1", TradeStatus.OPEN)
        repo.upsert_trade(mirror)

        mirror.status = TradeStatus.CLOSED
        mirror.exit_price = 95_500.0
        mirror.pnl_usdt = 5.0
        mirror.exit_type = ExitType.TP
        repo.upsert_trade(mirror)

        fetched = repo.get_trade("t1")
        assert fetched.status == TradeStatus.CLOSED
        assert fetched.exit_price == pytest.approx(95_500.0)
        assert fetched.exit_type == ExitType.TP

    def test_upsert_idempotent(self, repo):
        mirror = _make_mirror("t1")
        repo.upsert_trade(mirror)
        repo.upsert_trade(mirror)
        repo.upsert_trade(mirror)
        assert repo.count() == 1

    def test_multiple_trades(self, repo):
        for i in range(5):
            repo.upsert_trade(_make_mirror(f"order_{i:03d}"))
        assert repo.count() == 5


# ── upsert_from_open_position ──────────────────────────────────────────────────

class TestUpsertFromOpenPosition:
    def test_insert_from_position(self, repo):
        pos = LighterPosition(
            order_id="pos_001",
            symbol="BTC/USDC",
            side="SHORT",
            entry_price=96_000.0,
            size_base=0.005,
            ts_open_ms=int(time.time() * 1000) - 1800_000,
        )
        repo.upsert_from_open_position(pos)
        fetched = repo.get_trade("pos_001")
        assert fetched is not None
        assert fetched.status == TradeStatus.OPEN
        assert fetched.side == "SHORT"

    def test_idempotent_position_insert(self, repo):
        pos = LighterPosition(
            order_id="pos_002",
            symbol="BTC/USDC",
            side="LONG",
            entry_price=94_000.0,
            size_base=0.01,
            ts_open_ms=int(time.time() * 1000),
        )
        repo.upsert_from_open_position(pos)
        repo.upsert_from_open_position(pos)
        assert repo.count() == 1


# ── mark_closed ────────────────────────────────────────────────────────────────

class TestMarkClosed:
    def test_stuck_open_resolved(self, repo):
        # Insert as OPEN first
        repo.upsert_trade(_make_mirror("stuck_001", TradeStatus.OPEN))

        closed = _make_closed_order("stuck_001")
        repo.mark_closed("stuck_001", closed, ExitType.TP)

        fetched = repo.get_trade("stuck_001")
        assert fetched.status == TradeStatus.CLOSED
        assert fetched.exit_type == ExitType.TP
        assert fetched.exit_price == pytest.approx(95_675.0)
        assert fetched.pnl_usdt == pytest.approx(6.75)

    def test_reconciliation_lag_set(self, repo):
        repo.upsert_trade(_make_mirror("lag_001", TradeStatus.OPEN))
        closed = _make_closed_order("lag_001")
        repo.mark_closed("lag_001", closed, ExitType.SL)

        fetched = repo.get_trade("lag_001")
        # Lag should be ≥ 0 (closed_ms was 60s ago, but we're calling now)
        assert fetched.reconciliation_lag_ms is not None
        assert fetched.reconciliation_lag_ms >= 0

    def test_mark_closed_defaults_to_unknown(self, repo):
        repo.upsert_trade(_make_mirror("unk_001", TradeStatus.OPEN))
        closed = _make_closed_order("unk_001")
        repo.mark_closed("unk_001", closed, exit_type=None)

        fetched = repo.get_trade("unk_001")
        assert fetched.exit_type == ExitType.UNKNOWN


# ── get_open_trade_ids ────────────────────────────────────────────────────────

class TestGetOpenTradeIds:
    def test_empty_set(self, repo):
        assert repo.get_open_trade_ids() == set()

    def test_returns_open_ids(self, repo):
        repo.upsert_trade(_make_mirror("open_1", TradeStatus.OPEN))
        repo.upsert_trade(_make_mirror("open_2", TradeStatus.OPEN))
        closed = _make_mirror("closed_1", TradeStatus.CLOSED)
        closed.exit_price = 95_500.0
        closed.exit_type = ExitType.TP
        repo.upsert_trade(closed)

        ids = repo.get_open_trade_ids()
        assert ids == {"open_1", "open_2"}

    def test_excludes_closed(self, repo):
        m = _make_mirror("t_closed", TradeStatus.OPEN)
        repo.upsert_trade(m)
        m.status = TradeStatus.CLOSED
        m.exit_price = 95_000.0
        repo.upsert_trade(m)

        assert repo.get_open_trade_ids() == set()


# ── get_trade ─────────────────────────────────────────────────────────────────

class TestGetTrade:
    def test_returns_none_for_missing(self, repo):
        assert repo.get_trade("nonexistent") is None

    def test_returns_correct_trade(self, repo):
        mirror = _make_mirror("fetch_me", TradeStatus.OPEN)
        mirror.entry_price = 93_333.3
        repo.upsert_trade(mirror)

        fetched = repo.get_trade("fetch_me")
        assert fetched.trade_id == "fetch_me"
        assert fetched.entry_price == pytest.approx(93_333.3)
        assert fetched.symbol == "BTC/USDC"


# ── write_reconciliation_log ───────────────────────────────────────────────────

class TestWriteReconciliationLog:
    def test_write_and_read_log(self, conn, repo):
        import uuid
        log_id = str(uuid.uuid4())
        repo.write_reconciliation_log(
            log_id=log_id,
            mode="sweep",
            ts_ms=int(time.time() * 1000),
            stuck_resolved=2,
            missing_resolved=1,
            upserted=3,
            snapshots_inserted=0,
            duration_ms=345,
            api_calls_count=4,
            api_throttled_count=0,
            errors=[],
            success=True,
        )

        row = conn.execute(
            "SELECT stuck_resolved, missing_resolved, duration_ms FROM reconciliation_log WHERE log_id = ?",
            [log_id],
        ).fetchone()
        assert row is not None
        assert row[0] == 2
        assert row[1] == 1
        assert row[2] == 345

    def test_write_log_with_errors(self, conn, repo):
        import uuid
        log_id = str(uuid.uuid4())
        repo.write_reconciliation_log(
            log_id=log_id,
            mode="history",
            ts_ms=int(time.time() * 1000),
            stuck_resolved=0,
            missing_resolved=0,
            upserted=0,
            snapshots_inserted=0,
            duration_ms=100,
            api_calls_count=1,
            api_throttled_count=1,
            errors=["API 429: rate limited", "timeout on order_999"],
            success=False,
        )

        row = conn.execute(
            "SELECT success, errors FROM reconciliation_log WHERE log_id = ?",
            [log_id],
        ).fetchone()
        assert row[0] is False
        assert "429" in row[1]
