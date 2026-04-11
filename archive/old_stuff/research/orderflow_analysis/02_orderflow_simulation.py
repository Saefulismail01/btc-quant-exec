"""
02_orderflow_simulation.py
Full orderflow analysis simulation comparing:
  Model A  - Pure Auto (TP=0.71%, SL=1.333%, time exit 24h)
  Model V3 - Auto + Profit Protection (activate at +0.30% peak, close at +0.15%)
  Model V3+OF - V3 but only close protection if >=1 orderflow signal confirms
  Model B  - Manual actual results (from prior analysis, hardcoded)
"""

import json
import os
import math
import random
from dataclasses import dataclass, field
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
OUT_DIR = os.path.dirname(__file__)

# ── Strategy parameters ───────────────────────────────────────────────────────
TP_PCT   =  0.0071    # +0.71%
SL_PCT   = -0.01333   # -1.333%
PP_ACTIVATE = 0.0030  # profit protection activates at +0.30% peak
PP_CLOSE    = 0.0015  # profit protection closes at +0.15%
MAX_CANDLES = 96      # 96 x 15m = 24h

# ── Model B: actual manual trade results (PnL %) ─────────────────────────────
# From prior analysis (trade-level actuals provided externally)
MODEL_B_RESULTS = {
    1:  +0.71,  2:  +0.71,  3:  +0.71,  4:  +0.71,  5: -1.333,
    6:  +0.71,  7: -1.333,  8:  -1.333, 9: +0.71,   10: +0.71,
    11: +0.71,  12: +0.71,  13: -1.333, 14: -1.333, 15: +0.71,
    16: +0.71,  17: +0.71,  18: +0.71,  19: +0.71,  20: +0.71,
    21: +0.71,  22: -1.333, 23: -1.333, 24: +0.71,  25: +0.71,
    26: +0.71,
}

# ── Data loading ──────────────────────────────────────────────────────────────

def load_trade_data(trade_id: int) -> dict:
    path = os.path.join(DATA_DIR, f"trade_{trade_id:02d}.json")
    with open(path) as f:
        return json.load(f)

# ── Orderflow signal functions ────────────────────────────────────────────────

def check_OF1_momentum_death(candles_since_peak: list, side: str) -> bool:
    """3 consecutive candles with decreasing body size after peak."""
    if len(candles_since_peak) < 3:
        return False
    bodies = [abs(c["close"] - c["open"]) for c in candles_since_peak[-3:]]
    return bodies[0] > bodies[1] > bodies[2]


def check_OF2_rejection(current_candle: dict, side: str) -> bool:
    """Wick > 60% of total range in adverse direction."""
    total_range = current_candle["high"] - current_candle["low"]
    if total_range == 0:
        return False
    if side == "LONG":
        upper_wick = current_candle["high"] - max(current_candle["open"], current_candle["close"])
        return upper_wick / total_range > 0.60
    else:
        lower_wick = min(current_candle["open"], current_candle["close"]) - current_candle["low"]
        return lower_wick / total_range > 0.60


def check_OF3_volume_exhaustion(candles_window: list, last_2: list) -> bool:
    """Volume of last 2 candles < 50% of 10-candle average."""
    if len(candles_window) < 10:
        return False
    avg_vol = sum(c["volume"] for c in candles_window[-10:]) / 10
    if avg_vol == 0:
        return False
    recent_avg = sum(c["volume"] for c in last_2) / 2
    return recent_avg < avg_vol * 0.50


def check_OF4_failed_push(candles_since_peak: list, side: str) -> bool:
    """Price fails to make HH (LONG) or LL (SHORT) in 4 candles after peak."""
    if len(candles_since_peak) < 4:
        return False
    if side == "LONG":
        peak_high = candles_since_peak[0]["high"]
        return all(c["high"] <= peak_high for c in candles_since_peak[1:4])
    else:
        peak_low = candles_since_peak[0]["low"]
        return all(c["low"] >= peak_low for c in candles_since_peak[1:4])


def check_OF5_delta_flip(last_2_candles: list, side: str) -> bool:
    """Taker sell > taker buy for 2 consecutive candles adverse to position."""
    if len(last_2_candles) < 2:
        return False
    for c in last_2_candles:
        taker_buy = c["taker_buy_volume"]
        taker_sell = c["volume"] - taker_buy
        if side == "LONG" and taker_sell <= taker_buy:
            return False
        if side == "SHORT" and taker_buy <= taker_sell:
            return False
    return True


def check_all_of_signals(candles: list, idx: int, side: str) -> dict:
    """
    At candle index idx (0-based), check all 5 OF signals.
    candles_since_peak = candles from protection_activate_idx to idx (inclusive).
    """
    current = candles[idx]
    window = candles[max(0, idx - 9): idx + 1]   # up to 10 candles ending at idx
    last_2 = candles[max(0, idx - 1): idx + 1]    # last 2 candles

    # candles_since_peak: from first candle after peak activation to now
    # We pass this in from the caller for OF1 and OF4
    return {
        "OF2": check_OF2_rejection(current, side),
        "OF3": check_OF3_volume_exhaustion(window, last_2),
        "OF5": check_OF5_delta_flip(last_2, side),
    }
    # OF1 and OF4 need candles_since_peak context; handled in simulate_trade


# ── Core simulation ───────────────────────────────────────────────────────────

@dataclass
class TradeResult:
    trade_id: int
    date: str
    side: str
    entry: float
    peak_pct: float = 0.0

    # Model A
    a_exit_reason: str = ""
    a_pnl_pct: float = 0.0
    a_exit_candle: int = 0

    # Model V3
    v3_exit_reason: str = ""
    v3_pnl_pct: float = 0.0
    v3_exit_candle: int = 0

    # Model V3+OF
    vof_exit_reason: str = ""
    vof_pnl_pct: float = 0.0
    vof_exit_candle: int = 0
    vof_of_signals: list = field(default_factory=list)
    vof_pp_triggered: bool = False   # did protection ever want to close?
    vof_pp_blocked: int = 0          # times OF blocked a closure
    vof_pp_confirmed: int = 0        # times OF confirmed a closure


def signed_pnl(price: float, entry: float, side: str) -> float:
    if side == "LONG":
        return (price - entry) / entry
    else:
        return (entry - price) / entry


def simulate_trade(data: dict) -> TradeResult:
    t = data["trade"]
    trade_id = t["id"]
    side = t["side"]
    entry = float(t["entry"])
    candles = data["candles_15m"][:MAX_CANDLES]

    res = TradeResult(
        trade_id=trade_id,
        date=t["date"],
        side=side,
        entry=entry,
    )

    # ── State shared across models ────────────────────────────────────────────
    peak_pnl = 0.0
    protection_active = False
    peak_candle_idx = 0   # candle where peak was set
    protection_activate_idx = 0  # candle when protection first activated

    # ── Model A state ─────────────────────────────────────────────────────────
    a_done = False; a_reason = ""; a_pnl = 0.0; a_exit_c = 0

    # ── Model V3 state ────────────────────────────────────────────────────────
    v3_done = False; v3_reason = ""; v3_pnl = 0.0; v3_exit_c = 0
    v3_protection = False; v3_peak = 0.0

    # ── Model V3+OF state ─────────────────────────────────────────────────────
    vof_done = False; vof_reason = ""; vof_pnl = 0.0; vof_exit_c = 0
    vof_protection = False; vof_peak = 0.0; vof_peak_c = 0
    vof_pp_triggered = False; vof_pp_blocked = 0; vof_pp_confirmed = 0
    vof_signals_fired: list = []

    for i, c in enumerate(candles):
        h, l, cl = c["high"], c["low"], c["close"]

        # PnL at candle extremes
        if side == "LONG":
            worst  = (l  - entry) / entry
            best   = (h  - entry) / entry
        else:
            worst  = (entry - h) / entry
            best   = (entry - l) / entry
        current_pnl = signed_pnl(cl, entry, side)

        # ── MODEL A ──────────────────────────────────────────────────────────
        if not a_done:
            if worst <= SL_PCT:
                a_reason = "SL"; a_pnl = SL_PCT; a_exit_c = i; a_done = True
            elif best >= TP_PCT:
                a_reason = "TP"; a_pnl = TP_PCT; a_exit_c = i; a_done = True
            elif i == len(candles) - 1:
                a_reason = "TIME"; a_pnl = current_pnl; a_exit_c = i; a_done = True

        # ── MODEL V3 ─────────────────────────────────────────────────────────
        if not v3_done:
            if worst <= SL_PCT:
                v3_reason = "SL"; v3_pnl = SL_PCT; v3_exit_c = i; v3_done = True
            elif best >= TP_PCT:
                v3_reason = "TP"; v3_pnl = TP_PCT; v3_exit_c = i; v3_done = True
            else:
                v3_peak = max(v3_peak, best)
                if v3_peak >= PP_ACTIVATE:
                    v3_protection = True
                if v3_protection and current_pnl <= PP_CLOSE:
                    v3_reason = "PP"; v3_pnl = PP_CLOSE; v3_exit_c = i; v3_done = True
                elif i == len(candles) - 1:
                    v3_reason = "TIME"; v3_pnl = current_pnl; v3_exit_c = i; v3_done = True

        # ── MODEL V3+OF ───────────────────────────────────────────────────────
        if not vof_done:
            if worst <= SL_PCT:
                vof_reason = "SL"; vof_pnl = SL_PCT; vof_exit_c = i; vof_done = True
            elif best >= TP_PCT:
                vof_reason = "TP"; vof_pnl = TP_PCT; vof_exit_c = i; vof_done = True
            else:
                prev_peak = vof_peak
                vof_peak = max(vof_peak, best)
                if vof_peak > prev_peak:
                    vof_peak_c = i  # update peak candle

                if vof_peak >= PP_ACTIVATE:
                    vof_protection = True

                if vof_protection and current_pnl <= PP_CLOSE:
                    vof_pp_triggered = True
                    # Check OF signals
                    candles_since_peak = candles[vof_peak_c: i + 1]
                    of_basic = check_all_of_signals(candles, i, side)
                    of1 = check_OF1_momentum_death(candles_since_peak, side)
                    of4 = check_OF4_failed_push(candles_since_peak, side)
                    of_all = {
                        "OF1": of1,
                        "OF2": of_basic["OF2"],
                        "OF3": of_basic["OF3"],
                        "OF4": of4,
                        "OF5": of_basic["OF5"],
                    }
                    any_signal = any(of_all.values())
                    fired = [k for k, v in of_all.items() if v]

                    if any_signal:
                        vof_pp_confirmed += 1
                        vof_signals_fired.extend(fired)
                        vof_reason = f"PP+OF({','.join(fired)})"
                        vof_pnl = PP_CLOSE; vof_exit_c = i; vof_done = True
                    else:
                        vof_pp_blocked += 1
                        # Do NOT close; continue holding

                if not vof_done and i == len(candles) - 1:
                    vof_reason = "TIME"; vof_pnl = current_pnl; vof_exit_c = i; vof_done = True

    # Clamp time exits to SL/TP if they overshoot
    # (shouldn't happen since we check inside loop, but safety)
    res.peak_pct = max(vof_peak, v3_peak, 0.0) * 100

    res.a_exit_reason = a_reason; res.a_pnl_pct = a_pnl * 100; res.a_exit_candle = a_exit_c
    res.v3_exit_reason = v3_reason; res.v3_pnl_pct = v3_pnl * 100; res.v3_exit_candle = v3_exit_c
    res.vof_exit_reason = vof_reason; res.vof_pnl_pct = vof_pnl * 100; res.vof_exit_candle = vof_exit_c
    res.vof_of_signals = list(set(vof_signals_fired))
    res.vof_pp_triggered = vof_pp_triggered
    res.vof_pp_blocked = vof_pp_blocked
    res.vof_pp_confirmed = vof_pp_confirmed

    return res


# ── Summary metrics ───────────────────────────────────────────────────────────

def compute_metrics(pnl_list: list, label: str) -> dict:
    n = len(pnl_list)
    wins = [p for p in pnl_list if p > 0]
    losses = [p for p in pnl_list if p < 0]
    wr = len(wins) / n * 100
    ev = sum(pnl_list) / n
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses)) if losses else 0
    pf = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    cum_pnl = sum(pnl_list)

    # Max drawdown (running cumulative)
    running = 0.0; peak_eq = 0.0; max_dd = 0.0
    for p in pnl_list:
        running += p
        peak_eq = max(peak_eq, running)
        dd = peak_eq - running
        max_dd = max(max_dd, dd)

    return {
        "label": label, "n": n,
        "WR%": round(wr, 1),
        "EV%": round(ev, 3),
        "PF": round(pf, 2) if pf != float("inf") else 999,
        "MaxDD%": round(max_dd, 3),
        "CumPnL%": round(cum_pnl, 3),
    }


# ── Monte Carlo ───────────────────────────────────────────────────────────────

def monte_carlo(pnl_list: list, n_paths: int = 1000, n_trades: int = 100, seed: int = 42):
    random.seed(seed)
    final_pnls = []
    for _ in range(n_paths):
        path_pnl = sum(random.choices(pnl_list, k=n_trades))
        final_pnls.append(path_pnl)
    final_pnls.sort()
    p5  = final_pnls[int(0.05 * n_paths)]
    p50 = final_pnls[int(0.50 * n_paths)]
    p95 = final_pnls[int(0.95 * n_paths)]
    p_profit = sum(1 for x in final_pnls if x > 0) / n_paths * 100
    return {"p5": round(p5, 2), "median": round(p50, 2), "p95": round(p95, 2), "P_profit%": round(p_profit, 1)}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    results: list[TradeResult] = []
    print("Running simulation for 26 trades...\n")
    for i in range(1, 27):
        data = load_trade_data(i)
        r = simulate_trade(data)
        results.append(r)
        print(f"  Trade {r.trade_id:2d} | {r.side:5s} | peak={r.peak_pct:+.2f}% | "
              f"A={r.a_exit_reason}({r.a_pnl_pct:+.3f}%) | "
              f"V3={r.v3_exit_reason}({r.v3_pnl_pct:+.3f}%) | "
              f"V3+OF={r.vof_exit_reason}({r.vof_pnl_pct:+.3f}%)")

    # ── Per-trade table data ──────────────────────────────────────────────────
    print("\n\n=== PER-TRADE COMPARISON TABLE ===")
    header = f"{'#':>2} {'Date':<19} {'Side':<5} {'Entry':>7} {'Peak%':>6} | {'V3 Exit':<8} {'V3 PnL':>7} | {'V3+OF Exit':<20} {'V3+OF PnL':>9} | OF Signals"
    print(header)
    print("-" * len(header))
    for r in results:
        of_str = ",".join(sorted(set(r.vof_of_signals))) if r.vof_of_signals else "-"
        print(f"{r.trade_id:>2} {r.date:<19} {r.side:<5} {r.entry:>7.0f} {r.peak_pct:>+6.2f}% | "
              f"{r.v3_exit_reason:<8} {r.v3_pnl_pct:>+7.3f}% | "
              f"{r.vof_exit_reason:<20} {r.vof_pnl_pct:>+9.3f}% | {of_str}")

    # ── Summary metrics ───────────────────────────────────────────────────────
    a_pnls   = [r.a_pnl_pct for r in results]
    v3_pnls  = [r.v3_pnl_pct for r in results]
    vof_pnls = [r.vof_pnl_pct for r in results]
    b_pnls   = [MODEL_B_RESULTS[r.trade_id] for r in results]

    metrics_a   = compute_metrics(a_pnls,   "Model A (Pure Auto)")
    metrics_v3  = compute_metrics(v3_pnls,  "Model V3 (Profit Protection)")
    metrics_vof = compute_metrics(vof_pnls, "Model V3+OF (PP + Orderflow)")
    metrics_b   = compute_metrics(b_pnls,   "Model B (Manual Actual)")

    print("\n\n=== SUMMARY METRICS ===")
    print(f"{'Model':<35} {'WR%':>5} {'EV%':>6} {'PF':>6} {'MaxDD%':>7} {'CumPnL%':>9}")
    print("-" * 75)
    for m in [metrics_a, metrics_b, metrics_v3, metrics_vof]:
        print(f"{m['label']:<35} {m['WR%']:>5.1f} {m['EV%']:>+6.3f} {m['PF']:>6.2f} {m['MaxDD%']:>7.3f} {m['CumPnL%']:>+9.3f}")

    # ── V3+OF deep dive ───────────────────────────────────────────────────────
    pp_triggered   = [r for r in results if r.vof_pp_triggered]
    pp_confirmed   = [r for r in results if r.vof_pp_confirmed > 0]
    pp_blocked     = [r for r in results if r.vof_pp_blocked > 0 and r.vof_pp_confirmed == 0]

    # After being blocked, what happened?
    blocked_tp  = [r for r in pp_blocked if "TP" in r.vof_exit_reason]
    blocked_sl  = [r for r in pp_blocked if "SL" in r.vof_exit_reason]
    blocked_time= [r for r in pp_blocked if "TIME" in r.vof_exit_reason]
    blocked_pp  = [r for r in pp_blocked if "PP" in r.vof_exit_reason]  # eventual PP

    # Signal frequency
    all_signals = []
    for r in results:
        all_signals.extend(r.vof_of_signals)
    signal_counts = {}
    for s in ["OF1", "OF2", "OF3", "OF4", "OF5"]:
        signal_counts[s] = all_signals.count(s)

    # LONG vs SHORT
    long_vof  = [r for r in results if r.side == "LONG"]
    short_vof = [r for r in results if r.side == "SHORT"]

    print("\n\n=== V3+OF DEEP DIVE ===")
    print(f"Total trades: {len(results)}")
    print(f"PP triggered (wanted to close at +0.15%): {len(pp_triggered)}")
    print(f"  Confirmed by OF (closed at +0.15%): {len(pp_confirmed)}")
    print(f"  Blocked by OF (no signal, kept holding): {len(pp_blocked)}")
    print(f"    After block - TP hit: {len(blocked_tp)}")
    print(f"    After block - SL hit: {len(blocked_sl)}")
    print(f"    After block - TIME exit: {len(blocked_time)}")
    print(f"    After block - PP closed later: {len(blocked_pp)}")

    print(f"\nOrderflow signal frequency:")
    for s, cnt in sorted(signal_counts.items(), key=lambda x: -x[1]):
        print(f"  {s}: {cnt} fires")

    lm = compute_metrics([r.vof_pnl_pct for r in long_vof], "LONG")
    sm = compute_metrics([r.vof_pnl_pct for r in short_vof], "SHORT")
    print(f"\nV3+OF by direction:")
    print(f"  LONG  (n={lm['n']}): WR={lm['WR%']}%, EV={lm['EV%']:+.3f}%, CumPnL={lm['CumPnL%']:+.3f}%")
    print(f"  SHORT (n={sm['n']}): WR={sm['WR%']}%, EV={sm['EV%']:+.3f}%, CumPnL={sm['CumPnL%']:+.3f}%")

    # ── Monte Carlo ───────────────────────────────────────────────────────────
    mc_a   = monte_carlo(a_pnls)
    mc_v3  = monte_carlo(v3_pnls)
    mc_vof = monte_carlo(vof_pnls)
    mc_b   = monte_carlo(b_pnls)

    print("\n\n=== MONTE CARLO (1000 paths × 100 trades) ===")
    print(f"{'Model':<35} {'P5%':>7} {'Median%':>9} {'P95%':>7} {'P(+)%':>7}")
    print("-" * 70)
    for label, mc in [("Model A", mc_a), ("Model B", mc_b), ("Model V3", mc_v3), ("Model V3+OF", mc_vof)]:
        print(f"{label:<35} {mc['p5']:>+7.2f} {mc['median']:>+9.2f} {mc['p95']:>+7.2f} {mc['P_profit%']:>7.1f}%")

    # ── Return structured data for results.md ────────────────────────────────
    return {
        "results": results,
        "metrics": {"A": metrics_a, "B": metrics_b, "V3": metrics_v3, "VOF": metrics_vof},
        "mc": {"A": mc_a, "B": mc_b, "V3": mc_v3, "VOF": mc_vof},
        "pp": {
            "triggered": len(pp_triggered),
            "confirmed": len(pp_confirmed),
            "blocked": len(pp_blocked),
            "blocked_tp": len(blocked_tp),
            "blocked_sl": len(blocked_sl),
            "blocked_time": len(blocked_time),
        },
        "signal_counts": signal_counts,
        "long_metrics": lm,
        "short_metrics": sm,
    }


if __name__ == "__main__":
    sim_data = main()
