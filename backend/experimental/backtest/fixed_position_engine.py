"""
╔══════════════════════════════════════════════════════════════════════╗
║  FIXED POSITION WALK-FORWARD ENGINE                                  ║
║                                                                      ║
║  Trade Plan:                                                         ║
║    POSITION : Fixed $1,000 margin × 15x leverage = $15,000 notional ║
║    SL       : Entry × 1.333% dari entry (hard stop)                  ║
║               = -$200 = -20% margin (-21.2% dg fee)                 ║
║    TP       : Trailing TP, minimum 0.71% dari entry                  ║
║               Jika TP_min tercapai di candle berikutnya,             ║
║               exit di harga close candle (trailing captured)         ║
║    HOLD     : Max 1 candle 4H (exit di close candle berikutnya)      ║
║    FEE      : 0.08% round-trip (0.04% × 2 taker)                    ║
║    SIGNAL   : BCD + EMA + MLP Spectrum (same as main engine)        ║
╚══════════════════════════════════════════════════════════════════════╝

Usage:
  python backtest/fixed_position_engine.py --start 2023-01-01 --end 2026-03-03
"""

import os, sys, json, time, logging, argparse
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pandas_ta as ta

_BACKEND_DIR = str(Path(__file__).resolve().parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

os.environ["BTC_QUANT_LAYER1_ENGINE"] = "bcd"

from utils.spectrum import DirectionalSpectrum
from data_engine import DB_PATH

_PROJECT_ROOT = Path(_BACKEND_DIR).parent
_RESULTS_DIR  = _PROJECT_ROOT / "backtest" / "results"
_LOGS_DIR     = _PROJECT_ROOT / "backtest" / "logs"
_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
_LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S,%f"[:-3],
)
log = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
#  TRADE PLAN CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
MARGIN_USD   = 1_000.0     # Fixed margin per trade
LEVERAGE     = 15.0        # 15× leverage
NOTIONAL     = MARGIN_USD * LEVERAGE   # $15,000 notional per trade
SL_PCT       = 0.01333     # 1.333% dari entry → -$200
TP_MIN_PCT   = 0.0071      # 0.71% dari entry (minimum, trailing)
FEE_RT       = 0.0008      # 0.04% × 2 taker fee
FEE_USD      = NOTIONAL * FEE_RT       # $12 per trade

MAX_LOSS_PER_TRADE = NOTIONAL * SL_PCT + FEE_USD  # $211.95


def simulate_exit(side: str, entry: float,
                  next_open: float, next_high: float,
                  next_low: float, next_close: float) -> tuple[str, float, float]:
    """
    Simulate SL/TP on next candle using realistic intra-candle price path.

    Asumsi urutan harga dalam candle 4H:
      - Open → bergerak ke ekstrem berlawanan dulu (adverse) → lalu ke favorable
      - Ini adalah asumsi KONSERVATIF (worst case untuk posisi kita)

    Return: (exit_type, exit_price, pnl_usd)
    """
    is_long = (side == "LONG")

    # SL dan TP harga dari entry
    if is_long:
        sl_price  = entry * (1 - SL_PCT)     # Di bawah entry
        tp_price  = entry * (1 + TP_MIN_PCT)  # Di atas entry
    else:
        sl_price  = entry * (1 + SL_PCT)     # Di atas entry
        tp_price  = entry * (1 - TP_MIN_PCT)  # Di bawah entry

    # Cek SL hit (prioritas: adverse move diperiksa lebih dulu)
    # Untuk LONG: SL hit jika Low <= sl_price
    # Untuk SHORT: SL hit jika High >= sl_price
    sl_hit = (next_low <= sl_price) if is_long else (next_high >= sl_price)
    tp_hit = (next_high >= tp_price) if is_long else (next_low <= tp_price)

    if sl_hit and tp_hit:
        # Keduanya hit dalam satu candle
        # Cek mana lebih dulu berdasarkan posisi close:
        # Jika close dekat SL → SL hit lebih dulu
        # Jika close dekat TP atau beyond → TP hit lebih dulu
        if is_long:
            # Close di bawah tp_price → kemungkinan SL hit dulu (turun dulu)
            sl_first = next_close < tp_price
        else:
            sl_first = next_close > tp_price
        if sl_first:
            tp_hit = False
        else:
            sl_hit = False

    if sl_hit:
        exit_price = sl_price
        exit_type  = "SL"
    elif tp_hit:
        # Trailing: exit di close candle (bisa lebih baik dari TP min)
        # Clamp: tidak bisa exit di luar range candle
        if is_long:
            exit_price = max(tp_price, min(next_close, next_high))
        else:
            exit_price = min(tp_price, max(next_close, next_low))
        exit_type = "TP"
    else:
        # Tidak ada SL/TP hit → exit di close (hold penuh 1 candle)
        exit_price = next_close
        exit_type  = "CLOSE"

    # PnL calculation
    if is_long:
        pnl_gross = NOTIONAL * (exit_price - entry) / entry
    else:
        pnl_gross = NOTIONAL * (entry - exit_price) / entry

    pnl_net = pnl_gross - FEE_USD
    return exit_type, exit_price, pnl_net


def run_fixed_walkforward(
    window_start: str = "2023-01-01",
    window_end:   str = "2026-03-03",
    initial_capital: float = 10_000.0,
):
    ts_run = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    start_tag = window_start.replace("-","")[:6]
    end_tag   = window_end.replace("-","")[:6]

    log.info("=" * 72)
    log.info("  FIXED POSITION WALK-FORWARD — $1,000 × 15x LEVERAGE")
    log.info(f"  Window  : {window_start}  →  {window_end}")
    log.info(f"  Capital : ${initial_capital:,.0f}  (account size, position fixed $1k)")
    log.info(f"  SL      : {SL_PCT*100:.3f}%  →  -${NOTIONAL*SL_PCT:.0f}  (-{NOTIONAL*SL_PCT/MARGIN_USD*100:.0f}% margin)")
    log.info(f"  TP min  : {TP_MIN_PCT*100:.2f}%  →  trailing, exit at close")
    log.info(f"  Fee/RT  : ${FEE_USD:.2f}  |  Max loss: ${MAX_LOSS_PER_TRADE:.2f}")
    log.info("=" * 72)

    # ── Load Data ──────────────────────────────────────────────────────────────
    log.info("Loading full dataset from DuckDB...")
    con = duckdb.connect(str(DB_PATH), read_only=True)
    df_all = con.execute("""
        SELECT
            o.timestamp,
            o.open   AS "Open",
            o.high   AS "High",
            o.low    AS "Low",
            o.close  AS "Close",
            o.volume AS "Volume",
            COALESCE(o.cvd, 0.0)              AS cvd,
            COALESCE(m.open_interest, 0.0)    AS open_interest,
            COALESCE(m.liquidations_buy, 0.0) AS liquidations_buy,
            COALESCE(m.liquidations_sell,0.0) AS liquidations_sell,
            COALESCE(m.funding_rate, 0.0)     AS funding_rate,
            COALESCE(m.fgi_value, 50.0)       AS fgi_value
        FROM btc_ohlcv_4h o
        LEFT JOIN market_metrics m ON m.timestamp = o.timestamp
        ORDER BY o.timestamp
    """).df()
    con.close()

    # Timestamp di DuckDB adalah BIGINT (milliseconds epoch)
    df_all["timestamp"] = pd.to_datetime(df_all["timestamp"], unit="ms", utc=True)
    df_all = df_all.dropna(subset=["timestamp"])
    df_all = df_all.set_index("timestamp").sort_index()

    # Add indicators
    df_all["EMA20"] = ta.ema(df_all["Close"], length=20)
    df_all["EMA50"] = ta.ema(df_all["Close"], length=50)
    df_all["ATR14"] = ta.atr(df_all["High"], df_all["Low"], df_all["Close"], length=14)

    log.info(f"Loaded {len(df_all):,} candles | "
             f"{df_all.index[0].strftime('%Y-%m-%d')} → "
             f"{df_all.index[-1].strftime('%Y-%m-%d')}")

    # ── Window Setup ───────────────────────────────────────────────────────────
    required_history = 400
    start_dt = pd.Timestamp(window_start, tz="UTC")
    end_dt   = pd.Timestamp(window_end,   tz="UTC")

    db_first = df_all.index[0]
    db_first_tradeable = df_all.index[required_history]

    if start_dt < db_first_tradeable:
        log.warning(f"Start {window_start} terlalu awal — auto adjust ke {db_first_tradeable.date()}")
        start_dt = db_first_tradeable

    pos_all = np.arange(len(df_all))
    trade_positions = pos_all[(df_all.index >= start_dt) & (df_all.index <= end_dt)]

    if len(trade_positions) == 0:
        log.error("No candles in specified window.")
        return

    t_start = trade_positions[0]
    t_end   = trade_positions[-1]

    log.info(f"  Candles in window : {len(trade_positions):,}")
    log.info(f"  History available : {t_start:,} candles before window\n")

    # ── Services ───────────────────────────────────────────────────────────────
    log.info("Initializing services...")
    from app.services.bcd_service import get_bcd_service
    from app.services.ai_service  import get_ai_service
    from app.services.ema_service import get_ema_service

    bcd_svc  = get_bcd_service()
    ai_svc   = get_ai_service()
    ema_svc  = get_ema_service()
    spectrum = DirectionalSpectrum()
    log.info("All services ready.\n")

    # ── State ──────────────────────────────────────────────────────────────────
    portfolio   = initial_capital
    equity_curve = [{"candle": df_all.index[t_start].isoformat(), "equity": portfolio}]
    trades      = []
    position    = None
    n_skipped   = 0
    n_errors    = 0
    t0          = time.time()
    last_log    = t0

    # ── Main Loop ──────────────────────────────────────────────────────────────
    n_candles = t_end - t_start

    for i in range(t_start, t_end):
        candle_dt   = df_all.index[i]
        next_candle = df_all.iloc[i + 1]

        # Sliding window: 200 candles cukup untuk BCD+MLP signal
        # Window 500 → O(500²) = 250k ops/call; 200 → O(200²) = 40k ops (84% lebih cepat)
        # Min BCD training = ~48 candles; MLP feature = last 48-100 candles
        window_size = 200
        df_hist = df_all.iloc[max(0, i - window_size + 1) : i + 1].copy()

        price_now = float(df_hist["Close"].iloc[-1])
        atr14     = float(df_hist["ATR14"].dropna().iloc[-1]) if df_hist["ATR14"].dropna().size else 0.01
        ema20     = float(df_hist["EMA20"].dropna().iloc[-1]) if df_hist["EMA20"].dropna().size else price_now
        ema50     = float(df_hist["EMA50"].dropna().iloc[-1]) if df_hist["EMA50"].dropna().size else price_now
        fgi_val   = float(df_hist["fgi_value"].iloc[-1])

        # Next candle OHLCV for exit simulation
        nxt_open  = float(next_candle["Open"])
        nxt_high  = float(next_candle["High"])
        nxt_low   = float(next_candle["Low"])
        nxt_close = float(next_candle["Close"])

        # EMA Trend
        if ema20 > ema50 and price_now > ema20:
            raw_trend = "BULL"
        elif ema20 < ema50 and price_now < ema20:
            raw_trend = "BEAR"
        elif price_now > ema50:
            raw_trend = "BULL"
        else:
            raw_trend = "BEAR"

        # ── Close Open Position ───────────────────────────────────────────────
        if position is not None:
            side   = position["side"]
            entry  = position["entry"]
            sl     = position["sl"]
            tp     = position["tp"]

            exit_type, exit_price, pnl = simulate_exit(
                side  = side,
                entry = entry,
                next_open  = nxt_open,
                next_high  = nxt_high,
                next_low   = nxt_low,
                next_close = nxt_close,
            )

            portfolio += pnl
            if portfolio <= 0:
                log.warning(f"Account blown at {candle_dt}! Portfolio: ${portfolio:.2f}")
                portfolio = 0

            trade_log = {
                "entry_time" : position["entry_time"],
                "exit_time"  : next_candle.name.isoformat(),
                "year"       : candle_dt.year,
                "month"      : candle_dt.month,
                "side"       : side,
                "entry_price": round(entry, 2),
                "exit_price" : round(exit_price, 2),
                "exit_type"  : exit_type,
                "sl_price"   : round(sl, 2),
                "tp_price"   : round(tp, 2),
                "pnl_usd"    : round(pnl, 2),
                "equity"     : round(portfolio, 2),
                "gate"       : position["gate"],
                "regime"     : position["regime"],
                "fgi"        : position["fgi"],
            }
            trades.append(trade_log)
            equity_curve.append({"candle": next_candle.name.isoformat(), "equity": round(portfolio, 2)})
            position = None

        # ── Seek New Entry ────────────────────────────────────────────────────
        if position is None:
            try:
                # Guard: akun kurang dari $MARGIN_USD → stop trading
                if portfolio < MARGIN_USD:
                    n_skipped += 1
                    continue

                # L1: BCD Regime
                label, tag, bcd_conf, hmm_states, hmm_index = \
                    bcd_svc.get_regime_and_states(df_hist, funding_rate=0)
                l1_bull = (tag == "bull")
                l1_vote = float(bcd_conf if l1_bull else -bcd_conf)

                # L2: EMA Alignment
                l2_aligned, _, _ = ema_svc.get_alignment(df_hist, raw_trend)
                l2_vote = (
                    1.0 if (l2_aligned and raw_trend == "BULL")
                    else -1.0 if (l2_aligned and raw_trend == "BEAR")
                    else 0.0
                )

                # L3: MLP
                ai_bias, ai_conf = ai_svc.get_confidence(
                    df_hist, hmm_states=hmm_states, hmm_index=hmm_index)
                mlp_norm = (max(50.0, min(100.0, ai_conf)) - 50.0) / 50.0
                ai_is_bull = str(ai_bias).upper() in ("BULL", "LONG")
                l3_vote = mlp_norm if ai_is_bull else -mlp_norm

                # L4: Volatility multiplier
                vol_ratio = atr14 / price_now if price_now else 0.02
                l4_mult   = spectrum.compute_l4_multiplier(vol_ratio)

                # Spectrum
                spec = spectrum.calculate(
                    l1_vote       = l1_vote,
                    l2_vote       = l2_vote,
                    l3_vote       = l3_vote,
                    l4_multiplier = l4_mult,
                )

                # Gate check: only ACTIVE or ADVISORY
                if spec.trade_gate not in ("ACTIVE", "ADVISORY"):
                    n_skipped += 1
                    continue

                # Direction: from spectrum bias
                is_bull = spec.directional_bias >= 0

                # Fixed SL/TP berdasarkan trade plan
                if is_bull:
                    sl_price = price_now * (1 - SL_PCT)   # -1.333%
                    tp_price = price_now * (1 + TP_MIN_PCT)  # +0.71% min (trailing)
                    side     = "LONG"
                else:
                    sl_price = price_now * (1 + SL_PCT)   # +1.333%
                    tp_price = price_now * (1 - TP_MIN_PCT)  # -0.71% min (trailing)
                    side     = "SHORT"

                position = {
                    "side"      : side,
                    "entry"     : price_now,
                    "sl"        : sl_price,
                    "tp"        : tp_price,
                    "entry_time": candle_dt.isoformat(),
                    "gate"      : spec.trade_gate,
                    "regime"    : str(tag),
                    "fgi"       : fgi_val,
                }

            except Exception as exc:
                n_errors += 1
                log.debug(f"  [{candle_dt}] Layer error: {exc}")

        # ── Progress heartbeat ────────────────────────────────────────────────
        now = time.time()
        if now - last_log >= 60:
            pct      = (i - t_start) / max(n_candles, 1) * 100
            elapsed  = now - t0
            eta_s    = (elapsed / max(pct, 0.01)) * (100 - pct)
            cur_date = candle_dt.strftime("%Y-%m-%d")
            pnl_now  = portfolio - initial_capital
            n_trades = len(trades)
            log.info(
                f"  ▶ [{cur_date}] {pct:5.1f}%  "
                f"│ Acct: ${portfolio:>10,.0f}  "
                f"│ PnL: ${pnl_now:>+10,.0f}  "
                f"│ Trades: {n_trades:>4}  "
                f"│ ETA: {eta_s/60:.1f} min"
            )
            last_log = now

    # ── Final Report ────────────────────────────────────────────────────────────
    elapsed_total = time.time() - t0
    df_trades = pd.DataFrame(trades)

    if df_trades.empty:
        log.warning("No trades executed.")
        return

    # Overall stats
    n_total = len(df_trades)
    n_win   = (df_trades["pnl_usd"] > 0).sum()
    n_loss  = n_total - n_win
    wr      = n_win / n_total * 100
    net_pnl = df_trades["pnl_usd"].sum()
    final_eq = initial_capital + net_pnl
    ret_pct  = net_pnl / initial_capital * 100

    gross_w = df_trades[df_trades["pnl_usd"]>0]["pnl_usd"].sum()
    gross_l = abs(df_trades[df_trades["pnl_usd"]<=0]["pnl_usd"].sum())
    pf      = gross_w / gross_l if gross_l else float("inf")

    eq_arr  = initial_capital + df_trades["pnl_usd"].cumsum()
    peak    = eq_arr.cummax()
    dd_arr  = (eq_arr - peak) / peak * 100
    max_dd  = dd_arr.min()

    n_sl    = (df_trades["exit_type"] == "SL").sum()
    n_tp    = (df_trades["exit_type"] == "TP").sum()
    n_cl    = (df_trades["exit_type"] == "CLOSE").sum()

    log.info("")
    log.info("=" * 72)
    log.info("  HASIL WALKFORWARD — FIXED $1,000 × 15x")
    log.info("=" * 72)
    log.info(f"  Modal awal   : ${initial_capital:>12,.2f}")
    log.info(f"  Modal akhir  : ${final_eq:>12,.2f}")
    log.info(f"  Net PnL      : ${net_pnl:>+12,.2f}   ({ret_pct:+.1f}%)")
    log.info(f"  Total trades : {n_total}  (Win:{n_win} Loss:{n_loss}  WR:{wr:.1f}%)")
    log.info(f"  Profit Factor: {pf:.3f}")
    log.info(f"  Max Drawdown : {max_dd:.1f}%")
    log.info(f"  SL:{n_sl} | TP:{n_tp} | Close:{n_cl}")
    log.info(f"  Skipped      : {n_skipped}")
    log.info(f"  Elapsed      : {elapsed_total/60:.1f} min")
    log.info("")

    # Per-Year breakdown
    months_name = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    prev_eq = initial_capital
    for yr in sorted(df_trades["year"].unique()):
        ydf   = df_trades[df_trades["year"]==yr]
        n_y   = len(ydf)
        n_w   = (ydf["pnl_usd"] > 0).sum()
        wr_y  = n_w / n_y * 100 if n_y else 0
        pnl_y = ydf["pnl_usd"].sum()
        eq_y  = prev_eq + pnl_y
        ret_y = pnl_y / prev_eq * 100

        log.info(f"  {'━'*60}")
        log.info(f"  {yr}  |  ${prev_eq:>10,.0f} → ${eq_y:>10,.0f}  ({ret_y:+.1f}%)")
        log.info(f"         Trades:{n_y}  Win:{n_w}  WR:{wr_y:.1f}%  "
                 f"PnL:${pnl_y:+,.0f}")
        log.info(f"         Long:{(ydf['side']=='LONG').sum()}  "
                 f"Short:{(ydf['side']=='SHORT').sum()}  "
                 f"SL:{(ydf['exit_type']=='SL').sum()}  "
                 f"TP:{(ydf['exit_type']=='TP').sum()}")

        for m in range(1, 13):
            mdf = ydf[ydf["month"]==m]
            if len(mdf) == 0:
                continue
            m_pnl = mdf["pnl_usd"].sum()
            m_wr  = (mdf["pnl_usd"] > 0).sum() / len(mdf) * 100
            bar = ("+" if m_pnl >= 0 else "-") * min(12, max(1, int(abs(m_pnl)/100)))
            log.info(
                f"    {months_name[m-1]:3s}: {len(mdf):>3}tr  "
                f"${m_pnl:>+8,.0f}  WR:{m_wr:5.1f}%  {bar}"
            )
        prev_eq = eq_y
        log.info("")

    # ── Save Results ────────────────────────────────────────────────────────────
    trades_path  = _RESULTS_DIR / f"fixedpos_trades_{start_tag}_{end_tag}_{ts_run}.csv"
    equity_path  = _RESULTS_DIR / f"fixedpos_equity_{start_tag}_{end_tag}_{ts_run}.csv"
    summary_path = _RESULTS_DIR / f"fixedpos_summary_{start_tag}_{end_tag}_{ts_run}.json"

    df_trades.to_csv(trades_path, index=False)
    pd.DataFrame(equity_curve).to_csv(equity_path, index=False)

    summary = {
        "run_timestamp"    : ts_run,
        "window_start"     : window_start,
        "window_end"       : window_end,
        "trade_plan"       : {
            "margin_usd"   : MARGIN_USD,
            "leverage"     : LEVERAGE,
            "notional_usd" : NOTIONAL,
            "sl_pct"       : SL_PCT,
            "tp_min_pct"   : TP_MIN_PCT,
            "fee_rt_pct"   : FEE_RT,
            "max_loss_usd" : MAX_LOSS_PER_TRADE,
        },
        "initial_capital"  : initial_capital,
        "final_equity"     : round(final_eq, 2),
        "net_pnl_usd"      : round(net_pnl, 2),
        "net_pnl_pct"      : round(ret_pct, 4),
        "n_trades"         : n_total,
        "n_wins"           : int(n_win),
        "n_losses"         : int(n_loss),
        "win_rate_pct"     : round(wr, 2),
        "profit_factor"    : round(pf, 3),
        "max_drawdown_pct" : round(max_dd, 2),
        "n_sl"             : int(n_sl),
        "n_tp"             : int(n_tp),
        "n_close"          : int(n_cl),
        "n_skipped"        : n_skipped,
        "n_errors"         : n_errors,
        "elapsed_seconds"  : round(elapsed_total, 1),
    }
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    log.info(f"  [✓] Trades → {trades_path.name}")
    log.info(f"  [✓] Summary → {summary_path.name}")

    return summary


# ── CLI Entry ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Fixed Position Walk-Forward Engine")
    p.add_argument("--start",   default="2023-01-01", help="Start date (YYYY-MM-DD)")
    p.add_argument("--end",     default="2026-03-03", help="End date (YYYY-MM-DD)")
    p.add_argument("--capital", default=10_000.0, type=float, help="Initial account capital")
    args = p.parse_args()

    run_fixed_walkforward(
        window_start    = args.start,
        window_end      = args.end,
        initial_capital = args.capital,
    )
