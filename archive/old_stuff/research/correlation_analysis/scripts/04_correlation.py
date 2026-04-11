"""
Phase 4: Correlation Analysis (Inti Riset)
4a. Static Correlation (Pearson + Spearman) -- sudah di EDA, recap saja
4b. Rolling Correlation (30, 60, 90 period windows)
4c. Conditional Correlation (BTC up vs BTC down)
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
COLORS = {
    "ETH": "#627EEA", "SOL": "#9945FF", "AVAX": "#E84142", 
    "ARB": "#28A0F0", "LINK": "#2A5ADA", "LTC": "#345D9D", "DOGE": "#C2A633"
}


def load(tf: str):
    returns = pd.read_csv(PROCESSED_DIR / f"returns_{tf}.csv", parse_dates=["timestamp"], index_col="timestamp")
    return returns


# ── 4b. Rolling Correlation ──────────────────────────────────────────────

def plot_rolling_correlation(returns: pd.DataFrame, tf: str):
    """Rolling Pearson correlation BTC vs each altcoin, multiple windows."""
    windows = [30, 60, 90]

    fig, axes = plt.subplots(len(ALTCOINS), 1, figsize=(14, 3.5 * len(ALTCOINS)), sharex=True)

    for i, alt in enumerate(ALTCOINS):
        ax = axes[i]
        for w in windows:
            rolling = returns["BTC"].rolling(window=w).corr(returns[alt])
            ax.plot(rolling.index, rolling, label=f"w={w}", linewidth=0.9)

        ax.set_ylabel(f"BTC-{alt}")
        ax.axhline(0, color="gray", linestyle="--", alpha=0.4)
        ax.axhline(0.5, color="red", linestyle=":", alpha=0.3)
        ax.set_ylim(-0.2, 1.0)
        ax.legend(loc="lower right", fontsize=8)
        ax.grid(True, alpha=0.2)

    axes[0].set_title(f"Rolling Correlation BTC vs Altcoins - {tf.upper()}", fontsize=14)
    axes[-1].set_xlabel("Date")
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / f"05_rolling_correlation_{tf}.png", dpi=150)
    plt.close(fig)
    print(f"  Saved: 05_rolling_correlation_{tf}.png")

    # Print summary stats for w=30
    print(f"\n  Rolling Corr (w=30) stats vs BTC ({tf}):")
    print(f"  {'Pair':<10} {'Mean':>7} {'Std':>7} {'Min':>7} {'Max':>7}")
    for alt in ALTCOINS:
        r = returns["BTC"].rolling(30).corr(returns[alt]).dropna()
        print(f"  BTC-{alt:<4} {r.mean():>7.3f} {r.std():>7.3f} {r.min():>7.3f} {r.max():>7.3f}")


# ── 4c. Conditional Correlation ──────────────────────────────────────────

def conditional_correlation(returns: pd.DataFrame, tf: str):
    """Korelasi saat BTC naik vs turun vs extreme moves."""
    btc_up = returns[returns["BTC"] > 0]
    btc_down = returns[returns["BTC"] < 0]
    # Extreme = beyond 1 std dev
    btc_std = returns["BTC"].std()
    btc_crash = returns[returns["BTC"] < -btc_std]
    btc_pump = returns[returns["BTC"] > btc_std]

    conditions = {
        "All": returns,
        "BTC Up": btc_up,
        "BTC Down": btc_down,
        "BTC Crash (<-1std)": btc_crash,
        "BTC Pump (>+1std)": btc_pump,
    }

    rows = []
    for cond_name, subset in conditions.items():
        row = {"Condition": cond_name, "N": len(subset)}
        for alt in ALTCOINS:
            if len(subset) > 5:
                row[f"BTC-{alt}"] = subset["BTC"].corr(subset[alt])
            else:
                row[f"BTC-{alt}"] = np.nan
        rows.append(row)

    df = pd.DataFrame(rows).set_index("Condition")
    print(f"\n  Conditional Correlation ({tf}):")
    print(df.to_string(float_format="{:.4f}".format))

    # Plot as grouped bar chart
    fig, ax = plt.subplots(figsize=(12, 6))
    corr_cols = [c for c in df.columns if c.startswith("BTC-")]
    x = np.arange(len(corr_cols))
    width = 0.15
    cond_names = df.index.tolist()

    for i, cond in enumerate(cond_names):
        if cond == "N":
            continue
        vals = [df.loc[cond, c] for c in corr_cols]
        offset = (i - len(cond_names) / 2 + 0.5) * width
        bars = ax.bar(x + offset, vals, width, label=f"{cond} (n={int(df.loc[cond, 'N'])})")

    ax.set_xticks(x)
    ax.set_xticklabels(corr_cols)
    ax.set_ylabel("Pearson Correlation")
    ax.set_title(f"Conditional Correlation: BTC Up vs Down vs Extreme - {tf.upper()}", fontsize=13)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.2, axis="y")
    ax.set_ylim(0, 1)
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / f"06_conditional_correlation_{tf}.png", dpi=150)
    plt.close(fig)
    print(f"  Saved: 06_conditional_correlation_{tf}.png")

    return df


def main():
    for tf in ["4h", "1d"]:
        print(f"\n=== Correlation Analysis: {tf.upper()} ===")
        returns = load(tf)
        plot_rolling_correlation(returns, tf)
        conditional_correlation(returns, tf)

    print(f"\nPhase 4 complete.")


if __name__ == "__main__":
    main()
