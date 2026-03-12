import sys
import os
import traceback
import duckdb
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

sys.path.append(r'c:\Users\ThinkPad\Documents\Windsurf\btc-scalping-quant-fix\backend')

try:
    from engines.layer1_hmm import RegimeModel

    print('Memuat data...')
    with duckdb.connect(r'c:\Users\ThinkPad\Documents\Windsurf\btc-scalping-quant-fix\backend\btc-quant.db', read_only=True) as con:
        df = con.execute('SELECT timestamp, open, high, low, close, volume FROM btc_ohlcv_4h ORDER BY timestamp').fetchdf()
    
    print(f'Data termuat: {len(df)} candle.')

    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('datetime', inplace=True)
    df = df[df.index >= '2022-11-18']  # Start from the earliest available data in 2022
    
    print(f'Sisa data untuk diplot: {len(df)} candle. Melatih model BCD/HMM...')

    model = RegimeModel()
    df = model.fit_predict(df)

    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(15, 7))

    ax.plot(df.index, df['close'], color='white', linewidth=1.5, alpha=0.9, label='BTC Close Price')

    colors = {'bull': 'green', 'bear': 'red', 'neutral': 'yellow'}
    current_regime = df['regime'].iloc[0]
    start_idx = df.index[0]

    for idx, row in df.iterrows():
        if row['regime'] != current_regime:
            ax.axvspan(start_idx, idx, facecolor=colors.get(current_regime, 'gray'), alpha=0.3)
            start_idx = idx
            current_regime = row['regime']
    ax.axvspan(start_idx, df.index[-1], facecolor=colors.get(current_regime, 'gray'), alpha=0.3)

    ax.set_title('Deteksi Fase Pasar BCD (Nov 2022 - Mar 2026)', fontsize=16, pad=20, color='white')
    ax.set_ylabel('Harga BTC', fontsize=12)
    ax.set_yscale('log')

    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='green', alpha=0.5, label='Bull'),
        Patch(facecolor='red', alpha=0.5, label='Bear'),
        Patch(facecolor='yellow', alpha=0.5, label='Neutral')
    ]
    ax.legend(handles=legend_elements, loc='upper left', fontsize=11)

    out_dir = r'c:\Users\ThinkPad\Documents\Windsurf\btc-scalping-quant-fix\docs\reports'
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, 'regime_plot_2022_2026.png')
    
    plt.tight_layout()
    plt.savefig(out_file, dpi=300)
    print(f'Grafik SUKSES tersimpan di: {out_file}')

except Exception as e:
    print("Ada error!")
    traceback.print_exc()
