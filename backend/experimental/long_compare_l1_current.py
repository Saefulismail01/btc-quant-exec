import os
import sys
import time
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.config import settings
from app.core.engines.experimental.layer1_hmm import MarketRegimeModel
from app.core.engines.layer1_bcd import BayesianChangepointModel


def _load_comparison_data(limit: int = 8000) -> pd.DataFrame:
    query = """
        SELECT
            o.timestamp,
            o.open,
            o.high,
            o.low,
            o.close,
            o.volume,
            o.cvd,
            m.open_interest,
            m.liquidations_buy,
            m.liquidations_sell
        FROM btc_ohlcv_4h o
        ASOF LEFT JOIN market_metrics m ON o.timestamp >= m.timestamp
        ORDER BY o.timestamp DESC
        LIMIT ?
    """
    with duckdb.connect(settings.db_path, read_only=True) as con:
        df = con.execute(query, [limit]).fetchdf()

    if df.empty:
        return df

    # Keep chronological order and names expected by the engines.
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.set_index("datetime")
    df = df.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
    )

    for col in ["cvd", "open_interest", "liquidations_buy", "liquidations_sell"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = df[col].fillna(0.0)

    return df


def _count_switches(labels: pd.Series) -> int:
    switches = (labels != labels.shift(1)).sum() - 1
    return int(max(switches, 0))


def run_long_comparison(limit: int = 8000) -> None:
    print("\n" + "=" * 72)
    print(" BTC-QUANT: LONG TIMEFRAME LAYER-1 COMPARISON (CURRENT MODELS)")
    print("=" * 72 + "\n")

    print("1. Loading historical data from DuckDB...")
    df = _load_comparison_data(limit=limit)
    if df is None or len(df) < 500:
        print(" [!] Insufficient data for comparison. Need at least 500 rows.")
        return

    print(f"    Loaded {len(df)} candles")
    print(f"    Timeframe: {df.index[0]} to {df.index[-1]}")

    print("\n2. Initializing engines...")
    hmm_model = MarketRegimeModel()
    bcd_model = BayesianChangepointModel()

    print("\n3. Training engines (global mode)...")
    t0 = time.time()
    hmm_ok = hmm_model.train_global(df)
    hmm_t = time.time() - t0

    t0 = time.time()
    bcd_ok = bcd_model.train_global(df)
    bcd_t = time.time() - t0

    print(f"    HMM train: {'SUCCESS' if hmm_ok else 'FAILED'} ({hmm_t:.2f}s)")
    print(f"    BCD train: {'SUCCESS' if bcd_ok else 'FAILED'} ({bcd_t:.2f}s)")
    if not hmm_ok or not bcd_ok:
        print(" [!] One or more engines failed to train.")
        return

    print("\n4. Running inference...")
    hmm_states, hmm_idx = hmm_model.get_state_sequence_raw(df)
    bcd_states, bcd_idx = bcd_model.get_state_sequence_raw(df)
    if hmm_states is None or bcd_states is None or hmm_idx is None or bcd_idx is None:
        print(" [!] Failed to extract state sequences.")
        return

    hmm_series = pd.Series(hmm_states, index=hmm_idx, name="hmm_raw_state")
    bcd_series = pd.Series(bcd_states, index=bcd_idx, name="bcd_raw_state")

    common_idx = hmm_series.index.intersection(bcd_series.index).intersection(df.index)
    if len(common_idx) < 200:
        print(" [!] Overlap between engines too small for reliable visualization.")
        return

    df_compare = df.loc[common_idx].copy()
    df_compare["hmm_raw_state"] = hmm_series.reindex(common_idx).values
    df_compare["bcd_raw_state"] = bcd_series.reindex(common_idx).values
    df_compare["hmm_label"] = df_compare["hmm_raw_state"].map(hmm_model.state_map).fillna("Unknown Regime")
    df_compare["bcd_label"] = df_compare["bcd_raw_state"].map(bcd_model.state_map).fillna("Unknown Regime")

    hmm_switches = _count_switches(df_compare["hmm_label"])
    bcd_switches = _count_switches(df_compare["bcd_label"])
    print("\n5. Stability summary:")
    print(f"    HMM switches: {hmm_switches}")
    print(f"    BCD switches: {bcd_switches}")
    print(f"    HMM avg persistence: {len(df_compare) / (hmm_switches + 1):.1f} candles")
    print(f"    BCD avg persistence: {len(df_compare) / (bcd_switches + 1):.1f} candles")

    print("\n6. Generating plot...")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(20, 12), sharex=True)

    color_map = {
        "Bullish Trend": "#18A558",
        "Bearish Trend": "#D7263D",
        "High Volatility Sideways": "#F49D37",
        "Low Volatility Sideways": "#2E86AB",
        "Unknown Regime": "#8A8A8A",
    }

    ax1.plot(df_compare.index, df_compare["Close"], color="black", alpha=0.18, linewidth=0.9)
    ax1.set_title("Layer 1 Current HMM (Experimental) - Long Timeframe")
    for label, color in color_map.items():
        mask = df_compare["hmm_label"] == label
        if mask.any():
            ax1.scatter(df_compare.index[mask], df_compare["Close"][mask], color=color, s=6, label=label)
    ax1.legend(loc="upper left")

    ax2.plot(df_compare.index, df_compare["Close"], color="black", alpha=0.18, linewidth=0.9)
    ax2.set_title("Layer 1 Current BCD (Production) - Long Timeframe")
    for label, color in color_map.items():
        mask = df_compare["bcd_label"] == label
        if mask.any():
            ax2.scatter(df_compare.index[mask], df_compare["Close"][mask], color=color, s=6, label=label)
    ax2.legend(loc="upper left")

    plt.tight_layout()

    paper_fig_dir = _BACKEND_DIR.parent / "paper" / "figures"
    os.makedirs(paper_fig_dir, exist_ok=True)
    out_current = paper_fig_dir / "long_compare_viz_current.png"
    out_default = paper_fig_dir / "long_compare_viz.png"
    fig.savefig(out_current, dpi=170)
    fig.savefig(out_default, dpi=170)
    plt.close(fig)

    print(f"    [OK] Saved: {out_current}")
    print(f"    [OK] Updated: {out_default}")


if __name__ == "__main__":
    run_long_comparison()
