"""
Phase 6: Regime-Specific Correlation
- Pearson correlation BTC vs altcoins per MA regime (bull/bear/sideways)
- Pearson correlation per volatility regime (high/low vol)
- Combined regime (MA x Vol) analysis
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
REPORTS_DIR = Path(__file__).parent.parent / "reports"

ALTCOINS = ["ETH", "SOL", "AVAX", "ARB", "LINK", "LTC", "DOGE"]
REGIME_COLORS = {"bull": "#2ecc71", "bear": "#e74c3c", "sideways": "#f39c12"}
VOL_COLORS = {"high_vol": "#e74c3c", "low_vol": "#3498db"}


def load(tf: str):
    returns = pd.read_csv(PROCESSED_DIR / f"returns_{tf}.csv", parse_dates=["timestamp"], index_col="timestamp")
    regimes = pd.read_csv(PROCESSED_DIR / f"regimes_{tf}.csv", parse_dates=["timestamp"], index_col="timestamp")
    return returns, regimes


def corr_by_group(returns: pd.DataFrame, group_col: pd.Series, group_name: str, tf: str):
    """Compute BTC vs altcoin correlation for each group value."""
    merged = returns.copy()
    merged["_group"] = group_col
    merged = merged.dropna(subset=["_group"])

    results = []
    for gval in sorted(merged["_group"].unique()):
        subset = merged[merged["_group"] == gval]
        row = {"regime": gval, "n": len(subset)}
        for alt in ALTCOINS:
            # Correlation
            row[f"Corr-{alt}"] = subset["BTC"].corr(subset[alt]) if len(subset) > 10 else np.nan
            # Beta (Cov / Var_btc)
            if len(subset) > 10:
                var_btc = subset["BTC"].var()
                if var_btc > 0:
                    row[f"Beta-{alt}"] = subset["BTC"].cov(subset[alt]) / var_btc
                else:
                    row[f"Beta-{alt}"] = np.nan
            else:
                row[f"Beta-{alt}"] = np.nan
        results.append(row)

    df = pd.DataFrame(results).set_index("regime")
    print(f"\n  {group_name} Analysis ({tf}):")
    # Only print correlation for quick summary
    corr_cols = [c for c in df.columns if c.startswith("Corr-")]
    print("  Correlation Matrix:")
    print(df[corr_cols].to_string(float_format="{:.4f}".format))
    beta_cols = [c for c in df.columns if c.startswith("Beta-")]
    print("\n  Beta Matrix (Sensitivity vs BTC):")
    print(df[beta_cols].to_string(float_format="{:.4f}".format))
    return df


def plot_regime_corr(df: pd.DataFrame, colors: dict, title: str, filename: str):
    """Grouped bar chart for regime-specific correlations."""
    regimes = df.index.tolist()

    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(ALTCOINS))
    width = 0.8 / len(regimes)

    for i, regime in enumerate(regimes):
        vals = [df.loc[regime, f"Corr-{alt}"] for alt in ALTCOINS]
        n = int(df.loc[regime, "n"])
        offset = (i - len(regimes) / 2 + 0.5) * width
        ax.bar(x + offset, vals, width, label=f"{regime} (n={n})",
               color=colors.get(regime, f"C{i}"), alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(ALTCOINS)
    ax.set_ylabel("Pearson Correlation")
    ax.set_title(title, fontsize=13)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.2, axis="y")
    ax.set_ylim(0, 1)
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / filename, dpi=150)
    plt.close(fig)
    print(f"  Saved: {filename}")


def plot_combined_heatmap(returns: pd.DataFrame, regimes: pd.DataFrame, tf: str):
    """Heatmap: rows = MA regime x Vol regime, cols = altcoin pairs."""
    merged = returns.copy()
    merged["ma"] = regimes["ma_regime"]
    merged["vol"] = regimes["vol_regime"]
    merged = merged.dropna(subset=["ma", "vol"])
    merged["combined"] = merged["ma"] + " / " + merged["vol"]

    combos = sorted(merged["combined"].unique())
    rows = []
    for combo in combos:
        subset = merged[merged["combined"] == combo]
        row = {"regime": combo, "n": len(subset)}
        row = {"regime": combo, "n": len(subset)}
        for alt in ALTCOINS:
            row[f"Corr-{alt}"] = subset["BTC"].corr(subset[alt]) if len(subset) > 10 else np.nan
        rows.append(row)

    df = pd.DataFrame(rows).set_index("regime")
    corr_cols = [c for c in df.columns if c.startswith("Corr-")]

    print(f"\n  Combined Regime Correlation ({tf}):")
    print(df.to_string(float_format="{:.4f}".format))

    fig, ax = plt.subplots(figsize=(10, 5))
    import seaborn as sns
    heatmap_data = df[corr_cols].astype(float)
    # Add n to index labels
    heatmap_data.index = [f"{idx} (n={int(df.loc[idx, 'n'])})" for idx in heatmap_data.index]
    sns.heatmap(heatmap_data, annot=True, fmt=".3f", cmap="RdYlGn", center=0.6,
                vmin=0.3, vmax=1.0, ax=ax, linewidths=0.5)
    ax.set_title(f"Combined Regime Correlation (BCD x Vol) - {tf.upper()}", fontsize=13)
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / f"11_combined_regime_heatmap_{tf}.png", dpi=150)
    plt.close(fig)
    print(f"  Saved: 11_combined_regime_heatmap_{tf}.png")


def main():
    for tf in ["4h", "1d"]:
        print(f"\n=== Regime-Specific Correlation: {tf.upper()} ===")
        returns, regimes = load(tf)

        # BCD regime correlation
        bcd_df = corr_by_group(returns, regimes["ma_regime"], "BCD Regime", tf)
        plot_regime_corr(bcd_df, REGIME_COLORS,
                         f"Correlation by BCD Regime - {tf.upper()}",
                         f"09_bcd_regime_correlation_{tf}.png")

        # Vol regime correlation
        vol_df = corr_by_group(returns, regimes["vol_regime"], "Vol Regime", tf)
        plot_regime_corr(vol_df, VOL_COLORS,
                         f"Correlation by Volatility Regime - {tf.upper()}",
                         f"10_vol_regime_correlation_{tf}.png")

        # Combined heatmap
        plot_combined_heatmap(returns, regimes, tf)

    print(f"\nPhase 6 complete.")


if __name__ == "__main__":
    main()
