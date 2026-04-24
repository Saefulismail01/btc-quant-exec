"""Reconciliation service — wires LighterReconciliationWorker to the app (Tier 0b)."""
from __future__ import annotations
import asyncio
import logging
import os
from typing import Optional
import duckdb
from backend.app.adapters.repositories.reconciliation import (
    LighterReconciliationWorker,
    TradesLighterRepository,
    LighterGatewayProtocol,
)
from backend.app.adapters.repositories.reconciliation.lighter_gateway_adapter import LighterGatewayAdapter

logger = logging.getLogger(__name__)


class ReconciliationService:
    """
    Service that manages the reconciliation worker lifecycle.
    
    Usage:
        service = ReconciliationService(gateway, db_path)
        await service.start()  # Starts background loops
        ...
        await service.stop()   # Graceful shutdown
    """

    def __init__(
        self,
        lighter_gateway: object,
        db_path: Optional[str] = None,
        sweep_interval_s: float = 90.0,
        history_interval_s: float = 3600.0,
    ) -> None:
        """
        Args:
            lighter_gateway: LighterExecutionGateway instance
            db_path: Path to DuckDB file (defaults to env DB_PATH)
            sweep_interval_s: Interval between open position sweeps
            history_interval_s: Interval between history backfills
        """
        self._db_path = db_path or os.getenv("DB_PATH", "backend/app/infrastructure/database/btc-quant.db")
        self._conn = duckdb.connect(self._db_path)
        self._repo = TradesLighterRepository(self._conn)
        
        adapter = LighterGatewayAdapter(lighter_gateway)
        self._worker = LighterReconciliationWorker(
            gateway=adapter,
            repo=self._repo,
            sweep_interval_s=sweep_interval_s,
            history_interval_s=history_interval_s,
        )
        self._tasks: list[asyncio.Task] = []
        self._running = False

    async def start(self) -> None:
        """Start reconciliation background loops."""
        if self._running:
            logger.warning("[ReconciliationService] already running")
            return
        
        logger.info("[ReconciliationService] starting")
        self._tasks = [
            asyncio.create_task(self._worker.run_sweep_loop()),
            asyncio.create_task(self._worker.run_history_loop()),
        ]
        self._running = True

    async def stop(self) -> None:
        """Stop reconciliation background loops."""
        if not self._running:
            return
        
        logger.info("[ReconciliationService] stopping")
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks = []
        self._running = False
        self._conn.close()
        logger.info("[ReconciliationService] stopped")

    async def run_once(self) -> None:
        """Run single reconciliation sweep (for manual trigger/testing)."""
        result = await self._worker.reconcile_open_positions()
        logger.info("[ReconciliationService] single sweep completed", extra={
            "stuck_resolved": result.stuck_resolved,
            "missing_resolved": result.missing_resolved,
            "success": result.success,
        })
