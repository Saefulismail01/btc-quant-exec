"""Read-only analysis for Areas D (partial), E (partial). Writes printout for findings."""
import duckdb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DB = ROOT / "backend" / "app" / "infrastructure" / "database" / "btc-quant.db"


def main():
    con = duckdb.connect(str(DB), read_only=True)
    closed = con.execute(
        """
        SELECT id, timestamp_open, timestamp_close, side, entry_price, exit_price,
               pnl_usdt, pnl_pct, exit_type, signal_verdict, signal_conviction
        FROM live_trades
        WHERE status = 'CLOSED'
        ORDER BY timestamp_open ASC
        """
    ).fetchdf()
    n = len(closed)
    print("CLOSED count:", n)
    if n == 0:
        con.close()
        return
    closed["hold_ms"] = closed["timestamp_close"] - closed["timestamp_open"]
    closed["hold_h"] = closed["hold_ms"] / 3_600_000
    closed["win"] = closed["pnl_usdt"] > 0
    print("\n--- holding hours ---")
    print(closed[["id", "side", "hold_h", "pnl_usdt", "exit_type", "win"]].to_string())
    print("\nmedian hold_h:", closed["hold_h"].median())

    # Funding at entry (ASOF)
    j = con.execute(
        """
        WITH lt AS (
          SELECT *, ROW_NUMBER() OVER (ORDER BY timestamp_open ASC) AS trade_seq
          FROM live_trades
          WHERE status = 'CLOSED'
        )
        SELECT lt.trade_seq, lt.side, lt.pnl_usdt, m.funding_rate
        FROM lt
        ASOF LEFT JOIN market_metrics m ON lt.timestamp_open >= m.timestamp
        ORDER BY lt.timestamp_open
        """
    ).fetchdf()
    print("\n--- funding at entry (ASOF) ---")
    print(j.to_string())

    # OHLCV range for B partial
    r = con.execute(
        "SELECT min(timestamp) as ts_min, max(timestamp) as ts_max, count(*) as n FROM btc_ohlcv_4h"
    ).fetchdf()
    print("\n--- btc_ohlcv_4h ---")
    print(r.to_string())
    mm = con.execute(
        "SELECT min(timestamp) as ts_min, max(timestamp) as ts_max, count(*) as n FROM market_metrics"
    ).fetchdf()
    print("\n--- market_metrics ---")
    print(mm.to_string())
    con.close()


if __name__ == "__main__":
    main()
