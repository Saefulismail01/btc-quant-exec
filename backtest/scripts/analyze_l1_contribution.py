"""
╔══════════════════════════════════════════════════════════════════════╗
║  BTC-QUANT-BTC: LAYER 1 HMM CONTRIBUTION ANALYSIS                     ║
║                                                                      ║
║  Pertanyaan: apakah l1_aligned=True menghasilkan trade yang          ║
║  lebih baik dibanding l1_aligned=False?                              ║
║                                                                      ║
║  Metodologi:                                                         ║
║    Re-run backtest dengan logika identik engine.py, tapi             ║
║    setiap trade dicatat: l1_aligned, hmm_label, direction,           ║
║    win/loss, pnl, exit_reason.                                       ║
║                                                                      ║
║    Kemudian bandingkan:                                              ║
║      • Win rate   : l1_aligned=True vs False                        ║
║      • Avg PnL    : l1_aligned=True vs False                        ║
║      • Per arah   : LONG dan SHORT dipisah                          ║
║      • Per label  : Bullish/Bearish/Sideways dipisah                ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import sys
import warnings
from pathlib import Path
from datetime import datetime
from collections import defaultdict

import numpy as np
import pandas as pd
import pandas_ta as ta

warnings.filterwarnings("ignore")

_BACKTEST_DIR = Path(__file__).resolve().parent
_BACKEND_DIR  = _BACKTEST_DIR.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from engines.layer1_hmm import MarketRegimeModel
from engines.layer2_ema  import EMAStructureModel
from utils.spectrum      import DirectionalSpectrum

LOG_DIR = _BACKTEST_DIR / "logs"


# ════════════════════════════════════════════════════════════════════
#  BACKTEST RUNNER — identik engine.py, tapi catat l1 per trade
# ════════════════════════════════════════════════════════════════════

def run_detailed_backtest(year: int, initial_capital: float = 1000.0) -> list[dict]:
    """
    Jalankan ulang backtest dengan parameter identik engine.py.
    Return list of trade records, setiap record berisi:
      l1_aligned, hmm_label, trend_short, direction,
      win, pnl_usd, pnl_pct, exit_reason, spectrum_gate,
      conviction_pct, leverage, entry_price, exit_price
    """
    data_path = _BACKTEST_DIR / "data" / f"BTC_USDT_4h_{year}.csv"
    df_full   = pd.read_csv(data_path, index_col=0, parse_dates=True)
    df_full.rename(columns={
        "open": "Open", "high": "High",
        "low": "Low", "close": "Close", "volume": "Volume"
    }, inplace=True)

    hmm_model   = MarketRegimeModel()
    ema_model   = EMAStructureModel(ema_fast=20, ema_slow=50)
    spectrum    = DirectionalSpectrum()

    capital      = initial_capital
    warmup       = 250
    trades       = []

    # position state
    position     = None
    entry_price  = 0.0
    size_usd     = 0.0
    leverage     = 1
    stop_loss    = 0.0
    tp1          = 0.0
    tp2          = 0.0
    trade_meta   = {}   # l1_aligned, hmm_label, dll saat entry

    for i in range(warmup, len(df_full) - 1):
        df_window   = df_full.iloc[i - warmup : i + 1].copy()
        next_candle = df_full.iloc[i + 1]
        curr        = df_window.iloc[-1]

        # ── Indicators ──────────────────────────────────────────────
        df_window["ATR14"] = ta.atr(
            df_window["High"], df_window["Low"], df_window["Close"], length=14
        )

        price  = float(curr["Close"])
        atr14  = float(curr["ATR14"]) if not pd.isna(curr["ATR14"]) else None

        if atr14 is None:
            continue

        # ── Layer 1: HMM (Continuous) ────────────────────────────────
        l1_vote = hmm_model.get_directional_vote(df_window)

        # ── Layer 2: EMA (Continuous) ────────────────────────────────
        l2_vote = ema_model.get_directional_vote(df_window)

        # ── Layer 3: MACD proxy ───────────────────────────────────────
        macd      = ta.macd(df_window["Close"])
        if macd is not None and "MACDh_12_26_9" in macd.columns:
            macd_hist = float(macd["MACDh_12_26_9"].iloc[-1])
            l3_vote   = float(pd.Series([macd_hist / (atr14 + 1e-9)]).apply(np.tanh).iloc[0])
        else:
            l3_vote = 0.0

        # ── Layer 4: Volatility gate ──────────────────────────────────
        vol_ratio  = atr14 / price
        l4_mult    = spectrum.compute_l4_multiplier(vol_ratio)
        lev        = (2 if vol_ratio > 0.015 else
                      3 if vol_ratio > 0.012 else
                      5 if vol_ratio > 0.008 else 7)

        # ── Spectrum ─────────────────────────────────────────────────
        spec = spectrum.calculate(
            l1_vote         = l1_vote,
            l2_vote         = l2_vote,
            l3_vote         = l3_vote,
            l4_multiplier   = l4_mult,
            base_size       = 5.0,
        )

        # ── Manage open position ──────────────────────────────────────
        if position is not None:
            high  = float(curr["High"])
            low   = float(curr["Low"])
            close = float(curr["Close"])
            exit_price_  = None
            exit_reason_ = None

            # Sign reversal check
            sign_reversed = (position == "LONG" and spec.directional_bias < 0) or \
                            (position == "SHORT" and spec.directional_bias > 0)

            if position == "LONG":
                if low   <= stop_loss: exit_price_, exit_reason_ = stop_loss,  "SL"
                elif high >= tp2:      exit_price_, exit_reason_ = tp2,        "TP2"
                elif spec.trade_gate == "SUSPENDED" or sign_reversed:
                    exit_price_, exit_reason_ = close, f"SoftExit(Rev={sign_reversed})"
            else:  # SHORT
                if high  >= stop_loss: exit_price_, exit_reason_ = stop_loss,  "SL"
                elif low  <= tp2:      exit_price_, exit_reason_ = tp2,        "TP2"
                elif spec.trade_gate == "SUSPENDED" or sign_reversed:
                    exit_price_, exit_reason_ = close, f"SoftExit(Rev={sign_reversed})"

            if exit_price_ is not None:
                if position == "LONG":
                    unlev_pct = (exit_price_ - entry_price) / entry_price
                else:
                    unlev_pct = (entry_price - exit_price_) / entry_price

                pnl_usd = size_usd * unlev_pct * leverage
                capital += pnl_usd

                trades.append({
                    **trade_meta,
                    "exit_price"    : exit_price_,
                    "exit_reason"   : exit_reason_,
                    "pnl_usd"       : pnl_usd,
                    "pnl_pct"       : unlev_pct * leverage * 100,
                    "win"           : pnl_usd > 0,
                })
                position = None

        # ── New entry ─────────────────────────────────────────────────
        if position is None and spec.trade_gate == "ACTIVE":
            direction   = spec.action
            ep          = float(next_candle["Open"])
            risk_atr    = atr14 * 1.5

            if direction == "SHORT":
                sl_ = ep + risk_atr
                t1_ = ep - risk_atr * 1.5
                t2_ = ep - risk_atr * 2.5
            else:
                sl_ = ep - risk_atr
                t1_ = ep + risk_atr * 1.5
                t2_ = ep + risk_atr * 2.5

            sz = capital * (spec.position_size_pct / 100.0)

            position    = direction
            entry_price = ep
            size_usd    = sz
            leverage    = lev
            stop_loss   = sl_
            tp1         = t1_
            tp2         = t2_

            trade_meta = {
                "year"          : year,
                "entry_ts"      : str(df_window.index[-1]),
                "direction"     : direction,
                "entry_price"   : ep,
                "l1_vote"       : l1_vote,
                "l2_vote"       : l2_vote,
                "l3_vote"       : l3_vote,
                "l4_mult"       : l4_mult,
                "bias"          : spec.directional_bias,
                "trade_gate"    : spec.trade_gate,
                "size_usd"      : sz,
            }

    # Close any open position at end
    if position is not None:
        last    = df_full.iloc[-1]
        ep_exit = float(last["Close"])
        if position == "LONG":
            unlev_pct = (ep_exit - entry_price) / entry_price
        else:
            unlev_pct = (entry_price - ep_exit) / entry_price
        pnl_usd = size_usd * unlev_pct * leverage
        capital += pnl_usd
        trades.append({
            **trade_meta,
            "exit_price"    : ep_exit,
            "exit_reason"   : "EndOfData",
            "pnl_usd"       : pnl_usd,
            "pnl_pct"       : unlev_pct * leverage * 100,
            "win"           : pnl_usd > 0,
        })

    return trades


# ════════════════════════════════════════════════════════════════════
#  ANALYSIS ENGINE
# ════════════════════════════════════════════════════════════════════

def analyze_l1(trades: list[dict]) -> dict:
    """
    Split trades by l1_vote sign (Bullish bias vs Bearish bias).
    """
    groups = {"Bullish Bias (>0)": [], "Bearish Bias (<0)": [], "Neutral (0)": []}
    for t in trades:
        vote = t.get("l1_vote", 0)
        if vote > 0: groups["Bullish Bias (>0)"].append(t)
        elif vote < 0: groups["Bearish Bias (<0)"].append(t)
        else: groups["Neutral (0)"].append(t)

    result = {}
    for label, grp in groups.items():
        if not grp:
            result[label] = None
            continue
        n       = len(grp)
        wins    = sum(1 for t in grp if t["win"])
        pnls    = [t["pnl_usd"] for t in grp]
        pnl_pct = [t["pnl_pct"] for t in grp]
        gross_w = sum(p for p in pnls if p > 0)
        gross_l = abs(sum(p for p in pnls if p < 0))
        result[label] = {
            "n"           : n,
            "win_rate"    : wins / n * 100,
            "avg_pnl_usd" : np.mean(pnls),
            "avg_pnl_pct" : np.mean(pnl_pct),
            "total_pnl"   : sum(pnls),
            "profit_factor": gross_w / gross_l if gross_l > 0 else float("inf"),
            "best"        : max(pnls),
            "worst"       : min(pnls),
        }
    return result


def analyze_by_hmm_label(trades: list[dict]) -> dict:
    """
    Per HMM label, hitung metrik.
    """
    by_label = defaultdict(list)
    for t in trades:
        by_label[t["hmm_label"]].append(t)

    result = {}
    for label, grp in sorted(by_label.items()):
        n       = len(grp)
        wins    = sum(1 for t in grp if t["win"])
        pnls    = [t["pnl_usd"] for t in grp]
        result[label] = {
            "n"         : n,
            "win_rate"  : wins / n * 100,
            "avg_pnl"   : np.mean(pnls),
            "total_pnl" : sum(pnls),
        }
    return result


def analyze_by_direction(trades: list[dict]) -> dict:
    """
    Per direction (LONG/SHORT), split l1_aligned=T vs F.
    """
    result = {}
    for direction in ["LONG", "SHORT"]:
        grp = [t for t in trades if t["direction"] == direction]
        if not grp:
            continue
        result[direction] = {
            True : [],
            False: [],
        }
        for t in grp:
            result[direction][t["l1_aligned"]].append(t)

        for aligned in [True, False]:
            sub = result[direction][aligned]
            if not sub:
                result[direction][aligned] = None
                continue
            n      = len(sub)
            wins   = sum(1 for t in sub if t["win"])
            pnls   = [t["pnl_usd"] for t in sub]
            result[direction][aligned] = {
                "n"        : n,
                "win_rate" : wins / n * 100,
                "avg_pnl"  : np.mean(pnls),
                "total_pnl": sum(pnls),
            }
    return result


def analyze_exit_reasons(trades: list[dict]) -> dict:
    """
    Per l1_aligned, breakdown exit reason (SL / TP2 / SoftExit).
    """
    result = {True: defaultdict(int), False: defaultdict(int)}
    for t in trades:
        result[t["l1_aligned"]][t["exit_reason"]] += 1
    return result


# ════════════════════════════════════════════════════════════════════
#  REPORT WRITER
# ════════════════════════════════════════════════════════════════════

def write_report(all_trades: list[dict], buf: list[str]):
    sep  = "═" * 70
    sep2 = "─" * 70

    def p(line=""): buf.append(line); print(line)

    years = sorted(set(t["year"] for t in all_trades))
    label_aligned   = {True: "l1_aligned = TRUE  (HMM selaras dengan trend)",
                       False: "l1_aligned = FALSE (HMM berlawanan / Sideways)"}

    for year in years:
        trades = [t for t in all_trades if t["year"] == year]
        p()
        p(sep)
        p(f"  YEAR {year}  —  {len(trades)} trades total")
        p(sep)

        # ── 1. Overall: aligned vs not aligned ──────────────────────
        l1_analysis = analyze_l1(trades)
        p()
        p("  [1] WIN RATE & PNL: l1_aligned TRUE vs FALSE")
        p(sep2)
        p(f"  {'Grup':<42} {'N':>5}  {'Win%':>7}  {'AvgPnL':>9}  {'TotalPnL':>10}  {'PF':>6}")
        p(f"  {'-'*42} {'-'*5}  {'-'*7}  {'-'*9}  {'-'*10}  {'-'*6}")

        for aligned in [True, False]:
            d = l1_analysis[aligned]
            if d is None:
                p(f"  {label_aligned[aligned]:<42} {'—':>5}")
                continue
            pf = f"{d['profit_factor']:.2f}" if d['profit_factor'] != float('inf') else "∞"
            flag = ""
            if aligned and d["win_rate"] > l1_analysis[False]["win_rate"] + 5:
                flag = " ✅ LEBIH BAIK"
            elif aligned and d["win_rate"] < l1_analysis[False]["win_rate"] - 5:
                flag = " ⚠ LEBIH BURUK"
            p(f"  {label_aligned[aligned]:<42} "
              f"{d['n']:>5}  "
              f"{d['win_rate']:>6.1f}%  "
              f"${d['avg_pnl_usd']:>+8.2f}  "
              f"${d['total_pnl']:>+9.2f}  "
              f"{pf:>6}{flag}")

        # Delta
        if l1_analysis[True] and l1_analysis[False]:
            delta_wr  = l1_analysis[True]["win_rate"] - l1_analysis[False]["win_rate"]
            delta_pnl = l1_analysis[True]["avg_pnl_usd"] - l1_analysis[False]["avg_pnl_usd"]
            p()
            p(f"  Delta win rate  : {delta_wr:+.1f}% (positif = aligned lebih baik)")
            p(f"  Delta avg PnL   : ${delta_pnl:+.2f}")

        # ── 2. Per direction ─────────────────────────────────────────
        dir_analysis = analyze_by_direction(trades)
        p()
        p("  [2] PER DIRECTION: LONG dan SHORT dipisah")
        p(sep2)
        p(f"  {'Grup':<38} {'N':>5}  {'Win%':>7}  {'AvgPnL':>9}  {'TotalPnL':>10}")
        p(f"  {'-'*38} {'-'*5}  {'-'*7}  {'-'*9}  {'-'*10}")

        for direction in ["LONG", "SHORT"]:
            if direction not in dir_analysis:
                continue
            for aligned in [True, False]:
                d = dir_analysis[direction].get(aligned)
                tag = f"{direction} | aligned={aligned}"
                if d is None:
                    p(f"  {tag:<38} {'—':>5}")
                    continue
                p(f"  {tag:<38} "
                  f"{d['n']:>5}  "
                  f"{d['win_rate']:>6.1f}%  "
                  f"${d['avg_pnl_usd'] if 'avg_pnl_usd' in d else d['avg_pnl']:>+8.2f}  "
                  f"${d['total_pnl']:>+9.2f}")

        # ── 3. Per HMM label ─────────────────────────────────────────
        lbl_analysis = analyze_by_hmm_label(trades)
        p()
        p("  [3] PER HMM LABEL")
        p(sep2)
        p(f"  {'HMM Label':<34} {'N':>5}  {'Win%':>7}  {'AvgPnL':>9}  {'TotalPnL':>10}")
        p(f"  {'-'*34} {'-'*5}  {'-'*7}  {'-'*9}  {'-'*10}")

        for label, d in sorted(lbl_analysis.items()):
            p(f"  {label:<34} "
              f"{d['n']:>5}  "
              f"{d['win_rate']:>6.1f}%  "
              f"${d['avg_pnl']:>+8.2f}  "
              f"${d['total_pnl']:>+9.2f}")

        # ── 4. Exit reason breakdown ─────────────────────────────────
        exit_analysis = analyze_exit_reasons(trades)
        p()
        p("  [4] EXIT REASON BREAKDOWN per l1_aligned")
        p(sep2)
        all_reasons = sorted(set(
            r for grp in exit_analysis.values() for r in grp
        ))
        header = f"  {'Exit Reason':<16}" + "".join(
            f"  {'aligned='+str(a):>16}" for a in [True, False]
        )
        p(header)
        p("  " + "-" * (len(header) - 2))
        for reason in all_reasons:
            row = f"  {reason:<16}"
            for aligned in [True, False]:
                cnt   = exit_analysis[aligned].get(reason, 0)
                total = sum(exit_analysis[aligned].values())
                pct   = cnt / total * 100 if total > 0 else 0
                row  += f"  {cnt:>5} ({pct:>4.1f}%)     "
            p(row)

        p()


def write_summary(all_trades: list[dict], buf: list[str]):
    sep = "═" * 70

    def p(line=""): buf.append(line); print(line)

    p()
    p(sep)
    p("  KESIMPULAN: APAKAH LAYER 1 HMM MEMBERIKAN NILAI?")
    p(sep)

    # Aggregate across years
    wr_aligned   = []
    wr_unaligned = []
    pnl_aligned  = []
    pnl_unaligned= []

    for year in sorted(set(t["year"] for t in all_trades)):
        trades = [t for t in all_trades if t["year"] == year]
        l1 = analyze_l1(trades)

        if l1[True]:
            wr_aligned.append(l1[True]["win_rate"])
            pnl_aligned.append(l1[True]["avg_pnl_usd"])
        if l1[False]:
            wr_unaligned.append(l1[False]["win_rate"])
            pnl_unaligned.append(l1[False]["avg_pnl_usd"])

    avg_wr_a  = np.mean(wr_aligned)   if wr_aligned   else 0
    avg_wr_u  = np.mean(wr_unaligned) if wr_unaligned else 0
    avg_pnl_a = np.mean(pnl_aligned)  if pnl_aligned  else 0
    avg_pnl_u = np.mean(pnl_unaligned)if pnl_unaligned else 0
    delta_wr  = avg_wr_a - avg_wr_u
    delta_pnl = avg_pnl_a - avg_pnl_u

    p()
    p(f"  Avg win rate  aligned   : {avg_wr_a:.1f}%")
    p(f"  Avg win rate  unaligned : {avg_wr_u:.1f}%")
    p(f"  Delta win rate          : {delta_wr:+.1f}%")
    p()
    p(f"  Avg PnL/trade aligned   : ${avg_pnl_a:+.2f}")
    p(f"  Avg PnL/trade unaligned : ${avg_pnl_u:+.2f}")
    p(f"  Delta PnL/trade         : ${delta_pnl:+.2f}")
    p()

    # Verdict
    if delta_wr >= 10 and delta_pnl > 0:
        verdict = "✅ LAYER 1 BERGUNA"
        detail  = (f"Trade dengan l1_aligned memberikan win rate lebih tinggi "
                   f"{delta_wr:+.1f}% dan PnL lebih baik ${delta_pnl:+.2f}/trade. "
                   f"Bobot 30% di Spectrum justified.")
    elif delta_wr >= 5 or delta_pnl > 0:
        verdict = "🟡 LAYER 1 MARGINAL"
        detail  = (f"Ada sedikit perbedaan (delta win rate {delta_wr:+.1f}%, "
                   f"delta PnL ${delta_pnl:+.2f}), tapi tidak cukup kuat. "
                   f"Pertimbangkan turunkan bobot dari 30% ke 15%.")
    else:
        verdict = "🔴 LAYER 1 TIDAK MEMBERIKAN NILAI"
        detail  = (f"Tidak ada perbedaan signifikan antara aligned dan unaligned. "
                   f"HMM dalam kondisi saat ini berperan sebagai noise di Spectrum. "
                   f"Rekomendasi: ganti peran HMM dari directional gate menjadi "
                   f"volatility regime filter saja (HV vs LV untuk sizing).")

    p(f"  VERDICT: {verdict}")
    p()
    p(f"  {detail}")
    p()
    p(sep)
    p(f"  Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    p(sep)


# ════════════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════════════

def main():
    sep = "═" * 70
    print(f"\n{sep}")
    print("  BTC-QUANT-BTC · LAYER 1 HMM CONTRIBUTION ANALYSIS")
    print(f"  Run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(sep)

    LOG_DIR.mkdir(exist_ok=True)
    run_ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = LOG_DIR / f"l1_contribution_{run_ts}.log"

    buf: list[str] = []
    all_trades: list[dict] = []

    for year in [2023, 2025]:
        print(f"\n  Running detailed backtest {year}...")
        trades = run_detailed_backtest(year)
        print(f"  → {len(trades)} trades recorded")
        all_trades.extend(trades)

    write_report(all_trades, buf)
    write_summary(all_trades, buf)

    with open(report_file, "w", encoding="utf-8") as f:
        f.write("\n".join(buf))

    print(f"\n  📄 Saved: {report_file}\n")


if __name__ == "__main__":
    main()
