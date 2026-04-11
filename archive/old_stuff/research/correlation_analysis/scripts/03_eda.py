"""
Phase 3: Exploratory Data Analysis (EDA)
1. Normalized Price Chart (base 100)
2. Returns Distribution (histogram + stats)
3. Volatility Comparison (rolling std dev)
4. Static Correlation Heatmap
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
REPORTS_DIR = Path(__file__).parent.parent / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

COLORS = {
    "BTC": "#F7931A", "ETH": "#627EEA", "SOL": "#9945FF", "AVAX": "#E84142", 
    "ARB": "#28A0F0", "LINK": "#2A5ADA", "LTC": "#345D9D", "DOGE": "#C2A633"
}


def load(tf: str):
    close = pd.read_csv(PROCESSED_DIR / f"close_{tf}.csv", parse_dates=["timestamp"], index_col="timestamp")
    returns = pd.read_csv(PROCESSED_DIR / f"returns_{tf}.csv", parse_dates=["timestamp"], index_col="timestamp")
    log_ret = pd.read_csv(PROCESSED_DIR / f"log_returns_{tf}.csv", parse_dates=["timestamp"], index_col="timestamp")
    return close, returns, log_ret


def plot_normalized_prices(close: pd.DataFrame, tf: str):
    """All assets normalized to base 100 at start."""
    norm = close / close.iloc[0] * 100
    fig, ax = plt.subplots(figsize=(14, 6))
    for col in norm.columns:
        ax.plot(norm.index, norm[col], label=col, color=COLORS.get(col, None), linewidth=1.2)
    ax.set_title(f"Normalized Price (Base 100) - {tf.upper()}", fontsize=14)
    ax.set_ylabel("Normalized Price")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)
    ax.axhline(100, color="gray", linestyle="--", alpha=0.5)
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / f"01_normalized_prices_{tf}.png", dpi=150)
    plt.close(fig)
    print(f"  Saved: 01_normalized_prices_{tf}.png")


def plot_returns_distribution(returns: pd.DataFrame, tf: str):
    """Histogram + stats for each asset."""
    n_assets = len(returns.columns)
    rows = int(np.ceil(n_assets / 3))
    fig, axes = plt.subplots(rows, 3, figsize=(16, 4 * rows))
    axes = axes.flatten()
    for i, col in enumerate(returns.columns):
        ax = axes[i]
        ax.hist(returns[col], bins=100, color=COLORS.get(col, "steelblue"), alpha=0.7, edgecolor="white", linewidth=0.3)
        mu = returns[col].mean()
        sigma = returns[col].std()
        skew = returns[col].skew()
        kurt = returns[col].kurt()
        ax.set_title(f"{col}", fontsize=12, fontweight="bold")
        ax.axvline(mu, color="red", linestyle="--", linewidth=1)
        stats_text = f"mean={mu:.5f}\nstd={sigma:.4f}\nskew={skew:.2f}\nkurt={kurt:.1f}"
        ax.text(0.95, 0.95, stats_text, transform=ax.transAxes, fontsize=8,
                verticalalignment="top", horizontalalignment="right",
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
        ax.grid(True, alpha=0.2)
    fig.suptitle(f"Returns Distribution - {tf.upper()}", fontsize=14, y=1.01)
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / f"02_returns_distribution_{tf}.png", dpi=150)
    plt.close(fig)
    print(f"  Saved: 02_returns_distribution_{tf}.png")


def plot_rolling_volatility(returns: pd.DataFrame, tf: str):
    """Rolling std dev (annualized) per asset."""
    # Annualization factor
    factor = np.sqrt(365 * 6) if tf == "4h" else np.sqrt(365)
    window = 30 if tf == "4h" else 30  # 30 periods

    rolling_vol = returns.rolling(window=window).std() * factor
    fig, ax = plt.subplots(figsize=(14, 6))
    for col in rolling_vol.columns:
        ax.plot(rolling_vol.index, rolling_vol[col], label=col, color=COLORS.get(col, None), linewidth=1)
    ax.set_title(f"Rolling {window}-Period Annualized Volatility - {tf.upper()}", fontsize=14)
    ax.set_ylabel("Annualized Volatility")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / f"03_rolling_volatility_{tf}.png", dpi=150)
    plt.close(fig)
    print(f"  Saved: 03_rolling_volatility_{tf}.png")


def plot_correlation_heatmap(returns: pd.DataFrame, tf: str):
    """Static Pearson & Spearman correlation heatmap."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    for ax, method, title in zip(axes, ["pearson", "spearman"], ["Pearson", "Spearman"]):
        corr = returns.corr(method=method)
        mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
        sns.heatmap(corr, annot=True, fmt=".3f", cmap="RdYlGn", center=0,
                    vmin=-1, vmax=1, mask=mask, ax=ax, linewidths=0.5,
                    cbar_kws={"shrink": 0.8}, annot_kws={"size": 9})
        ax.set_title(f"{title} Correlation", fontsize=12)
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

    fig.suptitle(f"Static Correlation Heatmap - {tf.upper()}", fontsize=14)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(REPORTS_DIR / f"04_correlation_heatmap_{tf}.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: 04_correlation_heatmap_{tf}.png")

    # Print correlation values
    pearson = returns.corr(method="pearson")
    print(f"\n  Pearson Correlation vs BTC ({tf}):")
    for col in pearson.columns:
        if col != "BTC":
            print(f"    BTC-{col}: {pearson.loc['BTC', col]:.4f}")


def main():
    for tf in ["4h", "1d"]:
        print(f"\n=== EDA: {tf.upper()} ===")
        close, returns, log_ret = load(tf)
        plot_normalized_prices(close, tf)
        plot_returns_distribution(returns, tf)
        plot_rolling_volatility(returns, tf)
        plot_correlation_heatmap(returns, tf)

    print(f"\nPhase 3 EDA complete. All plots in reports/")


if __name__ == "__main__":
    main()
