"""
Phase 5: Regime Detection
1. MA Regime: Bull / Bear / Sideways based on SMA50 & SMA200
2. Volatility Regime: High vol vs Low vol using rolling std dev
3. Save regime labels to data/processed/
4. Visualize regimes overlaid on BTC price
"""

import sys
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from pathlib import Path

# Add backend to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from app.core.engines.layer1_bcd import BayesianChangepointModel
except ImportError:
    print("Error: Could not import BayesianChangepointModel from backend.")
    sys.exit(1)

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
REPORTS_DIR = Path(__file__).parent.parent / "reports"


def load(tf: str):
    close = pd.read_csv(PROCESSED_DIR / f"close_{tf}.csv", parse_dates=["timestamp"], index_col="timestamp")
    returns = pd.read_csv(PROCESSED_DIR / f"returns_{tf}.csv", parse_dates=["timestamp"], index_col="timestamp")
    
    # Load raw BTC OHLCV for BCD features
    path = RAW_DIR / f"BTCUSDT_{tf}.csv"
    btc_ohlcv = pd.read_csv(path, parse_dates=["timestamp"])
    btc_ohlcv = btc_ohlcv.set_index("timestamp").sort_index()
    # Map to Title Case columns for BCD engine
    btc_ohlcv = btc_ohlcv.rename(columns={
        "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"
    })
    
    # Align BTC OHLCV with processed timeframe (using inner join to match timestamps)
    btc_ohlcv = btc_ohlcv.loc[close.index]
    
    return close, returns, btc_ohlcv


# ── BCD Regime ───────────────────────────────────────────────────────────

def detect_bcd_regime(btc_ohlcv: pd.DataFrame, tf: str):
    """
    Detect regimes using Bayesian Changepoint Detection (BCD).
    Maps BCD labels to simplified bull/bear/sideways categories.
    """
    model = BayesianChangepointModel()
    
    # BCD engine detects segments and labels them
    states, index = model.get_state_sequence_raw(btc_ohlcv)
    
    if states is None:
        print(f"  Warning: BCD failed for {tf}. Falling back to sideways.")
        return pd.Series("sideways", index=btc_ohlcv.index), model

    # Map BCD states to simplified labels
    bcd_regime = pd.Series("sideways", index=index)
    for sid, label in model.state_map.items():
        if "Bullish" in label:
            bcd_regime[states == sid] = "bull"
        elif "Bearish" in label:
            bcd_regime[states == sid] = "bear"
        else:
            bcd_regime[states == sid] = "sideways"
            
    return bcd_regime, model


# ── Volatility Regime ────────────────────────────────────────────────────

def detect_vol_regime(returns: pd.DataFrame, tf: str):
    """High vol vs Low vol based on rolling std dev vs median."""
    window = 180 if tf == "4h" else 30  # ~30 days
    rolling_vol = returns["BTC"].rolling(window).std()
    median_vol = rolling_vol.median()

    vol_regime = pd.Series("low_vol", index=returns.index)
    vol_regime[rolling_vol > median_vol] = "high_vol"

    return vol_regime, rolling_vol, median_vol


# ── Visualization ────────────────────────────────────────────────────────

def plot_bcd_regime(close: pd.DataFrame, regime: pd.Series, model, tf: str):
    fig, ax = plt.subplots(figsize=(16, 6))

    btc = close["BTC"]
    ax.plot(btc.index, btc, color="black", linewidth=0.8, label="BTC Price (BCD)")

    colors = {"bull": "#2ecc71", "bear": "#e74c3c", "sideways": "#f39c12"}
    for r, color in colors.items():
        mask = regime == r
        ax.fill_between(btc.index, btc.min() * 0.9, btc.max() * 1.5,
                        where=mask, alpha=0.15, color=color)

    legend_patches = [Patch(facecolor=c, alpha=0.3, label=r.capitalize()) for r, c in colors.items()]
    ax.legend(handles=[ax.lines[0]] + legend_patches,
              labels=["BTC", "Bull", "Bear", "Sideways"],
              loc="upper left", fontsize=9)
    ax.set_title(f"BTC BCD Regime Detection - {tf.upper()}", fontsize=14)
    ax.set_ylabel("Price (USDT)")
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / f"07_bcd_regime_{tf}.png", dpi=150)
    plt.close(fig)
    print(f"  Saved: 07_bcd_regime_{tf}.png")


def plot_vol_regime(returns: pd.DataFrame, vol_regime: pd.Series, rolling_vol, median_vol, tf: str):
    fig, ax = plt.subplots(figsize=(16, 4))

    ax.plot(rolling_vol.index, rolling_vol, color="steelblue", linewidth=0.8, label="Rolling Vol")
    ax.axhline(median_vol, color="red", linestyle="--", linewidth=1, label=f"Median ({median_vol:.5f})")

    mask_high = vol_regime == "high_vol"
    ax.fill_between(rolling_vol.index, 0, rolling_vol.max() * 1.1,
                    where=mask_high, alpha=0.15, color="red")
    ax.fill_between(rolling_vol.index, 0, rolling_vol.max() * 1.1,
                    where=~mask_high, alpha=0.1, color="green")

    ax.legend(loc="upper right", fontsize=9)
    ax.set_title(f"BTC Volatility Regime - {tf.upper()}", fontsize=14)
    ax.set_ylabel("Rolling Std Dev")
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / f"08_vol_regime_{tf}.png", dpi=150)
    plt.close(fig)
    print(f"  Saved: 08_vol_regime_{tf}.png")


def main():
    for tf in ["4h", "1d"]:
        print(f"\n=== Regime Detection (BCD): {tf.upper()} ===")
        close, returns, btc_ohlcv = load(tf)

        # BCD regime
        bcd_regime, bcd_model = detect_bcd_regime(btc_ohlcv, tf)
        plot_bcd_regime(close, bcd_regime, bcd_model, tf)

        counts = bcd_regime.value_counts()
        total = len(bcd_regime)
        print(f"  BCD Regime distribution:")
        for r in ["bull", "bear", "sideways"]:
            n = counts.get(r, 0)
            print(f"    {r:<10} {n:>5} candles ({n/total*100:.1f}%)")

        # Vol regime
        vol_regime, rolling_vol, median_vol = detect_vol_regime(returns, tf)
        plot_vol_regime(returns, vol_regime, rolling_vol, median_vol, tf)

        vol_counts = vol_regime.value_counts()
        print(f"  Vol Regime distribution:")
        for r in ["high_vol", "low_vol"]:
            n = vol_counts.get(r, 0)
            print(f"    {r:<10} {n:>5} candles ({n/total*100:.1f}%)")

        # Save regimes
        regimes = pd.DataFrame({
            "ma_regime": bcd_regime, # Maintain column name for downstream scripts
            "vol_regime": vol_regime,
        })
        out_path = PROCESSED_DIR / f"regimes_{tf}.csv"
        regimes.to_csv(out_path)
        print(f"  Saved: {out_path.name}")

    print(f"\nPhase 5 complete.")


if __name__ == "__main__":
    main()
