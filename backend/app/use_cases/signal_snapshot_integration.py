"""Signal Snapshot Integration — Tier 0c wiring to signal_service and position_manager.

This module provides helper functions to:
1. Create signal snapshots when signals are generated
2. Update linkage when orders are placed/filled
3. Fix the candle_open_ts bug (was using time.time() instead of candle timestamp)
"""
from __future__ import annotations
import logging
import os
from typing import Optional
import duckdb
from app.adapters.repositories.signal_snapshot import SignalSnapshot, SignalSnapshotRepository, LinkStatus
from app.schemas.signal import SignalResponse

logger = logging.getLogger(__name__)


class SignalSnapshotIntegration:
    """
    Integration helper for signal snapshots.
    
    Usage:
        # In signal_service.py after generating signal:
        snapshot_id = SignalSnapshotIntegration.create_snapshot(signal, candle_open_ts, ...)
        
        # In position_manager.py after placing order:
        SignalSnapshotIntegration.update_linkage(snapshot_id, order_id, "ORDER_PLACED")
    """

    _instance: Optional["SignalSnapshotIntegration"] = None

    def __new__(cls) -> "SignalSnapshotIntegration":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._db_path = os.getenv("DB_PATH", "backend/app/infrastructure/database/btc-quant.db")
        self._conn: Optional[duckdb.DuckDBPyConnection] = None
        self._repo: Optional[SignalSnapshotRepository] = None
        self._initialized = True

    def _ensure_connection(self) -> SignalSnapshotRepository:
        """Lazy connection to avoid DB connection at import time."""
        if self._conn is None:
            self._conn = duckdb.connect(self._db_path)
            from app.adapters.repositories.signal_snapshot.signal_snapshot_repository import ensure_schema
            ensure_schema(self._conn)
            self._repo = SignalSnapshotRepository(self._conn)
        return self._repo

    @classmethod
    def create_snapshot(
        cls,
        signal: SignalResponse,
        candle_open_ts: int,
        intended_side: str,
        intended_size_usdt: float,
        intended_entry_price: Optional[float] = None,
        intended_sl_price: Optional[float] = None,
        intended_tp_price: Optional[float] = None,
        l1_regime: Optional[str] = None,
        l1_changepoint_prob: Optional[float] = None,
        l2_ema_vote: Optional[float] = None,
        l2_aligned: Optional[bool] = None,
        l3_prob_bear: Optional[float] = None,
        l3_prob_neutral: Optional[float] = None,
        l3_prob_bull: Optional[float] = None,
        l3_class: Optional[str] = None,
        l4_vol_regime: Optional[str] = None,
        l4_current_vol: Optional[float] = None,
        l4_long_run_vol: Optional[float] = None,
        atr_at_signal: Optional[float] = None,
        funding_at_signal: Optional[float] = None,
        oi_at_signal: Optional[float] = None,
        cvd_at_signal: Optional[float] = None,
        htf_zscore_at_signal: Optional[float] = None,
    ) -> str:
        """
        Create a signal snapshot when signal is generated.
        
        Returns snapshot_id to be passed downstream to position_manager.
        """
        instance = cls()
        repo = instance._ensure_connection()

        snapshot = SignalSnapshot.create(
            candle_open_ts=candle_open_ts,
            intended_side=intended_side,
            intended_size_usdt=intended_size_usdt,
            intended_entry_price=intended_entry_price,
            intended_sl_price=intended_sl_price,
            intended_tp_price=intended_tp_price,
            l1_regime=l1_regime,
            l1_changepoint_prob=l1_changepoint_prob,
            l2_ema_vote=l2_ema_vote,
            l2_aligned=l2_aligned,
            l3_prob_bear=l3_prob_bear,
            l3_prob_neutral=l3_prob_neutral,
            l3_prob_bull=l3_prob_bull,
            l3_class=l3_class,
            l4_vol_regime=l4_vol_regime,
            l4_current_vol=l4_current_vol,
            l4_long_run_vol=l4_long_run_vol,
            atr_at_signal=atr_at_signal,
            funding_at_signal=funding_at_signal,
            oi_at_signal=oi_at_signal,
            cvd_at_signal=cvd_at_signal,
            htf_zscore_at_signal=htf_zscore_at_signal,
            signal_verdict=signal.confluence.verdict if signal.confluence else None,
            signal_conviction=signal.confluence.conviction_pct if signal.confluence else None,
        )

        try:
            snapshot_id = repo.insert(snapshot)
            logger.info("[SignalSnapshotIntegration] created snapshot", extra={"snapshot_id": snapshot_id})
            return snapshot_id
        except Exception as exc:
            logger.error("[SignalSnapshotIntegration] failed to create snapshot", extra={"error": str(exc)})
            raise

    @classmethod
    def update_linkage(
        cls,
        snapshot_id: Optional[str],
        lighter_order_id: str,
        link_status: str,
        ts_order_placed_ms: Optional[int] = None,
    ) -> None:
        """
        Update snapshot linkage after order placement.
        
        Called by position_manager after successfully placing order to Lighter.
        """
        if snapshot_id is None:
            logger.debug("[SignalSnapshotIntegration] no snapshot_id provided, skipping linkage update")
            return

        instance = cls()
        repo = instance._ensure_connection()

        try:
            status = LinkStatus(link_status)
            repo.update_linkage(
                snapshot_id=snapshot_id,
                link_status=status,
                lighter_order_id=lighter_order_id,
                ts_order_placed_ms=ts_order_placed_ms,
            )
            logger.info(
                "[SignalSnapshotIntegration] updated linkage",
                extra={"snapshot_id": snapshot_id, "order_id": lighter_order_id, "status": link_status},
            )
        except Exception as exc:
            logger.error("[SignalSnapshotIntegration] failed to update linkage", extra={"snapshot_id": snapshot_id, "error": str(exc)})
            # Don't raise - linkage update failure shouldn't break trade execution

    def close(self) -> None:
        """Close DB connection. Call on shutdown."""
        if self._conn:
            self._conn.close()
            self._conn = None
            self._repo = None
            SignalSnapshotIntegration._instance = None
