abaikan dulu push """
Test dengan CSV Lokal
===================
Contoh lengkap untuk load CSV dan generate signal
"""
import pandas as pd
import numpy as np
from datetime import datetime

# 1. LOAD CSV
print("=" * 60)
print("LOADING CSV")
print("=" * 60)

# Ganti nama file sesuai dataset Anda
df = pd.read_csv("btc_usdt_4h.csv", index_col=0, parse_dates=True)

print(f"Loaded {len(df)} rows")
print(f"Date range: {df.index[0]} to {df.index[-1]}")
print(f"Columns: {list(df.columns)}")
print()

# 2. PREPARE DATA (rename columns if needed)
# Pastikan column names sesuai: Open, High, Low, Close, Volume
df.columns = [col.capitalize() if col.lower() in ['open', 'high', 'low', 'close', 'volume'] else col for col in df.columns]

# 3. IMPORT LAYERS (copy dari colab_core.ipynb atau import dari file)
# Jika file .py sudah ada:
# from engines.layer1_bcd import BayesianChangepointModel
# from engines.layer2_ema import EMASignalModel
# from engines.layer3_mlp import MLPSignalModel
# from engines.layer4_risk import RiskModel
# from engines.spectrum import DirectionalSpectrum

# 4. INITIALIZE MODELS
print("=" * 60)
print("INITIALIZING MODELS")
print("=" * 60)

# Import classes (copy dari colab_core.ipynb)
exec(open("engines/layer1_bcd.py").read())
exec(open("engines/layer2_ema.py").read())
exec(open("engines/layer3_mlp.py").read())
exec(open("engines/layer4_risk.py").read())
exec(open("engines/spectrum.py").read())

l1 = BayesianChangepointModel()
l2 = EMASignalModel()
l3 = MLPSignalModel()
l4 = RiskModel()
spectrum = DirectionalSpectrum()

print("Models initialized")
print()

# 5. TRAIN MODEL
print("=" * 60)
print("TRAINING MLP MODEL")
print("=" * 60)

# Use subset untuk training cepat (misal: 500 baris terakhir)
train_df = df.tail(500)
success = l3.train(train_df)

if success:
    print("Training successful!")
else:
    print("Training failed - using untrained model")
print()

# 6. GENERATE SIGNAL untuk data terakhir
print("=" * 60)
print("GENERATING SIGNAL")
print("=" * 60)

# Fit BCD
l1.fit(train_df)

# Get votes
l1_vote = l1.get_directional_vote(train_df)
l2_vote = l2.get_directional_vote(train_df)
l3_vote = l3.get_directional_vote(train_df)
l4_mult = l4.get_multiplier(train_df)

# Calculate spectrum
result = spectrum.calculate(l1_vote, l2_vote, l3_vote, l4_mult)
risk_params = l4.get_risk_params(train_df)

# Display results
price = train_df['Close'].iloc[-1]

print(f"\nTimestamp: {datetime.now()}")
print(f"Price: ${price:,.2f}")
print(f"\nLayer Votes:")
print(f"  L1 (BCD):  {l1_vote:+.3f} [30%]")
print(f"  L2 (EMA):  {l2_vote:+.3f} [25%]")
print(f"  L3 (MLP):  {l3_vote:+.3f} [45%] ← GATEKEEPER")
print(f"  L4 (Risk): {l4_mult:.3f} [multiplier]")
print(f"\nSpectrum:")
print(f"  Directional Bias: {result.directional_bias:+.3f}")
print(f"  Action: {result.action}")
print(f"  Conviction: {result.conviction_pct:.1f}%")
print(f"  Trade Gate: {result.trade_gate}")
print(f"  Position Size: {result.position_size_pct:.2f}%")
print(f"\nRisk Params:")
print(f"  SL: {risk_params['sl_pct']}%")
print(f"  TP: {risk_params['tp_pct']}%")
print(f"  Leverage: {risk_params['leverage']}x")

# Gate status
if result.trade_gate == 'ACTIVE':
    print(f"\n✅ SIGNAL IS ACTIVE - Can Enter Trade")
elif result.trade_gate == 'ADVISORY':
    print(f"\n⚠️  ADVISORY - Reduce Size")
else:
    print(f"\n❌ SUSPENDED - Do Not Trade")

# 7. BACKTEST SINGKAT (opsional)
print("\n" + "=" * 60)
print("QUICK BACKTEST (Last 100 candles)")
print("=" * 60)

test_df = df.tail(100)
signals = []

for i in range(50, len(test_df)):
    current = test_df.iloc[:i+1]
    
    if i % 12 == 0:
        l1.fit(current)
    
    l1_vote = l1.get_directional_vote(current)
    l2_vote = l2.get_directional_vote(current)
    l3_vote = l3.get_directional_vote(current) if l3._is_trained else 0
    
    result = spectrum.calculate(l1_vote, l2_vote, l3_vote, 1.0)
    
    signals.append({
        'timestamp': current.index[-1],
        'price': current['Close'].iloc[-1],
        'bias': result.directional_bias,
        'action': result.action,
        'gate': result.trade_gate
    })

results_df = pd.DataFrame(signals)

active_count = len(results_df[results_df['gate'] == 'ACTIVE'])
print(f"\nActive signals: {active_count} / {len(results_df)} ({active_count/len(results_df)*100:.1f}%)")
print(f"Avg bias: {results_df['bias'].mean():+.4f}")
print(f"Long signals: {len(results_df[results_df['action'] == 'LONG'])}")
print(f"Short signals: {len(results_df[results_df['action'] == 'SHORT'])}")

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)
