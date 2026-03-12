"""
DuckDB Repository — read-only access to btc-quant.db.
No business logic here; only SQL queries.
"""
import sys
from pathlib import Path

import duckdb
import pandas as pd

# Allow importing from engines/ directory
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "engines"))

from app.config import settings


class DuckDBRepository:
    """Read-only access to btc-quant.db."""

    def __init__(self):
        self.db_path = settings.db_path
        self.limit   = settings.ohlcv_limit
        self._init_paper_tables()

    def _init_paper_tables(self):
        """Ensure paper trading tables exist. Gracefully skip if locked (multi-process)."""
        import time
        try:
            with duckdb.connect(self.db_path) as con:
                con.execute("""
                    CREATE TABLE IF NOT EXISTS paper_account (
                        id              INTEGER PRIMARY KEY,
                        balance         DOUBLE,
                        equity          DOUBLE,
                        last_update     BIGINT
                    )
                """)
                con.execute("""
                    CREATE TABLE IF NOT EXISTS paper_trades (
                        id              VARCHAR PRIMARY KEY,
                        timestamp       BIGINT,
                        symbol          VARCHAR,
                        side            VARCHAR,
                        entry_price     DOUBLE,
                        exit_price      DOUBLE,
                        size_base       DOUBLE,
                        size_quote      DOUBLE,
                        sl              DOUBLE,
                        tp              DOUBLE,
                        status          VARCHAR,
                        pnl             DOUBLE,
                        pnl_pct         DOUBLE
                    )
                """)
                count = con.execute("SELECT count(*) FROM paper_account").fetchone()[0]
                if count == 0:
                    con.execute("INSERT INTO paper_account VALUES (1, 10000.0, 10000.0, ?)", [int(time.time() * 1000)])
        except (duckdb.IOException, duckdb.InternalException) as e:
            # Most likely database is locked by another process (paper_executor.py)
            # If so, the tables should already be there. We skip and log.
            import logging
            logging.warning(f"[DuckDB] Skipping _init_paper_tables (DB locked): {e}")

    # ── OHLCV ──────────────────────────────────────────────

    def get_ohlcv(self) -> pd.DataFrame:
        """
        Return the latest N 4H candles joined with latest metrics.
        Includes: OHLCV + CVD + Funding + OI.
        """
        with duckdb.connect(self.db_path, read_only=True) as con:
            # We join ohlcv with the closest market metrics snapshot
            # DuckDB supports ASOF JOIN which is perfect for this
            df = con.execute(f"""
                SELECT 
                    o.*,
                    m.funding_rate,
                    m.open_interest,
                    m.fgi_value
                FROM btc_ohlcv_4h o
                ASOF LEFT JOIN market_metrics m ON o.timestamp >= m.timestamp
                ORDER BY o.timestamp DESC
                LIMIT {self.limit}
            """).fetchdf()

        if df.empty:
            return df

        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.sort_values("datetime").set_index("datetime")
        # Capitalize standard columns, UPPERCASE for acronyms
        df.columns = [
            "CVD" if c == "cvd" 
            else "Funding" if c == "funding_rate"
            else "OI" if c == "open_interest"
            else "FGI" if c == "fgi_value"
            else (c.capitalize() if c != "timestamp" else c) 
            for c in df.columns
        ]
        return df

    # ── Market Metrics ────────────────────────────────────

    def get_latest_metrics(self) -> dict:
        """Return the most recent market metrics row."""
        with duckdb.connect(self.db_path, read_only=True) as con:
            row = con.execute("""
                SELECT * FROM market_metrics
                ORDER BY timestamp DESC
                LIMIT 1
            """).fetchone()

        if row is None:
            return {
                "funding_rate": 0.0,
                "open_interest": 0.0,
                "global_mcap_change": 0.0,
                "order_book_imbalance": 0.0,
                "cvd": 0.0,
                "liquidations_buy": 0.0,
                "liquidations_sell": 0.0,
            }

        return {
            "timestamp":            row[0],
            "funding_rate":         row[1],
            "open_interest":        row[2],
            "global_mcap_change":   row[3],
            "order_book_imbalance": row[4],
            "cvd":                   row[5],
            "liquidations_buy":      row[6],
            "liquidations_sell":     row[7],
        }

    # ── Paper Trading ─────────────────────────────────────

    def get_paper_account(self) -> dict:
        """Return the current paper account state."""
        with duckdb.connect(self.db_path, read_only=True) as con:
            row = con.execute("SELECT balance, equity, last_update FROM paper_account WHERE id = 1").fetchone()
        
        if row is None:
            return {"balance": 10000.0, "equity": 10000.0, "last_update": 0}
        
        return {
            "balance": row[0],
            "equity": row[1],
            "last_update": row[2]
        }

    def get_open_trades(self, symbol: str = "BTC/USDT") -> pd.DataFrame:
        """Return all OPEN trades."""
        with duckdb.connect(self.db_path, read_only=True) as con:
            df = con.execute(f"SELECT * FROM paper_trades WHERE status = 'OPEN' AND symbol = '{symbol}'").fetchdf()
        return df

    def get_trade_history(self, limit: int = 50) -> pd.DataFrame:
        """Return the most recent CLOSED trades."""
        with duckdb.connect(self.db_path, read_only=True) as con:
            df = con.execute(f"SELECT * FROM paper_trades WHERE status = 'CLOSED' ORDER BY timestamp DESC LIMIT {limit}").fetchdf()
        return df


# Module-level singleton
_repo: DuckDBRepository | None = None


def get_repo() -> DuckDBRepository:
    global _repo
    if _repo is None:
        _repo = DuckDBRepository()
    return _repo
