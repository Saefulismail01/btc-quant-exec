"""Domain models for reconciliation pipeline (Tier 0b)."""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TradeStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class ExitType(str, Enum):
    TP = "TP"
    SL = "SL"
    TIME = "TIME"
    MANUAL = "MANUAL"
    UNKNOWN = "UNKNOWN"


class ReconcileMode(str, Enum):
    SWEEP = "sweep"
    HISTORY = "history"


@dataclass
class LighterTradeMirror:
    trade_id: str
    symbol: str
    side: str
    ts_open_ms: int
    entry_price: float
    size_base: float
    status: TradeStatus = TradeStatus.OPEN
    ts_close_ms: Optional[int] = None
    exit_price: Optional[float] = None
    pnl_usdt: Optional[float] = None
    fee_usdt: Optional[float] = None
    exit_type: Optional[ExitType] = None
    last_synced_ms: int = field(default_factory=lambda: _now_ms())
    source_checksum: Optional[str] = None
    reconciliation_lag_ms: Optional[int] = None
    created_at_ms: int = field(default_factory=lambda: _now_ms())
    updated_at_ms: int = field(default_factory=lambda: _now_ms())

    def is_open(self) -> bool:
        return self.status == TradeStatus.OPEN

    def is_closed(self) -> bool:
        return self.status == TradeStatus.CLOSED


@dataclass
class LighterPosition:
    order_id: str
    symbol: str
    side: str
    entry_price: float
    size_base: float
    ts_open_ms: int


@dataclass
class LighterClosedOrder:
    order_id: str
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    size_base: float
    pnl_usdt: Optional[float]
    fee_usdt: Optional[float]
    ts_open_ms: int
    ts_close_ms: int
    order_type: str
    raw_checksum: Optional[str] = None


@dataclass
class ReconciliationResult:
    log_id: str
    mode: ReconcileMode
    ts_ms: int = field(default_factory=lambda: _now_ms())
    stuck_resolved: int = 0
    missing_resolved: int = 0
    upserted: int = 0
    snapshots_inserted: int = 0
    duration_ms: int = 0
    api_calls_count: int = 0
    api_throttled_count: int = 0
    errors: list[str] = field(default_factory=list)
    success: bool = True

    def mark_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.success = False


def _now_ms() -> int:
    return int(time.time() * 1000)
