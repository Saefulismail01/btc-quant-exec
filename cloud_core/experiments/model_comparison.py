"""
Model Comparison Framework - Compare different L3 models
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Callable
import json
from datetime import datetime

from engines.layer1_bcd import BayesianChangepointModel
from engines.layer2_ema import EMASignalModel
from engines.layer3_mlp import MLPSignalModel
from engines.layer3_xgboost import XGBoostSignalModel
from engines.spectrum import DirectionalSpectrum
from data.fetcher import DataFetcher


class ModelComparator:
    """
    Compare different Layer 3 models on same dataset.
    """
    
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.results = {}
        
        # Shared layers
        self.l1 = BayesianChangepointModel()
        self.l2 = EMASignalModel()
        self.spectrum = DirectionalSpectrum()
        
        # Models to compare
        self.models = {
            "mlp": MLPSignalModel(),
            "xgboost": XGBoostSignalModel(),
        }
    
    def evaluate_model(self, model_name: str) -> Dict:
        """
        Evaluate a single L3 model.
        
        Returns metrics:
        - Prediction accuracy
        - Directional accuracy
        - Confidence calibration
        - Signal distribution
        """
        if model_name not in self.models:
            raise ValueError(f"Unknown model: {model_name}")
        
        model = self.models[model_name]
        
        # Train model
        print(f"[Comparator] Training {model_name}...")
        model.train(self.df)
        
        # Fit L1
        self.l1.fit(self.df)
        
        # Walk-forward evaluation
        predictions = []
        actuals = []
        confidences = []
        biases = []
        
        # Use last 30% for testing
        test_start = int(len(self.df) * 0.7)
        
        for i in range(test_start, len(self.df) - 1):  # -1 because we need next candle
            current_df = self.df.iloc[:i+1]
            
            # Get votes
            l1_vote = self.l1.get_directional_vote(current_df)
            l2_vote = self.l2.get_directional_vote(current_df)
            l3_vote = model.get_directional_vote(current_df)
            
            # Calculate bias (without L4 for pure model evaluation)
            raw_score = l1_vote * 0.30 + l2_vote * 0.25 + l3_vote * 0.45
            
            # Get actual next candle direction
            current_price = self.df['Close'].iloc[i]
            next_price = self.df['Close'].iloc[i+1]
            actual_direction = 1 if next_price > current_price else -1
            
            # Record
            predictions.append(np.sign(raw_score))
            actuals.append(actual_direction)
            biases.append(raw_score)
            
            # Get confidence from model
            if hasattr(model, 'predict'):
                _, conf, _ = model.predict(current_df)
                confidences.append(conf)
        
        # Calculate metrics
        predictions = np.array(predictions)
        actuals = np.array(actuals)
        
        # Directional accuracy
        correct_directions = (predictions == actuals).sum()
        directional_accuracy = correct_directions / len(predictions) * 100
        
        # Signal distribution
        long_signals = (predictions > 0).sum()
        short_signals = (predictions < 0).sum()
        
        # Average bias (how aggressive is the model)
        avg_bias = np.mean(np.abs(biases))
        
        return {
            "model": model_name,
            "directional_accuracy": round(directional_accuracy, 2),
            "avg_bias_magnitude": round(avg_bias, 4),
            "total_predictions": len(predictions),
            "long_signals": int(long_signals),
            "short_signals": int(short_signals),
            "neutral_signals": int(len(predictions) - long_signals - short_signals),
        }
    
    def compare_all(self) -> pd.DataFrame:
        """Compare all models and return DataFrame."""
        results = []
        
        for model_name in self.models.keys():
            print(f"\n{'='*50}")
            print(f"Evaluating: {model_name.upper()}")
            print(f"{'='*50}")
            
            metrics = self.evaluate_model(model_name)
            results.append(metrics)
            
            print(f"Directional Accuracy: {metrics['directional_accuracy']}%")
            print(f"Avg Bias Magnitude: {metrics['avg_bias_magnitude']}")
            print(f"Signal Distribution: {metrics['long_signals']} Long / {metrics['short_signals']} Short")
        
        return pd.DataFrame(results)
    
    def save_report(self, output_path: str = "model_comparison_report.json"):
        """Save comparison report."""
        df = self.compare_all()
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "data_points": len(self.df),
            "models": df.to_dict('records')
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n[Comparator] Report saved to {output_path}")
        return df


def run_model_comparison():
    """Run model comparison with live data."""
    print("[Model Comparison] Fetching data...")
    fetcher = DataFetcher()
    df = fetcher.fetch_ohlcv("BTC/USDT", "4h", limit=500)
    
    if df is None:
        print("Failed to fetch data")
        return
    
    comparator = ModelComparator(df)
    df_results = comparator.save_report()
    
    print("\n" + "="*60)
    print("MODEL COMPARISON SUMMARY")
    print("="*60)
    print(df_results.to_string(index=False))
    print("="*60)


if __name__ == "__main__":
    run_model_comparison()
