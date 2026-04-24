"""Domain model for signal_snapshots (Tier 0c)."""
from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class LinkStatus(str, Enum):
    PENDING = "PENDING"
    ORDER_PLACED = "ORDER_PLACED"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORPHANED = "ORPHANED"


@dataclass
class SignalSnapshot:
    ts_signal_ms: int
    candle_open_ts: int
    ts_order_placed_ms: Optional[int] = None
    intended_side: str = "LONG"
    intended_size_usdt: float = 0.0
    intended_entry_price: Optional[float] = None
    intended_sl_price: Optional[float] = None
    intended_tp_price: Optional[float] = None
    l1_regime: Optional[str] = None
    l1_changepoint_prob: Optional[float] = None
    l2_ema_vote: Optional[float] = None
    l2_aligned: Optional[bool] = None
    l3_prob_bear: Optional[float] = None
    l3_prob_neutral: Optional[float] = None
    l3_prob_bull: Optional[float] = None
    l3_class: Optional[str] = None
    l4_vol_regime: Optional[str] = None
    l4_current_vol: Optional[float] = None
    l4_long_run_vol: Optional[float] = None
    atr_at_signal: Optional[float] = None
    funding_at_signal: Optional[float] = None
    oi_at_signal: Optional[float] = None
    cvd_at_signal: Optional[float] = None
    htf_zscore_at_signal: Optional[float] = None
    signal_verdict: Optional[str] = None
    signal_conviction: Optional[float] = None
    lighter_order_id: Optional[str] = None
    link_status: LinkStatus = LinkStatus.PENDING
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))

    @classmethod
    def create(cls, candle_open_ts: int, intended_side: str, intended_size_usdt: float, **kwargs) -> "SignalSnapshot":
        return cls(
            ts_signal_ms=int(time.time() * 1000),
            candle_open_ts=candle_open_ts,
            intended_side=intended_side,
            intended_size_usdt=intended_size_usdt,
            **kwargs,
        )
