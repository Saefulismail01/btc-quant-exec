"""
Domain models for the reconciliation pipeline (Tier 0b).

All models are plain dataclasses — no ORM, no Lighter SDK import.
The gateway abstraction uses Protocol (structural subtyping) so that
production code and test mocks are interchangeable without inheritance.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Enums ─────────────────────────────────────────────────────────────────────

class TradeStatus(str, Enum):
    OPEN   = "OPEN"
    CLOSED = "CLOSED"


class ExitType(str, Enum):
    TP      = "TP"
    SL      = "SL"
    TIME    = "TIME"
    MANUAL  = "MANUAL"
    UNKNOWN = "UNKNOWN"


class ReconcileMode(str, Enum):
    SWEEP   = "sweep"    # Mode A — open positions sweep (60-120s interval)
    HISTORY = "history"  # Mode B — 24h history backfill (1h interval)


# ── Core trade mirror ──────────────────────────────────────────────────────────

@dataclass
class LighterTradeMirror:
    """
    Row in `trades_lighter` table — mirror of a single Lighter order lifecycle.

    trade_id is the Lighter entry-market order_id (frozen decision #2 in DESIGN_DOC v0.3).
    All timestamps are Unix milliseconds UTC.
    """
    trade_id:               str
    symbol:                 str                      # e.g. "BTC/USDC"
    side:                   str                      # "LONG" | "SHORT"
    ts_open_ms:             int
    entry_price:            float
    size_base:              float

    status:                 TradeStatus = TradeStatus.OPEN
    ts_close_ms:            Optional[int]   = None
    exit_price:             Optional[float] = None
    pnl_usdt:               Optional[float] = None
    fee_usdt:               Optional[float] = None
    exit_type:              Optional[ExitType] = None

    # Reconciliation metadata
    last_synced_ms:         int = field(default_factory=lambda: _now_ms())
    source_checksum:        Optional[str]  = None
    reconciliation_lag_ms:  Optional[int]  = None

    # Audit
    created_at_ms:          int = field(default_factory=lambda: _now_ms())
    updated_at_ms:          int = field(default_factory=lambda: _now_ms())

    def is_open(self) -> bool:
        return self.status == TradeStatus.OPEN

    def is_closed(self) -> bool:
        return self.status == TradeStatus.CLOSED


# ── Lightweight Lighter response models (Protocol-aligned, no SDK) ─────────────

@dataclass
class LighterPosition:
    """
    Minimal representation of an open position from Lighter `/account` response.
    Field names intentionally decoupled from SDK — mapped in gateway adapter.
    """
    order_id:       str
    symbol:         str
    side:           str
    entry_price:    float
    size_base:      float
    ts_open_ms:     int


@dataclass
class LighterClosedOrder:
    """
    Minimal representation of a closed order from Lighter `accountInactiveOrders`.
    Sufficient to reconstruct CLOSED row in trades_lighter.
    """
    order_id:       str
    symbol:         str
    side:           str
    entry_price:    float
    exit_price:     float
    size_base:      float
    pnl_usdt:       Optional[float]
    fee_usdt:       Optional[float]
    ts_open_ms:     int
    ts_close_ms:    int
    order_type:     str      # e.g. "stop-loss-limit", "take-profit-limit", "market"
    raw_checksum:   Optional[str] = None


# ── Reconciliation result ──────────────────────────────────────────────────────

@dataclass
class ReconciliationResult:
    """
    Summary of a single reconciliation run (written to reconciliation_log table).
    """
    log_id:              str
    mode:                ReconcileMode
    ts_ms:               int = field(default_factory=lambda: _now_ms())
    stuck_resolved:      int = 0
    missing_resolved:    int = 0
    upserted:            int = 0
    snapshots_inserted:  int = 0
    duration_ms:         int = 0
    api_calls_count:     int = 0
    api_throttled_count: int = 0
    errors:              list[str] = field(default_factory=list)
    success:             bool = True

    def mark_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.success = False


# ── Utility ───────────────────────────────────────────────────────────────────

def _now_ms() -> int:
    return int(time.time() * 1000)
