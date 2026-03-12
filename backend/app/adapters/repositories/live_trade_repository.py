"""
LiveTradeRepository for tracking live execution trades.

Stores all trades executed via the execution layer in DuckDB.
Separate from paper_trades table.
"""

import os
import duckdb
import time
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


def _retry_write(fn, max_attempts: int = 5, delay: float = 1.0):
    """Retry a DuckDB write operation on lock conflict (multi-process race)."""
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except (duckdb.IOException, duckdb.InternalException) as e:
            if attempt == max_attempts:
                raise
            logging.warning(f"[DB] Write locked (attempt {attempt}/{max_attempts}), retrying in {delay}s: {e}")
            time.sleep(delay)


DEFAULT_DB_PATH = os.getenv("DB_PATH") or str(
    Path(__file__).resolve().parent.parent.parent.parent / "app" / "infrastructure" / "database" / "btc-quant.db"
)


@dataclass
class LiveTradeRecord:
    """Represents a live trade record."""
    id: str
    timestamp_open: int
    timestamp_close: Optional[int]
    symbol: str
    side: str  # LONG | SHORT
    entry_price: float
    exit_price: Optional[float]
    size_usdt: float
    size_base: float
    leverage: int
    sl_price: float
    tp_price: float
    sl_order_id: Optional[str]
    tp_order_id: Optional[str]
    exit_type: Optional[str]  # SL | TP | TIME_EXIT | MANUAL | None
    status: str  # OPEN | CLOSED
    pnl_usdt: Optional[float]
    pnl_pct: Optional[float]
    signal_verdict: Optional[str]
    signal_conviction: Optional[float]
    candle_open_ts: int


class LiveTradeRepository:
    """
    Repository for live execution trades.
    Uses DuckDB for persistence.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._init_tables()

    def _init_tables(self):
        """Create live_trades table if not exists."""
        try:
            with duckdb.connect(self.db_path) as con:
                con.execute("""
                    CREATE TABLE IF NOT EXISTS live_trades (
                        id                  VARCHAR PRIMARY KEY,
                        timestamp_open      BIGINT NOT NULL,
                        timestamp_close     BIGINT,
                        symbol              VARCHAR NOT NULL,
                        side                VARCHAR NOT NULL,
                        entry_price         DOUBLE NOT NULL,
                        exit_price          DOUBLE,
                        size_usdt           DOUBLE NOT NULL,
                        size_base           DOUBLE NOT NULL,
                        leverage            INTEGER NOT NULL,
                        sl_price            DOUBLE NOT NULL,
                        tp_price            DOUBLE NOT NULL,
                        sl_order_id         VARCHAR,
                        tp_order_id         VARCHAR,
                        exit_type           VARCHAR,
                        status              VARCHAR NOT NULL,
                        pnl_usdt            DOUBLE,
                        pnl_pct             DOUBLE,
                        signal_verdict      VARCHAR,
                        signal_conviction   DOUBLE,
                        candle_open_ts      BIGINT NOT NULL
                    )
                """)
            logging.info("[LiveTradeRepository] Tables initialized")
        except (duckdb.IOException, duckdb.InternalException) as e:
            logging.warning(f"[LiveTradeRepository] Skipping _init_tables (DB locked): {e}")

    def insert_trade(
        self,
        trade_id: str,
        symbol: str,
        side: str,
        entry_price: float,
        size_usdt: float,
        size_base: float,
        leverage: int,
        sl_price: float,
        tp_price: float,
        sl_order_id: Optional[str],
        tp_order_id: Optional[str],
        signal_verdict: Optional[str],
        signal_conviction: Optional[float],
        candle_open_ts: int,
    ) -> bool:
        """
        Insert a new live trade record.

        Args:
            trade_id: Unique trade ID (e.g., order_id from exchange)
            symbol: "BTC/USDT"
            side: "LONG" or "SHORT"
            entry_price: Entry price
            size_usdt: Margin in USDT
            size_base: Base currency quantity (BTC)
            leverage: Leverage multiplier
            sl_price: Stop-loss price
            tp_price: Take-profit price
            sl_order_id: SL order ID from exchange
            tp_order_id: TP order ID from exchange
            signal_verdict: Signal verdict (e.g., "CONFLUENCE_5")
            signal_conviction: Conviction percentage (0-100)
            candle_open_ts: Timestamp of candle that triggered signal

        Returns:
            True if successful, False otherwise
        """
        def _write():
            with duckdb.connect(self.db_path) as con:
                con.execute("""
                    INSERT INTO live_trades (
                        id, timestamp_open, symbol, side,
                        entry_price, exit_price, size_usdt, size_base, leverage,
                        sl_price, tp_price, sl_order_id, tp_order_id,
                        exit_type, status, pnl_usdt, pnl_pct,
                        signal_verdict, signal_conviction, candle_open_ts,
                        timestamp_close
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    trade_id, int(time.time() * 1000), symbol, side,
                    entry_price, None, size_usdt, size_base, leverage,
                    sl_price, tp_price, sl_order_id, tp_order_id,
                    None, "OPEN", None, None,
                    signal_verdict, signal_conviction, candle_open_ts,
                    None
                ])

        try:
            _retry_write(_write)
            logging.info(f"[LiveTradeRepository] ✅ Trade inserted: {trade_id}")
            return True
        except Exception as e:
            logging.error(f"[LiveTradeRepository] Failed to insert trade {trade_id}: {e}")
            return False

    def update_trade_on_close(
        self,
        trade_id: str,
        exit_price: float,
        exit_type: str,
        pnl_usdt: float,
        pnl_pct: float,
    ) -> bool:
        """
        Update a trade when it's closed.

        Args:
            trade_id: Trade ID
            exit_price: Exit price
            exit_type: "SL" | "TP" | "TIME_EXIT" | "MANUAL"
            pnl_usdt: PnL in USDT
            pnl_pct: PnL percentage

        Returns:
            True if successful, False otherwise
        """
        def _write():
            with duckdb.connect(self.db_path) as con:
                con.execute("""
                    UPDATE live_trades
                    SET
                        timestamp_close = ?,
                        exit_price = ?,
                        exit_type = ?,
                        status = ?,
                        pnl_usdt = ?,
                        pnl_pct = ?
                    WHERE id = ?
                """, [
                    int(time.time() * 1000), exit_price, exit_type, "CLOSED",
                    pnl_usdt, pnl_pct, trade_id
                ])

        try:
            _retry_write(_write)
            logging.info(
                f"[LiveTradeRepository] ✅ Trade closed: {trade_id} | "
                f"Exit: ${exit_price:,.2f} | PnL: ${pnl_usdt:+.2f} ({pnl_pct:+.2f}%)"
            )
            return True
        except Exception as e:
            logging.error(f"[LiveTradeRepository] Failed to update trade {trade_id}: {e}")
            return False

    def get_open_trade(self) -> Optional[LiveTradeRecord]:
        """
        Get the current open trade (OPEN status).

        Returns:
            LiveTradeRecord if one exists, None otherwise
        """
        try:
            with duckdb.connect(self.db_path, read_only=True) as con:
                result = con.execute("""
                    SELECT
                        id, timestamp_open, timestamp_close, symbol, side,
                        entry_price, exit_price, size_usdt, size_base, leverage,
                        sl_price, tp_price, sl_order_id, tp_order_id,
                        exit_type, status, pnl_usdt, pnl_pct,
                        signal_verdict, signal_conviction, candle_open_ts
                    FROM live_trades
                    WHERE status = 'OPEN'
                    ORDER BY timestamp_open DESC
                    LIMIT 1
                """).fetchall()

                if not result:
                    return None

                row = result[0]
                return LiveTradeRecord(
                    id=row[0],
                    timestamp_open=row[1],
                    timestamp_close=row[2],
                    symbol=row[3],
                    side=row[4],
                    entry_price=row[5],
                    exit_price=row[6],
                    size_usdt=row[7],
                    size_base=row[8],
                    leverage=row[9],
                    sl_price=row[10],
                    tp_price=row[11],
                    sl_order_id=row[12],
                    tp_order_id=row[13],
                    exit_type=row[14],
                    status=row[15],
                    pnl_usdt=row[16],
                    pnl_pct=row[17],
                    signal_verdict=row[18],
                    signal_conviction=row[19],
                    candle_open_ts=row[20],
                )

        except Exception as e:
            logging.error(f"[LiveTradeRepository] Failed to get open trade: {e}")
            return None

    def get_trade_history(self, limit: int = 50) -> list[LiveTradeRecord]:
        """
        Get recent closed trades.

        Args:
            limit: Number of trades to return

        Returns:
            List of LiveTradeRecord (most recent first)
        """
        try:
            with duckdb.connect(self.db_path, read_only=True) as con:
                results = con.execute(f"""
                    SELECT
                        id, timestamp_open, timestamp_close, symbol, side,
                        entry_price, exit_price, size_usdt, size_base, leverage,
                        sl_price, tp_price, sl_order_id, tp_order_id,
                        exit_type, status, pnl_usdt, pnl_pct,
                        signal_verdict, signal_conviction, candle_open_ts
                    FROM live_trades
                    WHERE status = 'CLOSED'
                    ORDER BY timestamp_close DESC
                    LIMIT {limit}
                """).fetchall()

                trades = []
                for row in results:
                    trades.append(LiveTradeRecord(
                        id=row[0],
                        timestamp_open=row[1],
                        timestamp_close=row[2],
                        symbol=row[3],
                        side=row[4],
                        entry_price=row[5],
                        exit_price=row[6],
                        size_usdt=row[7],
                        size_base=row[8],
                        leverage=row[9],
                        sl_price=row[10],
                        tp_price=row[11],
                        sl_order_id=row[12],
                        tp_order_id=row[13],
                        exit_type=row[14],
                        status=row[15],
                        pnl_usdt=row[16],
                        pnl_pct=row[17],
                        signal_verdict=row[18],
                        signal_conviction=row[19],
                        candle_open_ts=row[20],
                    ))

                return trades

        except Exception as e:
            logging.error(f"[LiveTradeRepository] Failed to get trade history: {e}")
            return []

    def get_daily_pnl(self) -> tuple[float, float]:
        """
        Get daily PnL (all closed trades today).

        Returns:
            Tuple of (pnl_usdt, pnl_pct)
        """
        try:
            with duckdb.connect(self.db_path, read_only=True) as con:
                today_start = int((time.time() // 86400) * 86400 * 1000)  # Start of today (ms)

                result = con.execute("""
                    SELECT
                        COALESCE(SUM(pnl_usdt), 0) as total_pnl_usdt,
                        COALESCE(SUM(pnl_pct * size_usdt), 0) / COALESCE(SUM(size_usdt), 1) as avg_pnl_pct
                    FROM live_trades
                    WHERE status = 'CLOSED' AND timestamp_close >= ?
                """, [today_start]).fetchone()

                if result:
                    return float(result[0]), float(result[1])
                return 0.0, 0.0

        except Exception as e:
            logging.error(f"[LiveTradeRepository] Failed to get daily PnL: {e}")
            return 0.0, 0.0
