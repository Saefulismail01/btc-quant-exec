"""
╔══════════════════════════════════════════════════════════════╗
║  BTC-QUANT: Confluence Walk-Forward Test                    ║
║  Tests full pipeline: BCD + EMA + MLP via Spectrum          ║
║                                                              ║
║  Variasi:                                                    ║
║    V0: BCD saja (baseline)                                  ║
║    V1: BCD + EMA (Spectrum L1+L2, L3=0)                     ║
║    V2: BCD + MLP (Spectrum L1+L3, L2=0)                     ║
║    V3: BCD + EMA + MLP (full Spectrum)                      ║
║    V4: Full Spectrum + strict gate (ACTIVE only)            ║
║                                                              ║
║  Spectrum weights: L1=0.30, L2=0.25, L3=0.45               ║
║  Gate: ACTIVE ≥ 0.20, ADVISORY ≥ 0.10, SUSPENDED < 0.10   ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

_BACKEND_DIR = str(Path(__file__).resolve().parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

os.environ.setdefault("BTC_QUANT_LAYER1_ENGINE", "bcd")

from data_engine import DuckDBManager, DB_PATH
from engines.layer1_bcd import BayesianChangepointModel
from engines.layer2_ema import EMAStructureModel
from engines.layer3_ai import SignalIntelligenceModel
from engines.layer1_volatility import VolatilityRegimeEstimator

# ── Spectrum Configuration (from utils/spectrum.py) ──────────
L1_W = 0.30   # BCD weight
L2_W = 0.25   # EMA weight
L3_W = 0.45   # MLP weight

GATE_ACTIVE   = 0.20
GATE_ADVISORY = 0.10
FEE_RATE      = 0.0004


def compute_l4_multiplier(vol_ratio: float) -> float:
    """L4 risk multiplier from vol ratio."""
    MIN_ATR, MAX_ATR = 0.006, 0.030
    if vol_ratio <= MIN_ATR:
        return 1.0
    if vol_ratio >= MAX_ATR:
        return 0.0
    return round(1.0 - (vol_ratio - MIN_ATR) / (MAX_ATR - MIN_ATR), 4)


def spectrum_score(l1_vote, l2_vote, l3_vote, l4_mult):
    """Replicate DirectionalSpectrum.calculate() inline."""
    raw = L1_W * l1_vote + L2_W * l2_vote + L3_W * l3_vote
    bias = raw * l4_mult
    action = "LONG" if bias >= 0 else "SHORT"
    abs_bias = abs(bias)
    if abs_bias >= GATE_ACTIVE:
        gate = "ACTIVE"
    elif abs_bias >= GATE_ADVISORY:
        gate = "ADVISORY"
    else:
        gate = "SUSPENDED"
    return bias, action, gate


def run_confluence_backtest(
    df: pd.DataFrame,
    window_name: str = "Full",
    variation: str = "V0",
    gate_mode: str = "ADVISORY",  # minimum gate to trade: "ADVISORY" or "ACTIVE"
) -> dict:
    """
    Run backtest with Spectrum-based confluence filtering.
    
    Variations:
        V0: BCD only (L2=0, L3=0)
        V1: BCD + EMA (L3=0)
        V2: BCD + MLP (L2=0)
        V3: Full (all layers)
        V4: Full + ACTIVE gate only
    """
    import pandas_ta as ta

    t0 = time.time()
    min_gate = gate_mode

    if len(df) < 200:
        return {"window": window_name, "variation": variation, "error": "insufficient"}

    # ── Train engines ────────────────────────────────────────
    # BCD (always)
    bcd = BayesianChangepointModel()
    bcd.train_global(df)
    states, idx = bcd.get_state_sequence_raw(df)
    if states is None:
        return {"window": window_name, "variation": variation, "error": "bcd_failed"}

    regime_series = pd.Series(
        [bcd.state_map.get(int(s), "Unknown") for s in states],
        index=idx, name="regime"
    )

    # EMA (for V1, V3, V4)
    ema_model = EMAStructureModel()

    # MLP (for V2, V3, V4) — get_ai_confidence handles train+predict
    mlp = SignalIntelligenceModel()
    use_mlp = variation in ("V2", "V3", "V4")

    # Heston for SL/TP
    vol_est = VolatilityRegimeEstimator()
    vol_params = vol_est.estimate_params(df)
    vol_regime = vol_params.get("vol_regime", "Normal")
    halflife = float(vol_params.get("mean_reversion_halflife_candles", 999))
    sl_tp = vol_est.get_sl_tp_multipliers(vol_regime, halflife, 0.5)
    sl_mult = sl_tp["sl_multiplier"]
    tp_mult = sl_tp["tp1_multiplier"]

    # ATR
    df["ATR14"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)
    df["EMA20"] = ta.ema(df["Close"], length=20)
    df["EMA50"] = ta.ema(df["Close"], length=50)

    bcd_time = time.time() - t0

    # ── Simulate ─────────────────────────────────────────────
    valid_df = df.loc[idx].copy()
    valid_df["regime"] = regime_series.values

    trades = []
    position = None
    skipped = 0
    total_signals = 0

    for i in range(len(valid_df) - 1):
        row = valid_df.iloc[i]
        next_row = valid_df.iloc[i + 1]

        close = float(row["Close"])
        high_next = float(next_row["High"])
        low_next = float(next_row["Low"])
        regime = row["regime"]
        atr = float(row["ATR14"]) if not pd.isna(row.get("ATR14", float("nan"))) else close * 0.01
        vol_ratio = atr / close if close > 0 else 0.01

        # ── Exit check ───────────────────────────────────────
        if position is not None:
            exit_price = None
            exit_type = None

            if position["side"] == "LONG":
                if low_next <= position["sl"]:
                    exit_price, exit_type = position["sl"], "SL"
                elif high_next >= position["tp"]:
                    exit_price, exit_type = position["tp"], "TP"
                elif regime != "Bullish Trend":
                    exit_price, exit_type = close, "REGIME_FLIP"
            else:
                if high_next >= position["sl"]:
                    exit_price, exit_type = position["sl"], "SL"
                elif low_next <= position["tp"]:
                    exit_price, exit_type = position["tp"], "TP"
                elif regime != "Bearish Trend":
                    exit_price, exit_type = close, "REGIME_FLIP"

            if exit_price is not None:
                if position["side"] == "LONG":
                    pnl = (exit_price / position["entry"] - 1) * 100
                else:
                    pnl = (1 - exit_price / position["entry"]) * 100
                pnl -= FEE_RATE * 2 * 100
                trades.append({
                    "side": position["side"],
                    "pnl_pct": round(pnl, 4),
                    "exit_type": exit_type,
                    "gate": position.get("gate", "N/A"),
                    "bias": position.get("bias_score", 0),
                })
                position = None

        # ── Entry check ──────────────────────────────────────
        if position is None and regime in ("Bullish Trend", "Bearish Trend"):
            total_signals += 1
            is_bull = regime == "Bullish Trend"

            # ── Compute Spectrum votes ───────────────────────
            # L1: BCD regime as directional vote
            # Map regime to confidence based on segment stats
            l1_vote = 0.7 if is_bull else -0.7

            # L2: EMA structural vote
            if variation in ("V1", "V3", "V4"):
                # Use the candle context up to this point
                context_df = valid_df.iloc[:i+1].copy()
                if len(context_df) >= 50:
                    l2_vote = ema_model.get_directional_vote(context_df)
                else:
                    l2_vote = 0.0
            else:
                l2_vote = 0.0  # disabled for V0, V2

            # L3: MLP confidence vote
            if use_mlp and variation in ("V2", "V3", "V4"):
                try:
                    context_df = valid_df.iloc[:i+1].copy()
                    if len(context_df) >= 50:
                        ai_bias, ai_conf = mlp.get_ai_confidence(
                            context_df,
                            hmm_states=states[:i+1] if i+1 <= len(states) else states,
                            hmm_index=idx[:i+1] if i+1 <= len(idx) else idx,
                        )
                        conf_norm = (max(50.0, min(100.0, ai_conf)) - 50.0) / 50.0
                        l3_vote = conf_norm if ai_bias == "BULL" else -conf_norm
                    else:
                        l3_vote = 0.0
                except Exception:
                    l3_vote = 0.0
            else:
                l3_vote = 0.0  # disabled for V0, V1

            # L4: Vol multiplier
            l4_mult = compute_l4_multiplier(vol_ratio)

            # Spectrum
            bias_score, spec_action, gate = spectrum_score(l1_vote, l2_vote, l3_vote, l4_mult)

            # ── Gate check ───────────────────────────────────
            gate_ok = False
            if min_gate == "ADVISORY":
                gate_ok = gate in ("ACTIVE", "ADVISORY")
            elif min_gate == "ACTIVE":
                gate_ok = gate == "ACTIVE"

            # Direction must match regime
            direction_ok = (is_bull and spec_action == "LONG") or (not is_bull and spec_action == "SHORT")

            if gate_ok and direction_ok:
                side = "LONG" if is_bull else "SHORT"
                if side == "LONG":
                    position = {
                        "side": "LONG", "entry": close,
                        "sl": close - atr * sl_mult,
                        "tp": close + atr * tp_mult,
                        "gate": gate, "bias_score": round(bias_score, 4),
                    }
                else:
                    position = {
                        "side": "SHORT", "entry": close,
                        "sl": close + atr * sl_mult,
                        "tp": close - atr * tp_mult,
                        "gate": gate, "bias_score": round(bias_score, 4),
                    }
            else:
                skipped += 1

    # Close remaining
    if position is not None:
        last_close = float(valid_df.iloc[-1]["Close"])
        if position["side"] == "LONG":
            pnl = (last_close / position["entry"] - 1) * 100
        else:
            pnl = (1 - last_close / position["entry"]) * 100
        pnl -= FEE_RATE * 2 * 100
        trades.append({"side": position["side"], "pnl_pct": round(pnl, 4),
                        "exit_type": "EOD", "gate": position.get("gate"),
                        "bias": position.get("bias_score", 0)})

    # ── Results ──────────────────────────────────────────────
    if not trades:
        return {"window": window_name, "variation": variation, "error": "no_trades",
                "total_signals": total_signals, "skipped": skipped}

    tdf = pd.DataFrame(trades)
    total = len(tdf)
    wins = (tdf["pnl_pct"] > 0).sum()
    wr = wins / total * 100
    total_pnl = tdf["pnl_pct"].sum()
    total_days = len(valid_df) / 6.0
    daily_ret = total_pnl / total_days if total_days > 0 else 0

    cumul = tdf["pnl_pct"].cumsum().values
    running_max = np.maximum.accumulate(cumul)
    max_dd = float(np.min(cumul - running_max)) if len(cumul) > 0 else 0

    gross_p = tdf[tdf["pnl_pct"] > 0]["pnl_pct"].sum()
    gross_l = abs(tdf[tdf["pnl_pct"] <= 0]["pnl_pct"].sum())
    pf = gross_p / gross_l if gross_l > 0 else float("inf")

    filter_rate = skipped / total_signals * 100 if total_signals > 0 else 0

    elapsed = time.time() - t0

    return {
        "window": window_name,
        "variation": variation,
        "trades": total,
        "wins": int(wins),
        "wr_pct": round(wr, 1),
        "total_pnl": round(total_pnl, 2),
        "daily_pct": round(daily_ret, 3),
        "max_dd": round(max_dd, 2),
        "pf": round(pf, 2),
        "dd_return_ratio": round(max_dd / daily_ret, 1) if daily_ret != 0 else -999,
        "total_signals": total_signals,
        "skipped": skipped,
        "filter_rate_pct": round(filter_rate, 1),
        "elapsed": round(elapsed, 1),
        "sl_tp": f"SL={sl_mult}×/TP={tp_mult}×",
    }


def main():
    print("\n" + "═" * 70)
    print("  BTC-QUANT: Confluence Walk-Forward (Spectrum v2)")
    print("  Testing V0-V4 across 3 windows")
    print("═" * 70)

    db = DuckDBManager(DB_PATH)
    full_df = db.get_ohlcv_with_metrics(limit=8000)
    print(f"\n  Data: {len(full_df)} candles")
    print(f"  Range: {full_df.index[0]} to {full_df.index[-1]}")

    windows = [
        ("2023 Full", datetime(2023, 1, 1), datetime(2024, 1, 1)),
        ("2024 H2",   datetime(2024, 7, 1), datetime(2025, 1, 1)),
        ("2025-2026", datetime(2025, 1, 1), datetime(2026, 12, 31)),
    ]

    variations = [
        ("V0", "ADVISORY"),   # BCD only
        ("V1", "ADVISORY"),   # BCD + EMA
        ("V2", "ADVISORY"),   # BCD + MLP
        ("V3", "ADVISORY"),   # Full
        ("V4", "ACTIVE"),     # Full + strict gate
    ]

    all_results = []

    for wname, start, end in windows:
        start_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)
        wdf = full_df[
            (full_df["timestamp"] >= start_ms) & (full_df["timestamp"] < end_ms)
        ].copy()

        if len(wdf) < 200:
            print(f"\n  [!] Skipping {wname}: only {len(wdf)} candles")
            continue

        print(f"\n{'═'*60}")
        print(f"  WINDOW: {wname} ({len(wdf)} candles)")
        print(f"{'═'*60}")

        for var_name, gate in variations:
            print(f"\n  ── {var_name} (gate={gate}) ──")
            result = run_confluence_backtest(wdf, wname, var_name, gate)

            if "error" in result:
                print(f"    Error: {result['error']}")
                all_results.append(result)
                continue

            r = result
            print(f"    Trades: {r['trades']} | WR: {r['wr_pct']}% | PnL: {r['total_pnl']:+.2f}%")
            print(f"    Daily: {r['daily_pct']:+.3f}% | DD: {r['max_dd']:.2f}% | PF: {r['pf']:.2f}")
            print(f"    Filtered: {r['skipped']}/{r['total_signals']} ({r['filter_rate_pct']:.0f}%) | {r['elapsed']:.0f}s")
            all_results.append(result)

    # ── Summary Table ────────────────────────────────────────
    valid = [r for r in all_results if "error" not in r]
    if not valid:
        print("\n  No valid results.")
        return

    print("\n" + "═" * 90)
    print("  FULL COMPARISON TABLE")
    print("═" * 90)

    summary_df = pd.DataFrame([{
        "Window": r["window"],
        "Var": r["variation"],
        "Trades": r["trades"],
        "WR%": r["wr_pct"],
        "PnL%": f"{r['total_pnl']:+.1f}",
        "Daily%": f"{r['daily_pct']:+.3f}",
        "MaxDD%": f"{r['max_dd']:.1f}",
        "PF": r["pf"],
        "DD/Ret": r["dd_return_ratio"],
        "Filtered%": f"{r['filter_rate_pct']:.0f}",
    } for r in valid])
    print(summary_df.to_string(index=False))

    # Per-variation averages
    print("\n" + "─" * 70)
    print("  AVERAGE PER VARIATION")
    print("─" * 70)

    for var in ["V0", "V1", "V2", "V3", "V4"]:
        vr = [r for r in valid if r["variation"] == var]
        if not vr:
            continue
        avg_wr = np.mean([r["wr_pct"] for r in vr])
        avg_daily = np.mean([r["daily_pct"] for r in vr])
        avg_dd = np.mean([r["max_dd"] for r in vr])
        avg_pf = np.mean([r["pf"] for r in vr])
        avg_filter = np.mean([r["filter_rate_pct"] for r in vr])
        avg_trades = np.mean([r["trades"] for r in vr])
        avg_ddr = np.mean([r["dd_return_ratio"] for r in vr])

        print(f"  {var}: WR={avg_wr:.1f}% | Daily={avg_daily:+.3f}% | DD={avg_dd:.1f}% | "
              f"PF={avg_pf:.2f} | Filter={avg_filter:.0f}% | Trades={avg_trades:.0f} | DD/Ret={avg_ddr:.1f}")

    # Save
    out_dir = Path(_BACKEND_DIR).parent / "backtest" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(valid).to_csv(out_dir / "confluence_results.csv", index=False)
    print(f"\n  [✓] Saved → {out_dir / 'confluence_results.csv'}")

    # Best variation
    var_avgs = {}
    for var in ["V0", "V1", "V2", "V3", "V4"]:
        vr = [r for r in valid if r["variation"] == var]
        if vr:
            var_avgs[var] = {
                "wr": np.mean([r["wr_pct"] for r in vr]),
                "daily": np.mean([r["daily_pct"] for r in vr]),
                "dd": np.mean([r["max_dd"] for r in vr]),
                "pf": np.mean([r["pf"] for r in vr]),
            }

    # Pick best by highest PF with DD < baseline
    baseline_dd = var_avgs.get("V0", {}).get("dd", -25)
    best_var = "V0"
    best_score = 0
    for var, avgs in var_avgs.items():
        # Score = PF * (1 + DD improvement) — reward both PF and DD reduction
        dd_improvement = (baseline_dd - avgs["dd"]) / abs(baseline_dd) if baseline_dd != 0 else 0
        score = avgs["pf"] * (1 + max(0, dd_improvement))
        if score > best_score:
            best_score = score
            best_var = var

    print(f"\n  🏆 BEST VARIATION: {best_var}")
    b = var_avgs[best_var]
    print(f"     WR={b['wr']:.1f}% | Daily={b['daily']:+.3f}% | DD={b['dd']:.1f}% | PF={b['pf']:.2f}")


if __name__ == "__main__":
    main()
