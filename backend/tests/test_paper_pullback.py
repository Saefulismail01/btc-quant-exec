"""
Unit tests for paper_executor_pullback.py
==========================================
Test semua logic core tanpa butuh DuckDB / signal_service.
"""

import sys
import time
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

# ── Import target module ──────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import paper_executor_pullback as pb


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _ts(date_str: str, hour: int = 0) -> float:
    """Return epoch seconds untuk tanggal + jam UTC."""
    dt = datetime(
        *[int(x) for x in date_str.split("-")], hour, 0, 0, tzinfo=timezone.utc
    )
    return dt.timestamp()


def _make_executor(tmp_path: Path) -> pb.PullbackPaperExecutor:
    """Buat executor dengan output dir di tempdir (tidak menyentuh filesystem asli)."""
    with patch.object(pb, "OUTPUT_DIR", tmp_path), \
         patch.object(pb, "TRADES_CSV", tmp_path / "trades.csv"), \
         patch.object(pb, "STATE_FILE", tmp_path / "state.json"), \
         patch.object(pb, "LOG_FILE",   tmp_path / "pb.log"):
        executor = pb.PullbackPaperExecutor()
    return executor


# ══════════════════════════════════════════════════════════════════════════════
#  TEST: Helpers
# ══════════════════════════════════════════════════════════════════════════════

def test_wib_date_utc_midnight():
    """00:00 UTC = 07:00 WIB — hari yang sama di WIB."""
    ts = _ts("2026-04-28", hour=0)   # 00:00 UTC = 07:00 WIB 28 Apr
    assert pb._wib_date(ts) == "2026-04-28"


def test_wib_date_prev_day():
    """23:00 UTC = 06:00 WIB keesokan = masih hari sebelumnya di WIB."""
    ts = _ts("2026-04-27", hour=23)  # 23:00 UTC = 06:00 WIB 28 Apr
    assert pb._wib_date(ts) == "2026-04-28"


def test_calc_pnl_long_win():
    """LONG entry 100k exit 100.71k → profit bersih setelah fee."""
    pnl = pb._calc_pnl("LONG", 100_000, 100_710)
    expected = pb.NOTIONAL * (100_710 - 100_000) / 100_000 - pb.FEE_USD
    assert abs(pnl - expected) < 0.01


def test_calc_pnl_short_win():
    """SHORT entry 100k exit 98.667k → profit."""
    pnl = pb._calc_pnl("SHORT", 100_000, 98_667)
    assert pnl > 0


def test_calc_pnl_sl_long():
    """LONG kena SL 1.333% di bawah entry → rugi ~$200 + fee."""
    entry = 100_000
    sl    = entry * (1 - pb.SL_PCT)
    pnl   = pb._calc_pnl("LONG", entry, sl)
    assert pnl < -pb.FEE_USD   # rugi lebih dari fee


# ══════════════════════════════════════════════════════════════════════════════
#  TEST: PendingOrder
# ══════════════════════════════════════════════════════════════════════════════

def test_pending_order_not_expired():
    now = time.time()
    po  = pb.PendingOrder("LONG", 100_000, 99_700, 98_667, 100_710, now, "ts")
    assert not po.is_expired(now + 1)


def test_pending_order_expired():
    now = time.time()
    po  = pb.PendingOrder("LONG", 100_000, 99_700, 98_667, 100_710, now, "ts")
    assert po.is_expired(now + pb.MAX_WAIT_CANDLES * pb.CANDLE_SECONDS + 1)


def test_pending_order_serialization():
    now = time.time()
    po  = pb.PendingOrder("SHORT", 95_000, 95_285, 96_267, 94_325, now, "2026-01-01T00:00:00Z")
    restored = pb.PendingOrder.from_dict(po.to_dict())
    assert restored.side         == po.side
    assert restored.limit_price  == po.limit_price
    assert restored.expires_ts   == po.expires_ts


# ══════════════════════════════════════════════════════════════════════════════
#  TEST: ExecutorState persist / load
# ══════════════════════════════════════════════════════════════════════════════

def test_state_save_load(tmp_path):
    state_file = tmp_path / "state.json"
    now = time.time()

    with patch.object(pb, "STATE_FILE", state_file):
        s = pb.ExecutorState()
        s.total_pnl   = 1234.56
        s.n_trades    = 10
        s.n_wins      = 7
        s.n_sl        = 3
        s.n_miss      = 2
        s.freeze_date = "2026-04-28"
        s.pending_order = pb.PendingOrder(
            "LONG", 100_000, 99_700, 98_667, 100_710, now, "ts1"
        )
        s.save()

        s2 = pb.ExecutorState()
        s2.load()

    assert s2.total_pnl   == 1234.56
    assert s2.n_trades    == 10
    assert s2.freeze_date == "2026-04-28"
    assert s2.pending_order is not None
    assert s2.pending_order.side == "LONG"


# ══════════════════════════════════════════════════════════════════════════════
#  TEST: Freeze logic
# ══════════════════════════════════════════════════════════════════════════════

def test_is_frozen_same_day():
    state = pb.ExecutorState()
    now   = _ts("2026-04-28", hour=10)  # 10:00 UTC = 17:00 WIB
    state.freeze_date = pb._wib_date(now)
    assert pb._is_frozen(state, now)


def test_is_frozen_next_day():
    state = pb.ExecutorState()
    state.freeze_date = "2026-04-28"
    next_day = _ts("2026-04-29", hour=1)  # 01:00 UTC = 08:00 WIB 29 Apr
    assert not pb._is_frozen(state, next_day)


def test_is_frozen_none():
    state = pb.ExecutorState()
    state.freeze_date = None
    assert not pb._is_frozen(state, time.time())


# ══════════════════════════════════════════════════════════════════════════════
#  TEST: _check_freeze_reset
# ══════════════════════════════════════════════════════════════════════════════

def test_freeze_reset_on_new_day(tmp_path):
    state_file = tmp_path / "state.json"
    with patch.object(pb, "STATE_FILE", state_file), \
         patch.object(pb, "TRADES_CSV", tmp_path / "t.csv"):
        ex = pb.PullbackPaperExecutor()
        ex.state.freeze_date = "2026-04-27"
        now = _ts("2026-04-28", hour=2)   # 02:00 UTC = 09:00 WIB 28 Apr
        ex._check_freeze_reset(now)
        assert ex.state.freeze_date is None


def test_freeze_not_reset_same_day(tmp_path):
    state_file = tmp_path / "state.json"
    with patch.object(pb, "STATE_FILE", state_file), \
         patch.object(pb, "TRADES_CSV", tmp_path / "t.csv"):
        ex = pb.PullbackPaperExecutor()
        ex.state.freeze_date = "2026-04-28"
        now = _ts("2026-04-28", hour=10)  # masih hari yang sama WIB
        ex._check_freeze_reset(now)
        assert ex.state.freeze_date == "2026-04-28"


# ══════════════════════════════════════════════════════════════════════════════
#  TEST: _check_pending_fill
# ══════════════════════════════════════════════════════════════════════════════

def test_long_fill_when_price_below_limit(tmp_path):
    state_file = tmp_path / "state.json"
    trades_csv = tmp_path / "trades.csv"
    now = time.time()
    with patch.object(pb, "STATE_FILE", state_file), \
         patch.object(pb, "TRADES_CSV", trades_csv):
        ex = pb.PullbackPaperExecutor()
        ex.state.pending_order = pb.PendingOrder(
            "LONG", 100_000, 99_700, 98_667, 100_710, now, "ts"
        )
        ex._check_pending_fill(99_500, now + 60)
        assert ex.state.pending_order is None
        assert ex.state.open_position is not None
        assert ex.state.open_position.entry_price == 99_700


def test_long_no_fill_when_price_above_limit(tmp_path):
    state_file = tmp_path / "state.json"
    trades_csv = tmp_path / "trades.csv"
    now = time.time()
    with patch.object(pb, "STATE_FILE", state_file), \
         patch.object(pb, "TRADES_CSV", trades_csv):
        ex = pb.PullbackPaperExecutor()
        ex.state.pending_order = pb.PendingOrder(
            "LONG", 100_000, 99_700, 98_667, 100_710, now, "ts"
        )
        ex._check_pending_fill(100_500, now + 60)
        assert ex.state.pending_order is not None
        assert ex.state.open_position is None


def test_short_fill_when_price_above_limit(tmp_path):
    state_file = tmp_path / "state.json"
    trades_csv = tmp_path / "trades.csv"
    now = time.time()
    with patch.object(pb, "STATE_FILE", state_file), \
         patch.object(pb, "TRADES_CSV", trades_csv):
        ex = pb.PullbackPaperExecutor()
        ex.state.pending_order = pb.PendingOrder(
            "SHORT", 100_000, 100_300, 101_333, 99_290, now, "ts"
        )
        ex._check_pending_fill(100_500, now + 60)
        assert ex.state.pending_order is None
        assert ex.state.open_position is not None


def test_order_expired_written_to_csv(tmp_path):
    state_file = tmp_path / "state.json"
    trades_csv = tmp_path / "trades.csv"
    now = time.time()
    with patch.object(pb, "STATE_FILE", state_file), \
         patch.object(pb, "TRADES_CSV", trades_csv):
        ex = pb.PullbackPaperExecutor()
        ex.state.pending_order = pb.PendingOrder(
            "LONG", 100_000, 99_700, 98_667, 100_710, now, "ts"
        )
        expired_ts = now + pb.MAX_WAIT_CANDLES * pb.CANDLE_SECONDS + 100
        ex._check_pending_fill(100_500, expired_ts)
        assert ex.state.pending_order is None
        assert ex.state.n_miss == 1
        content = trades_csv.read_text()
        assert "MISS_EXPIRED" in content


# ══════════════════════════════════════════════════════════════════════════════
#  TEST: _check_open_exit
# ══════════════════════════════════════════════════════════════════════════════

def _open_pos(side: str, entry: float) -> pb.OpenPosition:
    sl = entry * (1 - pb.SL_PCT) if side == "LONG" else entry * (1 + pb.SL_PCT)
    tp = entry * (1 + pb.TP_PCT) if side == "LONG" else entry * (1 - pb.TP_PCT)
    return pb.OpenPosition(side, entry, sl, tp, time.time(), "ts", entry / (1 - 0.003))


def test_long_sl_hit(tmp_path):
    state_file = tmp_path / "state.json"
    trades_csv = tmp_path / "trades.csv"
    with patch.object(pb, "STATE_FILE", state_file), \
         patch.object(pb, "TRADES_CSV", trades_csv):
        ex = pb.PullbackPaperExecutor()
        entry = 100_000.0
        ex.state.open_position = _open_pos("LONG", entry)
        sl_price = entry * (1 - pb.SL_PCT) - 10
        now = time.time()
        ex._check_open_exit(sl_price, now)
        assert ex.state.open_position is None
        assert ex.state.n_trades == 1
        assert ex.state.n_sl     == 1
        assert ex.state.total_pnl < 0
        assert ex.state.freeze_date == pb._wib_date(now)
        content = trades_csv.read_text()
        assert "SL" in content


def test_long_tp_hit(tmp_path):
    state_file = tmp_path / "state.json"
    trades_csv = tmp_path / "trades.csv"
    with patch.object(pb, "STATE_FILE", state_file), \
         patch.object(pb, "TRADES_CSV", trades_csv):
        ex = pb.PullbackPaperExecutor()
        entry = 100_000.0
        ex.state.open_position = _open_pos("LONG", entry)
        tp_price = entry * (1 + pb.TP_PCT) + 10
        ex._check_open_exit(tp_price, time.time())
        assert ex.state.open_position is None
        assert ex.state.n_trades == 1
        assert ex.state.n_wins   == 1
        assert ex.state.total_pnl > 0
        assert ex.state.freeze_date is None
        content = trades_csv.read_text()
        assert "TRAIL_TP" in content


def test_short_sl_hit(tmp_path):
    state_file = tmp_path / "state.json"
    trades_csv = tmp_path / "trades.csv"
    with patch.object(pb, "STATE_FILE", state_file), \
         patch.object(pb, "TRADES_CSV", trades_csv):
        ex = pb.PullbackPaperExecutor()
        entry = 100_000.0
        ex.state.open_position = _open_pos("SHORT", entry)
        sl_price = entry * (1 + pb.SL_PCT) + 10
        ex._check_open_exit(sl_price, time.time())
        assert ex.state.n_sl == 1
        assert ex.state.total_pnl < 0


def test_sl_cancels_pending_order(tmp_path):
    """SL hit harus cancel pending order yang ada sekaligus."""
    state_file = tmp_path / "state.json"
    trades_csv = tmp_path / "trades.csv"
    now = time.time()
    with patch.object(pb, "STATE_FILE", state_file), \
         patch.object(pb, "TRADES_CSV", trades_csv):
        ex = pb.PullbackPaperExecutor()
        entry = 100_000.0
        ex.state.open_position  = _open_pos("LONG", entry)
        ex.state.pending_order  = pb.PendingOrder(
            "SHORT", 98_000, 98_294, 99_307, 97_303, now, "ts2"
        )
        sl_price = entry * (1 - pb.SL_PCT) - 10
        ex._check_open_exit(sl_price, now)
        assert ex.state.pending_order is None
        assert ex.state.n_miss == 1
        content = trades_csv.read_text()
        assert "MISS_FREEZE_CANCEL" in content


# ══════════════════════════════════════════════════════════════════════════════
#  TEST: _process_new_signal
# ══════════════════════════════════════════════════════════════════════════════

def _make_signal(action="LONG", status="ACTIVE", price=100_000.0):
    sig = MagicMock()
    sig.is_fallback              = False
    sig.price.now                = price
    sig.trade_plan.action        = action
    sig.trade_plan.status        = status
    sig.timestamp                = "2026-04-28T10:00:00Z"
    return sig


def test_new_signal_creates_pending_order(tmp_path):
    state_file = tmp_path / "state.json"
    trades_csv = tmp_path / "trades.csv"
    now = time.time()
    with patch.object(pb, "STATE_FILE", state_file), \
         patch.object(pb, "TRADES_CSV", trades_csv):
        ex = pb.PullbackPaperExecutor()
        ex._process_new_signal(_make_signal("LONG", "ACTIVE", 100_000), now)
        assert ex.state.pending_order is not None
        assert ex.state.pending_order.side == "LONG"
        expected_limit = 100_000 * (1 - pb.PULLBACK_PCT)
        assert abs(ex.state.pending_order.limit_price - expected_limit) < 0.01


def test_new_signal_skipped_when_frozen(tmp_path):
    state_file = tmp_path / "state.json"
    trades_csv = tmp_path / "trades.csv"
    now = _ts("2026-04-28", hour=10)
    with patch.object(pb, "STATE_FILE", state_file), \
         patch.object(pb, "TRADES_CSV", trades_csv):
        ex = pb.PullbackPaperExecutor()
        ex.state.freeze_date = "2026-04-28"
        ex._process_new_signal(_make_signal("LONG", "ACTIVE", 100_000), now)
        assert ex.state.pending_order is None


def test_new_signal_skipped_when_suspended(tmp_path):
    state_file = tmp_path / "state.json"
    trades_csv = tmp_path / "trades.csv"
    now = time.time()
    with patch.object(pb, "STATE_FILE", state_file), \
         patch.object(pb, "TRADES_CSV", trades_csv):
        ex = pb.PullbackPaperExecutor()
        ex._process_new_signal(_make_signal("LONG", "SUSPENDED", 100_000), now)
        assert ex.state.pending_order is None


def test_new_signal_skipped_when_position_open(tmp_path):
    state_file = tmp_path / "state.json"
    trades_csv = tmp_path / "trades.csv"
    now = time.time()
    with patch.object(pb, "STATE_FILE", state_file), \
         patch.object(pb, "TRADES_CSV", trades_csv):
        ex = pb.PullbackPaperExecutor()
        ex.state.open_position = _open_pos("LONG", 100_000)
        ex._process_new_signal(_make_signal("SHORT", "ACTIVE", 99_000), now)
        assert ex.state.pending_order is None


def test_short_limit_above_signal_price(tmp_path):
    """SHORT: limit harus di ATAS harga sinyal."""
    state_file = tmp_path / "state.json"
    trades_csv = tmp_path / "trades.csv"
    now = time.time()
    with patch.object(pb, "STATE_FILE", state_file), \
         patch.object(pb, "TRADES_CSV", trades_csv):
        ex = pb.PullbackPaperExecutor()
        ex._process_new_signal(_make_signal("SHORT", "ACTIVE", 100_000), now)
        assert ex.state.pending_order is not None
        assert ex.state.pending_order.limit_price > 100_000


# ══════════════════════════════════════════════════════════════════════════════
#  RUN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
