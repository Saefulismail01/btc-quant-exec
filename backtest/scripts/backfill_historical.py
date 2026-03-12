"""
backfill_historical.py
──────────────────────────────────────────────────────────────────────────────
Fetch historical BTC/USDT 4h OHLCV dari Binance USDT-M Futures
(fapi.binance.com) dan insert ke DuckDB btc_ohlcv_4h.

Source: fapi.binance.com/fapi/v1/klines — same as production gateway.
CVD dihitung dari taker_buy_volume (kolom k[9]), sama dengan BinanceGateway.

Usage:
    python backtest/scripts/backfill_historical.py
    python backtest/scripts/backfill_historical.py --start 2019-09-13 --end 2022-11-18
    python backtest/scripts/backfill_historical.py --dry-run
"""

import argparse
import sys
import time
import logging
import warnings
from datetime import datetime, timezone
from pathlib import Path

import requests
import duckdb
import pandas as pd

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# ── Path setup ─────────────────────────────────────────────────────────────────
_SCRIPT_DIR   = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent
_BACKEND_DIR  = str(_PROJECT_ROOT / "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.adapters.repositories.market_repository import MarketRepository

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(
        open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
    )],
)
log = logging.getLogger("backfill")

# ── Constants ──────────────────────────────────────────────────────────────────
FAPI_URL    = "https://fapi.binance.com/fapi/v1/klines"
SYMBOL      = "BTCUSDT"
INTERVAL    = "4h"
BATCH_LIMIT = 1500    # Binance Futures max per request
SLEEP_SEC   = 0.4     # rate-limit friendly

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

DEFAULT_START_STR = "2019-09-13"   # Genesis Binance USDT-M Futures
DEFAULT_END_STR   = "2022-11-18"   # Awal data produksi di DuckDB


# ══════════════════════════════════════════════════════════════════════════════
#  FETCHER — Binance Futures fapi/v1/klines
# ══════════════════════════════════════════════════════════════════════════════

def fetch_binance_futures(start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    """
    Fetch 4H klines dari Binance USDT-M Futures.
    Iterasi maju dari start_dt ke end_dt.
    CVD = 2*taker_buy_vol - total_vol (identik dengan BinanceGateway produksi).
    """
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms   = int(end_dt.timestamp()   * 1000)

    all_rows  = []
    cursor    = start_ms
    total     = 0

    log.info(f"Source: fapi.binance.com | {start_dt.date()} → {end_dt.date()}")

    while cursor < end_ms:
        try:
            resp = requests.get(
                FAPI_URL,
                params={
                    "symbol":    SYMBOL,
                    "interval":  INTERVAL,
                    "startTime": cursor,
                    "endTime":   end_ms,
                    "limit":     BATCH_LIMIT,
                },
                headers=HEADERS,
                verify=False,
                timeout=15,
            )
            resp.raise_for_status()
            klines = resp.json()
        except Exception as e:
            log.warning(f"Request error: {e} — retrying in 5s")
            time.sleep(5)
            continue

        if not klines:
            log.info("  -> Exchange returned empty response. Done.")
            break

        for k in klines:
            ts         = int(k[0])
            total_vol  = float(k[5])
            taker_buy  = float(k[9])
            cvd        = 2 * taker_buy - total_vol
            all_rows.append([
                ts,
                float(k[1]),  # open
                float(k[2]),  # high
                float(k[3]),  # low
                float(k[4]),  # close
                total_vol,
                cvd,
            ])

        total += len(klines)
        last_ts  = klines[-1][0]
        last_dt  = pd.to_datetime(last_ts, unit="ms", utc=True)
        log.info(
            f"  -> Fetched {len(klines):4d} candles | "
            f"last: {last_dt.strftime('%Y-%m-%d %H:%M')} | "
            f"total: {total:,}"
        )

        if len(klines) < BATCH_LIMIT:
            break  # Last batch, no more data

        # Lanjutkan dari candle berikutnya setelah yang terakhir
        cursor = last_ts + 1
        time.sleep(SLEEP_SEC)

    if not all_rows:
        log.warning("No data fetched.")
        return pd.DataFrame()

    df = pd.DataFrame(all_rows, columns=["timestamp", "open", "high", "low", "close", "volume", "cvd"])
    df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")

    # Buang candle yang melewati end_ms
    df = df[df["timestamp"] < end_ms]

    log.info(f"Total 4H candles fetched: {len(df):,}")
    return df


# ══════════════════════════════════════════════════════════════════════════════
#  DB HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def get_db_range(db_path: str) -> tuple:
    with duckdb.connect(db_path, read_only=True) as con:
        row = con.execute(
            "SELECT MIN(timestamp), MAX(timestamp), COUNT(*) FROM btc_ohlcv_4h"
        ).fetchone()
    return row


def insert_to_duckdb(df: pd.DataFrame, db_path: str) -> int:
    """Upsert DataFrame ke btc_ohlcv_4h. Idempotent."""
    if df.empty:
        return 0
    df = df[["timestamp", "open", "high", "low", "close", "volume", "cvd"]]
    with duckdb.connect(db_path) as con:
        con.execute("INSERT OR REPLACE INTO btc_ohlcv_4h SELECT * FROM df")
    return len(df)


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Backfill historical BTCUSDT 4h Futures data into DuckDB"
    )
    parser.add_argument(
        "--start", default=DEFAULT_START_STR,
        help=f"Start date YYYY-MM-DD (default: {DEFAULT_START_STR})",
    )
    parser.add_argument(
        "--end", default=DEFAULT_END_STR,
        help=f"End date YYYY-MM-DD exclusive (default: {DEFAULT_END_STR})",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Fetch data tapi TIDAK tulis ke DB",
    )
    args = parser.parse_args()

    start_dt = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end_dt   = datetime.strptime(args.end,   "%Y-%m-%d").replace(tzinfo=timezone.utc)

    if start_dt >= end_dt:
        log.error("--start harus lebih kecil dari --end")
        sys.exit(1)

    # ── Status DB saat ini ──────────────────────────────────────────────────
    repo    = MarketRepository()
    db_path = repo.db_path
    log.info(f"DB: {db_path}")

    min_ts, max_ts, count = get_db_range(db_path)
    if count:
        log.info(
            f"Existing DB : {pd.to_datetime(min_ts, unit='ms', utc=True).date()} "
            f"to {pd.to_datetime(max_ts, unit='ms', utc=True).date()} "
            f"({count:,} candles)"
        )
    else:
        log.info("DB kosong.")

    log.info(f"Backfill    : {start_dt.date()} to {end_dt.date()}")
    log.info("-" * 60)

    # ── Fetch dari Binance Futures ───────────────────────────────────────────
    df = fetch_binance_futures(start_dt, end_dt)
    if df.empty:
        log.error("Tidak ada data. Abort.")
        sys.exit(1)

    log.info("-" * 60)
    log.info(f"4H candles  : {len(df):,}")
    log.info(f"Range       : {pd.to_datetime(df['timestamp'].min(), unit='ms', utc=True)} "
             f"to {pd.to_datetime(df['timestamp'].max(), unit='ms', utc=True)}")
    log.info(f"Price range : ${df['close'].min():,.0f} to ${df['close'].max():,.0f}")
    log.info(f"CVD range   : {df['cvd'].min():.1f} to {df['cvd'].max():.1f}")
    log.info("-" * 60)

    if args.dry_run:
        log.info("[DRY RUN] Tidak menulis ke DB.")
        print(df.head(10).to_string(index=False))
        return

    # ── Insert ke DuckDB ────────────────────────────────────────────────────
    inserted = insert_to_duckdb(df, db_path)
    log.info(f"[OK] Inserted/updated {inserted:,} candles ke btc_ohlcv_4h")

    # ── Verifikasi akhir ────────────────────────────────────────────────────
    min_ts2, max_ts2, count2 = get_db_range(db_path)
    log.info(
        f"DB sekarang : {pd.to_datetime(min_ts2, unit='ms', utc=True).date()} "
        f"to {pd.to_datetime(max_ts2, unit='ms', utc=True).date()} "
        f"({count2:,} candles)"
    )
    log.info("Selesai.")


if __name__ == "__main__":
    main()
