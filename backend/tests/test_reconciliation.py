"""Tests for reconciliation package (Tier 0b)."""
import pytest
import duckdb
from backend.app.adapters.repositories.reconciliation import (
    LighterTradeMirror,
    LighterPosition,
    LighterClosedOrder,
    TradeStatus,
    ExitType,
    TradesLighterRepository,
    infer_exit_type,
)
from backend.app.adapters.repositories.reconciliation.models import ReconcileMode, ReconciliationResult


@pytest.fixture
def in_memory_db():
    """Create fresh in-memory DuckDB for each test."""
    conn = duckdb.connect(":memory:")
    from backend.app.adapters.repositories.reconciliation.trades_lighter_repository import ensure_schema
    ensure_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def repo(in_memory_db):
    """Repository instance with in-memory DB."""
    return TradesLighterRepository(in_memory_db)


class TestModels:
    """Test domain models."""

    def test_lighter_trade_mirror_defaults(self):
        mirror = LighterTradeMirror(
            trade_id="test-123",
            symbol="BTC/USDC",
            side="LONG",
            ts_open_ms=1000,
            entry_price=50000.0,
            size_base=0.1,
        )
        assert mirror.status == TradeStatus.OPEN
        assert mirror.is_open()
        assert not mirror.is_closed()

    def test_exit_type_enum(self):
        assert ExitType.TP.value == "TP"
        assert ExitType.SL.value == "SL"
        assert ExitType.UNKNOWN.value == "UNKNOWN"


class TestExitTypeInference:
    """Test exit type inference logic."""

    def test_tp_from_order_type(self):
        result = infer_exit_type("take-profit-limit")
        assert result == ExitType.TP

    def test_sl_from_order_type(self):
        result = infer_exit_type("stop-loss-limit")
        assert result == ExitType.SL

    def test_manual_from_market(self):
        result = infer_exit_type("market")
        assert result == ExitType.MANUAL

    def test_unknown_fallback(self):
        result = infer_exit_type("unknown-type")
        assert result == ExitType.UNKNOWN

    def test_tp_from_price_tolerance(self):
        result = infer_exit_type(
            "limit",
            exit_price=50500.0,
            intended_tp_price=50500.0,
            price_tolerance_pct=0.5
        )
        assert result == ExitType.TP

    def test_sl_from_price_tolerance(self):
        result = infer_exit_type(
            "limit",
            exit_price=49500.0,
            intended_sl_price=49500.0,
            price_tolerance_pct=0.5
        )
        assert result == ExitType.SL


class TestTradesLighterRepository:
    """Test repository CRUD operations."""

    def test_upsert_trade(self, repo):
        trade = LighterTradeMirror(
            trade_id="test-1",
            symbol="BTC/USDC",
            side="LONG",
            ts_open_ms=1000,
            entry_price=50000.0,
            size_base=0.1,
            status=TradeStatus.OPEN,
        )
        repo.upsert_trade(trade)

        # Verify
        assert repo.count() == 1
        assert repo.count(status="OPEN") == 1

    def test_get_open_trade_ids(self, repo):
        # Insert open trade
        open_trade = LighterTradeMirror(
            trade_id="open-1",
            symbol="BTC/USDC",
            side="LONG",
            ts_open_ms=1000,
            entry_price=50000.0,
            size_base=0.1,
            status=TradeStatus.OPEN,
        )
        repo.upsert_trade(open_trade)

        # Insert closed trade
        closed_trade = LighterTradeMirror(
            trade_id="closed-1",
            symbol="BTC/USDC",
            side="SHORT",
            ts_open_ms=2000,
            ts_close_ms=3000,
            entry_price=51000.0,
            exit_price=50000.0,
            size_base=0.1,
            status=TradeStatus.CLOSED,
        )
        repo.upsert_trade(closed_trade)

        open_ids = repo.get_open_trade_ids()
        assert open_ids == {"open-1"}

    def test_mark_closed(self, repo):
        # Insert open trade
        trade = LighterTradeMirror(
            trade_id="test-close",
            symbol="BTC/USDC",
            side="LONG",
            ts_open_ms=1000,
            entry_price=50000.0,
            size_base=0.1,
            status=TradeStatus.OPEN,
        )
        repo.upsert_trade(trade)

        # Close it
        closed_order = LighterClosedOrder(
            order_id="test-close",
            symbol="BTC/USDC",
            side="LONG",
            entry_price=50000.0,
            exit_price=50500.0,
            size_base=0.1,
            pnl_usdt=50.0,
            fee_usdt=2.0,
            ts_open_ms=1000,
            ts_close_ms=2000,
            order_type="take-profit-limit",
        )
        repo.mark_closed("test-close", closed_order, ExitType.TP)

        # Verify
        closed_trade = repo.get_trade("test-close")
        assert closed_trade.status == TradeStatus.CLOSED
        assert closed_trade.exit_type == ExitType.TP
        assert closed_trade.pnl_usdt == 50.0

    def test_upsert_from_open_position(self, repo):
        position = LighterPosition(
            order_id="pos-1",
            symbol="BTC/USDC",
            side="SHORT",
            entry_price=52000.0,
            size_base=0.05,
            ts_open_ms=3000,
        )
        repo.upsert_from_open_position(position)

        trade = repo.get_trade("pos-1")
        assert trade is not None
        assert trade.side == "SHORT"
        assert trade.status == TradeStatus.OPEN


class TestReconciliationResult:
    """Test reconciliation result model."""

    def test_result_defaults(self):
        result = ReconciliationResult(
            log_id="test-log-1",
            mode=ReconcileMode.SWEEP,
        )
        assert result.success is True
        assert result.stuck_resolved == 0
        assert result.missing_resolved == 0

    def test_mark_error(self):
        result = ReconciliationResult(
            log_id="test-log-2",
            mode=ReconcileMode.SWEEP,
        )
        result.mark_error("test error message")
        assert result.success is False
        assert "test error message" in result.errors


class TestReconciliationLog:
    """Test reconciliation_log table operations."""

    def test_write_reconciliation_log(self, repo):
        repo.write_reconciliation_log(
            log_id="log-1",
            mode="sweep",
            ts_ms=1000,
            stuck_resolved=2,
            missing_resolved=1,
            upserted=3,
            snapshots_inserted=0,
            duration_ms=500,
            api_calls_count=4,
            api_throttled_count=0,
            errors=[],
            success=True,
        )

        # Verify via direct query
        row = repo._conn.execute(
            "SELECT * FROM reconciliation_log WHERE log_id = ?", ["log-1"]
        ).fetchone()
        assert row is not None
        assert row[3] == 2  # stuck_resolved at index 3 (log_id, ts_ms, mode, stuck_resolved...)
