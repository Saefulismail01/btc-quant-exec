"""
Proposal D — Pullback Limit Entry: FULL ENGINE BACKTEST (v3)
=============================================================
Identik dengan v4_4_engine.py (engine asli Golden) tapi dengan dua mode:

  MODE = "market"   → entry di close candle signal (baseline, identik v4.4)
  MODE = "pullback" → pasang limit order di entry±pb%, tunggu max MAX_WAIT candle

Setiap signal dari layer stack (BCD+EMA+MLP+Spectrum) menghasilkan:
  - Satu trade di mode market
  - Satu trade (atau miss) di mode pullback

Output: CSV trades + summary JSON untuk kedua mode, plus tabel perbandingan.

Usage:
    cd backend
    python ..\backtest\scripts\pullback_v3_full_engine.py --start 2022-01-01 --end 2026-03-04
"""

import os
import sys
import json
import time
import logging
import argparse
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_ta as ta

# ── Path Setup (sama dengan v4_4_engine.py) ────────────────────────────────────
_SCRIPT_DIR   = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent
_BACKEND_DIR  = str(_PROJECT_ROOT / "backend")
_BACKEND_SCRIPTS = str(_PROJECT_ROOT / "backend" / "scripts")
for _p in [_BACKEND_DIR, _BACKEND_SCRIPTS]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ["BTC_QUANT_LAYER1_ENGINE"] = "bcd"

from utils.spectrum import DirectionalSpectrum
from data_engine   import DB_PATH

# ── Output ─────────────────────────────────────────────────────────────────────
_OUT_DIR = _PROJECT_ROOT / "backtest" / "results" / "pullback_v3"
_OUT_DIR.mkdir(parents=True, exist_ok=True)
_LOG_DIR = _PROJECT_ROOT / "backtest" / "logs" / "pullback_v3"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── Logging ────────────────────────────────────────────────────────────────────
_run_ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
_logfile = _LOG_DIR / f"pullback_v3_{_run_ts}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(_logfile, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("pullback_v3")


# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS — identik v4.4
# ══════════════════════════════════════════════════════════════════════════════

POSITION_USD     = 1_000.0
LEVERAGE         = 15.0
NOTIONAL         = POSITION_USD * LEVERAGE   # $15,000
FEE_RATE         = 0.0004
FEE_USD          = NOTIONAL * FEE_RATE * 2   # $12
SL_PCT           = 0.01333
TP_MIN_PCT       = 0.0071
MAX_HOLD_CANDLES = 6

# Pullback parameters (diuji semua dalam satu run)
PULLBACK_CONFIGS = [
    {"pb": 0.001, "wait": 1},
    {"pb": 0.002, "wait": 1},
    {"pb": 0.003, "wait": 1},
    {"pb": 0.003, "wait": 2},
    {"pb": 0.005, "wait": 1},
    {"pb": 0.005, "wait": 2},
]


# ══════════════════════════════════════════════════════════════════════════════
#  ENGINE PRIMITIVES — identik v4.4
# ══════════════════════════════════════════════════════════════════════════════

def calc_pnl(side: str, entry: float, exit_price: float) -> float:
    if side == "LONG":
        price_return = (exit_price - entry) / entry
    else:
        price_return = (entry - exit_price) / entry
    return round(NOTIONAL * price_return - FEE_USD, 2)


def check_sl_tp(side, sl, tp, c_high, c_low, c_close):
    """Identik dengan v4_4_engine.py — priority SL > TP, trail_tp = close."""
    if side == "LONG":
        if c_low <= sl:
            return sl, "SL"
        if c_high >= tp:
            return (c_close, "TRAIL_TP") if c_close >= tp else (tp, "TP")
    else:
        if c_high >= sl:
            return sl, "SL"
        if c_low <= tp:
            return (c_close, "TRAIL_TP") if c_close <= tp else (tp, "TP")
    return None, None


# ══════════════════════════════════════════════════════════════════════════════
#  DATA LOAD — identik v4.4 (DuckDB)
# ══════════════════════════════════════════════════════════════════════════════

def load_full_dataset() -> pd.DataFrame:
    import duckdb
    log.info("Loading full dataset from DuckDB...")
    with duckdb.connect(DB_PATH, read_only=True) as con:
        df = con.execute("""
            SELECT
                o.timestamp,
                o.open   AS Open,
                o.high   AS High,
                o.low    AS Low,
                o.close  AS Close,
                o.volume AS Volume,
                COALESCE(o.cvd, 0.0)           AS CVD,
                COALESCE(m.funding_rate, 0.0)  AS Funding,
                COALESCE(m.open_interest, 0.0) AS OI,
                COALESCE(m.fgi_value, 50.0)    AS FGI
            FROM btc_ohlcv_4h o
            ASOF LEFT JOIN market_metrics m ON o.timestamp >= m.timestamp
            ORDER BY o.timestamp ASC
        """).fetchdf()
    if df.empty:
        raise RuntimeError("DuckDB returned empty dataset.")
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("datetime")
    log.info(f"Loaded {len(df)} candles | {df.index[0]} → {df.index[-1]}")
    return df


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["EMA20"] = ta.ema(df["Close"], length=20)
    df["EMA50"] = ta.ema(df["Close"], length=50)
    df["ATR14"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)
    return df


# ══════════════════════════════════════════════════════════════════════════════
#  SIGNAL CAPTURE PASS — satu loop, kumpulkan semua signals
# ══════════════════════════════════════════════════════════════════════════════

def capture_signals(df_all: pd.DataFrame, t_start: int, t_end: int) -> list:
    """
    Jalankan layered signal stack (identik v4.4 entry section).
    Return list of signal dicts: {i, side, price, tag, bcd_conf, gate, fgi}.
    """
    from app.use_cases.bcd_service import get_bcd_service
    from app.use_cases.ai_service  import get_ai_service
    from app.use_cases.ema_service import get_ema_service
    from app.core.engines.layer1_volatility import get_vol_estimator

    bcd_svc  = get_bcd_service()
    ai_svc   = get_ai_service()
    ema_svc  = get_ema_service()
    vol_est  = get_vol_estimator()
    spectrum = DirectionalSpectrum()
    log.info("All services ready. Starting signal capture...")

    signals   = []
    n_candles = t_end - t_start
    t0 = time.time()
    last_log = t0

    for i in range(t_start, t_end - 1):   # -1 karena butuh candle i+1 untuk exit
        candle_dt = df_all.index[i]
        df_hist   = df_all.iloc[max(0, i - 499) : i + 1].copy()
        price_now = float(df_hist["Close"].iloc[-1])
        atr14     = float(df_hist["ATR14"].dropna().iloc[-1]) if df_hist["ATR14"].dropna().size else 0.01
        ema20     = float(df_hist["EMA20"].dropna().iloc[-1]) if df_hist["EMA20"].dropna().size else price_now
        ema50     = float(df_hist["EMA50"].dropna().iloc[-1]) if df_hist["EMA50"].dropna().size else price_now

        # EMA Trend
        if ema20 > ema50 and price_now > ema20:
            raw_trend = "BULL"
        elif ema20 < ema50 and price_now < ema20:
            raw_trend = "BEAR"
        elif price_now > ema50:
            raw_trend = "BULL"
        else:
            raw_trend = "BEAR"

        try:
            # L1: BCD
            label, tag, bcd_conf, hmm_states, hmm_index = \
                bcd_svc.get_regime_and_states(df_hist, funding_rate=0)
            l1_bull = (tag == "bull")
            l1_vote = float(bcd_conf if l1_bull else -bcd_conf)

            # L2: EMA
            l2_aligned, _, _ = ema_svc.get_alignment(df_hist, raw_trend)
            l2_vote = (
                1.0  if (l2_aligned and raw_trend == "BULL")
                else (-1.0 if (l2_aligned and raw_trend == "BEAR") else 0.0)
            )

            # L3: MLP AI
            ai_bias, ai_conf = ai_svc.get_confidence(
                df_hist, hmm_states=hmm_states, hmm_index=hmm_index
            )
            conf_norm = (max(50.0, min(100.0, float(ai_conf))) - 50.0) / 50.0
            l3_vote   = conf_norm if str(ai_bias) == "BULL" else -conf_norm

            # L4: Vol multiplier
            vol_ratio = atr14 / price_now if price_now > 0 else 0.001
            l4_mult   = spectrum.compute_l4_multiplier(vol_ratio)

            # Spectrum
            spec = spectrum.calculate(l1_vote, l2_vote, l3_vote, l4_mult, 5.0)

            fgi_val = float(df_hist["FGI"].iloc[-1]) if "FGI" in df_hist.columns else 50.0

            if spec.trade_gate not in ("ACTIVE", "ADVISORY"):
                continue

            is_bull = spec.directional_bias >= 0
            side    = "LONG" if is_bull else "SHORT"

            # Sama dengan v4.4 ADVISORY filter
            if spec.trade_gate == "ADVISORY" and side == "SHORT" and tag == "bear":
                continue

            signals.append({
                "i"       : i,
                "side"    : side,
                "price"   : price_now,
                "tag"     : str(tag),
                "bcd_conf": round(float(bcd_conf), 4),
                "gate"    : spec.trade_gate,
                "fgi"     : fgi_val,
            })

        except Exception as exc:
            pass

        # Progress
        now = time.time()
        if now - last_log >= 15:
            pct     = (i - t_start) / max(n_candles, 1) * 100
            elapsed = now - t0
            eta_s   = (elapsed / max(pct, 0.01)) * (100 - pct)
            log.info(
                f"  ▶ [{candle_dt.strftime('%Y-%m-%d')}] {pct:5.1f}%"
                f"  │ Signals: {len(signals)}"
                f"  │ ETA: {eta_s/60:.1f}m"
            )
            last_log = now

    log.info(f"Signal capture complete: {len(signals)} signals in {time.time()-t0:.0f}s")
    return signals


# ══════════════════════════════════════════════════════════════════════════════
#  SIMULATE TRADES — from list of signals
# ══════════════════════════════════════════════════════════════════════════════

def run_exit_from(df_all: pd.DataFrame, side: str, entry_px: float, entry_ci: int) -> tuple:
    """
    Jalankan exit logic dari entry_ci+1 s/d entry_ci+MAX_HOLD_CANDLES.
    Identik dengan v4_4_engine.py exit section.
    Return (pnl, exit_type, exit_price, holding_candles, exit_time).
    """
    N = len(df_all)
    if side == "LONG":
        sl = entry_px * (1.0 - SL_PCT)
        tp = entry_px * (1.0 + TP_MIN_PCT)
    else:
        sl = entry_px * (1.0 + SL_PCT)
        tp = entry_px * (1.0 - TP_MIN_PCT)

    for hold in range(1, MAX_HOLD_CANDLES + 1):
        ci = entry_ci + hold
        if ci >= N:
            ep  = float(df_all.iloc[N - 1]["Close"])
            et  = df_all.index[N - 1].isoformat()
            return calc_pnl(side, entry_px, ep), "TIME_EXIT", ep, hold, et

        c      = df_all.iloc[ci]
        c_high = float(c["High"])
        c_low  = float(c["Low"])
        c_close= float(c["Close"])

        ep, etype = check_sl_tp(side, sl, tp, c_high, c_low, c_close)
        if ep is not None:
            return calc_pnl(side, entry_px, ep), etype, ep, hold, df_all.index[ci].isoformat()

        if hold == MAX_HOLD_CANDLES:
            et = df_all.index[ci].isoformat()
            return calc_pnl(side, entry_px, c_close), "TIME_EXIT", c_close, hold, et

    # fallback
    last_ci = min(entry_ci + MAX_HOLD_CANDLES, N - 1)
    ep = float(df_all.iloc[last_ci]["Close"])
    return calc_pnl(side, entry_px, ep), "TIME_EXIT", ep, MAX_HOLD_CANDLES, df_all.index[last_ci].isoformat()


def simulate_market(df_all: pd.DataFrame, signals: list) -> list:
    """Baseline: entry langsung di close candle signal."""
    trades = []
    skip_until = -1
    for sig in signals:
        i = sig["i"]
        if i <= skip_until:
            continue

        side  = sig["side"]
        entry = sig["price"]   # close candle i = entry price

        pnl, etype, ep, hold, exit_t = run_exit_from(df_all, side, entry, i)

        trades.append({
            "entry_time"     : df_all.index[i].isoformat(),
            "exit_time"      : exit_t,
            "side"           : side,
            "entry_price"    : round(entry, 2),
            "exit_price"     : round(ep, 2),
            "pnl_usd"        : pnl,
            "exit_type"      : etype,
            "holding_candles": hold,
            "bcd_conf"       : sig["bcd_conf"],
            "regime"         : sig["tag"],
            "gate"           : sig["gate"],
        })
        skip_until = i + hold   # no overlapping positions
    return trades


def simulate_pullback(df_all: pd.DataFrame, signals: list, pb: float, max_wait: int) -> list:
    """
    Pullback mode: pasang limit di price*(1-pb) untuk LONG, price*(1+pb) untuk SHORT.
    Tunggu fill dalam max_wait candle setelah signal candle.
    Jika fill → jalankan exit dari fill candle.
    Jika tidak fill → trade MISS.
    """
    N = len(df_all)
    trades = []
    skip_until = -1

    for sig in signals:
        i = sig["i"]
        if i <= skip_until:
            continue

        side     = sig["side"]
        orig_px  = sig["price"]
        limit_px = orig_px * (1.0 - pb) if side == "LONG" else orig_px * (1.0 + pb)

        # Cari fill: scan candle i .. i+max_wait
        fill_ci = None
        for ci in range(i, min(i + max_wait + 1, N)):
            c = df_all.iloc[ci]
            if side == "LONG"  and float(c["Low"])  <= limit_px:
                fill_ci = ci
                break
            if side == "SHORT" and float(c["High"]) >= limit_px:
                fill_ci = ci
                break

        if fill_ci is None:
            trades.append({
                "entry_time"     : df_all.index[i].isoformat(),
                "exit_time"      : None,
                "side"           : side,
                "entry_price"    : None,
                "exit_price"     : None,
                "pnl_usd"        : None,
                "exit_type"      : "MISS",
                "holding_candles": 0,
                "bcd_conf"       : sig["bcd_conf"],
                "regime"         : sig["tag"],
                "gate"           : sig["gate"],
                "limit_px"       : round(limit_px, 2),
            })
            continue

        # Fill! Run exit
        pnl, etype, ep, hold, exit_t = run_exit_from(df_all, side, limit_px, fill_ci)
        trades.append({
            "entry_time"     : df_all.index[fill_ci].isoformat(),
            "exit_time"      : exit_t,
            "side"           : side,
            "entry_price"    : round(limit_px, 2),
            "exit_price"     : round(ep, 2),
            "pnl_usd"        : pnl,
            "exit_type"      : etype,
            "holding_candles": hold,
            "bcd_conf"       : sig["bcd_conf"],
            "regime"         : sig["tag"],
            "gate"           : sig["gate"],
            "limit_px"       : round(limit_px, 2),
        })
        skip_until = fill_ci + hold
    return trades


# ══════════════════════════════════════════════════════════════════════════════
#  STATS
# ══════════════════════════════════════════════════════════════════════════════

def calc_stats(trades: list, label: str) -> dict:
    filled = [t for t in trades if t["pnl_usd"] is not None]
    missed = [t for t in trades if t["pnl_usd"] is None]

    if not filled:
        return {"label": label, "n": 0, "n_missed": len(missed)}

    pnls   = [t["pnl_usd"] for t in filled]
    wins   = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gw     = sum(wins)
    gl     = abs(sum(losses))
    aw     = gw / len(wins)   if wins   else 0
    al     = gl / len(losses) if losses else 0

    return {
        "label"    : label,
        "n"        : len(filled),
        "n_missed" : len(missed),
        "fill_rate": round(len(filled) / (len(filled) + len(missed)) * 100, 1),
        "wr"       : round(len(wins) / len(filled) * 100, 2),
        "net"      : round(sum(pnls), 2),
        "avg_win"  : round(aw, 2),
        "avg_loss" : round(-al, 2),
        "rr"       : round(aw / al if al > 0 else 0, 3),
        "pf"       : round(gw / gl if gl > 0 else 0, 3),
        "npt"      : round(sum(pnls) / len(filled), 2),
        "n_sl"     : sum(1 for t in filled if t["exit_type"] == "SL"),
        "n_tp"     : sum(1 for t in filled if t["exit_type"] == "TP"),
        "n_trail"  : sum(1 for t in filled if t["exit_type"] == "TRAIL_TP"),
        "n_time"   : sum(1 for t in filled if t["exit_type"] == "TIME_EXIT"),
    }


def print_stats(s: dict, bl: dict = None):
    d = lambda key: f" (Δ{s[key]-bl[key]:+.2f})" if bl and key in bl and key in s else ""
    log.info(f"  {'─'*60}")
    log.info(f"  {s['label']}")
    if "fill_rate" in s:
        log.info(f"    Fill rate   : {s['fill_rate']}%  ({s['n']} filled | {s.get('n_missed',0)} missed)")
    log.info(f"    WR          : {s.get('wr', 0):.2f}%{d('wr')}")
    log.info(f"    Net PnL     : ${s.get('net', 0):,.2f}{d('net')}")
    log.info(f"    R:R         : {s.get('rr', 0):.3f}{d('rr')}")
    log.info(f"    PF          : {s.get('pf', 0):.3f}{d('pf')}")
    log.info(f"    Net/trade   : ${s.get('npt', 0):+.2f}{d('npt')}")
    if "n_sl" in s:
        log.info(f"    Exit dist   : SL={s['n_sl']} TP={s['n_tp']} TRAIL={s['n_trail']} TIME={s['n_time']}")


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start",   default="2022-01-01")
    parser.add_argument("--end",     default="2026-03-04")
    parser.add_argument("--capital", default=10_000.0, type=float)
    parser.add_argument("--history", default=400, type=int)
    args = parser.parse_args()

    log.info("=" * 72)
    log.info("  PULLBACK ENTRY — FULL ENGINE BACKTEST (v3)")
    log.info(f"  Window : {args.start}  →  {args.end}")
    log.info(f"  Engine : v4.4 Golden (BCD+EMA+MLP+Spectrum)")
    log.info(f"  Configs: {len(PULLBACK_CONFIGS)} pullback configs")
    log.info("=" * 72)

    # ── Load & Prep ────────────────────────────────────────────────────────────
    df_all = load_full_dataset()
    df_all = add_indicators(df_all)

    start_dt = pd.to_datetime(args.start).tz_localize("UTC")
    end_dt   = pd.to_datetime(args.end).tz_localize("UTC")

    db_first_tradeable = df_all.index[args.history]
    if start_dt < db_first_tradeable:
        log.warning(f"Auto-adjusting start → {db_first_tradeable.date()}")
        start_dt = db_first_tradeable

    pos_all   = np.arange(len(df_all))
    window_ci = pos_all[(df_all.index >= start_dt) & (df_all.index <= end_dt)]
    t_start   = int(window_ci[0])
    t_end     = int(window_ci[-1])
    log.info(f"  Candles in window : {len(window_ci):,}  (ci {t_start}–{t_end})\n")

    # ── Capture signals (satu pass, dipakai ulang untuk semua configs) ─────────
    signals = capture_signals(df_all, t_start, t_end)
    log.info(f"\n  Total signals: {len(signals)}\n")

    # ── Simulate baseline (market entry) ──────────────────────────────────────
    log.info("Simulating MARKET (baseline)...")
    market_trades = simulate_market(df_all, signals)
    bl = calc_stats(market_trades, "BASELINE (market entry)")
    print_stats(bl)

    # ── Save baseline trades ───────────────────────────────────────────────────
    bl_tag = f"pullback_v3_{_run_ts}"
    pd.DataFrame(market_trades).to_csv(_OUT_DIR / f"{bl_tag}_market_trades.csv", index=False)

    # ── Simulate pullback configs ──────────────────────────────────────────────
    all_stats = [bl]
    all_pb_trades = {}

    for cfg in PULLBACK_CONFIGS:
        pb       = cfg["pb"]
        max_wait = cfg["wait"]
        label    = f"PULLBACK pb={pb*100:.2f}% wait={max_wait}c"
        log.info(f"\nSimulating {label}...")

        pb_trades = simulate_pullback(df_all, signals, pb, max_wait)
        s = calc_stats(pb_trades, label)
        print_stats(s, bl)
        all_stats.append(s)
        all_pb_trades[f"pb{pb*1000:.0f}_w{max_wait}"] = pb_trades

        # Save trades CSV
        cfg_tag = f"pb{pb*1000:.0f}pct_w{max_wait}"
        pd.DataFrame(pb_trades).to_csv(_OUT_DIR / f"{bl_tag}_{cfg_tag}_trades.csv", index=False)

    # ── Summary Table ──────────────────────────────────────────────────────────
    log.info("\n" + "=" * 72)
    log.info("  SUMMARY TABLE")
    log.info("=" * 72)
    header = f"{'Config':35s} {'Fill%':6s} {'WR%':6s} {'ΔWR':6s} {'Net/tr':8s} {'ΔNet/tr':8s} {'PF':6s} {'R:R':6s}"
    log.info(header)
    log.info("─" * 72)
    for s in all_stats:
        fill = f"{s.get('fill_rate', 100):.1f}" if "fill_rate" in s else "100.0"
        dwr  = f"{s.get('wr',0)-bl['wr']:+.2f}" if s['label'] != bl['label'] else "  —  "
        dnpt = f"{s.get('npt',0)-bl['npt']:+.2f}" if s['label'] != bl['label'] else "  —  "
        log.info(
            f"{s['label'][:35]:35s} {fill:6s} {s.get('wr',0):6.2f} {dwr:6s} "
            f"{s.get('npt',0):8.2f} {dnpt:8s} {s.get('pf',0):6.3f} {s.get('rr',0):6.3f}"
        )

    # Best
    pb_only = [s for s in all_stats if s['label'] != bl['label'] and 'npt' in s]
    if pb_only:
        best = max(pb_only, key=lambda s: s['npt'])
        log.info(f"\n  ★ BEST pullback config: {best['label']}")
        log.info(f"    WR={best['wr']}%  Net/trade=${best['npt']:+.2f}  PF={best['pf']}  R:R={best['rr']}")

    # ── Save Summary JSON ──────────────────────────────────────────────────────
    summary = {
        "run_timestamp": _run_ts,
        "window_start" : args.start,
        "window_end"   : args.end,
        "n_signals"    : len(signals),
        "stats"        : all_stats,
    }
    out_path = _OUT_DIR / f"{bl_tag}_summary.json"
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    log.info(f"\n  [✓] Summary → {out_path}")
    log.info(f"  [✓] Log     → {_logfile}")
    log.info("=" * 72)


if __name__ == "__main__":
    main()
