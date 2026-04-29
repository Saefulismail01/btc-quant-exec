"""
Domain model for signal_snapshots (Tier 0c).

Schema aligned with DESIGN_DOC v0.3 §4.0.C.1.

Key design decisions:
  - Write-once: all fields except linkage (lighter_order_id, link_status,
    ts_order_placed_ms) are immutable after insert.
  - candle_open_ts is the timestamp of the 4H candle that triggered the signal
    (FIX for bug: position_manager.py:922 used time.time() instead).
  - Explicit columns (not JSON) for query performance on DuckDB OLAP aggregations.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Enums ─────────────────────────────────────────────────────────────────────

class LinkStatus(str, Enum):
    PENDING        = "PENDING"
    ORDER_PLACED   = "ORDER_PLACED"
    ORDER_FILLED   = "ORDER_FILLED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORPHANED       = "ORPHANED"


# ── Main model ────────────────────────────────────────────────────────────────

@dataclass
class SignalSnapshot:
    """
    Immutable signal context captured at the moment a signal is generated.

    Fields named to match signal_snapshots table columns exactly (§4.0.C.1).

    Usage:
        snapshot = SignalSnapshot.create(
            candle_open_ts=int(df.iloc[-1].timestamp),   # candle timestamp, not time.time()
            intended_side="LONG",
            intended_size_usdt=500.0,
            l1_regime="BULL",
            l3_prob_bull=0.82,
            ...
        )
        snapshot_id = repo.insert(snapshot)
    """

    # Timing
    ts_signal_ms:           int             # when signal was generated
    candle_open_ts:         int             # 4H candle that triggered signal (FIXED)
    ts_order_placed_ms:     Optional[int]   = None  # filled after order sent

    # Intent
    intended_side:          str             = "LONG"
    intended_size_usdt:     float           = 0.0
    intended_entry_price:   Optional[float] = None
    intended_sl_price:      Optional[float] = None
    intended_tp_price:      Optional[float] = None

    # Layer 1 — Bayesian Changepoint Detection (BOCPD)
    l1_regime:              Optional[str]   = None  # regime label
    l1_changepoint_prob:    Optional[float] = None  # 0..1

    # Layer 2 — Technical (EMA structure)
    l2_ema_vote:            Optional[float] = None  # [-1, +1]
    l2_aligned:             Optional[bool]  = None

    # Layer 3 — MLP classifier (3-class)
    l3_prob_bear:           Optional[float] = None
    l3_prob_neutral:        Optional[float] = None
    l3_prob_bull:           Optional[float] = None
    l3_class:               Optional[str]   = None  # "BULL" | "BEAR" | "NEUTRAL"

    # Layer 4 — Volatility (Heston-style)
    l4_vol_regime:          Optional[str]   = None  # "low" | "mid" | "high"
    l4_current_vol:         Optional[float] = None
    l4_long_run_vol:        Optional[float] = None

    # Market context at signal
    atr_at_signal:          Optional[float] = None
    funding_at_signal:      Optional[float] = None  # decimal e.g. 0.0001
    oi_at_signal:           Optional[float] = None
    cvd_at_signal:          Optional[float] = None
    htf_zscore_at_signal:   Optional[float] = None  # (close - ema50_4h) / atr14_4h

    # Aggregate (continuity with live_trades)
    signal_verdict:         Optional[str]   = None
    signal_conviction:      Optional[float] = None

    # Linkage — updated after order placement / fill detection
    lighter_order_id:       Optional[str]   = None
    link_status:            LinkStatus       = LinkStatus.PENDING

    # PK — auto-generated UUID
    snapshot_id:            str              = field(default_factory=lambda: str(uuid.uuid4()))
    created_at_ms:          int              = field(default_factory=lambda: int(time.time() * 1000))

    @classmethod
    def create(
        cls,
        candle_open_ts: int,
        intended_side: str,
        intended_size_usdt: float,
        **kwargs,
    ) -> "SignalSnapshot":
        """
        Factory that auto-fills ts_signal_ms from now.
        All other fields passed as kwargs.
        """
        return cls(
            ts_signal_ms=int(time.time() * 1000),
            candle_open_ts=candle_open_ts,
            intended_side=intended_side,
            intended_size_usdt=intended_size_usdt,
            **kwargs,
        )
