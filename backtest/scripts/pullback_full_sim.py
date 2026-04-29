"""
Proposal D — Pullback Limit Entry: FULL RE-SIMULATION
======================================================
Properly re-simulates the entire trade lifecycle after pullback fill:

1. Signal fires at candle T → baseline entry_price
2. Place limit at entry_price ± pb_pct
3. Scan forward up to MAX_WAIT candles for fill (check Low/High)
4. If filled at limit_px: set new SL and TP (same sl_pct / tp_pct from baseline)
5. Continue scanning candles AFTER fill candle for SL/TP/TIME exit
6. Exit logic mirrors baseline Golden model:
   - SL hit if Low (LONG) or High (SHORT) crosses sl level
   - TP hit if High (LONG) or Low (SHORT) crosses tp level
   - TIME_EXIT after max_hold candles (same as baseline holding_candles cap)
   - Trailing TP: if move exceeds tp_pct * 2, trail at highest/lowest close

No lookahead bias — exit is determined purely from OHLC data after fill candle.
"""

import csv
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.parent
TRADES_CSV = BASE_DIR / "results/v4_5_comparison_results/v4_5_201901_202603_20260309_102822_golden_trades.csv"
OHLCV_CSV  = BASE_DIR / "data/BTC_USDT_4h_2020_2026_with_bcd.csv"
OUT_DIR    = BASE_DIR / "results/rpf_analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Parameters ────────────────────────────────────────────────────────────────
PULLBACK_PCTS    = [0.0010, 0.0015, 0.0020, 0.0030, 0.0050]
MAX_WAIT_CANDLES = [1, 2, 3]
MAX_HOLD_CANDLES = 6     # max candles to hold — matches baseline engine (max=6 in data)
TRAIL_TRIGGER    = 2.0   # trailing TP activates when move >= tp_pct * TRAIL_TRIGGER

# ── Load OHLCV ────────────────────────────────────────────────────────────────
print("Loading OHLCV...")
ohlcv = pd.read_csv(OHLCV_CSV, index_col=0, parse_dates=True)
ohlcv.index = pd.to_datetime(ohlcv.index, utc=True)
ohlcv.columns = [c.capitalize() for c in ohlcv.columns]
if "High" not in ohlcv.columns:
    ohlcv.rename(columns={"high":"High","low":"Low","open":"Open","close":"Close"}, inplace=True)
ohlcv = ohlcv[["Open","High","Low","Close"]].copy()
print(f"  {len(ohlcv)} rows  ({str(ohlcv.index[0])[:10]} — {str(ohlcv.index[-1])[:10]})")

# ── Load Trades ───────────────────────────────────────────────────────────────
print("Loading trades...")
trades_raw = []
with open(TRADES_CSV, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        trades_raw.append(row)
print(f"  {len(trades_raw)} trades loaded.\n")

# ── Stats helper ──────────────────────────────────────────────────────────────
def calc_stats(pnls: list[float]) -> dict:
    if not pnls:
        return {"n":0,"wr":0,"net":0,"avg_win":0,"avg_loss":0,"rr":0,"pf":0,"npt":0}
    wins   = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    net    = sum(pnls)
    gw     = sum(wins)
    gl     = abs(sum(losses))
    aw     = gw / len(wins)   if wins   else 0
    al     = gl / len(losses) if losses else 0
    pf     = gw / gl          if gl > 0 else float("inf")
    rr     = aw / al          if al > 0 else float("inf")
    wr     = len(wins) / len(pnls) * 100
    return {
        "n":   len(pnls),
        "wr":  round(wr, 2),
        "net": round(net, 2),
        "avg_win":  round(aw, 2),
        "avg_loss": round(-al, 2),
        "rr":  round(rr, 3),
        "pf":  round(pf, 3),
        "npt": round(net / len(pnls), 2),
    }

# ── Baseline ──────────────────────────────────────────────────────────────────
baseline_pnls = [float(t["pnl_usd"]) for t in trades_raw]
bl = calc_stats(baseline_pnls)
print(f"{'='*72}")
print(f"BASELINE  n={bl['n']}  WR={bl['wr']}%  Net=${bl['net']:,.0f}  "
      f"R:R={bl['rr']}  PF={bl['pf']}  Net/trade=${bl['npt']}")
print(f"{'='*72}\n")

# ── Simulate one trade with pullback + proper exit ─────────────────────────────
def simulate_trade(
    side: str,
    signal_idx: int,
    orig_entry: float,
    sl_pct: float,
    tp_pct: float,
    notional: float,
    leverage: float,
    pb: float,
    max_wait: int,
) -> float | None:
    """
    Returns PnL USD if trade fills and exits, or None if limit never filled.
    signal_idx: index in ohlcv of the candle where signal fired (entry candle).
    """
    n = len(ohlcv)

    # Limit price
    if side == "LONG":
        limit_px = orig_entry * (1.0 - pb)
    else:
        limit_px = orig_entry * (1.0 + pb)

    # Phase 1: Scan for fill within max_wait candles starting at signal_idx
    fill_px  = None
    fill_candle_idx = None
    sig = int(signal_idx)
    for ci in range(sig, min(sig + max_wait + 1, n)):
        c = ohlcv.iloc[ci]
        if side == "LONG"  and c["Low"]  <= limit_px:
            fill_px = limit_px
            fill_candle_idx = ci
            break
        if side == "SHORT" and c["High"] >= limit_px:
            fill_px = limit_px
            fill_candle_idx = ci
            break

    if fill_px is None or fill_candle_idx is None:
        return None   # missed

    fill_px_f = float(fill_px)
    fill_ci   = int(fill_candle_idx)

    # Compute absolute SL / TP from new entry
    if side == "LONG":
        sl_abs = fill_px_f * (1.0 - sl_pct)
        tp_abs = fill_px_f * (1.0 + tp_pct)
        trail_trigger_abs = fill_px_f * (1.0 + tp_pct * TRAIL_TRIGGER)
    else:
        sl_abs = fill_px_f * (1.0 + sl_pct)
        tp_abs = fill_px_f * (1.0 - tp_pct)
        trail_trigger_abs = fill_px_f * (1.0 - tp_pct * TRAIL_TRIGGER)

    # Phase 2: Scan candles for exit — start at fill_ci itself (rest of fill candle)
    # then continue to subsequent candles up to MAX_HOLD_CANDLES after fill_ci
    trailing_active = False
    trail_ref       = fill_px_f   # best price seen once trailing active

    for ci in range(fill_ci, min(fill_ci + 1 + MAX_HOLD_CANDLES, n)):
        c = ohlcv.iloc[ci]
        high  = float(c["High"])
        low   = float(c["Low"])
        close = float(c["Close"])

        if side == "LONG":
            # Check SL
            if low <= sl_abs:
                exit_px = sl_abs
                move    = (exit_px - fill_px_f) / fill_px_f
                return notional * move * leverage

            # Activate trailing if high exceeds trigger
            if high >= trail_trigger_abs:
                trailing_active = True
                trail_ref = max(trail_ref, high)

            if trailing_active:
                trail_ref = max(trail_ref, high)
                trail_sl  = trail_ref * (1.0 - sl_pct)
                if low <= trail_sl:
                    exit_px = trail_sl
                    move    = (exit_px - fill_px_f) / fill_px_f
                    return notional * move * leverage

            # Check TP
            if high >= tp_abs and not trailing_active:
                exit_px = tp_abs
                move    = (exit_px - fill_px_f) / fill_px_f
                return notional * move * leverage

        else:  # SHORT
            # Check SL
            if high >= sl_abs:
                exit_px = sl_abs
                move    = (fill_px_f - exit_px) / fill_px_f
                return notional * move * leverage

            # Activate trailing
            if low <= trail_trigger_abs:
                trailing_active = True
                trail_ref = min(trail_ref, low)

            if trailing_active:
                trail_ref = min(trail_ref, low)
                trail_sl  = trail_ref * (1.0 + sl_pct)
                if high >= trail_sl:
                    exit_px = trail_sl
                    move    = (fill_px_f - exit_px) / fill_px_f
                    return notional * move * leverage

            # Check TP
            if low <= tp_abs and not trailing_active:
                exit_px = tp_abs
                move    = (fill_px_f - exit_px) / fill_px_f
                return notional * move * leverage

    # TIME_EXIT: use close of last scanned candle
    last_idx = min(fill_ci + MAX_HOLD_CANDLES, n - 1)
    exit_px  = float(ohlcv.iloc[last_idx]["Close"])
    if side == "LONG":
        move = (exit_px - fill_px_f) / fill_px_f
    else:
        move = (fill_px_f - exit_px) / fill_px_f
    return notional * move * leverage


# ── Pre-index: map entry_time → ohlcv index ──────────────────────────────────
ohlcv_start = pd.Timestamp(ohlcv.index[0])
ohlcv_end   = pd.Timestamp(ohlcv.index[-1])
n_out_of_range = sum(
    1 for t in trades_raw
    if pd.Timestamp(t["entry_time"].replace("+00:00",""), tz="UTC") < ohlcv_start
)
print(f"Trades outside OHLCV range (skipped from re-sim): {n_out_of_range} "
      f"({n_out_of_range/len(trades_raw)*100:.1f}%) — will use baseline PnL")
print(f"Trades within OHLCV range (fully re-simulated): {len(trades_raw)-n_out_of_range}")
print()

all_results = []

for pb in PULLBACK_PCTS:
    for max_wait in MAX_WAIT_CANDLES:
        pnls_filled       = []
        missed_pnls       = []
        out_of_range_pnls = []   # trades before OHLCV — kept at baseline PnL

        for t in trades_raw:
            side       = t["side"].upper()
            entry_ts   = pd.Timestamp(t["entry_time"].replace("+00:00",""), tz="UTC")
            orig_entry = float(t["entry_price"])
            sl_pct     = float(t["sl_pct"])
            tp_pct     = float(t["tp_pct"])
            notional   = float(t["notional"])
            leverage   = float(t["leverage"])
            orig_pnl   = float(t["pnl_usd"])

            # Bug fix: skip trades outside OHLCV — don't mismatch with wrong candles
            if entry_ts < ohlcv_start or entry_ts > ohlcv_end:
                out_of_range_pnls.append(orig_pnl)
                continue

            sig_idx = ohlcv.index.get_indexer([entry_ts], method="nearest")[0]
            if sig_idx < 0 or sig_idx >= len(ohlcv):
                out_of_range_pnls.append(orig_pnl)
                continue

            pnl = simulate_trade(
                side, sig_idx, orig_entry,
                sl_pct, tp_pct, notional, leverage,
                pb, max_wait
            )
            if pnl is None:
                missed_pnls.append(float(t["pnl_usd"]))
            else:
                pnls_filled.append(pnl)

        # Combine: re-simulated filled + out_of_range (kept at baseline PnL)
        all_pnls   = pnls_filled + out_of_range_pnls
        n_in_range = len(trades_raw) - len(out_of_range_pnls)
        fill_rate  = len(pnls_filled) / n_in_range * 100 if n_in_range > 0 else 0

        s = calc_stats(all_pnls)
        delta_wr    = round(s["wr"]  - bl["wr"],  2)
        delta_net   = round(s["net"] - bl["net"],  2)
        delta_rr    = round(s["rr"]  - bl["rr"],   3)
        delta_pf    = round(s["pf"]  - bl["pf"],   3)
        delta_npt   = round(s["npt"] - bl["npt"],   2)
        missed_sum  = round(sum(missed_pnls), 2)

        row = {
            "pb_pct": pb, "max_wait": max_wait,
            "n_filled": len(pnls_filled), "n_missed": len(missed_pnls),
            "n_out_of_range": len(out_of_range_pnls),
            "fill_rate_inrange": round(fill_rate, 1),
            "missed_pnl": missed_sum,
            "stats": s,
            "delta_wr": delta_wr, "delta_net": delta_net,
            "delta_rr": delta_rr, "delta_pf":  delta_pf,
            "delta_npt": delta_npt,
        }
        all_results.append(row)

        print(f"pb={pb:.3f} wait={max_wait}c  "
              f"fill={fill_rate:5.1f}% of in-range ({len(pnls_filled):4d} fill/{len(missed_pnls):3d} miss)  "
              f"WR={s['wr']:5.1f}% (Δ{delta_wr:+.1f})  "
              f"Net=${s['net']:>10,.0f} (Δ${delta_net:>+9,.0f})  "
              f"R:R={s['rr']:.3f} (Δ{delta_rr:+.3f})  "
              f"PF={s['pf']:.3f} (Δ{delta_pf:+.3f})  "
              f"Net/trade=${s['npt']:+.2f} (Δ${delta_npt:+.2f})  "
              f"| missed=${missed_sum:+,.0f}")

# ── Best ──────────────────────────────────────────────────────────────────────
def print_best(r: dict, label: str):
    s = r["stats"]
    print(f"\n{'='*72}")
    print(f"BEST ({label}):")
    print(f"  Pullback : {r['pb_pct']*100:.2f}%  |  Max wait: {r['max_wait']} candle(s)")
    print(f"  Fill rate (in-range): {r['fill_rate_inrange']}%  ({r['n_filled']} filled | {r['n_missed']} missed | {r['n_out_of_range']} out-of-range)")
    print(f"  Missed PnL if had taken at market: ${r['missed_pnl']:+,.2f}")
    print(f"  WR       : {s['wr']}%   (Δ{r['delta_wr']:+.2f}%)")
    print(f"  Net PnL  : ${s['net']:,.2f}  (Δ${r['delta_net']:+,.2f})")
    print(f"  R:R      : {s['rr']}   (Δ{r['delta_rr']:+.3f})")
    print(f"  PF       : {s['pf']}   (Δ{r['delta_pf']:+.3f})")
    print(f"  Net/trade: ${s['npt']:+.2f}  (Δ${r['delta_npt']:+.2f})")
    print(f"{'='*72}")

best_npt = max(all_results, key=lambda r: r["delta_npt"])
best_net = max(all_results, key=lambda r: r["delta_net"])
print_best(best_npt, "Net/trade")
print_best(best_net, "Absolute Net PnL")

# ── Save ──────────────────────────────────────────────────────────────────────
out = {
    "run_timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
    "baseline": bl,
    "results":  all_results,
    "best_npt": best_npt,
    "best_net": best_net,
}
out_path = OUT_DIR / "pullback_fullsim_results.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)
print(f"\nSaved: {out_path}")
