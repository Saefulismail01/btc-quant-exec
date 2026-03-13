"""
╔══════════════════════════════════════════════════════════════╗
║  BTC-QUANT: HISTORICAL DATA BACKFILL (I-08)                 ║
║  Target: 2000+ candle 4H (~333 hari)                        ║
║                                                              ║
║  Perbaikan dari backfill_data.py original:                  ║
║  1. Pagination otomatis (2000 candle via 2x fetch)          ║
║  2. Funding rate history di-fetch bulk via endpoint resmi   ║
║  3. Open Interest history dengan alignment timestamp        ║
║  4. Progress bar per batch                                  ║
║  5. Idempotent — aman dijalankan berulang kali (upsert)     ║
║  6. Proxy support dari .env                                 ║
║                                                              ║
║  Usage:                                                     ║
║      cd backend                                             ║
║      python backfill_historical.py                          ║
║                                                              ║
║  Output:                                                    ║
║      btc-quant.db tabel btc_ohlcv_4h    (target: 2000 row) ║
║      btc-quant.db tabel market_metrics  (funding + OI)     ║
╚══════════════════════════════════════════════════════════════╝
"""

import asyncio
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import duckdb
import pandas as pd
import numpy as np

# ── Path setup ────────────────────────────────────────────────────────────────
_BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND_DIR))
from dotenv import load_dotenv
load_dotenv(_BACKEND_DIR / ".env")

import ccxt.async_support as ccxt

# ════════════════════════════════════════════════════════════
#  KONFIGURASI
# ════════════════════════════════════════════════════════════

SYMBOL       = "BTC/USDT"
PERP_SYMBOL  = "BTC/USDT:USDT"
TIMEFRAME    = "4h"
DB_PATH      = str(_BACKEND_DIR / "btc-quant.db")

# Target candle historis
# 2000 candle 4H ≈ 333 hari ≈ lebih dari 1 siklus bull-bear BTC
TARGET_CANDLES = 2000

# Binance max per request = 1500 (4h), kita pakai 1000 untuk safety
BATCH_SIZE = 1000

# Jeda antar request (ms) — hindari rate limit
REQUEST_DELAY_MS = 500


# ════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════

def _log(tag: str, msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  [{ts}] [{tag}] {msg}")


def _get_exchange() -> ccxt.Exchange:
    """Buat instance Binance dengan proxy optional dari .env."""
    http_proxy  = os.getenv("HTTP_PROXY",  "").strip()
    https_proxy = os.getenv("HTTPS_PROXY", "").strip()

    config: dict = {
        "enableRateLimit": True,
        "options": {"defaultType": "future"},
    }
    if http_proxy or https_proxy:
        config["proxies"] = {
            "http":  http_proxy  or https_proxy,
            "https": https_proxy or http_proxy,
        }
        config["aiohttp_proxy"] = https_proxy or http_proxy
        _log("Exchange", f"Proxy aktif: {https_proxy or http_proxy}")

    return ccxt.binance(config)


def _count_existing(db_path: str) -> int:
    """Hitung candle yang sudah ada di DB."""
    try:
        with duckdb.connect(db_path, read_only=True) as con:
            result = con.execute("SELECT COUNT(*) FROM btc_ohlcv_4h").fetchone()
            return int(result[0]) if result else 0
    except Exception:
        return 0


def _get_oldest_timestamp(db_path: str) -> int | None:
    """Ambil timestamp terlama di DB (untuk fetch data lebih lama)."""
    try:
        with duckdb.connect(db_path, read_only=True) as con:
            result = con.execute(
                "SELECT MIN(timestamp) FROM btc_ohlcv_4h"
            ).fetchone()
            return int(result[0]) if result and result[0] else None
    except Exception:
        return None


def _upsert_ohlcv_batch(db_path: str, rows: list[tuple]):
    """Upsert batch OHLCV ke DB."""
    if not rows:
        return
    with duckdb.connect(db_path) as con:
        con.executemany("""
            INSERT OR REPLACE INTO btc_ohlcv_4h
            (timestamp, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?)
        """, rows)


def _upsert_metrics_batch(db_path: str, rows: list[tuple]):
    """Upsert batch metrics ke DB (funding + OI)."""
    if not rows:
        return
    with duckdb.connect(db_path) as con:
        con.executemany("""
            INSERT OR REPLACE INTO market_metrics
            (timestamp, funding_rate, open_interest, global_mcap_change,
             order_book_imbalance, cvd, liquidations_buy, liquidations_sell)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)


def _ensure_tables(db_path: str):
    """Pastikan tabel ada sebelum insert."""
    with duckdb.connect(db_path) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS btc_ohlcv_4h (
                timestamp   BIGINT PRIMARY KEY,
                open        DOUBLE,
                high        DOUBLE,
                low         DOUBLE,
                close       DOUBLE,
                volume      DOUBLE
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
                liquidations_sell     DOUBLE
            )
        """)


# ════════════════════════════════════════════════════════════
#  MAIN BACKFILL
# ════════════════════════════════════════════════════════════

async def backfill():
    print("\n" + "═"*60)
    print("  BTC-QUANT · Historical Data Backfill (I-08)")
    print("═"*60)

    _ensure_tables(DB_PATH)

    existing = _count_existing(DB_PATH)
    _log("DB", f"Candle existing: {existing}")

    if existing >= TARGET_CANDLES:
        _log("DB", f"✅ Sudah {existing} candle (target {TARGET_CANDLES}). Tidak perlu backfill.")
        return

    needed = TARGET_CANDLES - existing
    _log("DB", f"Butuh {needed} candle lagi → mulai fetch...")

    exchange = _get_exchange()

    try:
        # ── FASE 1: Fetch OHLCV via pagination ───────────────────────────────
        print(f"\n  ── Fase 1: OHLCV (target {TARGET_CANDLES} candle) ──────────────")

        all_ohlcv: list[tuple] = []
        oldest_ts = _get_oldest_timestamp(DB_PATH)

        # Iterasi backward: fetch batch lama hingga target terpenuhi
        batches_done = 0
        max_batches  = (TARGET_CANDLES // BATCH_SIZE) + 2  # safety cap

        while (existing + len(all_ohlcv)) < TARGET_CANDLES and batches_done < max_batches:
            try:
                kwargs: dict = {"limit": BATCH_SIZE}

                # Jika ada data existing, fetch sebelum timestamp terlama
                if oldest_ts is not None and batches_done == 0:
                    # Mulai dari sebelum data terlama yang ada
                    kwargs["since"] = oldest_ts - (BATCH_SIZE * 4 * 3600 * 1000)
                elif oldest_ts is not None:
                    kwargs["since"] = oldest_ts - ((batches_done + 1) * BATCH_SIZE * 4 * 3600 * 1000)
                else:
                    # Tidak ada data: mulai dari TARGET_CANDLES candle ke belakang dari sekarang
                    since_ms = int(
                        (datetime.now(timezone.utc)
                         - timedelta(hours=4 * TARGET_CANDLES)).timestamp() * 1000
                    )
                    kwargs["since"] = since_ms

                raw = await exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, **kwargs)

                if not raw:
                    _log("OHLCV", "Tidak ada candle baru dari exchange.")
                    break

                batch_rows = [
                    (int(c[0]), float(c[1]), float(c[2]),
                     float(c[3]), float(c[4]), float(c[5]))
                    for c in raw
                ]

                all_ohlcv.extend(batch_rows)
                batches_done += 1
                total_so_far = existing + len(set(r[0] for r in all_ohlcv))

                _log("OHLCV",
                     f"Batch {batches_done}: +{len(batch_rows)} candle "
                     f"| Total ~{total_so_far}/{TARGET_CANDLES} "
                     f"| Dari: {datetime.fromtimestamp(batch_rows[0][0]/1000).strftime('%Y-%m-%d')}"
                )

                # Update oldest_ts untuk iterasi berikutnya
                if batch_rows:
                    oldest_ts = min(r[0] for r in batch_rows)

                await asyncio.sleep(REQUEST_DELAY_MS / 1000)

            except Exception as e:
                _log("OHLCV", f"⚠ Fetch error: {e}")
                await asyncio.sleep(3)
                break

        # Deduplicate dan upsert
        unique_ohlcv = {r[0]: r for r in all_ohlcv}  # keyed by timestamp
        rows_to_insert = list(unique_ohlcv.values())

        if rows_to_insert:
            _upsert_ohlcv_batch(DB_PATH, rows_to_insert)
            _log("OHLCV", f"✅ Upserted {len(rows_to_insert)} candle baru ke DB")
        else:
            _log("OHLCV", "⚠ Tidak ada candle baru untuk diinsert.")

        final_count = _count_existing(DB_PATH)
        _log("DB", f"Total OHLCV setelah backfill: {final_count} candle")

        # ── FASE 2: Funding Rate History ──────────────────────────────────────
        print(f"\n  ── Fase 2: Funding Rate History ──────────────────────────")

        funding_map: dict[int, float] = {}

        try:
            # Fetch semua funding rate history yang tersedia
            # Binance menyimpan hingga 500 record per request, 8 jam per entry
            # Untuk 2000 candle 4H: 2000 * 4h / 8h = 1000 funding entries
            fr_raw = await exchange.fetch_funding_rate_history(
                PERP_SYMBOL, limit=1000
            )

            for entry in fr_raw:
                ts_ms    = int(entry.get("timestamp", 0))
                fr_val   = float(entry.get("fundingRate", 0.0))
                if ts_ms:
                    funding_map[ts_ms] = fr_val

            _log("Funding", f"Fetched {len(funding_map)} funding rate entries")

        except Exception as e:
            _log("Funding", f"⚠ Tidak bisa fetch funding history: {e}. Akan diisi 0.0.")

        # ── FASE 3: Open Interest History ─────────────────────────────────────
        print(f"\n  ── Fase 3: Open Interest History ─────────────────────────")

        oi_map: dict[int, float] = {}

        try:
            oi_raw = await exchange.fetch_open_interest_history(
                PERP_SYMBOL, TIMEFRAME, limit=BATCH_SIZE
            )

            for entry in oi_raw:
                ts_ms  = int(entry.get("timestamp", 0))
                oi_val = float(entry.get("openInterestAmount",
                               entry.get("openInterest", 0.0)))
                if ts_ms:
                    oi_map[ts_ms] = oi_val

            _log("OI", f"Fetched {len(oi_map)} open interest entries")

        except Exception as e:
            _log("OI", f"⚠ Tidak bisa fetch OI history: {e}. Akan diisi 0.0.")

        # ── FASE 4: Assemble dan upsert metrics ───────────────────────────────
        print(f"\n  ── Fase 4: Assembling metrics table ──────────────────────")

        # Ambil semua timestamp OHLCV dari DB (termasuk yang baru)
        with duckdb.connect(DB_PATH, read_only=True) as con:
            ts_rows = con.execute(
                "SELECT timestamp FROM btc_ohlcv_4h ORDER BY timestamp ASC"
            ).fetchall()
        all_ts = [r[0] for r in ts_rows]

        # Sort funding & OI maps untuk nearest-neighbor lookup
        sorted_funding_ts = sorted(funding_map.keys())
        sorted_oi_ts      = sorted(oi_map.keys())

        def _nearest(sorted_keys: list[int], target: int) -> float | None:
            """Cari nilai terdekat dari target timestamp."""
            if not sorted_keys:
                return None
            # Binary search sederhana
            lo, hi = 0, len(sorted_keys) - 1
            best   = sorted_keys[0]
            while lo <= hi:
                mid = (lo + hi) // 2
                if abs(sorted_keys[mid] - target) < abs(best - target):
                    best = sorted_keys[mid]
                if sorted_keys[mid] < target:
                    lo = mid + 1
                else:
                    hi = mid - 1
            # Hanya pakai jika dalam rentang 1 periode (4H = 14400000ms)
            if abs(best - target) <= 14_400_000:
                return best
            return None

        metrics_rows: list[tuple] = []
        for ts in all_ts:
            # Funding rate: funding 8H terdekat
            fr_ts  = _nearest(sorted_funding_ts, ts)
            fr_val = funding_map.get(fr_ts, 0.0) if fr_ts else 0.0

            # Open interest: 4H terdekat
            oi_ts  = _nearest(sorted_oi_ts, ts)
            oi_val = oi_map.get(oi_ts, 0.0) if oi_ts else 0.0

            metrics_rows.append((
                ts,
                fr_val,  # funding_rate
                oi_val,  # open_interest
                0.0,     # global_mcap_change (tidak tersedia bulk historis)
                0.0,     # order_book_imbalance (snapshot realtime only)
                0.0,     # cvd
                0.0,     # liquidations_buy
                0.0,     # liquidations_sell
            ))

        _upsert_metrics_batch(DB_PATH, metrics_rows)
        _log("Metrics", f"✅ Upserted {len(metrics_rows)} metrics rows")

        # ── FASE 5: Verifikasi final ───────────────────────────────────────────
        print(f"\n  ── Fase 5: Verifikasi ────────────────────────────────────")

        with duckdb.connect(DB_PATH, read_only=True) as con:
            n_ohlcv = con.execute(
                "SELECT COUNT(*) FROM btc_ohlcv_4h"
            ).fetchone()[0]
            n_metrics = con.execute(
                "SELECT COUNT(*) FROM market_metrics"
            ).fetchone()[0]
            oldest = con.execute(
                "SELECT MIN(timestamp) FROM btc_ohlcv_4h"
            ).fetchone()[0]
            newest = con.execute(
                "SELECT MAX(timestamp) FROM btc_ohlcv_4h"
            ).fetchone()[0]
            fr_nonzero = con.execute(
                "SELECT COUNT(*) FROM market_metrics WHERE funding_rate != 0.0"
            ).fetchone()[0]
            oi_nonzero = con.execute(
                "SELECT COUNT(*) FROM market_metrics WHERE open_interest != 0.0"
            ).fetchone()[0]

        oldest_dt = datetime.fromtimestamp(oldest / 1000).strftime("%Y-%m-%d") if oldest else "N/A"
        newest_dt = datetime.fromtimestamp(newest / 1000).strftime("%Y-%m-%d") if newest else "N/A"

        print()
        print(f"  {'═'*50}")
        print(f"  BACKFILL SELESAI")
        print(f"  {'═'*50}")
        print(f"  OHLCV candle     : {n_ohlcv:,} ({'✅ OK' if n_ohlcv >= 500 else '⚠ Kurang dari 500'})")
        print(f"  Range data       : {oldest_dt} → {newest_dt}")
        print(f"  Metrics rows     : {n_metrics:,}")
        print(f"  Funding non-zero : {fr_nonzero:,} rows")
        print(f"  OI non-zero      : {oi_nonzero:,} rows")
        print()

        # ── Status untuk langkah berikutnya ──────────────────────────────────
        if n_ohlcv >= 1000:
            print("  ✅ Data mencukupi untuk I-00 dan walk-forward test.")
            print("  Langkah berikutnya:")
            print("    python backtest/hmm_predictive_power_test.py")
        elif n_ohlcv >= 500:
            print("  ⚠ Data cukup untuk I-00 tapi kurang ideal untuk walk-forward.")
            print("  Pertimbangkan jalankan backfill lagi nanti atau tambah BATCH_SIZE.")
            print("  Langkah berikutnya:")
            print("    python backtest/hmm_predictive_power_test.py")
        else:
            print("  ❌ Data masih kurang dari 500. Cek koneksi atau proxy Binance.")
            print("  Jalankan ulang script ini setelah memastikan koneksi aktif.")

        print(f"  {'═'*50}\n")

    finally:
        await exchange.close()


# ════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    start = time.time()
    asyncio.run(backfill())
    elapsed = time.time() - start
    print(f"  ⏱ Total waktu: {elapsed:.1f} detik\n")
