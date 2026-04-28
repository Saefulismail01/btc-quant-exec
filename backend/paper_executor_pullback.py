"""
Paper Executor — Pullback Entry + Daily Freeze Rule
=====================================================
Berjalan PARALEL dengan paper_executor.py / v4.4 live.
TIDAK mengubah apapun di sistem production.

Perbedaan dari paper_executor.py (baseline market entry):
  1. Entry via LIMIT ORDER virtual (bukan market)
     - LONG : limit di signal_price * (1 - PULLBACK_PCT)
     - SHORT: limit di signal_price * (1 + PULLBACK_PCT)
  2. Limit di-cancel jika tidak fill dalam MAX_WAIT_CANDLES candle 4H
  3. Daily Freeze Rule:
     - Jika trade kena SL di hari ini (WIB = UTC+7), stop semua entry baru
     - Cancel pending limit order yang ada
     - Resume jam 07:00 WIB keesokan harinya (00:00 UTC)
  4. Output ke file terpisah — tidak menyentuh DuckDB production

Output files:
  backend/paper_pullback_trades.csv   <- semua trade (filled + missed)
  backend/paper_pullback_state.json   <- state persistent (survive restart)
  backend/paper_pullback.log          <- log lengkap

Cara jalankan di VPS (paralel dengan v4.4):
  cd /path/to/backend
  python paper_executor_pullback.py >> logs/pullback_paper.out 2>&1 &

Environment variables:
  PB_PCT=0.003      pullback percentage (default 0.30%)
  PB_WAIT=2         max wait candles 4H (default 2)
  PB_CYCLE=60       polling interval detik (default 60)
  PB_NOTIONAL=15000 notional USD per trade (default $15,000)
"""

import os
import sys
import csv
import json
import time
import logging
import asyncio
import signal as _signal
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import aiohttp

# ── Path setup ────────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent

# ── Config ────────────────────────────────────────────────────────────────────
BACKEND_API_URL  = os.getenv("BACKEND_API_URL", "http://btc-quant-api:8000/api/signal")
PULLBACK_PCT     = float(os.getenv("PB_PCT",      "0.003"))   # 0.30%
MAX_WAIT_CANDLES = int(os.getenv("PB_WAIT",       "2"))        # 2 candle 4H = 8 jam
CANDLE_SECONDS   = 4 * 3600                                    # 4H dalam detik
CYCLE_INTERVAL   = int(os.getenv("PB_CYCLE",      "60"))       # polling (detik)
SIGNAL_TIMEOUT   = 30.0                                        # detik
NOTIONAL         = float(os.getenv("PB_NOTIONAL", "495"))    # $99 equity x 5x leverage
FEE_USD          = 0.0                                         # Lighter DEX: zero fee
SL_PCT           = 0.01333                                     # 1.333% SL
TP_PCT           = 0.0071                                      # 0.71% TP

# ── Output files ──────────────────────────────────────────────────────────────
# Di Docker: volume di-mount ke /app/data/paper_pullback/
# Di local: fallback ke BACKEND_DIR
_DOCKER_OUTPUT = Path("/app/data/paper_pullback")
_LOCAL_OUTPUT  = BACKEND_DIR
OUTPUT_DIR = _DOCKER_OUTPUT if _DOCKER_OUTPUT.exists() else _LOCAL_OUTPUT
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TRADES_CSV = OUTPUT_DIR / "paper_pullback_trades.csv"
STATE_FILE = OUTPUT_DIR / "paper_pullback_state.json"
LOG_FILE   = OUTPUT_DIR / "paper_pullback.log"

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | [PB-PAPER] | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger("PBPaper")

# ── CSV columns ───────────────────────────────────────────────────────────────
CSV_COLUMNS = [
    "timestamp", "signal_ts", "side",
    "signal_price", "limit_price", "fill_price",
    "sl", "tp", "exit_price", "exit_type",
    "pnl_usd", "total_pnl",
]


# ══════════════════════════════════════════════════════════════════════════════
#  STATE DATACLASSES
# ══════════════════════════════════════════════════════════════════════════════

class PendingOrder:
    """Limit order virtual yang belum fill."""

    def __init__(
        self,
        side: str,
        signal_price: float,
        limit_price: float,
        sl: float,
        tp: float,
        created_ts: float,
        signal_ts: str,
    ):
        self.side         = side
        self.signal_price = signal_price
        self.limit_price  = limit_price
        self.sl           = sl
        self.tp           = tp
        self.created_ts   = created_ts
        self.expires_ts   = created_ts + MAX_WAIT_CANDLES * CANDLE_SECONDS
        self.signal_ts    = signal_ts

    def is_expired(self, now_ts: float) -> bool:
        return now_ts >= self.expires_ts

    def to_dict(self) -> dict:
        return {
            "side"        : self.side,
            "signal_price": self.signal_price,
            "limit_price" : self.limit_price,
            "sl"          : self.sl,
            "tp"          : self.tp,
            "created_ts"  : self.created_ts,
            "expires_ts"  : self.expires_ts,
            "signal_ts"   : self.signal_ts,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PendingOrder":
        o = cls.__new__(cls)
        o.side         = d["side"]
        o.signal_price = d["signal_price"]
        o.limit_price  = d["limit_price"]
        o.sl           = d["sl"]
        o.tp           = d["tp"]
        o.created_ts   = d["created_ts"]
        o.expires_ts   = d["expires_ts"]
        o.signal_ts    = d["signal_ts"]
        return o


class OpenPosition:
    """Trade yang sudah fill dan sedang berjalan."""

    def __init__(
        self,
        side: str,
        entry_price: float,
        sl: float,
        tp: float,
        fill_ts: float,
        signal_ts: str,
        signal_price: float,
    ):
        self.side         = side
        self.entry_price  = entry_price
        self.sl           = sl
        self.tp           = tp
        self.fill_ts      = fill_ts
        self.signal_ts    = signal_ts
        self.signal_price = signal_price

    def to_dict(self) -> dict:
        return {
            "side"        : self.side,
            "entry_price" : self.entry_price,
            "sl"          : self.sl,
            "tp"          : self.tp,
            "fill_ts"     : self.fill_ts,
            "signal_ts"   : self.signal_ts,
            "signal_price": self.signal_price,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "OpenPosition":
        o = cls.__new__(cls)
        o.side         = d["side"]
        o.entry_price  = d["entry_price"]
        o.sl           = d["sl"]
        o.tp           = d["tp"]
        o.fill_ts      = d["fill_ts"]
        o.signal_ts    = d["signal_ts"]
        o.signal_price = d.get("signal_price", d["entry_price"])
        return o


class ExecutorState:
    """State lengkap yang disimpan ke JSON agar survive restart."""

    def __init__(self):
        self.pending_order : Optional[PendingOrder] = None
        self.open_position : Optional[OpenPosition] = None
        self.freeze_date   : Optional[str]          = None
        self.total_pnl     : float                  = 0.0
        self.n_trades      : int                    = 0
        self.n_wins        : int                    = 0
        self.n_sl          : int                    = 0
        self.n_miss        : int                    = 0

    def save(self):
        data = {
            "pending_order": self.pending_order.to_dict() if self.pending_order else None,
            "open_position": self.open_position.to_dict() if self.open_position else None,
            "freeze_date"  : self.freeze_date,
            "total_pnl"    : self.total_pnl,
            "n_trades"     : self.n_trades,
            "n_wins"       : self.n_wins,
            "n_sl"         : self.n_sl,
            "n_miss"       : self.n_miss,
        }
        with open(STATE_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def load(self):
        if not STATE_FILE.exists():
            return
        try:
            with open(STATE_FILE) as f:
                data = json.load(f)
            self.pending_order = (
                PendingOrder.from_dict(data["pending_order"])
                if data.get("pending_order") else None
            )
            self.open_position = (
                OpenPosition.from_dict(data["open_position"])
                if data.get("open_position") else None
            )
            self.freeze_date = data.get("freeze_date")
            self.total_pnl   = data.get("total_pnl", 0.0)
            self.n_trades    = data.get("n_trades",  0)
            self.n_wins      = data.get("n_wins",    0)
            self.n_sl        = data.get("n_sl",      0)
            self.n_miss      = data.get("n_miss",    0)
            log.info(
                f"State loaded: {self.n_trades} trades | "
                f"WR={self.n_wins/max(self.n_trades,1)*100:.1f}% | "
                f"PnL=${self.total_pnl:+.2f} | freeze={self.freeze_date}"
            )
        except Exception as e:
            log.warning(f"State load failed ({e}) — starting fresh")


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _wib_date(ts: float) -> str:
    """Return tanggal WIB (UTC+7) dari epoch seconds, format YYYY-MM-DD."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc) + timedelta(hours=7)
    return dt.strftime("%Y-%m-%d")


def _is_frozen(state: ExecutorState, now_ts: float) -> bool:
    if state.freeze_date is None:
        return False
    return state.freeze_date == _wib_date(now_ts)


def _calc_pnl(side: str, entry: float, exit_price: float) -> float:
    if side == "LONG":
        raw = NOTIONAL * (exit_price - entry) / entry
    else:
        raw = NOTIONAL * (entry - exit_price) / entry
    return round(raw - FEE_USD, 2)


def _write_trade(row: dict):
    """Append satu baris ke CSV trades."""
    file_exists = TRADES_CSV.exists()
    with open(TRADES_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerow({k: row.get(k) for k in CSV_COLUMNS})


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ══════════════════════════════════════════════════════════════════════════════
#  EXECUTOR
# ══════════════════════════════════════════════════════════════════════════════

class PullbackPaperExecutor:

    def __init__(self):
        self.state   = ExecutorState()
        self.state.load()
        self.running = True
        self.cycle   = 0

    # ── 1. Reset freeze ───────────────────────────────────────────────────────
    def _check_freeze_reset(self, now_ts: float):
        if self.state.freeze_date is None:
            return
        today_wib = _wib_date(now_ts)
        if today_wib != self.state.freeze_date:
            log.info(
                f"[FREEZE] Reset — hari baru {today_wib} "
                f"(freeze sebelumnya: {self.state.freeze_date})"
            )
            self.state.freeze_date = None
            self.state.save()

    # ── 2. Cek fill pending order ─────────────────────────────────────────────
    def _check_pending_fill(self, current_price: float, now_ts: float):
        po = self.state.pending_order
        if po is None:
            return

        if po.is_expired(now_ts):
            exp_str = datetime.fromtimestamp(
                po.expires_ts, tz=timezone.utc
            ).strftime("%Y-%m-%d %H:%M UTC")
            log.info(
                f"[ORDER] EXPIRED {po.side} limit@{po.limit_price:.2f} "
                f"(expired {exp_str})"
            )
            _write_trade({
                "timestamp"   : _now_str(),
                "signal_ts"   : po.signal_ts,
                "side"        : po.side,
                "signal_price": round(po.signal_price, 2),
                "limit_price" : round(po.limit_price,  2),
                "fill_price"  : None,
                "sl"          : round(po.sl, 2),
                "tp"          : round(po.tp, 2),
                "exit_price"  : None,
                "exit_type"   : "MISS_EXPIRED",
                "pnl_usd"     : None,
                "total_pnl"   : round(self.state.total_pnl, 2),
            })
            self.state.n_miss       += 1
            self.state.pending_order = None
            self.state.save()
            return

        filled = (
            (po.side == "LONG"  and current_price <= po.limit_price) or
            (po.side == "SHORT" and current_price >= po.limit_price)
        )

        if filled:
            log.info(
                f"[ORDER] FILLED {po.side} @ {po.limit_price:.2f} "
                f"(signal={po.signal_price:.2f}, pb={PULLBACK_PCT*100:.2f}%) | "
                f"SL={po.sl:.2f} TP={po.tp:.2f}"
            )
            self.state.open_position = OpenPosition(
                side         = po.side,
                entry_price  = po.limit_price,
                sl           = po.sl,
                tp           = po.tp,
                fill_ts      = now_ts,
                signal_ts    = po.signal_ts,
                signal_price = po.signal_price,
            )
            self.state.pending_order = None
            self.state.save()

    # ── 3. Cek exit open position ─────────────────────────────────────────────
    def _check_open_exit(self, current_price: float, now_ts: float):
        op = self.state.open_position
        if op is None:
            return

        exit_price: Optional[float] = None
        exit_type:  Optional[str]   = None

        if op.side == "LONG":
            if current_price <= op.sl:
                exit_price, exit_type = op.sl, "SL"
            elif current_price >= op.tp:
                exit_price, exit_type = current_price, "TRAIL_TP"
        else:
            if current_price >= op.sl:
                exit_price, exit_type = op.sl, "SL"
            elif current_price <= op.tp:
                exit_price, exit_type = current_price, "TRAIL_TP"

        if exit_price is None:
            return

        pnl = _calc_pnl(op.side, op.entry_price, exit_price)
        self.state.total_pnl += pnl
        self.state.n_trades  += 1
        if pnl > 0:
            self.state.n_wins += 1

        wr = self.state.n_wins / self.state.n_trades * 100

        _write_trade({
            "timestamp"   : _now_str(),
            "signal_ts"   : op.signal_ts,
            "side"        : op.side,
            "signal_price": round(op.signal_price, 2),
            "limit_price" : round(
                op.entry_price / (1 - PULLBACK_PCT) if op.side == "LONG"
                else op.entry_price / (1 + PULLBACK_PCT), 2
            ),
            "fill_price"  : round(op.entry_price, 2),
            "sl"          : round(op.sl, 2),
            "tp"          : round(op.tp, 2),
            "exit_price"  : round(exit_price, 2),
            "exit_type"   : exit_type,
            "pnl_usd"     : pnl,
            "total_pnl"   : round(self.state.total_pnl, 2),
        })

        log.info(
            f"[TRADE] CLOSE {op.side} {exit_type} @ {exit_price:.2f} | "
            f"Entry: {op.entry_price:.2f} | PnL: ${pnl:+.2f} | "
            f"Total: ${self.state.total_pnl:+.2f} | "
            f"WR: {wr:.1f}% ({self.state.n_trades} trades)"
        )

        if exit_type == "SL":
            self.state.n_sl += 1
            today_wib = _wib_date(now_ts)
            log.warning(
                f"[FREEZE] SL hit! Freeze entry sampai 07:00 WIB besok "
                f"(freeze_date={today_wib})"
            )
            self.state.freeze_date = today_wib

            if self.state.pending_order is not None:
                log.info("[FREEZE] Cancel pending limit order karena freeze.")
                _write_trade({
                    "timestamp"   : _now_str(),
                    "signal_ts"   : self.state.pending_order.signal_ts,
                    "side"        : self.state.pending_order.side,
                    "signal_price": round(self.state.pending_order.signal_price, 2),
                    "limit_price" : round(self.state.pending_order.limit_price,  2),
                    "fill_price"  : None,
                    "sl"          : round(self.state.pending_order.sl, 2),
                    "tp"          : round(self.state.pending_order.tp, 2),
                    "exit_price"  : None,
                    "exit_type"   : "MISS_FREEZE_CANCEL",
                    "pnl_usd"     : None,
                    "total_pnl"   : round(self.state.total_pnl, 2),
                })
                self.state.n_miss       += 1
                self.state.pending_order = None

        self.state.open_position = None
        self.state.save()

    # ── 4. Proses sinyal baru ─────────────────────────────────────────────────
    def _process_new_signal(self, signal, now_ts: float):
        if self.state.open_position is not None:
            log.debug("[SIGNAL] Skip — posisi sudah open")
            return
        if self.state.pending_order is not None:
            log.debug("[SIGNAL] Skip — masih ada pending order")
            return
        if _is_frozen(self.state, now_ts):
            log.warning(
                f"[SIGNAL] FROZEN — skip entry (freeze_date={self.state.freeze_date})"
            )
            return

        status = signal.trade_plan.status
        if status not in ("ACTIVE", "ADVISORY"):
            log.debug(f"[SIGNAL] Skip — status={status}")
            return

        action = signal.trade_plan.action
        price  = signal.price.now

        if action == "LONG":
            limit_px = price * (1 - PULLBACK_PCT)
            sl       = price * (1 - SL_PCT)
            tp       = price * (1 + TP_PCT)
        else:
            limit_px = price * (1 + PULLBACK_PCT)
            sl       = price * (1 + SL_PCT)
            tp       = price * (1 - TP_PCT)

        self.state.pending_order = PendingOrder(
            side         = action,
            signal_price = price,
            limit_price  = limit_px,
            sl           = sl,
            tp           = tp,
            created_ts   = now_ts,
            signal_ts    = signal.timestamp,
        )
        self.state.save()

        exp_str = datetime.fromtimestamp(
            now_ts + MAX_WAIT_CANDLES * CANDLE_SECONDS, tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M UTC")
        log.info(
            f"[ORDER] NEW {action} limit@{limit_px:.2f} "
            f"(signal={price:.2f}, pb={PULLBACK_PCT*100:.2f}%) | "
            f"SL={sl:.2f} TP={tp:.2f} | status={status} | expires {exp_str}"
        )

    # ── Fetch signal via HTTP ──────────────────────────────────────────────────
    async def _fetch_signal(self):
        """Call backend API and return a simple namespace with .price.now, .trade_plan.*, .is_fallback."""
        log.debug(f"Fetching signal from {BACKEND_API_URL}")
        try:
            timeout = aiohttp.ClientTimeout(total=SIGNAL_TIMEOUT, connect=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(BACKEND_API_URL) as resp:
                    if resp.status != 200:
                        log.warning(f"API returned {resp.status}")
                        return None
                    data = await resp.json()
        except asyncio.TimeoutError:
            log.warning(f"Signal API timeout (>{SIGNAL_TIMEOUT}s)")
            return None
        except Exception as e:
            log.warning(f"Signal API error: {e}")
            return None

        # Parse JSON → simple namespace
        try:
            tp = data.get("trade_plan", {})
            price_now = data.get("price", {}).get("now", 0.0)
            signal = type("Signal", (), {
                "is_fallback": data.get("is_fallback", True),
                "timestamp"  : data.get("timestamp", ""),
                "price"      : type("Price", (), {"now": float(price_now)})(),
                "trade_plan" : type("TP", (), {
                    "action" : tp.get("action", "LONG"),
                    "status" : tp.get("status", "SUSPENDED"),
                    "sl"     : float(tp.get("sl", 0)),
                    "tp"     : float(tp.get("tp", 0)),
                })(),
            })()
            return signal
        except Exception as e:
            log.warning(f"Signal parse error: {e}")
            return None

    # ── Main loop ─────────────────────────────────────────────────────────────
    async def run(self):
        log.info("=" * 70)
        log.info("  PULLBACK PAPER EXECUTOR — v1.0")
        log.info(
            f"  Pullback : {PULLBACK_PCT*100:.2f}%  |  "
            f"Max wait: {MAX_WAIT_CANDLES}x4H = {MAX_WAIT_CANDLES*4}h"
        )
        log.info(
            f"  Notional : ${NOTIONAL:,.0f}  |  Fee: ${FEE_USD:.2f}  |  "
            f"SL: {SL_PCT*100:.3f}%  |  TP: {TP_PCT*100:.3f}%"
        )
        log.info(
            f"  Cycle    : {CYCLE_INTERVAL}s  |  "
            f"Freeze reset: 07:00 WIB (00:00 UTC)"
        )
        log.info(f"  Trades   : {TRADES_CSV}")
        log.info(f"  State    : {STATE_FILE}")
        log.info("=" * 70)

        while self.running:
            self.cycle += 1
            now_ts = time.time()

            try:
                log.info(f"[CYCLE {self.cycle}] start")
                self._check_freeze_reset(now_ts)

                signal = await self._fetch_signal()
                if signal is None:
                    await asyncio.sleep(CYCLE_INTERVAL)
                    continue

                if not signal or signal.is_fallback:
                    log.debug(f"[CYCLE {self.cycle}] No signal / fallback — skip")
                    await asyncio.sleep(CYCLE_INTERVAL)
                    continue

                current_price = signal.price.now

                self._check_pending_fill(current_price, now_ts)
                self._check_open_exit(current_price, now_ts)
                self._process_new_signal(signal, now_ts)

                if self.cycle % 10 == 0:
                    wr = self.state.n_wins / max(self.state.n_trades, 1) * 100
                    frozen_str  = (
                        f"FROZEN({self.state.freeze_date})"
                        if self.state.freeze_date else "active"
                    )
                    pending_str = (
                        f"limit@{self.state.pending_order.limit_price:.0f}"
                        if self.state.pending_order else "none"
                    )
                    open_str = (
                        f"open@{self.state.open_position.entry_price:.0f}"
                        if self.state.open_position else "none"
                    )
                    log.info(
                        f"[STATUS c{self.cycle}] price={current_price:.0f} | "
                        f"trades={self.state.n_trades} | WR={wr:.1f}% | "
                        f"PnL=${self.state.total_pnl:+.2f} | miss={self.state.n_miss} | "
                        f"pending={pending_str} | pos={open_str} | {frozen_str}"
                    )

            except Exception as e:
                log.error(
                    f"[CYCLE {self.cycle}] Unexpected error: {e}", exc_info=True
                )

            await asyncio.sleep(CYCLE_INTERVAL)

    def stop(self):
        self.running = False
        wr = self.state.n_wins / max(self.state.n_trades, 1) * 100
        log.info(
            f"[SHUTDOWN] Trades={self.state.n_trades} | WR={wr:.1f}% | "
            f"SL={self.state.n_sl} | Miss={self.state.n_miss} | "
            f"Net PnL=${self.state.total_pnl:+.2f}"
        )


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    executor = PullbackPaperExecutor()

    def _handle_signal(signum, frame):
        executor.stop()

    _signal.signal(_signal.SIGINT,  _handle_signal)
    _signal.signal(_signal.SIGTERM, _handle_signal)

    try:
        asyncio.run(executor.run())
    except KeyboardInterrupt:
        executor.stop()


if __name__ == "__main__":
    main()
