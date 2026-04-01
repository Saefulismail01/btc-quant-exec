"""
Mini Trailing Profit Protection — Simulation against real Binance 1h candles.
26 BTC trades, March 10-29, 2026.
"""

import requests
import time
import numpy as np
from datetime import datetime, timezone
from dataclasses import dataclass

# ── Trade definitions ──────────────────────────────────────────────────────────
TRADES = [
    # (date_str, side, entry_price)  date_str in "YYYY-MM-DD HH:MM" UTC
    ("2026-03-10 16:05", "LONG", 71198),
    ("2026-03-11 04:08", "LONG", 69498),
    ("2026-03-11 08:06", "LONG", 69620),
    ("2026-03-12 08:05", "LONG", 69846),
    ("2026-03-12 12:15", "LONG", 70309),
    ("2026-03-12 20:09", "LONG", 70401),
    ("2026-03-13 04:03", "LONG", 71347),
    ("2026-03-13 08:02", "LONG", 71520),
    ("2026-03-13 14:13", "LONG", 73500),
    ("2026-03-13 16:02", "LONG", 71891),
    ("2026-03-16 08:14", "LONG", 73545),
    ("2026-03-16 16:01", "LONG", 73172),
    ("2026-03-17 00:51", "LONG", 74930),
    ("2026-03-17 02:07", "LONG", 75287),
    ("2026-03-17 04:02", "LONG", 74562),
    ("2026-03-17 07:21", "LONG", 74319),
    ("2026-03-17 12:00", "LONG", 74013),
    ("2026-03-22 00:00", "SHORT", 68744),
    ("2026-03-22 08:00", "SHORT", 68860),
    ("2026-03-22 12:00", "SHORT", 68217),
    ("2026-03-23 00:00", "SHORT", 67975),
    ("2026-03-26 12:00", "SHORT", 69215),
    ("2026-03-26 13:44", "SHORT", 69385),
    ("2026-03-27 04:00", "SHORT", 68702),
    ("2026-03-28 08:00", "SHORT", 66460),
    ("2026-03-28 16:00", "SHORT", 66998),
]

TP_PCT = 0.71
SL_PCT = 1.333
TIME_LIMIT_H = 24

VARIANTS = {
    "V1": (0.20, 0.05),
    "V2": (0.25, 0.10),
    "V3": (0.30, 0.15),
    "V4": (0.35, 0.20),
    "V5": (0.25, 0.15),
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def dt_to_ms(dt_str):
    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)

def fetch_candles(entry_dt_str, limit=30):
    ms = dt_to_ms(entry_dt_str)
    url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&startTime={ms}&limit={limit}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    candles = []
    for k in data:
        candles.append({
            "open_time": k[0],
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
        })
    return candles

def simulate_trade(side, entry, candles, activate_pct, close_pct):
    """
    Returns (exit_type, exit_pnl_pct, peak_pnl_pct, candle_index)
    """
    peak = 0.0
    protection_active = False

    for i, c in enumerate(candles):
        if i >= TIME_LIMIT_H:
            # time exit — use close of this candle
            if side == "LONG":
                pnl = (c["close"] - entry) / entry * 100
            else:
                pnl = (entry - c["close"]) / entry * 100
            return ("TIME_EXIT", round(pnl, 4), round(peak, 4), i)

        if side == "LONG":
            best = (c["high"] - entry) / entry * 100
            worst = (c["low"] - entry) / entry * 100
        else:
            best = (entry - c["low"]) / entry * 100
            worst = (entry - c["high"]) / entry * 100

        # Check SL first (conservative)
        if worst <= -SL_PCT:
            return ("SL", round(-SL_PCT, 4), round(peak, 4), i)

        # Check TP
        if best >= TP_PCT:
            return ("TP", round(TP_PCT, 4), round(peak, 4), i)

        # Update peak
        if best > peak:
            peak = best

        # Profit protection logic
        if peak >= activate_pct:
            protection_active = True

        if protection_active and worst <= close_pct:
            return ("PROFIT_PROTECT", round(close_pct, 4), round(peak, 4), i)

    # ran out of candles — use last close
    c = candles[-1]
    if side == "LONG":
        pnl = (c["close"] - entry) / entry * 100
    else:
        pnl = (entry - c["close"]) / entry * 100
    return ("TIME_EXIT", round(pnl, 4), round(peak, 4), len(candles)-1)


def simulate_trade_no_protection(side, entry, candles):
    """Model A: plain TP/SL only."""
    peak = 0.0
    for i, c in enumerate(candles):
        if i >= TIME_LIMIT_H:
            if side == "LONG":
                pnl = (c["close"] - entry) / entry * 100
            else:
                pnl = (entry - c["close"]) / entry * 100
            return ("TIME_EXIT", round(pnl, 4), round(peak, 4), i)

        if side == "LONG":
            best = (c["high"] - entry) / entry * 100
            worst = (c["low"] - entry) / entry * 100
        else:
            best = (entry - c["low"]) / entry * 100
            worst = (entry - c["high"]) / entry * 100

        if worst <= -SL_PCT:
            return ("SL", round(-SL_PCT, 4), round(peak, 4), i)
        if best >= TP_PCT:
            return ("TP", round(TP_PCT, 4), round(peak, 4), i)
        if best > peak:
            peak = best

    c = candles[-1]
    if side == "LONG":
        pnl = (c["close"] - entry) / entry * 100
    else:
        pnl = (entry - c["close"]) / entry * 100
    return ("TIME_EXIT", round(pnl, 4), round(peak, 4), len(candles)-1)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("Fetching Binance 1h candles for 26 trades...")
    all_candles = []
    for dt_str, side, entry in TRADES:
        candles = fetch_candles(dt_str, limit=30)
        all_candles.append(candles)
        time.sleep(0.15)  # rate limit
    print(f"Fetched candles for all {len(TRADES)} trades.\n")

    # ── Model A (no protection) ────────────────────────────────────────────
    model_a_results = []
    for idx, (dt_str, side, entry) in enumerate(TRADES):
        r = simulate_trade_no_protection(side, entry, all_candles[idx])
        model_a_results.append(r)

    # ── All variants ───────────────────────────────────────────────────────
    variant_results = {}
    for vname, (act, cls) in VARIANTS.items():
        results = []
        for idx, (dt_str, side, entry) in enumerate(TRADES):
            r = simulate_trade(side, entry, all_candles[idx], act, cls)
            results.append(r)
        variant_results[vname] = results

    # ── Print V2 per-trade detail ──────────────────────────────────────────
    print("=" * 90)
    print("V2 (Activate +0.25%, Close +0.10%) — Per-Trade Results")
    print("=" * 90)
    print(f"{'#':>3} | {'Date':>16} | {'Side':>5} | {'Entry':>7} | {'Peak%':>7} | {'Exit Type':>15} | {'Exit PnL%':>9}")
    print("-" * 90)

    v2 = variant_results["V2"]
    for idx, (dt_str, side, entry) in enumerate(TRADES):
        exit_type, exit_pnl, peak_pnl, ci = v2[idx]
        print(f"{idx+1:>3} | {dt_str:>16} | {side:>5} | {entry:>7} | {peak_pnl:>+7.3f} | {exit_type:>15} | {exit_pnl:>+9.4f}")

    # ── Comparison table ───────────────────────────────────────────────────
    print("\n")
    print("=" * 105)
    print("Comparison Table — All Models")
    print("=" * 105)
    print(f"{'Model':>12} | {'WinRate':>7} | {'EV/trade%':>10} | {'EV USD':>8} | {'PF':>6} | {'MaxDD%':>7} | {'CumPnL%':>8} | {'Wins':>4} | {'Losses':>6}")
    print("-" * 105)

    def calc_stats(results, label):
        pnls = [r[1] for r in results]
        wins = sum(1 for p in pnls if p > 0)
        losses = sum(1 for p in pnls if p <= 0)
        wr = wins / len(pnls) * 100
        ev = np.mean(pnls)
        ev_usd = ev / 100 * 140
        cum = sum(pnls)
        gross_profit = sum(p for p in pnls if p > 0)
        gross_loss = abs(sum(p for p in pnls if p < 0))
        pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        # max drawdown (cumulative)
        cum_arr = np.cumsum(pnls)
        peak_cum = np.maximum.accumulate(cum_arr)
        dd = peak_cum - cum_arr
        max_dd = np.max(dd) if len(dd) > 0 else 0
        print(f"{label:>12} | {wr:>6.1f}% | {ev:>+10.4f} | ${ev_usd:>+7.2f} | {pf:>6.2f} | {max_dd:>6.3f}% | {cum:>+8.3f} | {wins:>4} | {losses:>6}")
        return pnls

    model_a_pnls = calc_stats(model_a_results, "Model A")
    variant_pnls = {}
    for vname in ["V1", "V2", "V3", "V4", "V5"]:
        variant_pnls[vname] = calc_stats(variant_results[vname], vname)

    # ── Find best variant ──────────────────────────────────────────────────
    best_name = max(variant_pnls, key=lambda v: np.mean(variant_pnls[v]))
    best_pnls = variant_pnls[best_name]
    best_results = variant_results[best_name]

    print(f"\nBest variant: {best_name} (activate={VARIANTS[best_name][0]}%, close={VARIANTS[best_name][1]}%)")

    # ── LONG vs SHORT breakdown for best ───────────────────────────────────
    print(f"\n{'='*70}")
    print(f"{best_name} — LONG vs SHORT Breakdown")
    print(f"{'='*70}")
    for subset_name, subset_side in [("LONG", "LONG"), ("SHORT", "SHORT")]:
        sub_pnls = [best_results[i][1] for i in range(len(TRADES)) if TRADES[i][1] == subset_side]
        if not sub_pnls:
            continue
        wins = sum(1 for p in sub_pnls if p > 0)
        print(f"  {subset_name}: {len(sub_pnls)} trades, WR={wins/len(sub_pnls)*100:.1f}%, "
              f"EV={np.mean(sub_pnls):+.4f}%, Cum={sum(sub_pnls):+.3f}%")

    # ── Saved / Clipped analysis for best variant ──────────────────────────
    print(f"\n{'='*70}")
    print(f"{best_name} — Saved vs Clipped Analysis")
    print(f"{'='*70}")
    saved = 0  # PP exit, but Model A would have hit SL
    clipped = 0  # PP exit, but Model A would have hit TP
    neutral = 0
    for i in range(len(TRADES)):
        if best_results[i][0] == "PROFIT_PROTECT":
            a_type = model_a_results[i][0]
            if a_type == "SL":
                saved += 1
                print(f"  Trade #{i+1}: SAVED — PP exit at +{best_results[i][1]:.2f}% vs Model A SL at {model_a_results[i][1]:+.4f}%")
            elif a_type == "TP":
                clipped += 1
                print(f"  Trade #{i+1}: CLIPPED — PP exit at +{best_results[i][1]:.2f}% vs Model A TP at +{model_a_results[i][1]:.4f}%")
            else:
                neutral += 1
                print(f"  Trade #{i+1}: NEUTRAL — PP exit at +{best_results[i][1]:.2f}% vs Model A {a_type} at {model_a_results[i][1]:+.4f}%")

    pp_count = sum(1 for r in best_results if r[0] == "PROFIT_PROTECT")
    print(f"\n  Total PP triggers: {pp_count}")
    print(f"  Saved from SL: {saved}")
    print(f"  Clipped from TP: {clipped}")
    print(f"  Neutral: {neutral}")

    # ── Monte Carlo for best variant ───────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"{best_name} — Monte Carlo (1000 paths x 100 trades)")
    print(f"{'='*70}")
    rng = np.random.default_rng(42)
    n_paths = 1000
    n_trades = 100
    pnl_arr = np.array(best_pnls)
    final_pnls = []
    for _ in range(n_paths):
        sampled = rng.choice(pnl_arr, size=n_trades, replace=True)
        final_pnls.append(np.sum(sampled))
    final_pnls = np.array(final_pnls)

    median = np.median(final_pnls)
    p5 = np.percentile(final_pnls, 5)
    p95 = np.percentile(final_pnls, 95)
    p_profit = np.mean(final_pnls > 0) * 100

    margin_per_trade = 140  # $140 notional
    print(f"  Median cumulative PnL:   {median:+.2f}%  (${median/100*margin_per_trade:+.1f})")
    print(f"  5th percentile:          {p5:+.2f}%  (${p5/100*margin_per_trade:+.1f})")
    print(f"  95th percentile:         {p95:+.2f}%  (${p95/100*margin_per_trade:+.1f})")
    print(f"  P(profitable after 100): {p_profit:.1f}%")
    print(f"  Mean:                    {np.mean(final_pnls):+.2f}%")
    print(f"  Std:                     {np.std(final_pnls):.2f}%")


if __name__ == "__main__":
    main()
