"""
Tests for LighterReconciliationWorker — uses AsyncMock stubs, in-memory DuckDB.

Tests:
  - reconcile_open_positions (Mode A):
      stuck_open resolution
      missing_open insertion
      both simultaneously
      gateway error → result.success=False
  - reconcile_history (Mode B):
      single page of orders
      pagination (multi-page)
      empty results
  - reconciliation_log entry written for each run
"""

from __future__ import annotations

import time
import uuid
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import duckdb
import pytest
import pytest_asyncio

from reconciliation.lighter_reconciliation_worker import LighterReconciliationWorker
from reconciliation.models import (
    ExitType,
    LighterClosedOrder,
    LighterPosition,
    TradeStatus,
)
from reconciliation.trades_lighter_repository import (
    TradesLighterRepository,
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
    return TradesLighterRepository(conn)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _make_gateway_mock() -> AsyncMock:
    """Return an AsyncMock that satisfies LighterGatewayProtocol interface."""
    gw = AsyncMock()
    gw.get_open_position_ids = AsyncMock(return_value=set())
    gw.get_open_position_details = AsyncMock(return_value=None)
    gw.fetch_inactive_orders_page = AsyncMock(return_value=([], None))
    gw.get_closed_order_by_id = AsyncMock(return_value=None)
    return gw


def _make_position(order_id: str = "order_001") -> LighterPosition:
    return LighterPosition(
        order_id=order_id,
        symbol="BTC/USDC",
        side="LONG",
        entry_price=95_000.0,
        size_base=0.01,
        ts_open_ms=_now_ms() - 3600_000,
    )


def _make_closed_order(order_id: str = "order_001") -> LighterClosedOrder:
    return LighterClosedOrder(
        order_id=order_id,
        symbol="BTC/USDC",
        side="LONG",
        entry_price=95_000.0,
        exit_price=95_675.0,
        size_base=0.01,
        pnl_usdt=6.75,
        fee_usdt=0.19,
        ts_open_ms=_now_ms() - 7200_000,
        ts_close_ms=_now_ms() - 60_000,
        order_type="take-profit-limit",
    )


def _make_worker(gateway, repo) -> LighterReconciliationWorker:
    return LighterReconciliationWorker(gateway=gateway, repo=repo)


# ── Mode A: reconcile_open_positions ─────────────────────────────────────────

class TestReconcileOpenPositions:

    @pytest.mark.asyncio
    async def test_no_positions_no_change(self, repo):
        gw = _make_gateway_mock()
        gw.get_open_position_ids.return_value = set()
        worker = _make_worker(gw, repo)

        result = await worker.reconcile_open_positions()

        assert result.success is True
        assert result.stuck_resolved == 0
        assert result.missing_resolved == 0

    @pytest.mark.asyncio
    async def test_stuck_open_resolved(self, conn, repo):
        """Trade in DuckDB as OPEN but Lighter says no open positions → mark CLOSED."""
        from reconciliation.models import LighterTradeMirror
        trade = LighterTradeMirror(
            trade_id="stuck_001",
            symbol="BTC/USDC",
            side="LONG",
            ts_open_ms=_now_ms() - 7200_000,
            entry_price=95_000.0,
            size_base=0.01,
            status=TradeStatus.OPEN,
        )
        repo.upsert_trade(trade)

        gw = _make_gateway_mock()
        gw.get_open_position_ids.return_value = set()  # Lighter sees no open pos
        gw.get_closed_order_by_id.return_value = _make_closed_order("stuck_001")

        worker = _make_worker(gw, repo)
        result = await worker.reconcile_open_positions()

        assert result.stuck_resolved == 1
        assert result.success is True

        fetched = repo.get_trade("stuck_001")
        assert fetched.status == TradeStatus.CLOSED
        assert fetched.exit_type == ExitType.TP

    @pytest.mark.asyncio
    async def test_missing_open_inserted(self, repo):
        """Trade in Lighter as open but not in DuckDB → insert."""
        gw = _make_gateway_mock()
        gw.get_open_position_ids.return_value = {"new_pos_001"}
        gw.get_open_position_details.return_value = _make_position("new_pos_001")

        worker = _make_worker(gw, repo)
        result = await worker.reconcile_open_positions()

        assert result.missing_resolved == 1
        assert result.upserted == 1

        fetched = repo.get_trade("new_pos_001")
        assert fetched is not None
        assert fetched.status == TradeStatus.OPEN

    @pytest.mark.asyncio
    async def test_stuck_and_missing_simultaneously(self, repo):
        """One stuck OPEN + one new missing OPEN in the same sweep."""
        from reconciliation.models import LighterTradeMirror
        repo.upsert_trade(
            LighterTradeMirror(
                trade_id="stuck_002",
                symbol="BTC/USDC",
                side="LONG",
                ts_open_ms=_now_ms() - 3600_000,
                entry_price=94_000.0,
                size_base=0.01,
                status=TradeStatus.OPEN,
            )
        )

        gw = _make_gateway_mock()
        gw.get_open_position_ids.return_value = {"new_open_002"}
        gw.get_open_position_details.return_value = _make_position("new_open_002")
        gw.get_closed_order_by_id.return_value = _make_closed_order("stuck_002")

        worker = _make_worker(gw, repo)
        result = await worker.reconcile_open_positions()

        assert result.stuck_resolved == 1
        assert result.missing_resolved == 1
        assert result.success is True

    @pytest.mark.asyncio
    async def test_gateway_error_marks_failure(self, repo):
        """If gateway throws, result.success is False and error captured."""
        gw = _make_gateway_mock()
        gw.get_open_position_ids.side_effect = RuntimeError("API unreachable")

        worker = _make_worker(gw, repo)
        result = await worker.reconcile_open_positions()

        assert result.success is False
        assert any("API unreachable" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_stuck_resolution_failure_marked_in_result(self, repo):
        """Closed order fetch returns None → error captured, not raised."""
        from reconciliation.models import LighterTradeMirror
        repo.upsert_trade(
            LighterTradeMirror(
                trade_id="stuck_no_data",
                symbol="BTC/USDC",
                side="SHORT",
                ts_open_ms=_now_ms() - 1800_000,
                entry_price=96_000.0,
                size_base=0.005,
                status=TradeStatus.OPEN,
            )
        )

        gw = _make_gateway_mock()
        gw.get_open_position_ids.return_value = set()
        gw.get_closed_order_by_id.return_value = None  # Lighter has no data

        worker = _make_worker(gw, repo)
        result = await worker.reconcile_open_positions()

        assert result.stuck_resolved == 0
        assert result.success is False  # error logged

    @pytest.mark.asyncio
    async def test_reconciliation_log_written(self, conn, repo):
        """Each run must write exactly one row to reconciliation_log."""
        gw = _make_gateway_mock()
        worker = _make_worker(gw, repo)
        await worker.reconcile_open_positions()

        count = conn.execute("SELECT COUNT(*) FROM reconciliation_log").fetchone()[0]
        assert count == 1

        row = conn.execute(
            "SELECT mode FROM reconciliation_log"
        ).fetchone()
        assert row[0] == "sweep"


# ── Mode B: reconcile_history ──────────────────────────────────────────────────

class TestReconcileHistory:

    @pytest.mark.asyncio
    async def test_empty_history(self, repo):
        gw = _make_gateway_mock()
        gw.fetch_inactive_orders_page.return_value = ([], None)

        worker = _make_worker(gw, repo)
        result = await worker.reconcile_history()

        assert result.success is True
        assert result.upserted == 0

    @pytest.mark.asyncio
    async def test_single_page_upserted(self, repo):
        orders = [
            _make_closed_order("hist_001"),
            _make_closed_order("hist_002"),
        ]
        gw = _make_gateway_mock()
        gw.fetch_inactive_orders_page.return_value = (orders, None)

        worker = _make_worker(gw, repo)
        result = await worker.reconcile_history()

        assert result.upserted == 2
        assert result.success is True
        assert repo.count("CLOSED") == 2

    @pytest.mark.asyncio
    async def test_multi_page_pagination(self, repo):
        """Paginator must follow next_cursor until exhausted."""
        page1 = [_make_closed_order(f"h_{i:03d}") for i in range(3)]
        page2 = [_make_closed_order(f"h_{i:03d}") for i in range(3, 5)]

        call_count = 0

        async def fake_page(limit=100, cursor=None, between_timestamps=None):
            nonlocal call_count
            call_count += 1
            if cursor is None:
                return (page1, "cursor_abc")
            else:
                return (page2, None)

        gw = _make_gateway_mock()
        gw.fetch_inactive_orders_page = fake_page

        worker = _make_worker(gw, repo)
        result = await worker.reconcile_history()

        assert result.upserted == 5
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_history_idempotent(self, repo):
        """Running reconcile_history twice → still only 1 row per trade_id."""
        orders = [_make_closed_order("idem_001")]
        gw = _make_gateway_mock()
        gw.fetch_inactive_orders_page.return_value = (orders, None)

        worker = _make_worker(gw, repo)
        await worker.reconcile_history()
        await worker.reconcile_history()

        assert repo.count() == 1

    @pytest.mark.asyncio
    async def test_history_log_written(self, conn, repo):
        gw = _make_gateway_mock()
        worker = _make_worker(gw, repo)
        await worker.reconcile_history()

        row = conn.execute(
            "SELECT mode FROM reconciliation_log"
        ).fetchone()
        assert row[0] == "history"

    @pytest.mark.asyncio
    async def test_history_gateway_error(self, repo):
        gw = _make_gateway_mock()
        gw.fetch_inactive_orders_page.side_effect = ConnectionError("network down")

        worker = _make_worker(gw, repo)
        result = await worker.reconcile_history()

        assert result.success is False
        assert any("network down" in e for e in result.errors)
