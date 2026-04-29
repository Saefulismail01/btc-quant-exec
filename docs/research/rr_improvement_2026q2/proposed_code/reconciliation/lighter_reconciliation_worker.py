"""
Lighter Reconciliation Worker — async background task (Tier 0b).

Two modes (DESIGN_DOC v0.3 §4.0.B.2):
  Mode A (sweep):   Every 60–120 s — compare DuckDB OPEN set vs Lighter open positions.
                    Resolves "stuck OPEN" (closed at Lighter, still OPEN in DuckDB)
                    and "missing OPEN" (open at Lighter, not yet in DuckDB).
  Mode B (history): Every ~1 hour — fetch last 24h of inactive orders and upsert.
                    Idempotent; provides coverage for missed callbacks.

IMPORTANT — no `import lighter`.  The `LighterGatewayProtocol` is a structural
Protocol (PEP 544); production code will pass a thin adapter wrapping the real
aiohttp gateway; tests pass an AsyncMock / stub that satisfies the same Protocol.

Rate limit awareness (from findings/H §H.3):
  accountInactiveOrders: weight 100   → poll ≤ 240 times/min on premium tier
  account (open pos):    weight ~300  → poll ≤ 80 times/min on premium tier
  Worker uses conservative 2-call budget per sweep cycle. Exponential backoff on 429.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Protocol, runtime_checkable

from .exit_type_inference import infer_exit_type
from .models import (
    LighterClosedOrder,
    LighterPosition,
    ReconcileMode,
    ReconciliationResult,
)
from .trades_lighter_repository import TradesLighterRepository

logger = logging.getLogger(__name__)


# ── Gateway Protocol (structural typing — no Lighter SDK import) ──────────────

@runtime_checkable
class LighterGatewayProtocol(Protocol):
    """
    Minimal interface the reconciliation worker requires from a Lighter gateway.

    Production impl: thin async wrapper around LighterExecutionGateway + aiohttp.
    Test impl: AsyncMock / dataclass stub returned by fixture.

    Rate limit notes (do NOT call accountInactiveOrders > 14 times/minute on
    standard tier — weight 100 × 14 = 1400 >> 60/min unauthenticated limit).
    """

    async def get_open_position_ids(self) -> set[str]:
        """
        Return set of Lighter order_ids that correspond to currently open positions.
        Source: GET /account → filter positions where size != 0.
        """
        ...

    async def get_open_position_details(self, order_id: str) -> LighterPosition:
        """
        Fetch detail of a single open position by its entry order_id.
        Source: GET /account → filter by order_id / market context.
        """
        ...

    async def fetch_inactive_orders_page(
        self,
        limit: int = 100,
        cursor: str | None = None,
        between_timestamps: tuple[int, int] | None = None,
    ) -> tuple[list[LighterClosedOrder], str | None]:
        """
        Fetch a page of closed/inactive orders.
        Source: GET /accountInactiveOrders (weight 100).

        Returns:
            (orders, next_cursor) — next_cursor is None when pagination exhausted.
        """
        ...

    async def get_closed_order_by_id(self, order_id: str) -> LighterClosedOrder | None:
        """
        Fetch one closed order by its Lighter order_id.
        Used during stuck-OPEN resolution to get precise exit data.
        Source: accountInactiveOrders filtered client-side (no direct by-id REST).
        """
        ...


# ── Worker ────────────────────────────────────────────────────────────────────

class LighterReconciliationWorker:
    """
    Async reconciliation worker.

    Injection points (constructor):
      gateway: LighterGatewayProtocol  — production or mock
      repo:    TradesLighterRepository — DuckDB repository

    Usage (production):
        worker = LighterReconciliationWorker(gateway=adapter, repo=repo)
        await asyncio.gather(
            worker.run_sweep_loop(interval_s=90),
            worker.run_history_loop(interval_s=3600),
        )

    Usage (test — single run):
        result = await worker.reconcile_open_positions()
    """

    def __init__(
        self,
        gateway: LighterGatewayProtocol,
        repo: TradesLighterRepository,
        *,
        sweep_interval_s: float = 90.0,
        history_interval_s: float = 3600.0,
        backoff_base_s: float = 2.0,
        max_backoff_s: float = 120.0,
        history_window_ms: int = 24 * 3600 * 1000,
    ) -> None:
        self._gateway = gateway
        self._repo = repo
        self._sweep_interval_s = sweep_interval_s
        self._history_interval_s = history_interval_s
        self._backoff_base_s = backoff_base_s
        self._max_backoff_s = max_backoff_s
        self._history_window_ms = history_window_ms

    # ── Public single-run methods (also used in tests) ─────────────────────────

    async def reconcile_open_positions(self) -> ReconciliationResult:
        """
        Mode A — compare DuckDB OPEN set vs Lighter open positions.

        Resolves:
          stuck_open:   in DuckDB as OPEN, not in Lighter → mark CLOSED
          missing_open: in Lighter, not in DuckDB → insert as OPEN

        Returns ReconciliationResult (also written to reconciliation_log).
        """
        t_start = _now_ms()
        result = ReconciliationResult(
            log_id=str(uuid.uuid4()),
            mode=ReconcileMode.SWEEP,
            ts_ms=t_start,
        )

        try:
            # Step 1 — current state from both sides
            duckdb_open: set[str] = self._repo.get_open_trade_ids()
            lighter_open: set[str] = await self._gateway.get_open_position_ids()
            result.api_calls_count += 1

            # Step 2 — stuck OPEN (DuckDB says OPEN, Lighter says closed)
            stuck = duckdb_open - lighter_open
            for trade_id in stuck:
                await self._resolve_stuck_open(trade_id, result)

            # Step 3 — missing OPEN (Lighter has open pos, DuckDB doesn't know)
            missing = lighter_open - duckdb_open
            for order_id in missing:
                await self._insert_missing_open(order_id, result)

        except Exception as exc:
            result.mark_error(f"sweep error: {exc}")
            logger.error(
                "[ReconciliationWorker] reconcile_open_positions failed",
                extra={"error": str(exc)},
                exc_info=True,
            )
        finally:
            result.duration_ms = _now_ms() - t_start
            self._write_log(result)

        return result

    async def reconcile_history(self) -> ReconciliationResult:
        """
        Mode B — backfill last N hours from Lighter inactive orders.

        Idempotent: upsert on trade_id. Safe to run multiple times.

        Returns ReconciliationResult (also written to reconciliation_log).
        """
        t_start = _now_ms()
        result = ReconciliationResult(
            log_id=str(uuid.uuid4()),
            mode=ReconcileMode.HISTORY,
            ts_ms=t_start,
        )

        now_ms = t_start
        window_start_ms = now_ms - self._history_window_ms
        cursor: str | None = None

        try:
            while True:
                orders, next_cursor = await self._gateway.fetch_inactive_orders_page(
                    limit=100,
                    cursor=cursor,
                    between_timestamps=(window_start_ms, now_ms),
                )
                result.api_calls_count += 1

                for order in orders:
                    exit_type = infer_exit_type(
                        order_type=order.order_type,
                        exit_price=order.exit_price,
                    )
                    from .models import LighterTradeMirror, TradeStatus
                    mirror = LighterTradeMirror(
                        trade_id=order.order_id,
                        symbol=order.symbol,
                        side=order.side,
                        ts_open_ms=order.ts_open_ms,
                        ts_close_ms=order.ts_close_ms,
                        entry_price=order.entry_price,
                        exit_price=order.exit_price,
                        size_base=order.size_base,
                        pnl_usdt=order.pnl_usdt,
                        fee_usdt=order.fee_usdt,
                        status=TradeStatus.CLOSED,
                        exit_type=exit_type,
                        source_checksum=order.raw_checksum,
                    )
                    self._repo.upsert_trade(mirror)
                    result.upserted += 1

                if next_cursor is None:
                    break
                cursor = next_cursor

        except Exception as exc:
            result.mark_error(f"history error: {exc}")
            logger.error(
                "[ReconciliationWorker] reconcile_history failed",
                extra={"error": str(exc)},
                exc_info=True,
            )
        finally:
            result.duration_ms = _now_ms() - t_start
            self._write_log(result)

        return result

    # ── Continuous loop helpers (production use) ───────────────────────────────

    async def run_sweep_loop(self, interval_s: float | None = None) -> None:
        """
        Continuously run Mode A sweep. Intended to be wrapped in asyncio.gather().
        Applies exponential backoff on consecutive failures.
        """
        interval_s = interval_s or self._sweep_interval_s
        consecutive_failures = 0
        while True:
            result = await self.reconcile_open_positions()
            if result.success:
                consecutive_failures = 0
                await asyncio.sleep(interval_s)
            else:
                consecutive_failures += 1
                backoff = min(
                    self._backoff_base_s * (2 ** consecutive_failures),
                    self._max_backoff_s,
                )
                logger.warning(
                    "[ReconciliationWorker] sweep failed, backoff",
                    extra={"consecutive": consecutive_failures, "backoff_s": backoff},
                )
                await asyncio.sleep(backoff)

    async def run_history_loop(self, interval_s: float | None = None) -> None:
        """Continuously run Mode B history backfill."""
        interval_s = interval_s or self._history_interval_s
        consecutive_failures = 0
        while True:
            result = await self.reconcile_history()
            if result.success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
            await asyncio.sleep(interval_s)

    # ── Private helpers ────────────────────────────────────────────────────────

    async def _resolve_stuck_open(
        self, trade_id: str, result: ReconciliationResult
    ) -> None:
        """Fetch closed order details and mark DuckDB trade as CLOSED."""
        try:
            closed = await self._gateway.get_closed_order_by_id(trade_id)
            result.api_calls_count += 1

            if closed is None:
                result.mark_error(
                    f"stuck_open {trade_id}: could not fetch closed details"
                )
                logger.error(
                    "[ReconciliationWorker] stuck_open resolution failed: no data",
                    extra={"trade_id": trade_id},
                )
                return

            exit_type = infer_exit_type(
                order_type=closed.order_type,
                exit_price=closed.exit_price,
            )
            self._repo.mark_closed(trade_id, closed, exit_type)
            result.stuck_resolved += 1
            logger.warning(
                "[ReconciliationWorker] resolved stuck_open",
                extra={
                    "trade_id": trade_id,
                    "exit_type": exit_type.value,
                    "pnl_usdt": closed.pnl_usdt,
                },
            )
        except Exception as exc:
            result.mark_error(f"stuck_open {trade_id}: {exc}")
            logger.error(
                "[ReconciliationWorker] _resolve_stuck_open error",
                extra={"trade_id": trade_id, "error": str(exc)},
                exc_info=True,
            )

    async def _insert_missing_open(
        self, order_id: str, result: ReconciliationResult
    ) -> None:
        """Insert a position that Lighter knows is open but DuckDB doesn't have."""
        try:
            pos = await self._gateway.get_open_position_details(order_id)
            result.api_calls_count += 1
            self._repo.upsert_from_open_position(pos)
            result.missing_resolved += 1
            result.upserted += 1
            logger.warning(
                "[ReconciliationWorker] inserted missing_open",
                extra={"order_id": order_id},
            )
        except Exception as exc:
            result.mark_error(f"missing_open {order_id}: {exc}")
            logger.error(
                "[ReconciliationWorker] _insert_missing_open error",
                extra={"order_id": order_id, "error": str(exc)},
                exc_info=True,
            )

    def _write_log(self, result: ReconciliationResult) -> None:
        try:
            self._repo.write_reconciliation_log(
                log_id=result.log_id,
                mode=result.mode.value,
                ts_ms=result.ts_ms,
                stuck_resolved=result.stuck_resolved,
                missing_resolved=result.missing_resolved,
                upserted=result.upserted,
                snapshots_inserted=result.snapshots_inserted,
                duration_ms=result.duration_ms,
                api_calls_count=result.api_calls_count,
                api_throttled_count=result.api_throttled_count,
                errors=result.errors,
                success=result.success,
            )
        except Exception as exc:
            logger.error(
                "[ReconciliationWorker] failed to write reconciliation_log",
                extra={"log_id": result.log_id, "error": str(exc)},
                exc_info=True,
            )


# ── Utility ───────────────────────────────────────────────────────────────────

def _now_ms() -> int:
    return int(time.time() * 1000)
