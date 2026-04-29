"""One-off DB probe for research (read-only)."""
import duckdb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]  # .../btc-scalping-execution_layer
DB = ROOT / "backend" / "app" / "infrastructure" / "database" / "btc-quant.db"


def main():
    con = duckdb.connect(str(DB), read_only=True)
    print("DB:", DB, "exists:", DB.exists())
    q = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' ORDER BY 1"
    print("\n=== tables ===\n", con.execute(q).fetchdf().to_string())
    for t in ("live_trades", "paper_trades", "btc_ohlcv_4h", "market_metrics"):
        try:
            n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            print(f"{t}: {n}")
        except Exception as e:
            print(f"{t}: ERR {e}")
    print("\n=== DESCRIBE live_trades ===\n", con.execute("DESCRIBE live_trades").fetchdf().to_string())
    df = con.execute(
        "SELECT * FROM live_trades WHERE status = 'CLOSED' ORDER BY timestamp_close DESC LIMIT 5"
    ).fetchdf()
    print("\n=== sample CLOSED (5 rows) ===\n", df.to_string())
    con.close()


if __name__ == "__main__":
    main()
