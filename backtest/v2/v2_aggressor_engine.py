"""
╔══════════════════════════════════════════════════════════════════════╗
║  BTC-QUANT: TRUE WALK-FORWARD BACKTEST ENGINE                       ║
║  Simulates ALL system layers with ZERO lookahead bias.              ║
║                                                                      ║
║  Architecture:                                                       ║
║    L1: BCD (Bayesian Changepoint Detection) — regime                ║
║    L2: EMA alignment filter                                          ║
║    L3: MLP signal intelligence (retrained every 48 candles OOS)     ║
║    L4: Heston volatility — adaptive SL/TP multipliers               ║
║    L5: Risk Manager — position sizing, daily loss cap                ║
║    L6: FGI sentiment — risk adjustment                              ║
║                                                                      ║
║  Method: Expanding window. For each candle t, only data[0..t]       ║
║  is passed to all models. No data leaks from t+1..N ever.           ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import time
import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pandas_ta as ta

# ── Path Setup ─────────────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_BACKEND_DIR = str(_PROJECT_ROOT / "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# ── Force BCD as Layer 1 Engine ────────────────────────────────────────────────
os.environ["BTC_QUANT_LAYER1_ENGINE"] = "bcd"

from engines.layer1_volatility import get_vol_estimator
from app.services.risk_manager import get_risk_manager
from utils.spectrum import DirectionalSpectrum
from data_engine import DB_PATH

# ── Output Directories ─────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(_BACKEND_DIR).parent
_RESULTS_DIR  = _PROJECT_ROOT / "backtest" / "results" / "v2"
_LOGS_DIR     = _PROJECT_ROOT / "backtest" / "logs" / "v2"
_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
_LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Logging Setup ──────────────────────────────────────────────────────────────
_LOG_FILE = _LOGS_DIR / f"walkforward_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("walkforward")


# ══════════════════════════════════════════════════════════════════════════════
#  DATA LOADING
# ══════════════════════════════════════════════════════════════════════════════

def load_full_dataset() -> pd.DataFrame:
    """
    Load the full OHLCV dataset with market metrics via ASOF JOIN.
    Returns a datetime-indexed DataFrame with capitals (Open, High, Low, Close,
    Volume, CVD, Funding, OI, FGI) covering the entire DB history.
    """
    log.info("Loading full dataset from DuckDB with ASOF JOIN...")
    with duckdb.connect(DB_PATH, read_only=True) as con:
        df = con.execute("""
            SELECT
                o.timestamp,
                o.open   AS Open,
                o.high   AS High,
                o.low    AS Low,
                o.close  AS Close,
                o.volume AS Volume,
                COALESCE(o.cvd, 0.0)            AS CVD,
                COALESCE(m.funding_rate, 0.0)   AS Funding,
                COALESCE(m.open_interest, 0.0)  AS OI,
                COALESCE(m.fgi_value, 50.0)     AS FGI
            FROM btc_ohlcv_4h o
            ASOF LEFT JOIN market_metrics m ON o.timestamp >= m.timestamp
            ORDER BY o.timestamp ASC
        """).fetchdf()

    if df.empty:
        raise RuntimeError("DuckDB returned empty dataset. Run data_engine.py first.")

    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("datetime")
    log.info(f"Loaded {len(df)} candles | {df.index[0]} → {df.index[-1]}")
    return df


# ══════════════════════════════════════════════════════════════════════════════
#  INDICATOR HELPER
# ══════════════════════════════════════════════════════════════════════════════

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add EMA20, EMA50, ATR14 in-place. Returns same df."""
    df = df.copy()
    df["EMA20"] = ta.ema(df["Close"], length=20)
    df["EMA50"] = ta.ema(df["Close"], length=50)
    df["ATR14"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)
    return df


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def run_true_walkforward(
    window_start: str = "2022-11-01",
    window_end:   str = "2026-03-03",
    required_history: int = 400,
    initial_capital:  float = 10_000.0,
):
    """
    True Out-of-Sample Walk-Forward simulation across all system layers.

    Args:
        window_start:     First candle to trade (ISO date string, UTC).
        window_end:       Last candle to trade (ISO date string, UTC).
        required_history: Minimum candles before window_start required for
                          model initialisation. Default 400 (~67 days of 4H).
        initial_capital:  Starting portfolio value in USD.
    """
    run_ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    log.info("=" * 72)
    log.info("  BTC-QUANT TRUE WALK-FORWARD SIMULATION")
    log.info(f"  Window  : {window_start}  →  {window_end}")
    log.info(f"  Capital : ${initial_capital:,.0f}")
    log.info("=" * 72)

    # ── 1. Load Data ───────────────────────────────────────────────────────────
    df_all = load_full_dataset()
    df_all = add_indicators(df_all)

    start_dt = pd.to_datetime(window_start).tz_localize("UTC")
    end_dt   = pd.to_datetime(window_end  ).tz_localize("UTC")

    # ── Auto-adjust start_dt if DB doesn't have enough history before it ──────
    # We need at least `required_history` candles before the trading window.
    # If window_start is before (db_start + required_history), shift it forward.
    db_first_tradeable = df_all.index[required_history]  # first index that has enough history
    if start_dt < db_first_tradeable:
        log.warning(
            f"Requested start {start_dt.date()} is too early — "
            f"DB requires {required_history} warmup candles. "
            f"Auto-adjusting start to {db_first_tradeable.date()}."
        )
        start_dt = db_first_tradeable

    pos_all = np.arange(len(df_all))
    trade_positions = pos_all[(df_all.index >= start_dt) & (df_all.index <= end_dt)]

    if len(trade_positions) == 0:
        log.error("No candles found in specified window.")
        return

    t_start = trade_positions[0]
    t_end   = trade_positions[-1]  # inclusive

    if t_start < required_history:
        log.error(
            f"Not enough history. Need {required_history} candles before {window_start}, "
            f"but only {t_start} available."
        )
        return

    log.info(f"  Candles in window : {len(trade_positions):,}")
    log.info(f"  History available : {t_start:,} candles before window")
    log.info("")

    # ── 2. Services (initialized once, re-used each iteration) ────────────────
    log.info("Initializing services...")
    from app.services.bcd_service import get_bcd_service
    from app.services.ai_service  import get_ai_service
    from app.services.ema_service import get_ema_service

    bcd_svc  = get_bcd_service()
    ai_svc   = get_ai_service()
    ema_svc  = get_ema_service()
    vol_est  = get_vol_estimator()
    risk_mgr = get_risk_manager()
    spectrum = DirectionalSpectrum()
    log.info("All services ready.\n")

    # ── 3. State ───────────────────────────────────────────────────────────────
    portfolio   = initial_capital
    equity_curve = [{"candle": df_all.index[t_start].isoformat(), "equity": portfolio}]
    trades      = []
    position    = None          # Active open trade
    daily_stats = {}            # date → {pnl, n_trades}

    n_candles  = t_end - t_start
    t0         = time.time()
    last_log   = t0
    n_errors   = 0
    n_skipped  = 0

    # ── 4. Candle Loop ─────────────────────────────────────────────────────────
    for i in range(t_start, t_end):
        candle_dt   = df_all.index[i]
        next_candle = df_all.iloc[i + 1]         # Peek next candle for trade outcome ONLY
        
        # ── SLIDING WINDOW (Match Production) ──────────────────────────────────
        # Instead of full expanding window, we take only the last 500 candles.
        # This keeps BCD/MLP/Heston metrics realistic and FAST.
        window_size = 500
        df_hist = df_all.iloc[max(0, i - window_size + 1) : i + 1].copy()

        price_now = float(df_hist["Close"].iloc[-1])
        atr14     = float(df_hist["ATR14"].dropna().iloc[-1]) if df_hist["ATR14"].dropna().size else 0.01
        ema20     = float(df_hist["EMA20"].dropna().iloc[-1]) if df_hist["EMA20"].dropna().size else price_now
        ema50     = float(df_hist["EMA50"].dropna().iloc[-1]) if df_hist["EMA50"].dropna().size else price_now

        high_next  = float(next_candle["High"])
        low_next   = float(next_candle["Low"])

        # ── EMA Trend ──────────────────────────────────────────────────────────
        if ema20 > ema50 and price_now > ema20:
            raw_trend = "BULL"
        elif ema20 < ema50 and price_now < ema20:
            raw_trend = "BEAR"
        elif price_now > ema50:
            raw_trend = "BULL"
        else:
            raw_trend = "BEAR"

        # ── Check / Close Open Position ────────────────────────────────────────
        if position is not None:
            exit_price = None
            exit_type  = None

            if position["side"] == "LONG":
                if low_next <= position["sl"]:
                    exit_price, exit_type = position["sl"], "SL"
                elif high_next >= position["tp"]:
                    exit_price, exit_type = position["tp"], "TP"
            else:  # SHORT
                if high_next >= position["sl"]:
                    exit_price, exit_type = position["sl"], "SL"
                elif low_next <= position["tp"]:
                    exit_price, exit_type = position["tp"], "TP"

            if exit_price is not None:
                entry     = position["entry"]
                side      = position["side"]
                sl        = position["sl"]
                risk_usd  = position["risk_usd"]  # fixed 2% risk amount

                # PnL = risk_usd × (actual_move / sl_distance) − fee
                sl_dist   = abs(entry - sl)
                if sl_dist <= 0:
                    sl_dist = atr14 * 0.5   # fallback
                actual_move = (exit_price - entry) if side == "LONG" else (entry - exit_price)
                raw_ret  = actual_move / sl_dist   # ratio vs SL distance
                fee_pct  = 0.0008                  # 0.04% × 2 round-trip taker
                pnl_gross = risk_usd * raw_ret
                fee_usd   = abs(risk_usd) * fee_pct / (abs(actual_move / sl_dist) + 1e-9) * abs(raw_ret)
                pnl       = pnl_gross - abs(risk_usd) * fee_pct
                portfolio += pnl

                trade_log = {
                    "entry_time" : position["entry_time"],
                    "exit_time"  : next_candle.name.isoformat(),
                    "side"       : position["side"],
                    "entry_price": round(entry, 2),
                    "exit_price" : round(exit_price, 2),
                    "sl"         : round(position["sl"], 2),
                    "tp"         : round(position["tp"], 2),
                    "risk_usd"   : round(risk_usd, 2),
                    "pnl_usd"    : round(pnl, 2),
                    "equity"     : round(portfolio, 2),
                    "exit_type"  : exit_type,
                    "gate"       : position["gate"],
                    "fgi"        : position["fgi"],
                    "regime"     : position["regime"],
                }
                trades.append(trade_log)
                equity_curve.append({"candle": next_candle.name.isoformat(), "equity": round(portfolio, 2)})

                # Daily stats
                d_key = candle_dt.date().isoformat()
                if d_key not in daily_stats:
                    daily_stats[d_key] = {"pnl": 0.0, "n_trades": 0}
                daily_stats[d_key]["pnl"] += pnl
                daily_stats[d_key]["n_trades"] += 1

                log.debug(
                    f"  CLOSE {position['side']:5s} | {exit_type:3s} | "
                    f"PnL: {pnl:+.2f} USD | Equity: {portfolio:,.2f}"
                )
                position = None

        # ── Seek New Entry (only if flat) ──────────────────────────────────────
        if position is None:
            try:
                # L1: BCD Regime ───────────────────────────────────────────────
                label, tag, bcd_conf = bcd_svc.get_regime_with_posterior(df_hist, funding_rate=0)
                hmm_states, hmm_index = bcd_svc.get_state_sequence_raw(df_hist)
                l1_bull = (tag == "bull")
                l1_vote = float(bcd_conf if l1_bull else -bcd_conf)

                # L2: EMA Alignment ────────────────────────────────────────────
                l2_aligned, _, _ = ema_svc.get_alignment(df_hist, raw_trend)
                l2_vote = (
                    1.0 if (l2_aligned and raw_trend == "BULL")
                    else (-1.0 if (l2_aligned and raw_trend == "BEAR") else 0.0)
                )

                # L3: AI / MLP ─────────────────────────────────────────────────
                ai_bias, ai_conf = ai_svc.get_confidence(
                    df_hist, hmm_states=hmm_states, hmm_index=hmm_index
                )
                conf_norm = (max(50.0, min(100.0, float(ai_conf))) - 50.0) / 50.0
                l3_vote = conf_norm if str(ai_bias) == "BULL" else -conf_norm

                # L4: Volatility Multiplier ────────────────────────────────────
                vol_ratio = atr14 / price_now if price_now > 0 else 0.001
                l4_mult   = spectrum.compute_l4_multiplier(vol_ratio)

                # Directional Spectrum ─────────────────────────────────────────
                spec = spectrum.calculate(l1_vote, l2_vote, l3_vote, l4_mult, 5.0)

                # L4: Heston SL/TP Multipliers ─────────────────────────────────
                vol_params   = vol_est.estimate_params(df_hist)
                regime_biases = bcd_svc.get_regime_bias()
                bias_score   = float(
                    regime_biases.get(label, {}).get("bias_score", 0.5)
                    if label in regime_biases else 0.5
                )
                sl_tp = vol_est.get_sl_tp_multipliers(
                    vol_regime  = vol_params.get("vol_regime", "Normal"),
                    halflife    = float(vol_params.get("mean_reversion_halflife_candles", 999.0)),
                    bias_score  = bias_score,
                )
                sl_m  = sl_tp["sl_multiplier"]
                tp1_m = sl_tp["tp1_multiplier"]

                # FGI Sentiment Adjustment ─────────────────────────────────────
                fgi_val = float(df_hist["FGI"].iloc[-1]) if "FGI" in df_hist.columns else 50.0
                sentiment_adj = 1.0
                if fgi_val > 80:
                    sentiment_adj = 0.75
                elif fgi_val < 20 and spec.directional_bias >= 0:
                    sentiment_adj = 0.75

                # L5: Risk Manager ──────────────────────────────────────────────
                req_lev = int(max(1, min(20, round(
                    0.04 / (tp1_m * vol_ratio) if vol_ratio > 0 else 1
                ))))
                risk = risk_mgr.evaluate(
                    portfolio_value     = portfolio,
                    atr                 = atr14,
                    sl_multiplier       = sl_m,
                    requested_leverage  = req_lev,
                    current_price       = price_now,
                )

                # ── Trade Decision (V2 Aggressive) ──────────────────────────────
                # Skip Neutral regimes to filter out noise — only trade in Trend-following states
                is_neutral = (str(tag) == "neutral")
                
                if spec.trade_gate in ("ACTIVE", "ADVISORY") and risk.can_trade and not is_neutral:
                    is_bull = spec.directional_bias >= 0

                    if is_bull:
                        sl   = price_now - atr14 * sl_m
                        tp   = price_now + atr14 * tp1_m
                        side = "LONG"
                    else:
                        sl   = price_now + atr14 * sl_m
                        tp   = price_now - atr14 * tp1_m
                        side = "SHORT"

                    # V2 Aggressive: Increased risk pct per trade to 4%
                    RISK_PCT    = 0.04
                    sl_dist_now = abs(price_now - sl)
                    if sl_dist_now <= 0:
                        sl_dist_now = atr14 * sl_m
                    risk_usd_now = portfolio * RISK_PCT * sentiment_adj

                    position = {
                        "side"      : side,
                        "entry"     : price_now,
                        "sl"        : sl,
                        "tp"        : tp,
                        "risk_usd"  : risk_usd_now,   # constant dollar risk
                        "lev"       : min(risk.approved_leverage, 20),  # Raised cap to 20x for V2
                        "entry_time": candle_dt.isoformat(),
                        "gate"      : spec.trade_gate,
                        "fgi"       : fgi_val,
                        "regime"    : str(tag),
                    }
                    log.debug(
                        f"  OPEN {side:5s} @ {price_now:,.2f} | "
                        f"SL={sl:.2f} TP={tp:.2f} | Gate={spec.trade_gate}"
                    )
                else:
                    n_skipped += 1

            except Exception as exc:
                n_errors += 1
                log.debug(f"  [{candle_dt}] Layer error: {exc}")

        # ── Progress heartbeat every 60 seconds ────────────────────────────────
        now = time.time()
        if now - last_log >= 60:
            pct       = (i - t_start) / max(n_candles, 1) * 100
            elapsed   = now - t0
            eta_s     = (elapsed / max(pct, 0.01)) * (100 - pct)
            cur_year  = candle_dt.year
            cur_month = candle_dt.strftime("%b")
            cur_date  = candle_dt.strftime("%Y-%m-%d")
            pnl_total = portfolio - initial_capital
            log.info(
                f"  ▶ [{cur_date}] {pct:5.1f}%  "
                f"│ Equity: ${portfolio:>10,.0f}  "
                f"│ PnL: ${pnl_total:>+9,.0f}  "
                f"│ Trades: {len(trades):>4}  "
                f"│ ETA: {eta_s/60:.1f} min"
            )
            last_log = now

    # ══════════════════════════════════════════════════════════════════════════
    #  RESULTS
    # ══════════════════════════════════════════════════════════════════════════
    elapsed_total = time.time() - t0
    log.info("\n" + "═" * 72)
    log.info("  BACKTEST COMPLETE")
    log.info("═" * 72)

    tdf = pd.DataFrame(trades)
    if tdf.empty:
        log.warning("  No trades were taken during the simulation.")
        return

    total       = len(tdf)
    wins        = (tdf["pnl_usd"] > 0).sum()
    losses      = total - wins
    win_rate    = wins / total * 100
    gross_p     = tdf[tdf["pnl_usd"] > 0]["pnl_usd"].sum()
    gross_l     = abs(tdf[tdf["pnl_usd"] <= 0]["pnl_usd"].sum())
    profit_fac  = gross_p / gross_l if gross_l > 0 else float("inf")

    eq           = pd.Series([e["equity"] for e in equity_curve])
    running_max  = eq.cummax()
    drawdown_pct = ((eq - running_max) / running_max * 100)
    max_dd       = abs(drawdown_pct.min()) if not drawdown_pct.empty else 0.0

    final_pnl   = portfolio - initial_capital
    final_pct   = (portfolio / initial_capital - 1) * 100
    n_days      = (pd.to_datetime(window_end) - pd.to_datetime(window_start)).days
    daily_ret   = final_pct / n_days if n_days > 0 else 0.0

    # Sharpe (annualised, daily resolution)
    if daily_stats:
        daily_pnls  = pd.Series([v["pnl"] for v in daily_stats.values()])
        daily_rets  = daily_pnls / initial_capital * 100
        sharpe      = (daily_rets.mean() / daily_rets.std() * np.sqrt(365)) if daily_rets.std() > 0 else 0.0
    else:
        sharpe = 0.0

    summary = {
        "run_timestamp"   : run_ts,
        "window_start"    : window_start,
        "window_end"      : window_end,
        "initial_capital" : initial_capital,
        "final_equity"    : round(portfolio, 2),
        "net_pnl_usd"     : round(final_pnl, 2),
        "net_pnl_pct"     : round(final_pct, 4),
        "daily_return_pct": round(daily_ret, 4),
        "n_days"          : n_days,
        "n_candles"       : len(trade_positions),
        "n_trades"        : total,
        "n_wins"          : int(wins),
        "n_losses"        : int(losses),
        "win_rate_pct"    : round(win_rate, 2),
        "profit_factor"   : round(profit_fac, 3),
        "max_drawdown_pct": round(max_dd, 2),
        "sharpe_ratio"    : round(sharpe, 3),
        "n_skipped"       : n_skipped,
        "n_errors"        : n_errors,
        "elapsed_seconds" : round(elapsed_total, 1),
    }

    log.info(f"  Window        : {window_start}  →  {window_end}  ({n_days} days)")
    log.info(f"  Initial Cap   : ${initial_capital:>12,.2f}")
    log.info(f"  Final Equity  : ${portfolio:>12,.2f}")
    log.info(f"  Net PnL       : ${final_pnl:>+12,.2f}  ({final_pct:+.2f}%)")
    log.info(f"  Daily Return  : {daily_ret:+.3f}%/day")
    log.info(f"  Trades        : {total}  (W:{wins}  L:{losses})  WR: {win_rate:.1f}%")
    log.info(f"  Profit Factor : {profit_fac:.3f}")
    log.info(f"  Max Drawdown  : {max_dd:.2f}%")
    log.info(f"  Sharpe Ratio  : {sharpe:.3f}")
    log.info(f"  Errors/Skipped: {n_errors} / {n_skipped}")
    log.info(f"  Time taken    : {elapsed_total:.0f}s")
    log.info("═" * 72)

    # ── Save Results ───────────────────────────────────────────────────────────
    suffix = f"{window_start[:7].replace('-','')}_{window_end[:7].replace('-','')}"

    trades_csv = _RESULTS_DIR / f"walkforward_trades_{suffix}_{run_ts}.csv"
    tdf.to_csv(trades_csv, index=False)

    equity_csv = _RESULTS_DIR / f"walkforward_equity_{suffix}_{run_ts}.csv"
    pd.DataFrame(equity_curve).to_csv(equity_csv, index=False)

    daily_df = pd.DataFrame([
        {"date": k, "pnl": v["pnl"], "n_trades": v["n_trades"]}
        for k, v in sorted(daily_stats.items())
    ])
    daily_csv = _RESULTS_DIR / f"walkforward_daily_{suffix}_{run_ts}.csv"
    daily_df.to_csv(daily_csv, index=False)

    summary_json = _RESULTS_DIR / f"walkforward_summary_{suffix}_{run_ts}.json"
    with open(summary_json, "w") as f:
        json.dump(summary, f, indent=2)

    log.info(f"\n  [✓] Trades  → {trades_csv}")
    log.info(f"  [✓] Equity  → {equity_csv}")
    log.info(f"  [✓] Daily   → {daily_csv}")
    log.info(f"  [✓] Summary → {summary_json}")
    log.info(f"  [✓] Full log → {_LOG_FILE}")


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRYPOINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="BTC-Quant True Walk-Forward Backtest")
    parser.add_argument("--start",   default="2022-11-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end",     default="2026-03-03", help="End date   (YYYY-MM-DD)")
    parser.add_argument("--capital", default=10000.0,      type=float, help="Initial capital USD")
    parser.add_argument("--history", default=400,          type=int,   help="Min candles pre-window")
    args = parser.parse_args()

    run_true_walkforward(
        window_start     = args.start,
        window_end       = args.end,
        required_history = args.history,
        initial_capital  = args.capital,
    )
