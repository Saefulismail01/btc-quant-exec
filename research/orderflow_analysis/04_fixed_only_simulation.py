"""
04_fixed_only_simulation.py
===========================
Unified simulation using ONLY FixedStrategy trades (22 trades).
Excludes HestonStrategy trades #22-#25 from Mar 26-28 (old numbering).
New trade #22 = Mar 29 23:00 SHORT 66480 (TP confirmed, +0.88%).

Models compared:
  - Model A:  Pure auto (TP=+0.71%, SL=-1.333%, 24h time exit)
  - Model B:  Actual results (use actual_pnl_pct as-is)
  - Model V3: Profit protection (activate=0.30%, close=0.15%)

Author: BTC-QUANT research
Date: 2026-03-31
"""

import os
import json
import time
import random
import urllib.request
from datetime import datetime, timezone
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

SL_PCT        = -0.01333  # -1.333%
TP_PCT        = +0.0071   # +0.71%
PP_ACTIVATE   = 0.0030    # profit-protection activates at peak >= 0.30%
PP_EXIT_LEVEL = 0.0015    # exit if candle close pnl drops to 0.15%
MAX_CANDLES   = 96        # 24 hours of 15m candles

MONTE_N_PATHS  = 1000
MONTE_N_TRADES = 100

# ---------------------------------------------------------------------------
# Trade definitions — FixedStrategy only (22 trades)
# Trades 22-25 (HestonStrategy, Mar 26-28) excluded.
# New trade #22 = Mar 29 23:00 SHORT 66480 confirmed TP +0.88%
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
    # Trade 22: Mar 29 23:00 SHORT 66480, confirmed TP +0.88%, FixedStrategy
    {"id": 22, "date": "2026-03-29 23:00", "side": "SHORT", "entry": 66480, "actual_pnl_pct": +0.88, "actual_exit": "TP"},
]

# ---------------------------------------------------------------------------
# Data fetching
# Trade 22 uses a dedicated cache file "trade_fixed22.json" to avoid
# collision with the old trade_22.json (which was a HestonStrategy trade).
# ---------------------------------------------------------------------------

CACHE_OVERRIDES = {
    22: "trade_fixed22.json",
}


def date_str_to_ms(date_str: str) -> int:
    """Convert 'YYYY-MM-DD HH:MM' UTC string to milliseconds timestamp."""
    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
    epoch = datetime(1970, 1, 1)
    return int((dt - epoch).total_seconds() * 1000)


def fetch_klines(trade_id: int, date_str: str) -> list | None:
    """
    Fetch 100 x 15m klines from Binance starting at signal time.
    Caches to DATA_DIR.  Trade 22 uses separate cache file.
    """
    fname = CACHE_OVERRIDES.get(trade_id, f"trade_{trade_id}.json")
    cache_file = DATA_DIR / fname
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
        time.sleep(0.2)
        return data
    except Exception as e:
        print(f"  ERROR fetching trade {trade_id}: {e}")
        return None


# ---------------------------------------------------------------------------
# Core simulation engine
# ---------------------------------------------------------------------------

def simulate_trade(candles: list, side: str, entry: float, model: str) -> dict:
    """
    Simulate a single trade through up to MAX_CANDLES 15m candles.

    Priority each candle:
      1. SL:  unrealized_low  <= -0.01333  → exit -1.333%
      2. TP:  unrealized_high >= +0.0071   → exit +0.71%
      3. V3:  peak >= 0.30% AND close_pnl <= 0.15% → exit +0.15%
      4. Time exit: candle 96
    """
    peak_pnl  = 0.0
    peak_idx  = 0
    pp_active = False

    result = {
        "exit_reason":     "TIME",
        "exit_pnl_pct":    0.0,
        "peak_pnl_pct":    0.0,
        "exit_candle_idx": MAX_CANDLES - 1,
        "pp_activated":    False,
        "pp_exited":       False,
    }

    for i, c in enumerate(candles[:MAX_CANDLES]):
        high  = float(c[2])
        low   = float(c[3])
        close = float(c[4])

        if side == "LONG":
            unrealized_high  = (high  - entry) / entry
            unrealized_low   = (low   - entry) / entry
            unrealized_close = (close - entry) / entry
        else:
            unrealized_high  = (entry - low)   / entry
            unrealized_low   = (entry - high)  / entry
            unrealized_close = (entry - close) / entry

        # Track peak
        if unrealized_high > peak_pnl:
            peak_pnl = unrealized_high
            peak_idx = i

        # 1. SL
        if unrealized_low <= SL_PCT:
            result["exit_reason"]     = "SL"
            result["exit_pnl_pct"]    = SL_PCT * 100
            result["exit_candle_idx"] = i
            break

        # 2. TP
        if unrealized_high >= TP_PCT:
            result["exit_reason"]     = "TP"
            result["exit_pnl_pct"]    = TP_PCT * 100
            result["exit_candle_idx"] = i
            break

        # 3. V3 profit protection
        if model == "V3":
            if peak_pnl >= PP_ACTIVATE:
                pp_active = True
                result["pp_activated"] = True
            if pp_active and unrealized_close <= PP_EXIT_LEVEL:
                result["exit_reason"]     = "PP"
                result["exit_pnl_pct"]    = PP_EXIT_LEVEL * 100
                result["exit_candle_idx"] = i
                result["pp_exited"]       = True
                break

        # 4. Time exit
        if i == MAX_CANDLES - 1:
            result["exit_reason"]     = "TIME"
            result["exit_pnl_pct"]    = unrealized_close * 100
            result["exit_candle_idx"] = i

    result["peak_pnl_pct"] = peak_pnl * 100
    return result


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------

def compute_stats(pnl_list: list, label: str = "") -> dict:
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
        "label":   label,
        "n":       n,
        "wins":    len(wins),
        "losses":  len(losses),
        "wr_pct":  wr,
        "avg_win": avg_w,
        "avg_loss": avg_l,
        "ev":      ev,
        "pf":      pf,
        "max_dd":  max_dd,
        "cum_pnl": sum(pnl_list),
    }


def fmt_stat(s: dict) -> str:
    pf_str = f"{s['pf']:.2f}" if s['pf'] != float("inf") else "  inf"
    return (
        f"| {s['label']:<18} | {s['n']:>6} | {s['wins']:>4} | {s['losses']:>6} "
        f"| {s['wr_pct']:>5.1f}% | {s['avg_win']:>8.3f}% | {s['avg_loss']:>9.3f}% "
        f"| {s['ev']:>6.3f}% | {pf_str:>6} | {s['max_dd']:>7.3f}% | {s['cum_pnl']:>8.3f}% |"
    )


# ---------------------------------------------------------------------------
# Monte Carlo
# ---------------------------------------------------------------------------

def monte_carlo(pnl_list: list, n_paths: int, n_trades: int) -> dict:
    if not pnl_list:
        return {}
    final_pnls = []
    rng = random.Random(42)
    for _ in range(n_paths):
        path = rng.choices(pnl_list, k=n_trades)
        final_pnls.append(sum(path))
    final_pnls.sort()
    p5       = final_pnls[int(0.05 * n_paths)]
    p50      = final_pnls[int(0.50 * n_paths)]
    p95      = final_pnls[int(0.95 * n_paths)]
    p_profit = sum(1 for x in final_pnls if x > 0) / n_paths * 100
    return {"p5": p5, "p50": p50, "p95": p95, "p_profit": p_profit}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    lines = []

    def pr(s=""):
        print(s)
        lines.append(s)

    pr("=" * 90)
    pr("BTC-QUANT v4.4 — FixedStrategy Only Simulation (22 trades)")
    pr("HestonStrategy trades excluded (old #22-25, Mar 26-28)")
    pr(f"Date: 2026-03-31  |  Candles: 15m Binance BTCUSDT  |  Trades: {len(trades)}")
    pr("=" * 90)

    # ------------------------------------------------------------------
    # Step 1: Fetch / load data
    # ------------------------------------------------------------------
    pr("\n[1/4] Loading 15m kline data (cached where available)...")
    trade_candles = {}
    skipped = []
    for t in trades:
        candles = fetch_klines(t["id"], t["date"])
        if candles is None or len(candles) < 2:
            print(f"  SKIP trade {t['id']} — insufficient data")
            skipped.append(t["id"])
        else:
            trade_candles[t["id"]] = candles

    if skipped:
        pr(f"  WARNING: Skipped trades (no data): {skipped}")

    active_trades = [t for t in trades if t["id"] not in skipped]
    pr(f"  Active trades: {len(active_trades)}/{len(trades)}")

    # ------------------------------------------------------------------
    # Step 2: Simulate all models
    # ------------------------------------------------------------------
    pr("\n[2/4] Running simulations (Model A, Model B, Model V3)...")

    results_A  = []
    results_B  = []
    results_V3 = []

    for t in active_trades:
        candles = trade_candles[t["id"]]
        side    = t["side"]
        entry   = t["entry"]

        sim_A  = simulate_trade(candles, side, entry, "A")
        sim_V3 = simulate_trade(candles, side, entry, "V3")

        results_A.append({**t, **sim_A})
        results_B.append({**t,
                          "exit_reason":    t["actual_exit"],
                          "exit_pnl_pct":   t["actual_pnl_pct"],
                          "peak_pnl_pct":   sim_A["peak_pnl_pct"],
                          "pp_activated":   False,
                          "pp_exited":      False})
        results_V3.append({**t, **sim_V3})

    # ------------------------------------------------------------------
    # Step 3: Per-trade detail table
    # ------------------------------------------------------------------
    pr("\n[3/4] Per-trade table (Model A vs V3):")
    pr("-" * 115)
    pr(
        f"{'ID':>3} | {'Date':<16} | {'S':<5} | {'Entry':>7} | "
        f"{'Peak%':>7} | {'A_Exit':<8} | {'A_PnL%':>7} | "
        f"{'V3_Exit':<8} | {'V3_PnL%':>8} | {'B_Exit':<12} | {'B_PnL%':>7}"
    )
    pr("-" * 115)

    for a, v3, b in zip(results_A, results_V3, results_B):
        pr(
            f"{a['id']:>3} | {a['date']:<16} | {a['side']:<5} | {a['entry']:>7} | "
            f"{a['peak_pnl_pct']:>+7.2f}% | {a['exit_reason']:<8} | {a['exit_pnl_pct']:>+7.3f}% | "
            f"{v3['exit_reason']:<8} | {v3['exit_pnl_pct']:>+8.3f}% | "
            f"{b['exit_reason']:<12} | {b['exit_pnl_pct']:>+7.2f}%"
        )
    pr("-" * 115)

    # ------------------------------------------------------------------
    # Step 4: Master summary table
    # ------------------------------------------------------------------
    pr("\n[4/4] Master summary — all models, LONG/SHORT breakdown:")

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
        (results_A,  "Model_A"),
        (results_B,  "Model_B"),
        (results_V3, "Model_V3"),
    ]:
        all_stat_rows.extend(build_stats(res, label))

    hdr = (
        f"| {'Model':<18} | {'Trades':>6} | {'Wins':>4} | {'Losses':>6} "
        f"| {'WR%':>6} | {'AvgWin%':>8} | {'AvgLoss%':>9} "
        f"| {'EV%':>6} | {'PF':>6} | {'MaxDD%':>7} | {'CumPnL%':>8} |"
    )
    pr("-" * len(hdr))
    pr(hdr)
    pr("-" * len(hdr))
    for s in all_stat_rows:
        if s:
            pr(fmt_stat(s))
    pr("-" * len(hdr))

    # ------------------------------------------------------------------
    # Monte Carlo
    # ------------------------------------------------------------------
    pr(f"\nMonte Carlo ({MONTE_N_PATHS} paths x {MONTE_N_TRADES} trades, bootstrap with replacement):")
    pr("-" * 65)
    pr(f"  {'Model':<12} | {'P5%':>8} | {'Median%':>8} | {'P95%':>8} | {'P(profit)':>10}")
    pr("-" * 65)
    for res, label in [(results_A, "Model_A"), (results_V3, "Model_V3"), (results_B, "Model_B")]:
        pnl_list = [r["exit_pnl_pct"] for r in res]
        mc = monte_carlo(pnl_list, MONTE_N_PATHS, MONTE_N_TRADES)
        if mc:
            pr(f"  {label:<12} | {mc['p5']:>+8.2f}% | {mc['p50']:>+8.2f}% | "
               f"{mc['p95']:>+8.2f}% | {mc['p_profit']:>9.1f}%")
    pr("-" * 65)

    # ------------------------------------------------------------------
    # V3 diagnostics
    # ------------------------------------------------------------------
    v3_pp_act  = sum(1 for r in results_V3 if r["pp_activated"])
    v3_pp_exit = sum(1 for r in results_V3 if r["pp_exited"])
    pr(f"\nV3 diagnostics: PP activated in {v3_pp_act} trades, exited early in {v3_pp_exit} trades")
    if v3_pp_exit:
        pr("  Trades exited by V3 PP (peak>=0.30%, close<=0.15%):")
        for r in results_V3:
            if r["pp_exited"]:
                pr(f"    Trade {r['id']:>2} | {r['side']} | entry={r['entry']} | "
                   f"peak={r['peak_pnl_pct']:+.2f}% -> exit PP {r['exit_pnl_pct']:+.3f}% | "
                   f"actual={r['actual_pnl_pct']:+.2f}% ({r['actual_exit']})")

    # ------------------------------------------------------------------
    # Honest conclusion
    # ------------------------------------------------------------------
    ev_a  = compute_stats([r["exit_pnl_pct"] for r in results_A],  "A")
    ev_b  = compute_stats([r["exit_pnl_pct"] for r in results_B],  "B")
    ev_v3 = compute_stats([r["exit_pnl_pct"] for r in results_V3], "V3")

    long_a  = compute_stats([r["exit_pnl_pct"] for r in results_A if r["side"] == "LONG"],  "A_LONG")
    short_a = compute_stats([r["exit_pnl_pct"] for r in results_A if r["side"] == "SHORT"], "A_SHORT")

    models_ev = sorted(
        [("Model_A", ev_a), ("Model_B", ev_b), ("Model_V3", ev_v3)],
        key=lambda x: x[1]["ev"], reverse=True
    )

    pr("\n" + "=" * 90)
    pr("HONEST CONCLUSION")
    pr("=" * 90)
    pr(f"""
1. WINNER BY EV (expected value per trade):
   {" > ".join(f"{m} ({s['ev']:+.3f}%)" for m, s in models_ev)}

2. LONG vs SHORT performance (Model A):
   LONG  ({long_a['n']} trades):  WR={long_a['wr_pct']:.1f}%,  EV={long_a['ev']:+.3f}%,  CumPnL={long_a['cum_pnl']:+.2f}%
   SHORT ({short_a['n']} trades): WR={short_a['wr_pct']:.1f}%, EV={short_a['ev']:+.3f}%, CumPnL={short_a['cum_pnl']:+.2f}%

3. EV RELIABILITY:
   Breakeven WR = 1/(1 + TP/|SL|) = 1/(1 + 0.71/1.333) = 65.2%
   Model A WR={ev_a['wr_pct']:.1f}% — {"ABOVE breakeven, positive EV confirmed" if ev_a['wr_pct'] >= 65.2 else "BELOW breakeven — negative EV territory"}
   WARNING: 22 trades is well below the 200+ minimum for statistical significance.
   All rankings are directional estimates only — high variance, wide confidence intervals.

4. V3 vs A comparison:
   V3 EV={ev_v3['ev']:+.3f}% vs A EV={ev_a['ev']:+.3f}%
   {"V3 WINS — profit protection adds value on this sample" if ev_v3['ev'] > ev_a['ev'] else "Model A WINS — pure auto outperforms V3 on this sample"}
   V3 cut {v3_pp_exit} trades early at +0.15% (instead of waiting for TP +0.71%).

5. RECOMMENDATION:
   a) Deploy Model A (Pure Auto) as primary — fully systematic, reproducible, no bias.
   b) V3 may add value but needs 100+ more trades before a live switch is justified.
   c) SHORT side is a new regime (Mar 22+) — watch SL rate closely in live trading.
   d) The most dangerous scenario: consecutive SL hits. Monitor SL rate vs base rate.
""")

    # ------------------------------------------------------------------
    # Save results
    # ------------------------------------------------------------------
    output_path = Path(__file__).parent / "fixed_strategy_only_results.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# BTC-QUANT FixedStrategy Only Simulation Results\n\n")
        f.write("Generated: 2026-03-31  |  22 trades (HestonStrategy excluded)\n\n")
        f.write("```\n")
        f.write("\n".join(lines))
        f.write("\n```\n")

    pr(f"\nResults saved to: {output_path}")
    pr("Done.")


if __name__ == "__main__":
    main()
