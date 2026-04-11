"""
Phase 7: Lead/Lag Analysis
1. Cross-Correlation Function (CCF) -- altcoin vs BTC at lags -N..+N
2. Granger Causality Test -- does X help predict Y?
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats as scipy_stats
from statsmodels.tsa.stattools import grangercausalitytests
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
REPORTS_DIR = Path(__file__).parent.parent / "reports"

ALTCOINS = ["ETH", "SOL", "AVAX", "ARB", "LINK", "LTC", "DOGE"]
COLORS = {
    "ETH": "#627EEA", "SOL": "#9945FF", "AVAX": "#E84142", 
    "ARB": "#28A0F0", "LINK": "#2A5ADA", "LTC": "#345D9D", "DOGE": "#C2A633"
}
MAX_LAG = 12  # candles


def load(tf: str):
    returns = pd.read_csv(PROCESSED_DIR / f"returns_{tf}.csv", parse_dates=["timestamp"], index_col="timestamp")
    return returns


# -- CCF ----------------------------------------------------------------

def cross_correlation(x: pd.Series, y: pd.Series, max_lag: int):
    """Cross-correlation at lags -max_lag..+max_lag.
    Positive lag = x leads y (x moves first).
    """
    lags = range(-max_lag, max_lag + 1)
    ccf = []
    for lag in lags:
        if lag < 0:
            corr = x.iloc[:lag].corr(y.iloc[-lag:])
        elif lag > 0:
            corr = x.iloc[lag:].corr(y.iloc[:-lag])
        else:
            corr = x.corr(y)
        ccf.append(corr)
    return list(lags), ccf


def plot_ccf(returns: pd.DataFrame, tf: str):
    """Plot CCF for each altcoin vs BTC."""
    fig, axes = plt.subplots(len(ALTCOINS), 1, figsize=(12, 3.2 * len(ALTCOINS)), sharex=True)

    summary = []
    for i, alt in enumerate(ALTCOINS):
        ax = axes[i]
        lags, ccf = cross_correlation(returns[alt], returns["BTC"], MAX_LAG)

        # Bar chart
        colors_bar = ["#e74c3c" if l < 0 else "#2ecc71" if l > 0 else "#3498db" for l in lags]
        ax.bar(lags, ccf, color=colors_bar, alpha=0.7, width=0.8)
        ax.axhline(0, color="gray", linewidth=0.5)
        ax.set_ylabel(f"{alt}->BTC")
        ax.set_ylim(-0.1, max(ccf) * 1.15)
        ax.grid(True, alpha=0.2, axis="y")

        # Find peak
        peak_idx = np.argmax(ccf)
        peak_lag = lags[peak_idx]
        peak_val = ccf[peak_idx]
        ax.annotate(f"peak: lag={peak_lag}, r={peak_val:.4f}",
                    xy=(peak_lag, peak_val), xytext=(peak_lag + 2, peak_val),
                    fontsize=9, fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color="red"))

        # Interpretation
        if peak_lag < 0:
            interp = f"{alt} LEADS BTC by {abs(peak_lag)} candles"
        elif peak_lag > 0:
            interp = f"BTC LEADS {alt} by {peak_lag} candles"
        else:
            interp = f"{alt} and BTC move SIMULTANEOUSLY"
        summary.append({"pair": f"{alt}->BTC", "peak_lag": peak_lag, "peak_corr": peak_val, "interpretation": interp})

    axes[0].set_title(f"Cross-Correlation: Altcoin -> BTC - {tf.upper()}\n(negative lag = altcoin leads)", fontsize=13)
    axes[-1].set_xlabel("Lag (candles)")
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / f"12_ccf_{tf}.png", dpi=150)
    plt.close(fig)
    print(f"  Saved: 12_ccf_{tf}.png")

    df = pd.DataFrame(summary)
    print(f"\n  CCF Summary ({tf}):")
    print(df.to_string(index=False))
    return df


# -- Granger Causality --------------------------------------------------

def granger_test(returns: pd.DataFrame, tf: str):
    """Granger causality: does altcoin help predict BTC (and vice versa)?"""
    max_test_lag = 6
    results = []

    for alt in ALTCOINS:
        data = returns[["BTC", alt]].dropna()

        # Alt -> BTC (does alt Granger-cause BTC?)
        try:
            gc_alt_btc = grangercausalitytests(data[["BTC", alt]], maxlag=max_test_lag, verbose=False)
            min_p_alt_btc = min(gc_alt_btc[lag][0]["ssr_ftest"][1] for lag in range(1, max_test_lag + 1))
            best_lag_alt_btc = min(range(1, max_test_lag + 1),
                                   key=lambda l: gc_alt_btc[l][0]["ssr_ftest"][1])
        except Exception:
            min_p_alt_btc = np.nan
            best_lag_alt_btc = np.nan

        # BTC -> Alt (does BTC Granger-cause alt?)
        try:
            gc_btc_alt = grangercausalitytests(data[[alt, "BTC"]], maxlag=max_test_lag, verbose=False)
            min_p_btc_alt = min(gc_btc_alt[lag][0]["ssr_ftest"][1] for lag in range(1, max_test_lag + 1))
            best_lag_btc_alt = min(range(1, max_test_lag + 1),
                                   key=lambda l: gc_btc_alt[l][0]["ssr_ftest"][1])
        except Exception:
            min_p_btc_alt = np.nan
            best_lag_btc_alt = np.nan

        results.append({
            "pair": alt,
            f"{alt}->BTC p-val": min_p_alt_btc,
            f"{alt}->BTC lag": best_lag_alt_btc,
            f"{alt}->BTC sig": "YES" if min_p_alt_btc < 0.05 else "no",
            f"BTC->{alt} p-val": min_p_btc_alt,
            f"BTC->{alt} lag": best_lag_btc_alt,
            f"BTC->{alt} sig": "YES" if min_p_btc_alt < 0.05 else "no",
        })

    df = pd.DataFrame(results).set_index("pair")
    print(f"\n  Granger Causality ({tf}, p<0.05 = significant):")
    print(df.to_string(float_format="{:.6f}".format))

    # Summary plot
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    for ax_idx, direction in enumerate(["alt->BTC", "BTC->alt"]):
        ax = axes[ax_idx]
        pairs = []
        pvals = []
        for alt in ALTCOINS:
            if direction == "alt->BTC":
                p = df.loc[alt, f"{alt}->BTC p-val"]
            else:
                p = df.loc[alt, f"BTC->{alt} p-val"]
            pairs.append(alt)
            pvals.append(p)

        colors_bar = ["#2ecc71" if p < 0.05 else "#e74c3c" for p in pvals]
        ax.barh(pairs, [-np.log10(p) if p > 0 else 10 for p in pvals], color=colors_bar, alpha=0.8)
        ax.axvline(-np.log10(0.05), color="red", linestyle="--", label="p=0.05")
        ax.set_xlabel("-log10(p-value)")
        title = f"Altcoin Granger-causes BTC" if direction == "alt->BTC" else f"BTC Granger-causes Altcoin"
        ax.set_title(title, fontsize=11)
        ax.legend()
        ax.grid(True, alpha=0.2, axis="x")

    fig.suptitle(f"Granger Causality Test - {tf.upper()}", fontsize=13, y=1.02)
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / f"13_granger_{tf}.png", dpi=150)
    plt.close(fig)
    print(f"  Saved: 13_granger_{tf}.png")

    return df


def main():
    for tf in ["4h", "1d"]:
        print(f"\n=== Lead/Lag Analysis: {tf.upper()} ===")
        returns = load(tf)
        plot_ccf(returns, tf)
        granger_test(returns, tf)

    print(f"\nPhase 7 complete.")


if __name__ == "__main__":
    main()
