"""
Quick Evaluator - Test only working models
==========================================
"""
import pandas as pd
import numpy as np
from engines.layer3_mlp import MLPSignalModel
from engines.layer3_xgboost import XGBoostSignalModel
from engines.layer3_lightgbm import LightGBMSignalModel
from engines.layer3_rules import RuleBasedSignalModel
from engines.layer3_logistic import LogisticSignalModel
from engines.layer1_bcd import BayesianChangepointModel
from engines.layer2_ema import EMASignalModel
from engines.layer4_risk import RiskModel
from engines.spectrum import DirectionalSpectrum
from data.fetcher import DataFetcher

print("=" * 70)
print("QUICK MODEL EVALUATION - Working Models Only")
print("=" * 70)

# Load data
print("\nFetching data...")
df = DataFetcher().fetch_ohlcv('BTC/USDT', '4h', limit=800)
df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
print(f"Loaded {len(df)} candles from {df.index[0]} to {df.index[-1]}")

# Initialize models
models = {
    'lightgbm': LightGBMSignalModel(),
    'xgboost': XGBoostSignalModel(),
    'rule_based': RuleBasedSignalModel(),
    'logistic': LogisticSignalModel(),
    'mlp': MLPSignalModel(),
}

# Shared layers
l1 = BayesianChangepointModel()
l2 = EMASignalModel()
spectrum = DirectionalSpectrum()

# Train all models
print("\nTraining models...")
for name, model in models.items():
    print(f"  Training {name}...", end=" ")
    success = model.train(df)
    print("OK" if success else "FAILED")

l1.fit(df)

# Test on last 200 candles
test_size = 200
test_start = len(df) - test_size

print(f"\nTesting on last {test_size} candles...")
print("=" * 70)

results = {}

for name, model in models.items():
    print(f"\n{name.upper()}:")
    print("-" * 40)
    
    predictions = []
    actuals = []
    confidences = []
    
    for i in range(test_start, len(df) - 1):
        current_df = df.iloc[:i+1]
        
        l1_vote = l1.get_directional_vote(current_df)
        l2_vote = l2.get_directional_vote(current_df)
        l3_vote = model.get_directional_vote(current_df)
        
        raw_score = l1_vote * 0.30 + l2_vote * 0.25 + l3_vote * 0.45
        directional_bias = raw_score
        
        # Actual direction (3 candles ahead)
        if i + 3 < len(df):
            current_price = df['Close'].iloc[i]
            future_price = df['Close'].iloc[i + 3]
            actual_direction = 1 if future_price > current_price else -1
            
            predictions.append(np.sign(directional_bias))
            actuals.append(actual_direction)
    
    if len(predictions) > 0:
        predictions = np.array(predictions)
        actuals = np.array(actuals)
        
        # Calculate accuracy
        correct = np.sum(predictions == actuals)
        accuracy = correct / len(predictions) * 100
        
        # Long/Short breakdown
        long_mask = predictions > 0
        short_mask = predictions < 0
        
        long_correct = np.sum((predictions == actuals) & long_mask) if np.any(long_mask) else 0
        long_total = np.sum(long_mask)
        long_acc = long_correct / long_total * 100 if long_total > 0 else 0
        
        short_correct = np.sum((predictions == actuals) & short_mask) if np.any(short_mask) else 0
        short_total = np.sum(short_mask)
        short_acc = short_correct / short_total * 100 if short_total > 0 else 0
        
        # Signal frequency
        signal_count = np.sum(predictions != 0)
        signal_freq = signal_count / len(predictions) * 100
        
        results[name] = {
            'accuracy': accuracy,
            'long_acc': long_acc,
            'short_acc': short_acc,
            'signal_freq': signal_freq,
            'total_signals': signal_count
        }
        
        print(f"  Overall Accuracy: {accuracy:.1f}%")
        print(f"  Long Accuracy:    {long_acc:.1f}% ({long_correct}/{long_total})")
        print(f"  Short Accuracy:   {short_acc:.1f}% ({short_correct}/{short_total})")
        print(f"  Signal Frequency: {signal_freq:.1f}% ({signal_count} signals)")
    else:
        print("  No predictions made")

# Final ranking
print("\n" + "=" * 70)
print("FINAL RANKING")
print("=" * 70)

# Sort by accuracy
sorted_models = sorted(results.items(), key=lambda x: x[1]['accuracy'], reverse=True)

for rank, (name, metrics) in enumerate(sorted_models, 1):
    print(f"\n#{rank}: {name.upper()}")
    print(f"  Accuracy: {metrics['accuracy']:.1f}%")
    print(f"  Long: {metrics['long_acc']:.1f}% | Short: {metrics['short_acc']:.1f}%")
    print(f"  Signals: {metrics['total_signals']} ({metrics['signal_freq']:.1f}%)")

if sorted_models:
    winner = sorted_models[0][0]
    print(f"\n🏆 RECOMMENDED: {winner.upper()}")
    print("=" * 70)
