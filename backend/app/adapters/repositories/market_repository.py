# v2.2 — DuckDB write-lock retry
import os
import duckdb
import pandas as pd
import time
import logging
from pathlib import Path

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

# Path global bisa disesuaikan, atau dilewatkan saat init
DEFAULT_DB_PATH = os.getenv("DB_PATH") or str(Path(__file__).resolve().parent.parent.parent.parent / "app" / "infrastructure" / "database" / "btc-quant.db")

class MarketRepository:
    """
    Adapter Repository untuk DuckDB. 
    Mengelola penyimpanan data OHLCV, market metrics, dan akun paper trading.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH, read_only: bool = False):
        self.db_path = db_path
        self.read_only = read_only
        if not read_only:
            self._init_tables()

    def _init_tables(self):
        try:
            with duckdb.connect(self.db_path) as con:
                con.execute("""
                    CREATE TABLE IF NOT EXISTS btc_ohlcv_4h (
                        timestamp   BIGINT PRIMARY KEY,
                        open        DOUBLE,
                        high        DOUBLE,
                        low         DOUBLE,
                        close       DOUBLE,
                        volume      DOUBLE,
                        cvd         DOUBLE
                    )
                """)
                con.execute("""
                    CREATE TABLE IF NOT EXISTS market_metrics (
                        timestamp             BIGINT PRIMARY KEY,
                        funding_rate          DOUBLE,
                        open_interest         DOUBLE,
                        global_mcap_change    DOUBLE,
                        order_book_imbalance  DOUBLE,
                        cvd                   DOUBLE,
                        liquidations_buy      DOUBLE,
                        liquidations_sell     DOUBLE,
                        fgi_value             DOUBLE
                    )
                """)
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
            # Multi-process startup race: another process may hold a write lock momentarily.
            logging.warning(f"[MarketRepository] Skipping _init_tables (DB locked): {e}")

    def upsert_ohlcv(self, df: pd.DataFrame):
        if df.empty: return
        def _write():
            with duckdb.connect(self.db_path) as con:
                con.register("df", df)
                con.execute("INSERT OR REPLACE INTO btc_ohlcv_4h SELECT * FROM df")
        _retry_write(_write)

    def insert_metrics(self, metrics: dict):
        def _write():
            with duckdb.connect(self.db_path) as con:
                con.execute("""
                    INSERT OR REPLACE INTO market_metrics
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    metrics["timestamp"], metrics["funding_rate"], metrics["open_interest"],
                    metrics["global_mcap_change"], metrics["order_book_imbalance"],
                    metrics["cvd"], metrics["liquidations_buy"], metrics["liquidations_sell"],
                    metrics["fgi_value"]
                ])
        _retry_write(_write)

    def get_ohlcv_with_metrics(self, limit: int = 500) -> pd.DataFrame:
        """
        Return the latest N 4H candles joined with latest metrics.
        Includes: OHLCV + CVD + Funding + OI + FGI.
        Uses ASOF JOIN for temporal alignment.
        """
        with duckdb.connect(self.db_path, read_only=True) as con:
            # We join ohlcv with the closest market metrics snapshot
            df = con.execute(f"""
                SELECT 
                    o.*,
                    m.funding_rate,
                    m.open_interest,
                    m.fgi_value
                FROM btc_ohlcv_4h o
                ASOF LEFT JOIN market_metrics m ON o.timestamp >= m.timestamp
                ORDER BY o.timestamp DESC
                LIMIT {limit}
            """).fetchdf()

        if df.empty:
            return df

        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.sort_values("datetime").set_index("datetime")
        
        # Map columns to the format SignalService expects (Capitalized and Acronyms)
        cols_map = {
            "cvd":          "CVD",
            "funding_rate": "Funding",
            "open_interest":"OI",
            "fgi_value":    "FGI",
            "timestamp":    "timestamp"
        }
        df.columns = [cols_map.get(c, c.capitalize()) for c in df.columns]
        return df

    def get_latest_metrics(self) -> dict:
        """Return the most recent market metrics row."""
        with duckdb.connect(self.db_path, read_only=True) as con:
            row = con.execute("SELECT * FROM market_metrics ORDER BY timestamp DESC LIMIT 1").fetchone()
        if row is None:
            return {
                "funding_rate": 0.0, "open_interest": 0.0, "global_mcap_change": 0.0,
                "order_book_imbalance": 0.0, "cvd": 0.0, "liquidations_buy": 0.0, "liquidations_sell": 0.0
            }
        return {
            "timestamp": row[0], "funding_rate": row[1], "open_interest": row[2],
            "global_mcap_change": row[3], "order_book_imbalance": row[4],
            "cvd": row[5], "liquidations_buy": row[6], "liquidations_sell": row[7],
            "fgi_value": row[8] if len(row) > 8 else 50.0
        }

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

# Singleton for MarketRepository
# API process uses read_only=True to avoid DuckDB write-lock conflict
# with the data engine process (which is the sole writer).
_market_repo = None

def get_market_repository() -> MarketRepository:
    global _market_repo
    if _market_repo is None:
        _market_repo = MarketRepository(read_only=True)
    return _market_repo
