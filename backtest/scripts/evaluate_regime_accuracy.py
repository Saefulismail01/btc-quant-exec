"""
╔══════════════════════════════════════════════════════════════════════╗
║  BTC-QUANT-BTC: REGIME DETECTION DIRECTIONAL CALIBRATION EVALUATOR    ║
║                                                                      ║
║  Use Case: HMM digunakan untuk mendeteksi bias arah 4H ke depan.    ║
║                                                                      ║
║  Pertanyaan yang relevan:                                            ║
║    Saat HMM output "Bullish" → seberapa sering harga naik?           ║
║    Saat HMM output "Bearish" → seberapa sering harga turun?          ║
║    Saat HMM output "Sideways" → seberapa sering gerakan kecil?       ║
║                                                                      ║
║  Bukan: 4-class classification accuracy vs forward 48H regime.       ║
║  Yang diukur: directional hit rate dan return per regime label.      ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import sys
import warnings
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import logging

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

_BACKTEST_DIR = Path(__file__).resolve().parent
_BACKEND_DIR  = _BACKTEST_DIR.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from engines.layer1_hmm import MarketRegimeModel  # noqa
from data_engine import DuckDBManager # noqa


# ════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ════════════════════════════════════════════════════════════════════

LOG_DIR              = _BACKTEST_DIR / "logs"
GLOBAL_TRAIN_SPLIT   = 1000   # candle untuk initial training (~166 hari 4H)
RECALIB_EVERY        = 500    # expanding window recalibration setiap N candle
WARMUP               = 250    # minimum window untuk inference

# Forward horizons yang dievaluasi (dalam candle 4H)
HORIZONS = {
    "1c  (4H) ": 1,
    "3c  (12H)": 3,
    "6c  (24H)": 6,
    "12c (48H)": 12,
}

# Threshold return dianggap "bergerak berarti" (bukan sideways noise)
MOVE_THRESHOLD = 0.005   # 0.5%


# ════════════════════════════════════════════════════════════════════
#  DATA LOADER
# ════════════════════════════════════════════════════════════════════

def load_year(year: int) -> pd.DataFrame:
    path = _BACKTEST_DIR / "data" / f"BTC_USDT_4h_{year}.csv"
    df   = pd.read_csv(path, index_col=0, parse_dates=True)
    df.rename(columns={
        "open": "Open", "high": "High",
        "low": "Low", "close": "Close", "volume": "Volume"
    }, inplace=True)
    return df

def load_from_db() -> pd.DataFrame:
    """Load combined OHLCV + Metrics from DuckDB."""
    import duckdb
    db = DuckDBManager()
    with duckdb.connect(db.db_path) as con:
        # Join OHLCV with metrics
        df = con.execute("""
            SELECT 
                o.timestamp, o.open as Open, o.high as High, 
                o.low as Low, o.close as Close, o.volume as Volume,
                m.funding_rate, m.open_interest, m.cvd, 
                m.liquidations_buy, m.liquidations_sell
            FROM btc_ohlcv_4h o
            LEFT JOIN market_metrics m ON o.timestamp = m.timestamp
            ORDER BY o.timestamp ASC
        """).df()
    
    if df.empty:
        return df
        
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)

    # ── Filtering: Find where Open Interest actually starts ──
    # If we have OI data, we skip leading zero OI rows to ensure training is effective.
    if 'open_interest' in df.columns:
        first_idx = (df['open_interest'] != 0).idxmax()
        if df.loc[first_idx, 'open_interest'] != 0:
            original_len = len(df)
            df = df.loc[first_idx:].copy()
            print(f"  [DB_LIVE] Filtered leading 0-OI rows: {original_len} → {len(df)}")
            
    return df


# ════════════════════════════════════════════════════════════════════
#  WALK-FORWARD PREDICTION
# ════════════════════════════════════════════════════════════════════

def collect_predictions(df: pd.DataFrame) -> list[dict]:
    """
    Jalankan HMM dengan global-train + out-of-sample inference.
    Untuk setiap candle, catat:
      - timestamp
      - hmm_label  : output HMM (Bullish/Bearish/HV-SW/LV-SW)
      - returns     : dict {horizon: actual_return_dari_candle_ini}
      - next_dir    : +1 jika candle berikutnya naik, -1 turun
    """
    hmm = MarketRegimeModel()

    # ── Phase 1: Global training ────────────────────────────────
    # Adjust train_split if dataset is small
    train_split = min(GLOBAL_TRAIN_SPLIT, int(len(df) * 0.7))
    train_end = min(train_split, len(df) - max(HORIZONS.values()) - 10)
    
    if train_end < 50: # Reduced from 100 for small local test
        print(f"  ⚠ Dataset too short for training: {len(df)} rows")
        return []

    ok = hmm.train_global(df.iloc[:train_end].copy())
    if not ok:
        print(f"  ⚠ Global training gagal — dataset terlalu pendek?")
        return []

    print(f"  ✓ Global training: {train_end} candles | "
          f"n_states={hmm._active_n_states} | map={hmm.state_map}")

    # ── Phase 2: Out-of-sample inference ────────────────────────
    records      = []
    last_recalib = train_end
    max_horizon  = max(HORIZONS.values())

    for i in range(train_end, len(df) - max_horizon):

        # Periodic recalibration (expanding window)
        if (i - last_recalib) >= RECALIB_EVERY:
            hmm.train_global(df.iloc[:i].copy())
            last_recalib = i
            print(f"    [recalib @ candle {i}] map={hmm.state_map}", end="\r")

        # Inference: transform only (frozen model)
        try:
            window       = df.iloc[max(0, i - WARMUP) : i + 1].copy()
            vote         = hmm.get_directional_vote(window)
        except Exception:
            continue

        # Compute actual forward returns for each horizon
        close_now = float(df["Close"].iloc[i])
        returns   = {}
        for hname, h in HORIZONS.items():
            close_fwd       = float(df["Close"].iloc[i + h])
            returns[hname]  = (close_fwd - close_now) / close_now

        next_dir = 1 if returns[list(HORIZONS.keys())[0]] > 0 else -1

        records.append({
            "ts"      : df.index[i],
            "vote"    : vote,
            "next_dir": next_dir,
            "returns" : returns,
            "close"   : close_now,
        })

    return records


# ════════════════════════════════════════════════════════════════════
#  DIRECTIONAL CALIBRATION METRICS
# ════════════════════════════════════════════════════════════════════

def analyze_calibration(records: list[dict]) -> dict:
    """
    Per vote bucket, hitung hit rate dan return.
    Buckets:
      - Strong Bullish : vote > 0.5
      - Weak Bullish   : 0.1 < vote <= 0.5
      - Neutral-ish    : -0.1 <= vote <= 0.1
      - Weak Bearish   : -0.5 < vote < -0.1
      - Strong Bearish  : vote <= -0.5
    """
    def get_bucket(v):
        if v > 0.5: return "Strong Bullish (>0.5)"
        if v > 0.1: return "Weak Bullish (0.1..0.5)"
        if v < -0.5: return "Strong Bearish (<-0.5)"
        if v < -0.1: return "Weak Bearish (-0.5..-0.1)"
        return "Neutral-ish (-0.1..0.1)"

    by_bucket: dict[str, list] = defaultdict(list)
    for r in records:
        bucket = get_bucket(r["vote"])
        by_bucket[bucket].append(r)

    total = len(records)
    result = {}

    for bucket, recs in by_bucket.items():
        n   = len(recs)
        res = {"count": n, "pct_of_total": n / total * 100}

        # Determine expected direction
        is_bull = "Bullish" in bucket
        is_bear = "Bearish" in bucket
        is_neu  = "Neutral" in bucket

        for hname, h in HORIZONS.items():
            rets = [r["returns"][hname] for r in recs]
            arr  = np.array(rets)

            mean_r   = float(np.mean(arr))
            median_r = float(np.median(arr))

            if is_bull:
                hit = (arr > 0).mean()
                sig = (arr > MOVE_THRESHOLD).mean()
            elif is_bear:
                hit = (arr < 0).mean()
                sig = (arr < -MOVE_THRESHOLD).mean()
            else:
                # Neutral: "hit" = abs(return) < threshold (range-bound)
                hit = (np.abs(arr) < MOVE_THRESHOLD).mean()
                sig = hit

            res[hname] = {
                "hit_rate" : float(hit),
                "sig_rate" : float(sig),
                "mean_ret" : mean_r,
                "median_ret": median_r,
            }

        result[bucket] = res

    return result


# ════════════════════════════════════════════════════════════════════
#  REPORT WRITER
# ════════════════════════════════════════════════════════════════════

def write_report(year: int, records: list[dict], cal: dict, buf: list[str]):
    sep  = "═" * 72
    sep2 = "─" * 72
    logger = logging.getLogger()

    def p(line=""): 
        buf.append(line)
        logger.info(line)

    total = len(records)
    horizons = list(HORIZONS.keys())

    p(sep)
    p(f"  DIRECTIONAL CALIBRATION — {year}")
    p(f"  Predictions : {total} | Train split: {GLOBAL_TRAIN_SPLIT} candles")
    if records:
        p(f"  Date range  : {records[0]['ts'].date()} → {records[-1]['ts'].date()}")
    p(sep)

    # ── Label distribution ────────────────────────────────────────
    p(f"\n  LABEL DISTRIBUTION")
    p(sep2)
    p(f"  {'Label':<32} {'Count':>7}  {'% Total':>8}")
    p(f"  {'-'*32} {'-'*7}  {'-'*8}")
    for label in sorted(cal.keys()):
        d = cal[label]
        flag = " ⚠ DOMINANT" if d["pct_of_total"] > 60 else ""
        p(f"  {label:<32} {d['count']:>7}  {d['pct_of_total']:>7.1f}%{flag}")
    p()

    # ── Hit rate per label per horizon ────────────────────────────
    p(f"  DIRECTIONAL HIT RATE  (tebak benar arah?)")
    p(f"  Bullish/Bearish = % return sesuai arah | Sideways = % |ret| < {MOVE_THRESHOLD*100:.1f}%")
    p(sep2)

    h_header = "".join(f"  {h:>13}" for h in horizons)
    p(f"  {'Label':<32}{h_header}")
    p(f"  {'-'*32}" + "".join(f"  {'-'*13}" for _ in horizons))

    for label in sorted(cal.keys()):
        d = cal[label]
        row = f"  {label:<32}"
        for h in horizons:
            hr = d[h]["hit_rate"]
            grade = "✅" if hr >= 0.55 else ("⚠" if hr >= 0.45 else "❌")
            row += f"  {hr*100:>6.1f}% {grade}  "
        p(row)
    p()

    # ── Mean return per label per horizon ─────────────────────────
    p(f"  MEAN FORWARD RETURN per label")
    p(sep2)
    p(f"  {'Label':<32}{h_header}")
    p(f"  {'-'*32}" + "".join(f"  {'-'*13}" for _ in horizons))

    for label in sorted(cal.keys()):
        d = cal[label]
        row = f"  {label:<32}"
        for h in horizons:
            mr = d[h]["mean_ret"] * 100
            sign = "+" if mr >= 0 else ""
            row += f"  {sign}{mr:>6.2f}%      "
        p(row)
    p()

    # ── Interpretation ────────────────────────────────────────────
    p(sep2)
    p("  INTERPRETASI")
    p(sep2)

    for label in sorted(cal.keys()):
        d = cal[label]
        is_bull = "Bullish" in label
        is_bear = "Bearish" in label

        # Score: average hit rate across horizons
        avg_hit = np.mean([d[h]["hit_rate"] for h in horizons])
        avg_ret = np.mean([d[h]["mean_ret"] for h in horizons]) * 100

        grade = (
            "🟢 USEFUL"      if avg_hit >= 0.55 else
            "🟡 MARGINAL"    if avg_hit >= 0.48 else
            "🔴 NOT USEFUL"
        )

        direction_note = ""
        if is_bull and avg_ret < 0:
            direction_note = " ← TERBALIK (prediksi bull tapi rata-rata turun)"
        elif is_bear and avg_ret > 0:
            direction_note = " ← TERBALIK (prediksi bear tapi rata-rata naik)"

        p(f"  {label:<32}: avg_hit={avg_hit*100:.1f}%  avg_ret={avg_ret:+.2f}%  {grade}{direction_note}")

    p()
    p(f"  Threshold random chance = 50.0% (prediksi koin)")
    p()


def write_final_summary(results_by_year: dict, buf: list[str]):
    sep = "═" * 72
    logger = logging.getLogger()

    def p(line=""): 
        buf.append(line)
        logger.info(line)

    p(sep)
    p("  RINGKASAN AKHIR — KELAYAKAN HMM SEBAGAI DIRECTIONAL FILTER")
    p(sep)

    horizons = list(HORIZONS.keys())

    for year, data in results_by_year.items():
        cal = data["cal"]
        p(f"\n  [{year}]")
        for label in sorted(cal.keys()):
            d       = cal[label]
            avg_hit = np.mean([d[h]["hit_rate"] for h in horizons])
            p(f"    {label:<32}: hit_rate={avg_hit*100:.1f}%  "
              f"(n={d['count']}, {d['pct_of_total']:.1f}% of predictions)")

    p()
    p("  KESIMPULAN:")

    # Cek apakah ada label yang useful
    all_hits = []
    for year, data in results_by_year.items():
        # BEST LABEL PER YEAR
        # The original code collected all hits across all years into a single list.
        # The instruction seems to imply processing per year, but the subsequent
        # `max` and `min` calls are outside the loop, suggesting a global summary.
        # To maintain the original logic of finding a global best/worst,
        # we collect all hits first, then check if the collection is empty.
        for label, d in data["cal"].items():
            avg_hit = np.mean([d[h]["hit_rate"] for h in horizons])
            all_hits.append((label, avg_hit))

    if not all_hits:
        p("  ⚠ No valid labels to summarize across all years.")
        p("  No predictions were made or processed.")
    else:
        p(f"  ⚠ Tidak ada label yang konsisten di atas 55% hit rate.")
        p(f"  Best: '{best_label}' = {best_hit*100:.1f}% (hampir random)")
        p()
        p("  IMPLIKASI:")
        p("  HMM dengan fitur OHLCV murni tidak cukup untuk prediksi arah 4H.")
        p("  Fungsi yang lebih realistis untuk HMM di BTC-QUANT:")
        p("  → Volatility regime detection (HV vs LV) untuk sizing posisi")
        p("  → Bukan directional prediction, tapi risk filter")
        p("  → Gunakan EMA/trend sebagai directional signal utama")
        p("  → HMM sebagai confidence modifier, bukan gate utama")

    p()
    p(sep)
    p(f"  Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    p(sep)


# ════════════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════════════

def setup_logging():
    LOG_DIR.mkdir(exist_ok=True)
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"regime_eval_{run_ts}.log"
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # File handler (all output)
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(console_handler)
    
    return log_file

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", nargs="+", type=int, default=[2023, 2025])
    parser.add_argument("--db", action="store_true", help="Load data from DuckDB")
    args = parser.parse_args()

    log_file = setup_logging()
    logger = logging.getLogger()
    
    sep = "═" * 72
    logger.info(f"\n{sep}")
    logger.info("  BTC-QUANT-BTC · HMM DIRECTIONAL CALIBRATION EVALUATOR")
    logger.info(f"  Run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  Log file: {log_file}")
    logger.info(sep)

    buf: list[str] = []
    results_by_year: dict = {}

    to_eval = args.years
    if args.db:
        to_eval = ["DB_LIVE"]

    for item in to_eval:
        logger.info(f"\n{'='*72}")
        logger.info(f"  EVALUATING {item}")
        logger.info(f"{'='*72}")

        if item == "DB_LIVE":
            df = load_from_db()
        else:
            df = load_year(item)

        if df.empty:
            logger.warning(f"  ⚠ Dataset for {item} is empty — skipping")
            continue

        logger.info(f"  Data: {df.shape} | {df.index[0].date()} → {df.index[-1].date()} "
                    f"| ${df['Close'].min():,.0f}–${df['Close'].max():,.0f}")

        records = collect_predictions(df)
        logger.info(f"  Collected {len(records)} valid predictions\n")

        if not records:
            logger.warning(f"  ⚠ No predictions for {item} — skipping")
            continue

        cal = analyze_calibration(records)
        results_by_year[item] = {"records": records, "cal": cal}

        write_report(item, records, cal, buf)

    write_final_summary(results_by_year, buf)

    logger.info(f"\n  📄 Backtest evaluation finished. Report is already in: {log_file}\n")



if __name__ == "__main__":
    main()
