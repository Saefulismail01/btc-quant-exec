"""
╔══════════════════════════════════════════════════════════════════════╗
║  BTC-QUANT: EVOLUTION COMPARISON ENGINE                              ║
║                                                                      ║
║  Tujuan: Menjalankan tiga konfigurasi pada periode yang SAMA         ║
║  agar perbandingan antar generasi valid secara metodologis.          ║
║                                                                      ║
║  Konfigurasi:                                                        ║
║    v0.1-style  : L1 BCD only  + Compounding 2% equity/trade         ║
║    v1-style    : Full L1-L4   + Compounding 2% equity/trade         ║
║    v4.4 Golden : Full L1-L4   + Fixed $1,000 × 15x (referensi)      ║
║                                                                      ║
║  Variabel yang diisolasi:                                            ║
║    - layer_mode  : "l1_only" | "full"                                ║
║    - sizing_mode : "compound" | "fixed"                              ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pandas_ta as ta

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_BACKEND_DIR  = str(_PROJECT_ROOT / "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

os.environ["BTC_QUANT_LAYER1_ENGINE"] = "bcd"

from utils.spectrum import DirectionalSpectrum
from data_engine   import DB_PATH

_RESULTS_DIR = _PROJECT_ROOT / "backtest" / "results" / "v4_evolution_results"
_LOGS_DIR    = _PROJECT_ROOT / "backtest" / "logs"    / "v4_evolution"
_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
_LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Constants ──────────────────────────────────────────────────────────────────
SL_PCT          = 0.01333       # 1.333% SL (sama untuk semua mode)
TP_MIN_PCT      = 0.0071        # 0.71% TP (sama untuk semua mode)
FEE_RATE        = 0.0004        # 0.04% taker per leg
MAX_HOLD_CANDLES = 6

# Fixed sizing (v4.4 Golden mode)
FIXED_POSITION_USD = 1_000.0
FIXED_LEVERAGE     = 15.0
FIXED_NOTIONAL     = FIXED_POSITION_USD * FIXED_LEVERAGE
FIXED_FEE_USD      = FIXED_NOTIONAL * FEE_RATE * 2

# Compounding sizing (v0.1 / v1 mode)
COMPOUND_RISK_PCT  = 0.02       # 2% ekuitas per trade
COMPOUND_MAX_LEV   = 15.0       # cap leverage


def _setup_logger(run_name: str) -> logging.Logger:
    log_file = _LOGS_DIR / f"{run_name}.log"
    logger   = logging.getLogger(run_name)
    logger.setLevel(logging.INFO)
    if logger.hasHandlers():
        logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    logger.addHandler(logging.FileHandler(log_file, encoding="utf-8"))
    logger.addHandler(logging.StreamHandler(sys.stdout))
    for h in logger.handlers:
        h.setFormatter(fmt)
    return logger


def _load_dataset() -> pd.DataFrame:
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
    return df


def _add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["EMA20"] = ta.ema(df["Close"], length=20)
    df["EMA50"] = ta.ema(df["Close"], length=50)
    df["ATR14"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)
    return df


def _calc_notional_compound(portfolio: float) -> float:
    risk_usd = portfolio * COMPOUND_RISK_PCT
    notional = risk_usd / SL_PCT
    notional = min(notional, portfolio * COMPOUND_MAX_LEV)
    notional = max(notional, 100.0)
    return notional


def _calc_pnl(side: str, entry: float, exit_price: float, notional: float) -> float:
    fee_usd = notional * FEE_RATE * 2
    if side == "LONG":
        price_return = (exit_price - entry) / entry
    else:
        price_return = (entry - exit_price) / entry
    return round(notional * price_return - fee_usd, 2)


def _check_sl_tp(side, sl, tp, c_high, c_low, c_close):
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
    return None


def _record_trade(trades, daily_stats, equity_curve, position, exit_price,
                  exit_type, exit_time, pnl, portfolio, holding_candles):
    entry  = position["entry"]
    side   = position["side"]
    actual = ((exit_price - entry) / entry * 100 if side == "LONG"
              else (entry - exit_price) / entry * 100)
    trades.append({
        "entry_time"    : position["entry_time"],
        "exit_time"     : exit_time,
        "side"          : side,
        "entry_price"   : round(entry, 2),
        "exit_price"    : round(exit_price, 2),
        "pnl_usd"       : round(pnl, 2),
        "equity"        : round(portfolio, 2),
        "exit_type"     : exit_type,
        "gate"          : position["gate"],
        "regime"        : position["regime"],
        "notional"      : round(position["notional"], 2),
        "holding_candles": holding_candles,
        "actual_move_pct": round(actual, 4),
    })
    equity_curve.append({"candle": exit_time, "equity": round(portfolio, 2)})
    d_key = exit_time[:10]
    daily_stats.setdefault(d_key, {"pnl": 0.0, "n_trades": 0})
    daily_stats[d_key]["pnl"]      += pnl
    daily_stats[d_key]["n_trades"] += 1


def run_evolution(
    layer_mode:       str   = "full",      # "l1_only" | "full"
    sizing_mode:      str   = "fixed",     # "fixed" | "compound"
    window_start:     str   = "2024-01-01",
    window_end:       str   = "2026-03-04",
    required_history: int   = 400,
    initial_capital:  float = 10_000.0,
) -> dict:
    """
    Jalankan satu konfigurasi evolusi. Return dict summary.

    layer_mode:
        "l1_only" — hanya BCD (L1) yang berkontribusi ke Spectrum; L2 dan L3 di-disable.
                    Merepresentasikan v0.1: proof-of-concept validitas Layer 1 BCD.
        "full"    — full stack L1+L2+L3+L4, identik dengan arsitektur v4.4.

    sizing_mode:
        "fixed"    — margin $1,000 × 15x tetap per trade (v4.4 Golden).
        "compound" — 2% ekuitas per trade, notional menyesuaikan portfolio saat ini.
                     Merepresentasikan v1: sizing agresif yang memperbesar posisi
                     seiring pertumbuhan modal.
    """
    run_ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = f"evo_{layer_mode}_{sizing_mode}_{run_ts}"
    log      = _setup_logger(run_name)

    mode_label = {
        ("l1_only", "compound"): "v0.1-style  | L1 BCD only + Compounding 2%",
        ("full",    "compound"): "v1-style    | Full L1-L4 + Compounding 2%",
        ("full",    "fixed")   : "v4.4 Golden | Full L1-L4 + Fixed $1k×15x",
    }.get((layer_mode, sizing_mode), f"{layer_mode} / {sizing_mode}")

    log.info("=" * 72)
    log.info(f"  BTC-QUANT EVOLUTION ENGINE — {mode_label}")
    log.info(f"  Window  : {window_start}  →  {window_end}")
    log.info(f"  Capital : ${initial_capital:,.0f}")
    log.info(f"  Layers  : {layer_mode}  |  Sizing: {sizing_mode}")
    log.info("=" * 72)

    df_all = _load_dataset()
    df_all = _add_indicators(df_all)
    log.info(f"Loaded {len(df_all)} candles | {df_all.index[0]} → {df_all.index[-1]}")

    start_dt = pd.to_datetime(window_start).tz_localize("UTC")
    end_dt   = pd.to_datetime(window_end).tz_localize("UTC")

    db_first = df_all.index[required_history]
    if start_dt < db_first:
        log.warning(f"Auto-adjusting start → {db_first.date()}")
        start_dt = db_first

    pos_all         = np.arange(len(df_all))
    trade_positions = pos_all[(df_all.index >= start_dt) & (df_all.index <= end_dt)]
    if len(trade_positions) == 0:
        log.error("No candles in window.")
        return {}

    t_start = trade_positions[0]
    t_end   = trade_positions[-1]
    log.info(f"  Candles in window : {len(trade_positions):,}\n")

    log.info("Initializing services...")
    from app.use_cases.bcd_service import get_bcd_service
    from app.use_cases.ai_service  import get_ai_service
    from app.use_cases.ema_service import get_ema_service

    bcd_svc  = get_bcd_service()
    ai_svc   = get_ai_service()
    ema_svc  = get_ema_service()
    spectrum = DirectionalSpectrum()
    log.info("All services ready.\n")

    portfolio    = initial_capital
    equity_curve = [{"candle": df_all.index[t_start].isoformat(), "equity": portfolio}]
    trades       = []
    daily_stats  = {}
    position     = None
    n_errors     = 0
    n_skipped    = 0
    t0           = time.time()
    last_log     = t0

    n_candles = t_end - t_start

    for i in range(t_start, t_end):
        candle_dt   = df_all.index[i]
        next_candle = df_all.iloc[i + 1]

        df_hist   = df_all.iloc[max(0, i - 499) : i + 1].copy()
        price_now = float(df_hist["Close"].iloc[-1])
        atr14     = float(df_hist["ATR14"].dropna().iloc[-1]) if df_hist["ATR14"].dropna().size else 0.01
        ema20     = float(df_hist["EMA20"].dropna().iloc[-1]) if df_hist["EMA20"].dropna().size else price_now
        ema50     = float(df_hist["EMA50"].dropna().iloc[-1]) if df_hist["EMA50"].dropna().size else price_now

        c_high  = float(next_candle["High"])
        c_low   = float(next_candle["Low"])
        c_close = float(next_candle["Close"])

        raw_trend = ("BULL" if (ema20 > ema50 and price_now > ema20) or price_now > ema50
                     else "BEAR")

        # ── EXIT ──────────────────────────────────────────────────────────────
        if position is not None:
            sl       = position["sl"]
            tp       = position["tp"]
            side     = position["side"]
            entry    = position["entry"]
            notional = position["notional"]
            holding  = i - position["entry_idx"]

            hit = _check_sl_tp(side, sl, tp, c_high, c_low, c_close)
            if hit is not None:
                exit_price, exit_type = hit
                pnl = _calc_pnl(side, entry, exit_price, notional)
                portfolio += pnl
                _record_trade(trades, daily_stats, equity_curve, position,
                              exit_price, exit_type,
                              next_candle.name.isoformat(), pnl, portfolio, holding + 1)
                icon = "✅" if pnl > 0 else "❌"
                log.info(f"  {icon} CLOSE {side:5s} | {exit_type:12s} | "
                         f"held={holding+1}c | PnL: {pnl:+.2f} | Eq: {portfolio:,.2f}")
                position = None
            elif holding >= MAX_HOLD_CANDLES - 1:
                pnl = _calc_pnl(side, entry, c_close, notional)
                portfolio += pnl
                _record_trade(trades, daily_stats, equity_curve, position,
                              c_close, "TIME_EXIT",
                              next_candle.name.isoformat(), pnl, portfolio, holding + 1)
                icon = "✅" if pnl > 0 else "❌"
                log.info(f"  {icon} CLOSE {side:5s} | TIME_EXIT     | "
                         f"held={holding+1}c | PnL: {pnl:+.2f} | Eq: {portfolio:,.2f}")
                position = None
            continue

        # ── ENTRY ─────────────────────────────────────────────────────────────
        min_capital = FIXED_POSITION_USD if sizing_mode == "fixed" else 100.0
        if portfolio < min_capital:
            break

        try:
            # L1: BCD
            label, tag, bcd_conf, hmm_states, hmm_index = \
                bcd_svc.get_regime_and_states(df_hist, funding_rate=0)
            l1_vote = float(bcd_conf if tag == "bull" else -bcd_conf)

            if layer_mode == "l1_only":
                # v0.1: hanya L1 yang berkontribusi
                l2_vote = 0.0
                l3_vote = 0.0
            else:
                # v1 / v4.4: full stack
                l2_aligned, _, _ = ema_svc.get_alignment(df_hist, raw_trend)
                l2_vote = (1.0 if (l2_aligned and raw_trend == "BULL")
                           else (-1.0 if (l2_aligned and raw_trend == "BEAR") else 0.0))

                ai_bias, ai_conf = ai_svc.get_confidence(
                    df_hist, hmm_states=hmm_states, hmm_index=hmm_index)
                conf_norm = (max(50.0, min(100.0, float(ai_conf))) - 50.0) / 50.0
                l3_vote   = conf_norm if str(ai_bias) == "BULL" else -conf_norm

            vol_ratio = atr14 / price_now if price_now > 0 else 0.001
            l4_mult   = spectrum.compute_l4_multiplier(vol_ratio)
            spec      = spectrum.calculate(l1_vote, l2_vote, l3_vote, l4_mult, 5.0)

            if spec.trade_gate not in ("ACTIVE", "ADVISORY"):
                n_skipped += 1
                continue

            side = "LONG" if spec.directional_bias >= 0 else "SHORT"

            if side == "LONG":
                sl = price_now * (1.0 - SL_PCT)
                tp = price_now * (1.0 + TP_MIN_PCT)
            else:
                sl = price_now * (1.0 + SL_PCT)
                tp = price_now * (1.0 - TP_MIN_PCT)

            notional = (FIXED_NOTIONAL if sizing_mode == "fixed"
                        else _calc_notional_compound(portfolio))

            position = {
                "side"      : side,
                "entry"     : price_now,
                "sl"        : sl,
                "tp"        : tp,
                "entry_idx" : i,
                "entry_time": candle_dt.isoformat(),
                "gate"      : spec.trade_gate,
                "regime"    : str(tag),
                "notional"  : notional,
            }

            lev = notional / portfolio if portfolio > 0 else 0
            log.info(f"  🟢 OPEN  {side:5s} @ {price_now:,.0f} | "
                     f"SL={sl:,.0f} TP={tp:,.0f} | "
                     f"notional=${notional:,.0f} ({lev:.1f}x) | "
                     f"regime={tag} gate={spec.trade_gate}")

        except Exception as exc:
            n_errors += 1
            log.warning(f"  [ERROR] {candle_dt.date()} | {type(exc).__name__}: {exc}")
            continue

        now = time.time()
        if now - last_log >= 10:
            pct     = (i - t_start) / max(n_candles, 1) * 100
            elapsed = now - t0
            eta_s   = (elapsed / max(pct, 0.01)) * (100 - pct)
            log.info(f"  ▶ [{candle_dt.strftime('%Y-%m-%d')}] {pct:5.1f}%"
                     f"  │ Eq: ${portfolio:>10,.0f}"
                     f"  │ T: {len(trades):>4}"
                     f"  │ ETA: {eta_s/60:.1f}m")
            last_log = now

    # ── RESULTS ───────────────────────────────────────────────────────────────
    elapsed_total = time.time() - t0
    tdf = pd.DataFrame(trades)
    if tdf.empty:
        log.warning("No trades taken.")
        return {}

    total      = len(tdf)
    wins       = (tdf["pnl_usd"] > 0).sum()
    losses     = total - wins
    win_rate   = wins / total * 100
    gross_p    = tdf[tdf["pnl_usd"] > 0]["pnl_usd"].sum()
    gross_l    = abs(tdf[tdf["pnl_usd"] <= 0]["pnl_usd"].sum())
    profit_fac = gross_p / gross_l if gross_l > 0 else float("inf")
    avg_win    = gross_p / wins    if wins   > 0 else 0.0
    avg_loss   = gross_l / losses  if losses > 0 else 0.0
    rr_ratio   = avg_win / avg_loss if avg_loss > 0 else float("inf")

    eq           = pd.Series([e["equity"] for e in equity_curve])
    running_max  = eq.cummax()
    max_dd       = abs(((eq - running_max) / running_max * 100).min())

    final_pnl = portfolio - initial_capital
    final_pct = (portfolio / initial_capital - 1) * 100
    n_days    = (pd.to_datetime(window_end) - pd.to_datetime(window_start)).days
    daily_ret = final_pct / n_days if n_days > 0 else 0.0

    if daily_stats:
        dpnls  = pd.Series([v["pnl"] for v in daily_stats.values()])
        drets  = dpnls / initial_capital * 100
        sharpe = (drets.mean() / drets.std() * np.sqrt(365)) if drets.std() > 0 else 0.0
    else:
        sharpe = 0.0

    exit_dist = tdf["exit_type"].value_counts().to_dict()
    avg_hold  = tdf["holding_candles"].mean()

    regime_summary = {
        regime: {
            "trades"   : len(grp),
            "win_rate" : round((grp["pnl_usd"] > 0).sum() / len(grp) * 100, 1),
            "total_pnl": round(grp["pnl_usd"].sum(), 2),
        }
        for regime, grp in tdf.groupby("regime")
    }

    log.info("\n" + "═" * 72)
    log.info(f"  RESULT — {mode_label}")
    log.info("═" * 72)
    log.info(f"  Window        : {window_start}  →  {window_end}  ({n_days} days)")
    log.info(f"  Capital Start : ${initial_capital:>12,.2f}")
    log.info(f"  Capital End   : ${portfolio:>12,.2f}")
    log.info(f"  Net PnL       : ${final_pnl:>+12,.2f}  ({final_pct:+.2f}%)")
    log.info(f"  Daily Return  : {daily_ret:+.4f}%/day")
    log.info(f"  Trades        : {total}  (W:{wins}  L:{losses})  WR: {win_rate:.1f}%")
    log.info(f"  R:R Ratio     : {rr_ratio:.3f}")
    log.info(f"  Profit Factor : {profit_fac:.3f}")
    log.info(f"  Max Drawdown  : {max_dd:.2f}%")
    log.info(f"  Sharpe Ratio  : {sharpe:.3f}")
    log.info(f"  Avg Hold      : {avg_hold:.1f} candles")
    log.info("  ── Exit Distribution ──")
    for et, cnt in sorted(exit_dist.items()):
        log.info(f"     {et:<15s}: {cnt:>4}  ({cnt/total*100:.1f}%)")
    log.info("  ── Regime ──")
    for r, rd in sorted(regime_summary.items()):
        log.info(f"     {r:<10s}: {rd['trades']:>4} trades  WR={rd['win_rate']:.1f}%  "
                 f"PnL=${rd['total_pnl']:+,.0f}")
    log.info(f"  Errors/Skipped : {n_errors} / {n_skipped}")
    log.info(f"  Time taken     : {elapsed_total:.0f}s")
    log.info("═" * 72)

    run_tag = f"evo_{layer_mode}_{sizing_mode}_{window_start[:4]}_{window_end[:4]}_{run_ts}"
    tdf.to_csv(_RESULTS_DIR / f"{run_tag}_trades.csv", index=False)
    pd.DataFrame(equity_curve).to_csv(_RESULTS_DIR / f"{run_tag}_equity.csv", index=False)

    summary = {
        "run_timestamp"  : run_ts,
        "mode_label"     : mode_label,
        "layer_mode"     : layer_mode,
        "sizing_mode"    : sizing_mode,
        "window_start"   : window_start,
        "window_end"     : window_end,
        "initial_capital": initial_capital,
        "final_equity"   : round(portfolio, 2),
        "net_pnl_usd"    : round(final_pnl, 2),
        "net_pnl_pct"    : round(final_pct, 4),
        "daily_return_pct": round(daily_ret, 4),
        "n_days"         : n_days,
        "n_trades"       : total,
        "n_wins"         : int(wins),
        "n_losses"       : int(losses),
        "win_rate_pct"   : round(win_rate, 2),
        "avg_winner_usd" : round(avg_win, 2),
        "avg_loser_usd"  : round(avg_loss, 2),
        "rr_ratio"       : round(rr_ratio, 3),
        "profit_factor"  : round(profit_fac, 3),
        "max_drawdown_pct": round(max_dd, 2),
        "sharpe_ratio"   : round(sharpe, 3),
        "avg_hold_candles": round(float(avg_hold), 2),
        "exit_distribution": exit_dist,
        "regime_summary" : regime_summary,
        "n_skipped"      : n_skipped,
        "n_errors"       : n_errors,
        "elapsed_seconds": round(elapsed_total, 1),
    }

    summary_path = _RESULTS_DIR / f"{run_tag}_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    log.info(f"  [✓] Summary → {summary_path.name}")

    return summary
