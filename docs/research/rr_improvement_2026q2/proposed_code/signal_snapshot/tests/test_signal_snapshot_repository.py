"""
Tests for SignalSnapshotRepository — uses in-memory DuckDB (:memory:).

Covers:
  - insert(): new snapshot, duplicate PK raises
  - update_linkage(): link_status, lighter_order_id, ts_order_placed_ms
  - mark_orphaned(): batch orphan detection
  - get_by_order_id(): fetch by Lighter order id
  - get_by_snapshot_id(): fetch by PK
  - count(): total and filtered
  - Field integrity: candle_open_ts stores candle timestamp, not time.time()
"""

import time
import uuid

import duckdb
import pytest

from signal_snapshot.models import LinkStatus, SignalSnapshot
from signal_snapshot.signal_snapshot_repository import (
    SignalSnapshotRepository,
    ensure_schema,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def conn():
    c = duckdb.connect(":memory:")
    ensure_schema(c)
    yield c
    c.close()


@pytest.fixture
def repo(conn):
    return SignalSnapshotRepository(conn)


def _now_ms() -> int:
    return int(time.time() * 1000)


CANDLE_TS = 1_714_000_000_000   # fixed candle open timestamp (4H boundary)


def _make_snapshot(**kwargs) -> SignalSnapshot:
    defaults = dict(
        ts_signal_ms=_now_ms(),
        candle_open_ts=CANDLE_TS,
        intended_side="LONG",
        intended_size_usdt=500.0,
        l1_regime="BULL",
        l1_changepoint_prob=0.15,
        l2_ema_vote=0.8,
        l2_aligned=True,
        l3_prob_bull=0.72,
        l3_prob_neutral=0.20,
        l3_prob_bear=0.08,
        l3_class="BULL",
        l4_vol_regime="low",
        l4_current_vol=0.0012,
        l4_long_run_vol=0.0018,
        atr_at_signal=450.0,
        funding_at_signal=0.0001,
        oi_at_signal=3_200_000_000.0,
        cvd_at_signal=125_000.0,
        htf_zscore_at_signal=1.4,
        signal_verdict="STRONG BUY",
        signal_conviction=82.5,
        intended_sl_price=93_737.0,
        intended_tp_price=95_676.0,
    )
    defaults.update(kwargs)
    return SignalSnapshot(**defaults)


# ── insert ────────────────────────────────────────────────────────────────────

class TestInsert:
    def test_insert_returns_snapshot_id(self, repo):
        snap = _make_snapshot()
        returned_id = repo.insert(snap)
        assert returned_id == snap.snapshot_id

    def test_insert_persists_all_fields(self, conn, repo):
        snap = _make_snapshot()
        repo.insert(snap)

        row = conn.execute(
            "SELECT * FROM signal_snapshots WHERE snapshot_id = ?",
            [snap.snapshot_id],
        ).fetchone()
        assert row is not None

    def test_candle_open_ts_stored_correctly(self, conn, repo):
        """candle_open_ts must store the candle timestamp, NOT time.time()."""
        snap = _make_snapshot(candle_open_ts=CANDLE_TS)
        repo.insert(snap)

        stored = conn.execute(
            "SELECT candle_open_ts FROM signal_snapshots WHERE snapshot_id = ?",
            [snap.snapshot_id],
        ).fetchone()[0]
        assert stored == CANDLE_TS

    def test_duplicate_pk_raises(self, repo):
        snap = _make_snapshot()
        repo.insert(snap)
        with pytest.raises(Exception):
            repo.insert(snap)  # same snapshot_id → PK conflict

    def test_default_link_status_is_pending(self, conn, repo):
        snap = _make_snapshot()
        repo.insert(snap)

        status = conn.execute(
            "SELECT link_status FROM signal_snapshots WHERE snapshot_id = ?",
            [snap.snapshot_id],
        ).fetchone()[0]
        assert status == "PENDING"

    def test_multiple_inserts(self, repo):
        for _ in range(5):
            repo.insert(_make_snapshot())
        assert repo.count() == 5


# ── update_linkage ─────────────────────────────────────────────────────────────

class TestUpdateLinkage:
    def test_update_to_order_placed(self, conn, repo):
        snap = _make_snapshot()
        repo.insert(snap)
        now = _now_ms()

        repo.update_linkage(
            snapshot_id=snap.snapshot_id,
            link_status=LinkStatus.ORDER_PLACED,
            lighter_order_id="lighter_order_abc",
            ts_order_placed_ms=now,
        )

        row = conn.execute(
            "SELECT link_status, lighter_order_id, ts_order_placed_ms "
            "FROM signal_snapshots WHERE snapshot_id = ?",
            [snap.snapshot_id],
        ).fetchone()
        assert row[0] == "ORDER_PLACED"
        assert row[1] == "lighter_order_abc"
        assert row[2] == now

    def test_update_to_order_filled(self, repo):
        snap = _make_snapshot()
        repo.insert(snap)

        repo.update_linkage(snap.snapshot_id, LinkStatus.ORDER_PLACED, "order_x")
        repo.update_linkage(snap.snapshot_id, LinkStatus.ORDER_FILLED)

        fetched = repo.get_by_snapshot_id(snap.snapshot_id)
        assert fetched.link_status == LinkStatus.ORDER_FILLED
        assert fetched.lighter_order_id == "order_x"  # preserved by COALESCE

    def test_update_to_rejected(self, repo):
        snap = _make_snapshot()
        repo.insert(snap)
        repo.update_linkage(snap.snapshot_id, LinkStatus.ORDER_REJECTED)

        fetched = repo.get_by_snapshot_id(snap.snapshot_id)
        assert fetched.link_status == LinkStatus.ORDER_REJECTED

    def test_order_id_preserved_on_status_only_update(self, repo):
        """COALESCE: lighter_order_id not cleared when update_linkage passes None."""
        snap = _make_snapshot()
        repo.insert(snap)
        repo.update_linkage(snap.snapshot_id, LinkStatus.ORDER_PLACED, "keep_me")
        repo.update_linkage(snap.snapshot_id, LinkStatus.ORDER_FILLED, lighter_order_id=None)

        fetched = repo.get_by_snapshot_id(snap.snapshot_id)
        assert fetched.lighter_order_id == "keep_me"


# ── mark_orphaned ──────────────────────────────────────────────────────────────

class TestMarkOrphaned:
    def test_marks_old_placed_not_in_trades(self, conn, repo):
        """ORDER_PLACED older than threshold + order_id not in trades_lighter → ORPHANED."""
        old_ts = _now_ms() - 20 * 60 * 1000  # 20 minutes ago
        snap = _make_snapshot()
        repo.insert(snap)
        repo.update_linkage(
            snap.snapshot_id,
            LinkStatus.ORDER_PLACED,
            lighter_order_id="orphan_order",
            ts_order_placed_ms=old_ts,
        )

        threshold_ms = _now_ms() - 10 * 60 * 1000  # 10 min threshold
        count = repo.mark_orphaned(
            older_than_ms=threshold_ms,
            trades_lighter_ids=set(),  # no known filled trades
        )

        assert count == 1
        fetched = repo.get_by_snapshot_id(snap.snapshot_id)
        assert fetched.link_status == LinkStatus.ORPHANED

    def test_skips_recent_placed(self, repo):
        """Order placed recently (< threshold) should NOT be orphaned."""
        snap = _make_snapshot()
        repo.insert(snap)
        repo.update_linkage(
            snap.snapshot_id,
            LinkStatus.ORDER_PLACED,
            lighter_order_id="recent_order",
            ts_order_placed_ms=_now_ms() - 1_000,  # 1 second ago
        )

        threshold_ms = _now_ms() - 10 * 60 * 1000
        count = repo.mark_orphaned(threshold_ms, set())
        assert count == 0

    def test_skips_if_in_trades_lighter(self, repo):
        """If lighter_order_id is in trades_lighter_ids, do NOT mark orphan."""
        old_ts = _now_ms() - 30 * 60 * 1000
        snap = _make_snapshot()
        repo.insert(snap)
        repo.update_linkage(
            snap.snapshot_id,
            LinkStatus.ORDER_PLACED,
            lighter_order_id="filled_order_001",
            ts_order_placed_ms=old_ts,
        )

        threshold_ms = _now_ms() - 10 * 60 * 1000
        count = repo.mark_orphaned(
            threshold_ms,
            trades_lighter_ids={"filled_order_001"},  # this order IS filled
        )
        assert count == 0

    def test_only_marks_order_placed_status(self, repo):
        """PENDING and ORDER_FILLED snapshots should not be touched."""
        snap1 = _make_snapshot()
        snap2 = _make_snapshot()
        repo.insert(snap1)
        repo.insert(snap2)

        old_ts = _now_ms() - 30 * 60 * 1000
        # snap1: PENDING (default) with old ts_signal_ms — not order placed
        # snap2: FILLED
        repo.update_linkage(snap2.snapshot_id, LinkStatus.ORDER_FILLED, "fil_001")

        threshold_ms = _now_ms() - 10 * 60 * 1000
        count = repo.mark_orphaned(threshold_ms, set())
        assert count == 0  # neither PENDING nor FILLED should be orphaned


# ── get_by_order_id ────────────────────────────────────────────────────────────

class TestGetByOrderId:
    def test_returns_none_for_missing(self, repo):
        assert repo.get_by_order_id("does_not_exist") is None

    def test_returns_correct_snapshot(self, repo):
        snap = _make_snapshot()
        repo.insert(snap)
        repo.update_linkage(
            snap.snapshot_id,
            LinkStatus.ORDER_PLACED,
            lighter_order_id="target_order",
        )

        fetched = repo.get_by_order_id("target_order")
        assert fetched is not None
        assert fetched.snapshot_id == snap.snapshot_id
        assert fetched.l3_prob_bull == pytest.approx(0.72)

    def test_all_layer_fields_roundtrip(self, repo):
        snap = _make_snapshot(
            l1_regime="BEAR",
            l1_changepoint_prob=0.78,
            l2_ema_vote=-0.6,
            l2_aligned=False,
            l3_prob_bear=0.60,
            l3_class="BEAR",
            l4_vol_regime="high",
            htf_zscore_at_signal=-2.1,
        )
        repo.insert(snap)
        repo.update_linkage(snap.snapshot_id, LinkStatus.ORDER_PLACED, "order_bear_01")

        fetched = repo.get_by_order_id("order_bear_01")
        assert fetched.l1_regime == "BEAR"
        assert fetched.l1_changepoint_prob == pytest.approx(0.78)
        assert fetched.l2_aligned is False
        assert fetched.l4_vol_regime == "high"
        assert fetched.htf_zscore_at_signal == pytest.approx(-2.1)


# ── get_by_snapshot_id ─────────────────────────────────────────────────────────

class TestGetBySnapshotId:
    def test_returns_none_for_missing(self, repo):
        assert repo.get_by_snapshot_id("nonexistent-uuid") is None

    def test_roundtrip_all_nullable_fields_as_none(self, repo):
        """Insert a minimal snapshot with all optional fields as None."""
        snap = SignalSnapshot(
            ts_signal_ms=_now_ms(),
            candle_open_ts=CANDLE_TS,
            intended_side="SHORT",
            intended_size_usdt=200.0,
        )
        repo.insert(snap)
        fetched = repo.get_by_snapshot_id(snap.snapshot_id)

        assert fetched.l1_regime is None
        assert fetched.l3_prob_bull is None
        assert fetched.lighter_order_id is None
        assert fetched.link_status == LinkStatus.PENDING


# ── count ──────────────────────────────────────────────────────────────────────

class TestCount:
    def test_empty(self, repo):
        assert repo.count() == 0

    def test_total_count(self, repo):
        for _ in range(4):
            repo.insert(_make_snapshot())
        assert repo.count() == 4

    def test_count_by_link_status(self, repo):
        s1 = _make_snapshot()
        s2 = _make_snapshot()
        s3 = _make_snapshot()
        repo.insert(s1)
        repo.insert(s2)
        repo.insert(s3)
        repo.update_linkage(s1.snapshot_id, LinkStatus.ORDER_PLACED, "o1")
        repo.update_linkage(s2.snapshot_id, LinkStatus.ORDER_PLACED, "o2")

        assert repo.count("PENDING") == 1
        assert repo.count("ORDER_PLACED") == 2
