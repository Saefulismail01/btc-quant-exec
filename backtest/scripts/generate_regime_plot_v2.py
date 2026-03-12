import sys
import os
import traceback
import duckdb
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(r'c:\Users\ThinkPad\Documents\Windsurf\btc-scalping-quant-fix')
sys.path.append(str(PROJECT_ROOT / 'backend'))

try:
    from engines.layer1_bcd import BayesianChangepointModel

    print('Memuat data dari database...')
    db_path = str(PROJECT_ROOT / 'backend' / 'btc-quant.db')
    with duckdb.connect(db_path, read_only=True) as con:
        df = con.execute('SELECT timestamp, open, high, low, close, volume FROM btc_ohlcv_4h ORDER BY timestamp').fetchdf()
    
    print(f'Data termuat: {len(df)} candle.')

    # Preprocessing to match BayesianChangepointModel expectations
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('datetime', inplace=True)
    
    # Rename columns to Capitalized for the engine
    df = df.rename(columns={
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close',
        'volume': 'Volume'
    })
    
    # Start from available 2022 data for training
    df_train = df[df.index >= '2022-11-18']
    
    print(f'Data untuk training: {len(df_train)} candle. Melatih model BCD (BOCPD)...')

    model = BayesianChangepointModel()
    success = model.train_global(df_train)
    
    if not success:
        print("Model training failed!")
        sys.exit(1)
        
    # Get state sequence
    states_arr, valid_idx = model.get_state_sequence_raw(df_train)
    
    if states_arr is None:
        print("Could not get state sequence!")
        sys.exit(1)
        
    # Create the full data for mapping
    df_full = df_train.loc[valid_idx].copy()
    df_full['regime'] = [model.state_map.get(sid, "Unknown") for sid in states_arr]

    # FILTER FOR PLOT: Last 7 Days (Micro-level analysis)
    last_date = df_full.index.max()
    start_7d = last_date - pd.Timedelta(days=7)
    df_plot = df_full[df_full.index >= start_7d].copy()
    print(f'Sisa data untuk diplot (Last 7 Days): {len(df_plot)} candle.')
    print(f'Range: {start_7d} s/d {last_date}')

    print("Menghasilkan grafik (BCD 7-Day Ultra Zoom)...")
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(18, 9))

    # Market Regime Coloring Map
    color_map = {
        "Bullish Trend": "green",
        "Bearish Trend": "red",
        "High Volatility Sideways": "orange",
        "Low Volatility Sideways": "yellow",
        "Unknown": "gray"
    }

    # Plot BTC Close Price as Points colored by Regime
    for label, color in color_map.items():
        mask = df_plot['regime'] == label
        if mask.any():
            ax.scatter(df_plot.index[mask], df_plot.loc[mask, 'Close'], 
                       color=color, s=80, alpha=1.0, label=label, marker='o', edgecolors='white', linewidth=0.5)

    # Line connecting points - slightly more visible for 7-day view
    ax.plot(df_plot.index, df_plot['Close'], color='white', linewidth=1.5, alpha=0.3, zorder=0)

    # Labels and Title
    ax.set_title(f'BTC Market Regime Detection (Last 7 Days)\nBayesian Online Changepoint Detection (BCD)', fontsize=18, pad=25, color='white', fontweight='bold')
    ax.set_ylabel('BTC/USDT Price (Log Scale)', fontsize=14)
    ax.set_xlabel('Timeline', fontsize=14)
    ax.set_yscale('log')
    ax.grid(True, which='both', linestyle='--', alpha=0.2)

    # Custom Legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='green', alpha=0.5, label='Bullish Trend'),
        Patch(facecolor='red', alpha=0.5, label='Bearish Trend'),
        Patch(facecolor='orange', alpha=0.5, label='High Vol Sideways'),
        Patch(facecolor='yellow', alpha=0.5, label='Low Vol Sideways'),
    ]
    ax.legend(handles=legend_elements, loc='upper left', fontsize=12)

    # Stats Annotation
    regime_counts = df_plot['regime'].value_counts(normalize=True) * 100
    stats_text = "Market Composition:\n"
    for r, p in regime_counts.items():
        stats_text += f"• {r}: {p:.1f}%\n"
    
    plt.text(0.02, 0.05, stats_text, transform=ax.transAxes, fontsize=10, 
             verticalalignment='bottom', bbox=dict(boxstyle='round', facecolor='black', alpha=0.5))

    # Save
    out_dir = PROJECT_ROOT / 'docs' / 'reports'
    os.makedirs(out_dir, exist_ok=True)
    out_file = out_dir / 'regime_plot_original_2022_2026.png'
    
    plt.tight_layout()
    plt.savefig(out_file, dpi=300)
    plt.close()
    
    print(f'Grafik SUKSES tersimpan di: {out_file}')

except Exception as e:
    print("Ada error!")
    traceback.print_exc()
