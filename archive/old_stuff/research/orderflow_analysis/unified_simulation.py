"""
unified_simulation.py
=====================
Definitive strategy comparison simulation for BTC-QUANT v4.4.
ONE script, ONE data source, ONE granularity (15m Binance klines).
ALL models use identical data and identical simulation logic.

Models compared:
  - Model A:      Pure auto (TP=+0.71%, SL=-1.333%, 24h time exit)
  - Model B:      Actual manual (use real trade outcomes as-is)
  - Model V3:     Profit protection (exit at +0.15% if peak>=0.30% then retraces)
  - Model V3+OF:  V3 + orderflow filter (OF4/OF5 must fire before exiting)

Author: BTC-QUANT research
Date: 2026-03-31
"""

import os
import json
import time
import math
import random
import urllib.request
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).parent / "data" / "unified"
DATA_DIR.mkdir(parents=True, exist_ok=True)

BINANCE_KLINE_URL = (
    "https://api.binance.com/api/v3/klines"
    "?symbol=BTCUSDT&interval=15m&startTime={start_ms}&limit=100"
)

SL_PCT   = -0.01333   # -1.333%
TP_PCT   = +0.0071    # +0.71%
PP_ACTIVATE   = 0.0030   # profit-protection activates at peak >= 0.30%
PP_EXIT_LEVEL = 0.0015   # exit if candle close pnl drops to 0.15%
MAX_CANDLES   = 96       # 24 hours of 15m candles

MONTE_N_PATHS  = 1000
MONTE_N_TRADES = 100

# ---------------------------------------------------------------------------
# Trade definitions
# ---------------------------------------------------------------------------
trades = [
    {"id": 1,  "date": "2026-03-10 16:05", "side": "LONG",  "entry": 71198, "actual_pnl_pct": -1.20, "actual_exit": "MANUAL_LOSS"},
    {"id": 2,  "date": "2026-03-11 04:08", "side": "LONG",  "entry": 69498, "actual_pnl_pct": +0.73, "actual_exit": "TP"},
    {"id": 3,  "date": "2026-03-11 08:06", "side": "LONG",  "entry": 69620, "actual_pnl_pct": +0.24, "actual_exit": "MANUAL"},
    {"id": 4,  "date": "2026-03-12 08:05", "side": "LONG",  "entry": 69846, "actual_pnl_pct": +0.67, "actual_exit": "TP"},
    {"id": 5,  "date": "2026-03-12 12:15", "side": "LONG",  "entry": 70309, "actual_pnl_pct": -0.68, "actual_exit": "MANUAL_LOSS"},
    {"id": 6,  "date": "2026-03-12 20:09", "side": "LONG",  "entry": 70401, "actual_pnl_pct": +0.77, "actual_exit": "TP"},
    {"id": 7,  "date": "2026-03-13 04:03", "side": "LONG",  "entry": 71347, "actual_pnl_pct": +0.22, "actual_exit": "MANUAL"},
    {"id": 8,  "date": "2026-03-13 08:02", "side": "LONG",  "entry": 71520, "actual_pnl_pct": +0.77, "actual_exit": "TP"},
    {"id": 9,  "date": "2026-03-13 14:13", "side": "LONG",  "entry": 73500, "actual_pnl_pct": +0.34, "actual_exit": "MANUAL"},
    {"id": 10, "date": "2026-03-13 16:02", "side": "LONG",  "entry": 71891, "actual_pnl_pct": -0.67, "actual_exit": "MANUAL_LOSS"},
    {"id": 11, "date": "2026-03-16 08:14", "side": "LONG",  "entry": 73545, "actual_pnl_pct": +0.42, "actual_exit": "MANUAL"},
    {"id": 12, "date": "2026-03-16 16:01", "side": "LONG",  "entry": 73172, "actual_pnl_pct": +0.42, "actual_exit": "MANUAL"},
    {"id": 13, "date": "2026-03-17 00:51", "side": "LONG",  "entry": 74930, "actual_pnl_pct": +0.66, "actual_exit": "TP"},
    {"id": 14, "date": "2026-03-17 02:07", "side": "LONG",  "entry": 75287, "actual_pnl_pct": +0.08, "actual_exit": "MANUAL"},
    {"id": 15, "date": "2026-03-17 04:02", "side": "LONG",  "entry": 74562, "actual_pnl_pct": -0.68, "actual_exit": "MANUAL_LOSS"},
    {"id": 16, "date": "2026-03-17 07:21", "side": "LONG",  "entry": 74319, "actual_pnl_pct": +0.03, "actual_exit": "MANUAL"},
    {"id": 17, "date": "2026-03-17 12:00", "side": "LONG",  "entry": 74013, "actual_pnl_pct": +0.28, "actual_exit": "MANUAL"},
    {"id": 18, "date": "2026-03-22 00:00", "side": "SHORT", "entry": 68744, "actual_pnl_pct": +0.75, "actual_exit": "TP"},
    {"id": 19, "date": "2026-03-22 08:00", "side": "SHORT", "entry": 68860, "actual_pnl_pct": +0.34, "actual_exit": "MANUAL"},
    {"id": 20, "date": "2026-03-22 12:00", "side": "SHORT", "entry": 68217, "actual_pnl_pct": -0.71, "actual_exit": "SL"},
    {"id": 21, "date": "2026-03-23 00:00", "side": "SHORT", "entry": 67975, "actual_pnl_pct": +0.35, "actual_exit": "MANUAL"},
    {"id": 22, "date": "2026-03-26 12:00", "side": "SHORT", "entry": 69215, "actual_pnl_pct": -0.13, "actual_exit": "MANUAL_LOSS"},
    {"id": 23, "date": "2026-03-26 13:44", "side": "SHORT", "entry": 69385, "actual_pnl_pct": +0.70, "actual_exit": "TP"},
    {"id": 24, "date": "2026-03-27 04:00", "side": "SHORT", "entry": 68702, "actual_pnl_pct": +0.35, "actual_exit": "MANUAL"},
    {"id": 25, "date": "2026-03-28 08:00", "side": "SHORT", "entry": 66460, "actual_pnl_pct": +0.08, "actual_exit": "MANUAL"},
    {"id": 26, "date": "2026-03-28 16:00", "side": "SHORT", "entry": 66998, "actual_pnl_pct": +0.35, "actual_exit": "MANUAL"},
]

# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def date_str_to_ms(date_str: str) -> int:
    """Convert 'YYYY-MM-DD HH:MM' UTC string to milliseconds timestamp."""
    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
    epoch = datetime(1970, 1, 1)
    return int((dt - epoch).total_seconds() * 1000)


def fetch_klines(trade_id: int, date_str: str, entry_price: float) -> list | None:
    """
    Fetch 100 x 15m klines from Binance starting at entry candle.
    Caches to DATA_DIR/trade_{id}.json to avoid re-fetching.
    Returns list of raw kline arrays or None on error.
    """
    cache_file = DATA_DIR / f"trade_{trade_id}.json"
    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)

    start_ms = date_str_to_ms(date_str)
    url = BINANCE_KLINE_URL.format(start_ms=start_ms)
    try:
        print(f"  Fetching trade {trade_id} ({date_str}) from Binance...")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        if not data:
            print(f"  WARNING: No data returned for trade {trade_id}")
            return None
        with open(cache_file, "w") as f:
            json.dump(data, f)
        time.sleep(0.2)  # be gentle with Binance rate limits
        return data
    except Exception as e:
        print(f"  ERROR fetching trade {trade_id}: {e}")
        return None


# ---------------------------------------------------------------------------
# Order-flow signals
# ---------------------------------------------------------------------------

def check_of4(candles: list, peak_idx: int, curr_idx: int, side: str) -> bool:
    """
    OF4: Failed push — no new HH (LONG) or LL (SHORT) in last 4 candles since peak.
    Requires at least 4 candles after peak_idx before triggering.
    """
    if curr_idx - peak_idx < 4:
        return False
    peak_candle = candles[peak_idx]
    last_4 = candles[max(peak_idx + 1, curr_idx - 3): curr_idx + 1]
    if side == "LONG":
        # No candle has made a new high beyond peak candle's high
        return all(float(c[2]) <= float(peak_candle[2]) for c in last_4)
    else:
        # No candle has made a new low below peak candle's low
        return all(float(c[3]) >= float(peak_candle[3]) for c in last_4)


def check_of5(candles: list, curr_idx: int, side: str) -> bool:
    """
    OF5: Taker delta flip — taker sell > buy for last 2 candles (LONG bearish pressure),
    or taker buy > sell for last 2 candles (SHORT bullish pressure).
    """
    if curr_idx < 2:
        return False
    last2 = candles[curr_idx - 1: curr_idx + 1]
    for c in last2:
        vol = float(c[5])
        taker_buy = float(c[9])
        taker_sell = vol - taker_buy
        if side == "LONG" and taker_sell <= taker_buy:
            return False   # not bearish enough
        if side == "SHORT" and taker_buy <= taker_sell:
            return False   # not bullish enough
    return True


# ---------------------------------------------------------------------------
# Core simulation engine
# ---------------------------------------------------------------------------

def simulate_trade(candles: list, side: str, entry: float, model: str) -> dict:
    """
    Simulate a single trade through up to MAX_CANDLES 15m candles.

    Returns dict with:
      exit_reason: str
      exit_pnl_pct: float (as percentage, e.g. 0.71 means +0.71%)
      peak_pnl_pct: float
      exit_candle_idx: int
      pp_activated: bool
      pp_exited: bool
      of_blocked: bool   (V3+OF only)
    """
    peak_pnl   = 0.0
    peak_idx   = 0
    pp_active  = False    # profit protection activated

    result = {
        "exit_reason":    "TIME",
        "exit_pnl_pct":   0.0,
        "peak_pnl_pct":   0.0,
        "exit_candle_idx": MAX_CANDLES - 1,
        "pp_activated":   False,
        "pp_exited":      False,
        "of_blocked":     False,
    }

    for i, c in enumerate(candles[:MAX_CANDLES]):
        high  = float(c[2])
        low   = float(c[3])
        close = float(c[4])

        # Unrealized PnL extremes this candle
        if side == "LONG":
            unrealized_high = (high  - entry) / entry
            unrealized_low  = (low   - entry) / entry
            unrealized_close = (close - entry) / entry
        else:
            unrealized_high  = (entry - low)   / entry
            unrealized_low   = (entry - high)  / entry
            unrealized_close = (entry - close) / entry

        # Track peak
        if unrealized_high > peak_pnl:
            peak_pnl = unrealized_high
            peak_idx = i

        # 1. Check SL first
        if unrealized_low <= SL_PCT:
            result["exit_reason"]    = "SL"
            result["exit_pnl_pct"]   = SL_PCT * 100
            result["exit_candle_idx"] = i
            break

        # 2. Check TP
        if unrealized_high >= TP_PCT:
            result["exit_reason"]    = "TP"
            result["exit_pnl_pct"]   = TP_PCT * 100
            result["exit_candle_idx"] = i
            break

        # 3. Model-specific exit logic
        if model in ("V3", "V3+OF"):
            # Activate profit protection
            if peak_pnl >= PP_ACTIVATE:
                pp_active = True
                result["pp_activated"] = True

            if pp_active:
                # Check if close has retraced to or below PP_EXIT_LEVEL
                if unrealized_close <= PP_EXIT_LEVEL:
                    if model == "V3":
                        # Exit immediately
                        result["exit_reason"]    = "PP"
                        result["exit_pnl_pct"]   = PP_EXIT_LEVEL * 100
                        result["exit_candle_idx"] = i
                        result["pp_exited"]      = True
                        break
                    elif model == "V3+OF":
                        # Only exit if OF4 or OF5 fires
                        of4 = check_of4(candles, peak_idx, i, side)
                        of5 = check_of5(candles, i, side)
                        if of4 or of5:
                            result["exit_reason"]    = "PP+OF"
                            result["exit_pnl_pct"]   = PP_EXIT_LEVEL * 100
                            result["exit_candle_idx"] = i
                            result["pp_exited"]      = True
                            break
                        else:
                            result["of_blocked"] = True  # OF blocked this candle's exit
        # Model A: no additional logic — continue to next candle

        # 4. Time exit (last candle)
        if i == MAX_CANDLES - 1:
            result["exit_reason"]    = "TIME"
            result["exit_pnl_pct"]   = unrealized_close * 100
            result["exit_candle_idx"] = i

    result["peak_pnl_pct"] = peak_pnl * 100
    return result


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------

def compute_stats(pnl_list: list[float], label: str = "") -> dict:
    """Compute win-rate, avg win/loss, EV, PF, max drawdown, cumulative PnL."""
    if not pnl_list:
        return {}
    wins   = [p for p in pnl_list if p > 0]
    losses = [p for p in pnl_list if p <= 0]
    n      = len(pnl_list)
    wr     = len(wins) / n * 100 if n else 0
    avg_w  = sum(wins)   / len(wins)   if wins   else 0
    avg_l  = sum(losses) / len(losses) if losses else 0
    ev     = sum(pnl_list) / n if n else 0
    gross_profit = sum(wins)
    gross_loss   = abs(sum(losses))
    pf     = gross_profit / gross_loss if gross_loss else float("inf")

    # Max drawdown (cumulative)
    cum = 0.0
    peak_cum = 0.0
    max_dd = 0.0
    for p in pnl_list:
        cum += p
        if cum > peak_cum:
            peak_cum = cum
        dd = peak_cum - cum
        if dd > max_dd:
            max_dd = dd

    return {
        "label":    label,
        "n":        n,
        "wins":     len(wins),
        "losses":   len(losses),
        "wr_pct":   wr,
        "avg_win":  avg_w,
        "avg_loss": avg_l,
        "ev":       ev,
        "pf":       pf,
        "max_dd":   max_dd,
        "cum_pnl":  sum(pnl_list),
    }


def fmt_stat(s: dict) -> str:
    pf_str = f"{s['pf']:.2f}" if s['pf'] != float("inf") else "inf"
    return (
        f"| {s['label']:<16} | {s['n']:>6} | {s['wins']:>4} | {s['losses']:>6} "
        f"| {s['wr_pct']:>5.1f}% | {s['avg_win']:>8.3f}% | {s['avg_loss']:>9.3f}% "
        f"| {s['ev']:>6.3f}% | {pf_str:>6} | {s['max_dd']:>7.3f}% | {s['cum_pnl']:>8.3f}% |"
    )


# ---------------------------------------------------------------------------
# Monte Carlo
# ---------------------------------------------------------------------------

def monte_carlo(pnl_list: list[float], n_paths: int, n_trades: int) -> dict:
    """Bootstrap Monte Carlo: sample with replacement."""
    if not pnl_list:
        return {}
    final_pnls = []
    rng = random.Random(42)
    for _ in range(n_paths):
        path = rng.choices(pnl_list, k=n_trades)
        final_pnls.append(sum(path))
    final_pnls.sort()
    p5  = final_pnls[int(0.05 * n_paths)]
    p50 = final_pnls[int(0.50 * n_paths)]
    p95 = final_pnls[int(0.95 * n_paths)]
    p_profit = sum(1 for x in final_pnls if x > 0) / n_paths * 100
    return {"p5": p5, "p50": p50, "p95": p95, "p_profit": p_profit}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    lines = []  # collected output lines

    def pr(s=""):
        print(s)
        lines.append(s)

    pr("=" * 80)
    pr("BTC-QUANT v4.4 — Unified Strategy Simulation")
    pr(f"Date: 2026-03-31  |  Candles: 15m Binance BTCUSDT  |  Trades: {len(trades)}")
    pr("=" * 80)

    # ------------------------------------------------------------------
    # Step 1: Fetch data
    # ------------------------------------------------------------------
    pr("\n[1/5] Fetching 15m kline data from Binance (cached if available)...")
    trade_candles = {}
    skipped = []
    for t in trades:
        candles = fetch_klines(t["id"], t["date"], t["entry"])
        if candles is None or len(candles) < 2:
            print(f"  SKIP trade {t['id']} — insufficient data")
            skipped.append(t["id"])
        else:
            trade_candles[t["id"]] = candles

    if skipped:
        pr(f"\n  WARNING: Skipped trades (no data): {skipped}")

    active_trades = [t for t in trades if t["id"] not in skipped]
    pr(f"  Active trades: {len(active_trades)}/{len(trades)}")

    # ------------------------------------------------------------------
    # Step 2: Simulate all models
    # ------------------------------------------------------------------
    pr("\n[2/5] Running simulations...")

    results_A   = []
    results_B   = []
    results_V3  = []
    results_V3OF = []

    for t in active_trades:
        candles = trade_candles[t["id"]]
        side    = t["side"]
        entry   = t["entry"]

        sim_A    = simulate_trade(candles, side, entry, "A")
        sim_V3   = simulate_trade(candles, side, entry, "V3")
        sim_V3OF = simulate_trade(candles, side, entry, "V3+OF")

        results_A.append({**t, **sim_A})
        results_B.append({**t,
                          "exit_reason": t["actual_exit"],
                          "exit_pnl_pct": t["actual_pnl_pct"],
                          "peak_pnl_pct": sim_A["peak_pnl_pct"],  # same data
                          "pp_activated": False, "pp_exited": False, "of_blocked": False})
        results_V3.append({**t, **sim_V3})
        results_V3OF.append({**t, **sim_V3OF})

    # ------------------------------------------------------------------
    # Step 3: Per-trade detail table (Model A vs V3)
    # ------------------------------------------------------------------
    pr("\n[3/5] Per-trade detail (Model A vs V3):")
    pr("-" * 110)
    hdr = (
        f"{'ID':>3} | {'Date':<16} | {'Side':<5} | {'Entry':>7} | "
        f"{'Peak%':>6} | {'A_Exit':<8} | {'A_PnL%':>7} | "
        f"{'V3_Exit':<9} | {'V3_PnL%':>8} | {'B_Exit':<12} | {'B_PnL%':>7}"
    )
    pr(hdr)
    pr("-" * 110)

    for a, v3, b in zip(results_A, results_V3, results_B):
        pr(
            f"{a['id']:>3} | {a['date']:<16} | {a['side']:<5} | {a['entry']:>7} | "
            f"{a['peak_pnl_pct']:>+6.2f}% | {a['exit_reason']:<8} | {a['exit_pnl_pct']:>+7.3f}% | "
            f"{v3['exit_reason']:<9} | {v3['exit_pnl_pct']:>+8.3f}% | {b['exit_reason']:<12} | {b['exit_pnl_pct']:>+7.2f}%"
        )
    pr("-" * 110)

    # ------------------------------------------------------------------
    # Step 4: Master summary table
    # ------------------------------------------------------------------
    pr("\n[4/5] Master summary table (all models, LONG+SHORT combined):")

    def build_stats(results, label):
        all_pnl   = [r["exit_pnl_pct"] for r in results]
        long_pnl  = [r["exit_pnl_pct"] for r in results if r["side"] == "LONG"]
        short_pnl = [r["exit_pnl_pct"] for r in results if r["side"] == "SHORT"]
        return [
            compute_stats(all_pnl,   f"{label} (ALL)"),
            compute_stats(long_pnl,  f"{label} (LONG)"),
            compute_stats(short_pnl, f"{label} (SHORT)"),
        ]

    all_stat_rows = []
    for res, label in [
        (results_A,    "Model_A"),
        (results_B,    "Model_B"),
        (results_V3,   "Model_V3"),
        (results_V3OF, "Model_V3+OF"),
    ]:
        all_stat_rows.extend(build_stats(res, label))

    pr("-" * 120)
    pr(
        f"| {'Model':<16} | {'Trades':>6} | {'Wins':>4} | {'Losses':>6} "
        f"| {'WR%':>6} | {'AvgWin%':>8} | {'AvgLoss%':>9} "
        f"| {'EV%':>6} | {'PF':>6} | {'MaxDD%':>7} | {'CumPnL%':>8} |"
    )
    pr("-" * 120)
    for s in all_stat_rows:
        if s:
            pr(fmt_stat(s))
    pr("-" * 120)

    # ------------------------------------------------------------------
    # V3 / V3+OF diagnostics
    # ------------------------------------------------------------------
    pr("\n[5/5] V3 and V3+OF diagnostics:")

    v3_pp_act  = sum(1 for r in results_V3   if r["pp_activated"])
    v3_pp_exit = sum(1 for r in results_V3   if r["pp_exited"])
    of_blocked_count = sum(1 for r in results_V3OF if r["of_blocked"])
    of_pp_exit = sum(1 for r in results_V3OF if r["pp_exited"])

    pr(f"  V3:     PP activated in {v3_pp_act} trades, exited at PP in {v3_pp_exit} trades")
    pr(f"  V3+OF:  PP activated in {sum(1 for r in results_V3OF if r['pp_activated'])} trades, "
       f"exited at PP+OF in {of_pp_exit} trades")
    pr(f"  V3+OF:  OF blocked exit in {of_blocked_count} trade-candle instances")

    # Show which trades were PP-exited
    pr("\n  Trades exited by PP (V3):")
    for r in results_V3:
        if r["pp_exited"]:
            pr(f"    Trade {r['id']:>2} | {r['side']} | entry={r['entry']} | "
               f"peak={r['peak_pnl_pct']:+.2f}% | exit={r['exit_pnl_pct']:+.3f}% | "
               f"actual={r['actual_pnl_pct']:+.2f}% (actual_exit={r['actual_exit']})")

    pr("\n  Trades exited by PP+OF (V3+OF):")
    for r in results_V3OF:
        if r["pp_exited"]:
            pr(f"    Trade {r['id']:>2} | {r['side']} | entry={r['entry']} | "
               f"peak={r['peak_pnl_pct']:+.2f}% | exit={r['exit_pnl_pct']:+.3f}% | "
               f"actual={r['actual_pnl_pct']:+.2f}% (actual_exit={r['actual_exit']})")

    # ------------------------------------------------------------------
    # Monte Carlo
    # ------------------------------------------------------------------
    pr("\n[BONUS] Monte Carlo simulation (1000 paths x 100 trades, bootstrap):")
    pr(f"  Using {MONTE_N_PATHS} paths, {MONTE_N_TRADES} trades per path")
    pr("-" * 70)
    pr(f"  {'Model':<12} | {'P5%':>8} | {'Median%':>8} | {'P95%':>8} | {'P(profit)':>10}")
    pr("-" * 70)

    for res, label in [
        (results_A,    "Model_A"),
        (results_V3,   "Model_V3"),
        (results_V3OF, "Model_V3+OF"),
        (results_B,    "Model_B"),
    ]:
        pnl_list = [r["exit_pnl_pct"] for r in res]
        mc = monte_carlo(pnl_list, MONTE_N_PATHS, MONTE_N_TRADES)
        if mc:
            pr(f"  {label:<12} | {mc['p5']:>+8.2f}% | {mc['p50']:>+8.2f}% | "
               f"{mc['p95']:>+8.2f}% | {mc['p_profit']:>9.1f}%")
    pr("-" * 70)

    # ------------------------------------------------------------------
    # Honest conclusion
    # ------------------------------------------------------------------
    pr("\n" + "=" * 80)
    pr("HONEST CONCLUSION")
    pr("=" * 80)

    # Compute key numbers for conclusion
    ev_a    = compute_stats([r["exit_pnl_pct"] for r in results_A],    "A")
    ev_b    = compute_stats([r["exit_pnl_pct"] for r in results_B],    "B")
    ev_v3   = compute_stats([r["exit_pnl_pct"] for r in results_V3],   "V3")
    ev_v3of = compute_stats([r["exit_pnl_pct"] for r in results_V3OF], "V3+OF")

    models_ev = sorted(
        [("Model_A", ev_a), ("Model_B", ev_b), ("Model_V3", ev_v3), ("Model_V3+OF", ev_v3of)],
        key=lambda x: x[1]["ev"], reverse=True
    )

    pr(f"""
1. BEST MODEL BY EV (expected value per trade):
   Ranked: {" > ".join(f"{m} ({s['ev']:+.3f}%)" for m, s in models_ev)}

2. SAMPLE SIZE WARNING:
   Only {len(active_trades)} trades available. This is far below the ~200-300 minimum
   needed for statistically significant strategy comparison. All numbers have
   high uncertainty. Confidence intervals are wide — treat rankings as directional,
   not definitive.

3. MODEL CHARACTERISTICS:
   Model A (Pure Auto):
     - Systematic, removes all discretion
     - WR: {ev_a['wr_pct']:.1f}%, EV: {ev_a['ev']:+.3f}%, CumPnL: {ev_a['cum_pnl']:+.2f}%
     - Risk: SL is 1.333% — relatively wide for scalping; a few SL hits dominate losses

   Model B (Actual Manual):
     - Represents real historical execution INCLUDING human discretion
     - WR: {ev_b['wr_pct']:.1f}%, EV: {ev_b['ev']:+.3f}%, CumPnL: {ev_b['cum_pnl']:+.2f}%
     - WARNING: Past manual skill may not persist; highly subject to psychological bias
     - Several 'MANUAL' exits were suboptimal vs TP; others correctly avoided SL

   Model V3 (Profit Protection):
     - Locks in gains when peak >= 0.30%, exits if close retraces to 0.15%
     - WR: {ev_v3['wr_pct']:.1f}%, EV: {ev_v3['ev']:+.3f}%, CumPnL: {ev_v3['cum_pnl']:+.2f}%
     - Theoretically appealing but may cut winners too early in trending markets

   Model V3+OF (Profit Protection + Orderflow):
     - Adds OF4/OF5 confirmation before PP exit — reduces premature exits
     - WR: {ev_v3of['wr_pct']:.1f}%, EV: {ev_v3of['ev']:+.3f}%, CumPnL: {ev_v3of['cum_pnl']:+.2f}%

4. DEPLOYMENT RECOMMENDATION:
   Given the small sample and uncertainty:
   a) Deploy Model A (Pure Auto) as primary — fully systematic, no human bias,
      results reproducible. EV is transparent.
   b) Monitor V3 in shadow mode for 50+ more trades before live switch.
   c) Do NOT deploy based on 26-trade optimization — overfitting risk is high.
   d) The most important metric to watch live: whether SL rate stays near
      historical base rate. Multiple consecutive SLs = regime change signal.

5. KEY RISK:
   The SL at -1.333% is significantly larger than TP at +0.71%. A win-rate below
   ~65.5% produces negative EV (TP/|SL| = 0.71/1.333 = 0.533; breakeven WR =
   1/(1+0.533) = 65.2%). Current WR must be verified on larger sample.
""")

    # ------------------------------------------------------------------
    # Save results
    # ------------------------------------------------------------------
    output_path = Path(__file__).parent / "unified_results.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# BTC-QUANT Unified Simulation Results\n\n")
        f.write(f"Generated: 2026-03-31\n\n")
        f.write("```\n")
        f.write("\n".join(lines))
        f.write("\n```\n")

    pr(f"\nResults saved to: {output_path}")
    pr("Done.")


if __name__ == "__main__":
    main()
