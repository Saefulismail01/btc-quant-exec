"""
03_sensitivity_test.py
======================
Parameter sensitivity test for V3 Profit Protection strategy.
Tests all combinations of activate% and close% thresholds to determine
whether the strategy concept is robust or merely cherry-picked.

Author: BTC-QUANT research
Date: 2026-03-31
"""

import json
from pathlib import Path
from itertools import product

# ---------------------------------------------------------------------------
# Config — identical to unified_simulation.py
# ---------------------------------------------------------------------------
DATA_DIR   = Path(__file__).parent / "data" / "unified"
SL_PCT     = -0.01333   # -1.333%
TP_PCT     = +0.0071    # +0.71%
MAX_CANDLES = 96         # 24h of 15m candles

# Parameter grid
ACTIVATE_LEVELS = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]  # %
CLOSE_LEVELS    = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]               # %

# ---------------------------------------------------------------------------
# Trade definitions
# ---------------------------------------------------------------------------
trades = [
    {"id": 1,  "date": "2026-03-10 16:05", "side": "LONG",  "entry": 71198, "actual_pnl_pct": -1.20},
    {"id": 2,  "date": "2026-03-11 04:08", "side": "LONG",  "entry": 69498, "actual_pnl_pct": +0.73},
    {"id": 3,  "date": "2026-03-11 08:06", "side": "LONG",  "entry": 69620, "actual_pnl_pct": +0.24},
    {"id": 4,  "date": "2026-03-12 08:05", "side": "LONG",  "entry": 69846, "actual_pnl_pct": +0.67},
    {"id": 5,  "date": "2026-03-12 12:15", "side": "LONG",  "entry": 70309, "actual_pnl_pct": -0.68},
    {"id": 6,  "date": "2026-03-12 20:09", "side": "LONG",  "entry": 70401, "actual_pnl_pct": +0.77},
    {"id": 7,  "date": "2026-03-13 04:03", "side": "LONG",  "entry": 71347, "actual_pnl_pct": +0.22},
    {"id": 8,  "date": "2026-03-13 08:02", "side": "LONG",  "entry": 71520, "actual_pnl_pct": +0.77},
    {"id": 9,  "date": "2026-03-13 14:13", "side": "LONG",  "entry": 73500, "actual_pnl_pct": +0.34},
    {"id": 10, "date": "2026-03-13 16:02", "side": "LONG",  "entry": 71891, "actual_pnl_pct": -0.67},
    {"id": 11, "date": "2026-03-16 08:14", "side": "LONG",  "entry": 73545, "actual_pnl_pct": +0.42},
    {"id": 12, "date": "2026-03-16 16:01", "side": "LONG",  "entry": 73172, "actual_pnl_pct": +0.42},
    {"id": 13, "date": "2026-03-17 00:51", "side": "LONG",  "entry": 74930, "actual_pnl_pct": +0.66},
    {"id": 14, "date": "2026-03-17 02:07", "side": "LONG",  "entry": 75287, "actual_pnl_pct": +0.08},
    {"id": 15, "date": "2026-03-17 04:02", "side": "LONG",  "entry": 74562, "actual_pnl_pct": -0.68},
    {"id": 16, "date": "2026-03-17 07:21", "side": "LONG",  "entry": 74319, "actual_pnl_pct": +0.03},
    {"id": 17, "date": "2026-03-17 12:00", "side": "LONG",  "entry": 74013, "actual_pnl_pct": +0.28},
    {"id": 18, "date": "2026-03-22 00:00", "side": "SHORT", "entry": 68744, "actual_pnl_pct": +0.75},
    {"id": 19, "date": "2026-03-22 08:00", "side": "SHORT", "entry": 68860, "actual_pnl_pct": +0.34},
    {"id": 20, "date": "2026-03-22 12:00", "side": "SHORT", "entry": 68217, "actual_pnl_pct": -0.71},
    {"id": 21, "date": "2026-03-23 00:00", "side": "SHORT", "entry": 67975, "actual_pnl_pct": +0.35},
    {"id": 22, "date": "2026-03-26 12:00", "side": "SHORT", "entry": 69215, "actual_pnl_pct": -0.13},
    {"id": 23, "date": "2026-03-26 13:44", "side": "SHORT", "entry": 69385, "actual_pnl_pct": +0.70},
    {"id": 24, "date": "2026-03-27 04:00", "side": "SHORT", "entry": 68702, "actual_pnl_pct": +0.35},
    {"id": 25, "date": "2026-03-28 08:00", "side": "SHORT", "entry": 66460, "actual_pnl_pct": +0.08},
    {"id": 26, "date": "2026-03-28 16:00", "side": "SHORT", "entry": 66998, "actual_pnl_pct": +0.35},
]

TRAIN_IDS = list(range(1, 17))   # trades 1-16
TEST_IDS  = list(range(17, 27))  # trades 17-26

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_candles(trade_id: int) -> list | None:
    cache = DATA_DIR / f"trade_{trade_id}.json"
    if not cache.exists():
        print(f"  WARNING: cache missing for trade {trade_id}")
        return None
    with open(cache) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Simulation engine (identical logic to unified_simulation.py)
# ---------------------------------------------------------------------------

def simulate_trade_v3(candles: list, side: str, entry: float,
                      pp_activate: float, pp_exit: float) -> dict:
    """
    Simulate one trade with V3 profit protection.
    pp_activate and pp_exit are FRACTIONS (e.g., 0.003 for 0.30%).
    Returns dict with exit_pnl_pct (as %) and pp_exited flag.
    """
    peak_pnl  = 0.0
    pp_active = False

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

        if unrealized_high > peak_pnl:
            peak_pnl = unrealized_high

        # 1. SL
        if unrealized_low <= SL_PCT:
            return {"exit_pnl_pct": SL_PCT * 100, "exit_reason": "SL",
                    "pp_exited": False, "pp_activated": pp_active}

        # 2. TP
        if unrealized_high >= TP_PCT:
            return {"exit_pnl_pct": TP_PCT * 100, "exit_reason": "TP",
                    "pp_exited": False, "pp_activated": pp_active}

        # 3. V3 profit protection
        if peak_pnl >= pp_activate:
            pp_active = True
            if unrealized_close <= pp_exit:
                return {"exit_pnl_pct": pp_exit * 100, "exit_reason": "PP",
                        "pp_exited": True, "pp_activated": True}

        # 4. Time exit (last candle)
        if i == MAX_CANDLES - 1:
            return {"exit_pnl_pct": unrealized_close * 100, "exit_reason": "TIME",
                    "pp_exited": False, "pp_activated": pp_active}

    return {"exit_pnl_pct": 0.0, "exit_reason": "TIME",
            "pp_exited": False, "pp_activated": pp_active}


def simulate_trade_a(candles: list, side: str, entry: float) -> dict:
    """Model A — pure auto, no profit protection."""
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

        if unrealized_low <= SL_PCT:
            return {"exit_pnl_pct": SL_PCT * 100, "exit_reason": "SL"}
        if unrealized_high >= TP_PCT:
            return {"exit_pnl_pct": TP_PCT * 100, "exit_reason": "TP"}
        if i == MAX_CANDLES - 1:
            return {"exit_pnl_pct": unrealized_close * 100, "exit_reason": "TIME"}

    return {"exit_pnl_pct": 0.0, "exit_reason": "TIME"}


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def compute_stats(pnl_list: list) -> dict:
    if not pnl_list:
        return {"wr": 0, "ev": 0, "pf": 0, "max_dd": 0, "cum_pnl": 0}
    wins   = [p for p in pnl_list if p > 0]
    losses = [p for p in pnl_list if p <= 0]
    n      = len(pnl_list)
    wr     = len(wins) / n * 100
    ev     = sum(pnl_list) / n
    gross_profit = sum(wins)
    gross_loss   = abs(sum(losses))
    pf = gross_profit / gross_loss if gross_loss else float("inf")
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
    return {"wr": wr, "ev": ev, "pf": pf, "max_dd": max_dd, "cum_pnl": sum(pnl_list), "n": n}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    lines = []

    def pr(s=""):
        print(s)
        lines.append(s)

    pr("=" * 80)
    pr("BTC-QUANT V3 Parameter Sensitivity Test")
    pr("Date: 2026-03-31  |  Trades: 26  |  Candles: 15m Binance BTCUSDT")
    pr("=" * 80)

    # ------------------------------------------------------------------
    # Load cached candle data
    # ------------------------------------------------------------------
    pr("\nLoading cached kline data...")
    trade_candles = {}
    skipped = []
    for t in trades:
        c = load_candles(t["id"])
        if c and len(c) >= 2:
            trade_candles[t["id"]] = c
        else:
            skipped.append(t["id"])

    if skipped:
        pr(f"  WARNING: Missing data for trades: {skipped}")

    active_trades = [t for t in trades if t["id"] not in skipped]
    pr(f"  Active trades: {len(active_trades)}/26")
    if len(active_trades) < 26:
        pr("  STOPPING: not enough data. Please run unified_simulation.py first.")
        return

    # ------------------------------------------------------------------
    # Model A baseline (all 26 trades, train, test)
    # ------------------------------------------------------------------
    pnl_a_all = []
    pnl_a_train = []
    pnl_a_test  = []
    for t in active_trades:
        r = simulate_trade_a(trade_candles[t["id"]], t["side"], t["entry"])
        pnl = r["exit_pnl_pct"]
        pnl_a_all.append(pnl)
        if t["id"] in TRAIN_IDS:
            pnl_a_train.append(pnl)
        else:
            pnl_a_test.append(pnl)

    stats_a_all   = compute_stats(pnl_a_all)
    stats_a_train = compute_stats(pnl_a_train)
    stats_a_test  = compute_stats(pnl_a_test)

    pr(f"\nModel A (baseline):")
    pr(f"  ALL  ({stats_a_all['n']:>2} trades): EV={stats_a_all['ev']:+.3f}%  "
       f"WR={stats_a_all['wr']:.1f}%  CumPnL={stats_a_all['cum_pnl']:+.3f}%")
    pr(f"  TRAIN({stats_a_train['n']:>2} trades): EV={stats_a_train['ev']:+.3f}%  "
       f"WR={stats_a_train['wr']:.1f}%  CumPnL={stats_a_train['cum_pnl']:+.3f}%")
    pr(f"  TEST ({stats_a_test['n']:>2} trades): EV={stats_a_test['ev']:+.3f}%  "
       f"WR={stats_a_test['wr']:.1f}%  CumPnL={stats_a_test['cum_pnl']:+.3f}%")

    # ------------------------------------------------------------------
    # Grid search: all valid (activate, close) combinations
    # ------------------------------------------------------------------
    pr("\n" + "=" * 80)
    pr("PARAMETER GRID SEARCH — ALL VALID COMBINATIONS")
    pr("=" * 80)

    grid_results = []
    for act_pct, close_pct in product(ACTIVATE_LEVELS, CLOSE_LEVELS):
        if close_pct >= act_pct:
            continue  # invalid: close must be < activate

        act_frac   = act_pct   / 100.0
        close_frac = close_pct / 100.0

        pnl_all   = []
        pnl_train = []
        pnl_test  = []

        for t in active_trades:
            r = simulate_trade_v3(
                trade_candles[t["id"]], t["side"], t["entry"],
                act_frac, close_frac
            )
            pnl = r["exit_pnl_pct"]
            pnl_all.append(pnl)
            if t["id"] in TRAIN_IDS:
                pnl_train.append(pnl)
            else:
                pnl_test.append(pnl)

        s_all   = compute_stats(pnl_all)
        s_train = compute_stats(pnl_train)
        s_test  = compute_stats(pnl_test)

        grid_results.append({
            "act_pct":   act_pct,
            "close_pct": close_pct,
            "stats_all":   s_all,
            "stats_train": s_train,
            "stats_test":  s_test,
        })

    # Sort by EV (all trades), descending
    grid_results.sort(key=lambda x: x["stats_all"]["ev"], reverse=True)

    # ------------------------------------------------------------------
    # Section 1: Full grid results table
    # ------------------------------------------------------------------
    pr("\n--- Section 1: Full Grid Results (sorted by EV%, all 26 trades) ---\n")

    hdr = f"| {'act%':>5} | {'close%':>6} | {'WR%':>5} | {'EV%':>6} | {'PF':>5} | {'MaxDD%':>6} | {'CumPnL%':>8} | note"
    pr(hdr)
    pr("|" + "-" * 6 + "|" + "-" * 8 + "|" + "-" * 7 + "|" + "-" * 8 + "|" + "-" * 7 + "|" + "-" * 8 + "|" + "-" * 10 + "|------")

    for row in grid_results:
        s = row["stats_all"]
        pf_str = f"{s['pf']:.2f}" if s["pf"] != float("inf") else " inf"
        note = "**CHOSEN**" if (abs(row["act_pct"] - 0.30) < 0.001 and abs(row["close_pct"] - 0.15) < 0.001) else ""
        pr(f"| {row['act_pct']:>5.2f} | {row['close_pct']:>6.2f} | {s['wr']:>5.1f} | {s['ev']:>+6.3f} | {pf_str:>5} | {s['max_dd']:>6.3f} | {s['cum_pnl']:>+8.3f} | {note}")

    # Model A row for reference
    s = stats_a_all
    pf_str = f"{s['pf']:.2f}" if s["pf"] != float("inf") else " inf"
    pr(f"| {'N/A':>5} | {'N/A':>6} | {s['wr']:>5.1f} | {s['ev']:>+6.3f} | {pf_str:>5} | {s['max_dd']:>6.3f} | {s['cum_pnl']:>+8.3f} | MODEL A (baseline)")

    # ------------------------------------------------------------------
    # Section 2: Heatmap (EV% matrix)
    # ------------------------------------------------------------------
    pr("\n--- Section 2: EV% Heatmap (rows=activate%, cols=close%) ---\n")

    # Build lookup
    ev_map = {}
    for row in grid_results:
        ev_map[(row["act_pct"], row["close_pct"])] = row["stats_all"]["ev"]

    # Header row
    header_cols = "           " + "".join(f"  close={c:.2f}" for c in CLOSE_LEVELS)
    pr(header_cols)
    pr("           " + "-" * (len(header_cols) - 11))

    for act in ACTIVATE_LEVELS:
        cells = []
        for close in CLOSE_LEVELS:
            if close >= act:
                cells.append("    N/A  ")
            else:
                ev = ev_map.get((act, close), None)
                if ev is not None:
                    marker = "*" if (abs(act - 0.30) < 0.001 and abs(close - 0.15) < 0.001) else " "
                    cells.append(f" {ev:>+6.3f}{marker} ")
                else:
                    cells.append("    N/A  ")
        pr(f"  act={act:.2f}:  " + " ".join(cells))

    pr(f"\n  (*) = originally chosen parameters (act=0.30, close=0.15)")
    pr(f"  Model A EV = {stats_a_all['ev']:+.3f}% (reference)")

    # ------------------------------------------------------------------
    # Section 3: Robustness analysis
    # ------------------------------------------------------------------
    pr("\n--- Section 3: Robustness Analysis ---\n")

    n_combos = len(grid_results)
    n_beat_a = sum(1 for r in grid_results if r["stats_all"]["ev"] > stats_a_all["ev"])
    n_positive = sum(1 for r in grid_results if r["stats_all"]["ev"] > 0)
    all_evs = [r["stats_all"]["ev"] for r in grid_results]
    min_ev = min(all_evs)
    max_ev = max(all_evs)
    avg_ev = sum(all_evs) / len(all_evs)

    pr(f"  Total valid parameter combinations tested: {n_combos}")
    pr(f"  Model A EV (baseline): {stats_a_all['ev']:+.3f}%")
    pr(f"")
    pr(f"  Combinations with EV > Model A ({stats_a_all['ev']:+.3f}%): {n_beat_a}/{n_combos} ({n_beat_a/n_combos*100:.0f}%)")
    pr(f"  Combinations with EV > 0%:                             {n_positive}/{n_combos} ({n_positive/n_combos*100:.0f}%)")
    pr(f"")
    pr(f"  EV range across all combinations:")
    pr(f"    Min: {min_ev:+.3f}%")
    pr(f"    Max: {max_ev:+.3f}%")
    pr(f"    Avg: {avg_ev:+.3f}%")
    pr(f"    Std: {(sum((e - avg_ev)**2 for e in all_evs) / len(all_evs))**0.5:.3f}%")

    # Ridge analysis: look for parameter regions
    pr(f"\n  Ridge analysis (top 5 combinations by EV):")
    pr(f"  {'act%':>5}  {'close%':>6}  {'EV%':>7}")
    for row in grid_results[:5]:
        pr(f"  {row['act_pct']:>5.2f}  {row['close_pct']:>6.2f}  {row['stats_all']['ev']:>+7.3f}%")

    # Check if top combos cluster or are scattered
    top5_act = [r["act_pct"] for r in grid_results[:5]]
    top5_close = [r["close_pct"] for r in grid_results[:5]]
    act_range = max(top5_act) - min(top5_act)
    close_range = max(top5_close) - min(top5_close)
    pr(f"\n  Top-5 activate% span: {min(top5_act):.2f} to {max(top5_act):.2f} (range={act_range:.2f}%)")
    pr(f"  Top-5 close%    span: {min(top5_close):.2f} to {max(top5_close):.2f} (range={close_range:.2f}%)")

    if act_range <= 0.15 and close_range <= 0.10:
        ridge_verdict = "CLUSTERED — suggests a genuine ridge, not isolated peaks."
    elif act_range >= 0.25 or close_range >= 0.20:
        ridge_verdict = "SCATTERED — top results are spread across parameter space; fragile."
    else:
        ridge_verdict = "MIXED — moderate clustering; interpret with caution."
    pr(f"  Verdict: {ridge_verdict}")

    # ------------------------------------------------------------------
    # Section 4: Walk-forward split
    # ------------------------------------------------------------------
    pr("\n--- Section 4: Walk-Forward Split ---\n")
    pr(f"  Train set: trades 1-16 (Mar 10-17, {len(TRAIN_IDS)} trades, mostly LONG)")
    pr(f"  Test  set: trades 17-26 (Mar 17-29, {len(TEST_IDS)} trades, mixed LONG+SHORT)")
    pr("")

    # Best combo on train set
    grid_results_by_train = sorted(grid_results, key=lambda x: x["stats_train"]["ev"], reverse=True)
    best_train = grid_results_by_train[0]

    pr(f"  Best combo on TRAIN set: activate={best_train['act_pct']:.2f}%, close={best_train['close_pct']:.2f}%")
    pr(f"    Train EV:  {best_train['stats_train']['ev']:+.3f}%  WR={best_train['stats_train']['wr']:.1f}%  CumPnL={best_train['stats_train']['cum_pnl']:+.3f}%")
    pr(f"    Test  EV:  {best_train['stats_test']['ev']:+.3f}%  WR={best_train['stats_test']['wr']:.1f}%  CumPnL={best_train['stats_test']['cum_pnl']:+.3f}%")
    pr("")
    pr(f"  Chosen params (act=0.30, close=0.15) walk-forward:")
    chosen_row = next((r for r in grid_results if abs(r["act_pct"] - 0.30) < 0.001 and abs(r["close_pct"] - 0.15) < 0.001), None)
    if chosen_row:
        pr(f"    Train EV:  {chosen_row['stats_train']['ev']:+.3f}%  WR={chosen_row['stats_train']['wr']:.1f}%  CumPnL={chosen_row['stats_train']['cum_pnl']:+.3f}%")
        pr(f"    Test  EV:  {chosen_row['stats_test']['ev']:+.3f}%  WR={chosen_row['stats_test']['wr']:.1f}%  CumPnL={chosen_row['stats_test']['cum_pnl']:+.3f}%")
    pr("")
    pr(f"  Model A walk-forward:")
    pr(f"    Train EV:  {stats_a_train['ev']:+.3f}%  WR={stats_a_train['wr']:.1f}%  CumPnL={stats_a_train['cum_pnl']:+.3f}%")
    pr(f"    Test  EV:  {stats_a_test['ev']:+.3f}%  WR={stats_a_test['wr']:.1f}%  CumPnL={stats_a_test['cum_pnl']:+.3f}%")

    # Walk-forward degradation
    if chosen_row:
        chosen_train_ev = chosen_row["stats_train"]["ev"]
        chosen_test_ev  = chosen_row["stats_test"]["ev"]
        degradation = chosen_train_ev - chosen_test_ev
        pr(f"\n  Walk-forward degradation (chosen): train {chosen_train_ev:+.3f}% -> test {chosen_test_ev:+.3f}%  (delta={degradation:+.3f}%)")
        if degradation < -0.05:
            pr("    POSITIVE: Out-of-sample EV is HIGHER than train — no degradation observed.")
            pr("    NOTE: This may reflect regime differences between periods, not parameter robustness.")
        elif degradation > 0.10:
            pr("    WARNING: Significant degradation on out-of-sample data. Likely overfit.")
        elif degradation > 0.05:
            pr("    CAUTION: Moderate degradation. Monitor carefully if deployed.")
        else:
            pr("    OK: Minor degradation. Consistent across periods.")

    # ------------------------------------------------------------------
    # Section 5: Honest conclusion
    # ------------------------------------------------------------------
    pr("\n" + "=" * 80)
    pr("Section 5: HONEST CONCLUSION")
    pr("=" * 80)

    # Compute verdict components
    majority_beat_a = n_beat_a > n_combos * 0.5
    majority_positive = n_positive > n_combos * 0.5
    chosen_rank = next(i for i, r in enumerate(grid_results) if abs(r["act_pct"] - 0.30) < 0.001 and abs(r["close_pct"] - 0.15) < 0.001) + 1
    chosen_ev = chosen_row["stats_all"]["ev"] if chosen_row else 0
    chosen_test_ev = chosen_row["stats_test"]["ev"] if chosen_row else 0

    pr(f"""
1. IS V3 ROBUST ACROSS PARAMETERS?
   - Valid combinations tested: {n_combos}
   - EV range: {min_ev:+.3f}% to {max_ev:+.3f}% (avg={avg_ev:+.3f}%)
   - Combinations beating Model A: {n_beat_a}/{n_combos} ({n_beat_a/n_combos*100:.0f}%)
   - Combinations with EV > 0%:    {n_positive}/{n_combos} ({n_positive/n_combos*100:.0f}%)
   - Chosen params rank: #{chosen_rank} of {n_combos}

   Parameter ridge: {ridge_verdict}

2. WALK-FORWARD PERFORMANCE (chosen 0.30/0.15):
   Train (trades 1-16): EV={chosen_row["stats_train"]["ev"] if chosen_row else 0:+.3f}%
   Test  (trades 17-26): EV={chosen_row["stats_test"]["ev"] if chosen_row else 0:+.3f}%

3. IS THE CONCEPT VALID FOR DEPLOYMENT?""")

    # Evaluate deployment worthiness
    conditions_met = []
    conditions_failed = []

    if majority_positive:
        conditions_met.append(f"Most parameter combinations ({n_positive}/{n_combos}) have EV > 0%")
    else:
        conditions_failed.append(f"Only {n_positive}/{n_combos} combinations have EV > 0%")

    if majority_beat_a:
        conditions_met.append(f"Most combinations ({n_beat_a}/{n_combos}) beat Model A baseline")
    else:
        conditions_failed.append(f"Only {n_beat_a}/{n_combos} combinations beat Model A")

    if chosen_row and abs(chosen_row["stats_test"]["ev"] - stats_a_test["ev"]) < 0.05:
        conditions_failed.append("Chosen params show no clear advantage over Model A on test set")
    elif chosen_row and chosen_row["stats_test"]["ev"] > stats_a_test["ev"]:
        conditions_met.append(f"Chosen params outperform Model A on out-of-sample test set")
    else:
        conditions_failed.append(f"Chosen params underperform Model A on out-of-sample test set")

    conditions_failed.append("Sample size (26 trades) is far below the 200+ needed for statistical significance")

    for c in conditions_met:
        pr(f"   [PASS] {c}")
    for c in conditions_failed:
        pr(f"   [FAIL] {c}")

    # Overall confidence
    pass_count = len(conditions_met)
    total = pass_count + len(conditions_failed)

    if pass_count >= 3:
        confidence = "MEDIUM"
        deploy_rec = "Shadow-trade V3 alongside Model A for 50+ more trades. Do not deploy live without further validation."
    elif pass_count >= 2:
        confidence = "LOW-MEDIUM"
        deploy_rec = "Concept shows some promise but evidence is weak. Shadow trade only."
    else:
        confidence = "LOW"
        deploy_rec = "Insufficient evidence. Do NOT deploy V3 live. Continue with Model A."

    pr(f"""
4. CONFIDENCE LEVEL: {confidence}
   ({pass_count}/{total} validation criteria passed)

5. DEPLOYMENT RECOMMENDATION:
   {deploy_rec}

6. KEY CAVEAT:
   With only 26 trades, the probability of cherry-picking optimal parameters
   by chance is high. A parameter sensitivity test on 26 trades can confirm
   that a CONCEPT works across a range of inputs, but cannot confirm that
   the EXACT parameters chosen are optimal rather than lucky.
   Minimum sample for reliable strategy comparison: 200-300 trades.
""")

    # ------------------------------------------------------------------
    # Save results
    # ------------------------------------------------------------------
    output_path = Path(__file__).parent / "sensitivity_results.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# V3 Profit Protection — Parameter Sensitivity Test\n\n")
        f.write("Generated: 2026-03-31\n\n")
        f.write("```\n")
        f.write("\n".join(lines))
        f.write("\n```\n")

    pr(f"\nResults saved to: {output_path}")
    pr("Done.")


if __name__ == "__main__":
    main()
