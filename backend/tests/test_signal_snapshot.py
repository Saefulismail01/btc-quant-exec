"""Tests for signal_snapshot package (Tier 0c)."""
import pytest
import duckdb
from backend.app.adapters.repositories.signal_snapshot import (
    SignalSnapshot,
    SignalSnapshotRepository,
    LinkStatus,
)


@pytest.fixture
def in_memory_db():
    """Create fresh in-memory DuckDB for each test."""
    conn = duckdb.connect(":memory:")
    from backend.app.adapters.repositories.signal_snapshot.signal_snapshot_repository import ensure_schema
    ensure_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def repo(in_memory_db):
    """Repository instance with in-memory DB."""
    return SignalSnapshotRepository(in_memory_db)


class TestSignalSnapshotModel:
    """Test SignalSnapshot dataclass."""

    def test_create_factory(self):
        snapshot = SignalSnapshot.create(
            candle_open_ts=1000,
            intended_side="LONG",
            intended_size_usdt=500.0,
            l3_prob_bull=0.8,
            l3_prob_bear=0.1,
        )
        assert snapshot.candle_open_ts == 1000
        assert snapshot.intended_side == "LONG"
        assert snapshot.l3_prob_bull == 0.8
        assert snapshot.link_status == LinkStatus.PENDING
        assert snapshot.snapshot_id is not None

    def test_default_link_status(self):
        snapshot = SignalSnapshot(
            ts_signal_ms=1000,
            candle_open_ts=1000,
            intended_side="SHORT",
            intended_size_usdt=300.0,
        )
        assert snapshot.link_status == LinkStatus.PENDING

    def test_optional_fields(self):
        snapshot = SignalSnapshot(
            ts_signal_ms=1000,
            candle_open_ts=1000,
            intended_side="LONG",
            intended_size_usdt=500.0,
            l1_regime="BULL",
            l1_changepoint_prob=0.7,
            atr_at_signal=1500.0,
            funding_at_signal=0.0001,
        )
        assert snapshot.l1_regime == "BULL"
        assert snapshot.atr_at_signal == 1500.0


class TestSignalSnapshotRepository:
    """Test repository operations."""

    def test_insert_and_retrieve(self, repo):
        snapshot = SignalSnapshot.create(
            candle_open_ts=1000,
            intended_side="LONG",
            intended_size_usdt=500.0,
            l3_prob_bull=0.75,
            l3_prob_bear=0.15,
            l3_prob_neutral=0.10,
            l3_class="BULL",
            signal_verdict="WEAK BUY",
            signal_conviction=65.0,
        )

        snapshot_id = repo.insert(snapshot)
        assert snapshot_id is not None

        # Retrieve by snapshot_id
        retrieved = repo.get_by_snapshot_id(snapshot_id)
        assert retrieved is not None
        assert retrieved.l3_prob_bull == 0.75
        assert retrieved.signal_verdict == "WEAK BUY"

    def test_update_linkage(self, repo):
        # Create snapshot
        snapshot = SignalSnapshot.create(
            candle_open_ts=1000,
            intended_side="LONG",
            intended_size_usdt=500.0,
        )
        snapshot_id = repo.insert(snapshot)

        # Update linkage
        repo.update_linkage(
            snapshot_id=snapshot_id,
            link_status=LinkStatus.ORDER_PLACED,
            lighter_order_id="order-123",
            ts_order_placed_ms=2000,
        )

        # Verify
        retrieved = repo.get_by_snapshot_id(snapshot_id)
        assert retrieved.link_status == LinkStatus.ORDER_PLACED
        assert retrieved.lighter_order_id == "order-123"
        assert retrieved.ts_order_placed_ms == 2000

    def test_get_by_order_id(self, repo):
        snapshot = SignalSnapshot.create(
            candle_open_ts=1000,
            intended_side="SHORT",
            intended_size_usdt=300.0,
            lighter_order_id="order-456",
            link_status=LinkStatus.ORDER_FILLED,
        )
        repo.insert(snapshot)

        retrieved = repo.get_by_order_id("order-456")
        assert retrieved is not None
        assert retrieved.intended_side == "SHORT"

    def test_count_by_link_status(self, repo):
        # Insert PENDING
        pending = SignalSnapshot.create(
            candle_open_ts=1000,
            intended_side="LONG",
            intended_size_usdt=500.0,
        )
        repo.insert(pending)

        # Insert ORDER_PLACED
        placed = SignalSnapshot.create(
            candle_open_ts=2000,
            intended_side="SHORT",
            intended_size_usdt=300.0,
            lighter_order_id="order-1",
            link_status=LinkStatus.ORDER_PLACED,
        )
        repo.insert(placed)

        assert repo.count() == 2
        assert repo.count("PENDING") == 1
        assert repo.count("ORDER_PLACED") == 1

    def test_mark_orphaned(self, repo):
        # Create old ORDER_PLACED snapshot
        old_snapshot = SignalSnapshot.create(
            candle_open_ts=1000,
            intended_side="LONG",
            intended_size_usdt=500.0,
            lighter_order_id="orphan-order",
            link_status=LinkStatus.ORDER_PLACED,
            ts_order_placed_ms=1000,  # Very old
        )
        repo.insert(old_snapshot)

        # Mark as orphaned (orders older than 5000ms, not in trades_lighter)
        updated = repo.mark_orphaned(
            older_than_ms=5000,
            trades_lighter_ids=set()  # Empty = no matching orders
        )
        assert updated == 1

        # Verify
        retrieved = repo.get_by_order_id("orphan-order")
        assert retrieved.link_status == LinkStatus.ORPHANED

    def test_mark_orphaned_with_existing_orders(self, repo):
        # Create ORDER_PLACED snapshot
        snapshot = SignalSnapshot.create(
            candle_open_ts=1000,
            intended_side="LONG",
            intended_size_usdt=500.0,
            lighter_order_id="existing-order",
            link_status=LinkStatus.ORDER_PLACED,
            ts_order_placed_ms=1000,
        )
        repo.insert(snapshot)

        # Mark as orphaned, but order exists in trades_lighter
        updated = repo.mark_orphaned(
            older_than_ms=5000,
            trades_lighter_ids={"existing-order"}
        )
        assert updated == 0  # Not orphaned because order exists

        # Verify still ORDER_PLACED
        retrieved = repo.get_by_order_id("existing-order")
        assert retrieved.link_status == LinkStatus.ORDER_PLACED


class TestLinkStatusEnum:
    """Test LinkStatus enum values."""

    def test_all_statuses(self):
        assert LinkStatus.PENDING.value == "PENDING"
        assert LinkStatus.ORDER_PLACED.value == "ORDER_PLACED"
        assert LinkStatus.ORDER_FILLED.value == "ORDER_FILLED"
        assert LinkStatus.ORDER_REJECTED.value == "ORDER_REJECTED"
        assert LinkStatus.ORPHANED.value == "ORPHANED"
