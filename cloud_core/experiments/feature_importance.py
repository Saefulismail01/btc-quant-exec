"""
Feature Importance Analysis for Layer 3 Models
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List
import json


class FeatureAnalyzer:
    """
    Analyze which features are most important for prediction.
    """
    
    # All possible features to test
    ALL_FEATURES = [
        "rsi_14",
        "macd_hist", 
        "ema20_dist",
        "log_return",
        "norm_atr",
        "norm_cvd",
        "funding",
        "oi_change",
        "volatility_20",
        "price_momentum",
        "volume_change",
        "bb_position",  # Bollinger Bands position
        "stoch_k",     # Stochastic
    ]
    
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.results = {}
    
    def calculate_feature_correlation(self) -> pd.DataFrame:
        """
        Calculate correlation between features and future returns.
        """
        df = self.df.copy()
        
        # Calculate future return (target)
        df['future_return'] = df['Close'].shift(-1) / df['Close'] - 1
        
        # Calculate features
        import pandas_ta as ta
        
        df['rsi_14'] = ta.rsi(df['Close'], length=14)
        
        macd = ta.macd(df['Close'])
        df['macd_hist'] = macd['MACDh_12_26_9'] if macd is not None else 0
        
        ema20 = ta.ema(df['Close'], length=20)
        df['ema20_dist'] = (df['Close'] - ema20) / ema20
        
        df['log_return'] = np.log(df['Close'] / df['Close'].shift(1))
        
        atr = ta.atr(df['High'], df['Low'], df['Close'], length=14)
        df['norm_atr'] = atr / df['Close']
        
        df['volatility_20'] = df['log_return'].rolling(20).std()
        df['price_momentum'] = df['Close'].pct_change(5)
        df['volume_change'] = df['Volume'].pct_change()
        
        bb = ta.bbands(df['Close'])
        if bb is not None:
            df['bb_position'] = (df['Close'] - bb['BBL_20_2.0']) / (bb['BBU_20_2.0'] - bb['BBL_20_2.0'])
        else:
            df['bb_position'] = 0.5
        
        stoch = ta.stoch(df['High'], df['Low'], df['Close'])
        df['stoch_k'] = stoch['STOCHk_14_3_3'] if stoch is not None else 50
        
        # Calculate correlations
        correlations = {}
        
        for feature in self.ALL_FEATURES:
            if feature in df.columns:
                corr = df[feature].corr(df['future_return'])
                correlations[feature] = corr
        
        # Create DataFrame
        corr_df = pd.DataFrame([
            {"feature": k, "correlation": v, "abs_correlation": abs(v)}
            for k, v in correlations.items()
        ])
        
        return corr_df.sort_values("abs_correlation", ascending=False)
    
    def feature_ablation_study(self, model_class, base_features: List[str]) -> Dict:
        """
        Remove one feature at a time and measure performance drop.
        
        Args:
            model_class: Model class to test
            base_features: Base feature set
        
        Returns:
            Dict with importance score for each feature
        """
        from sklearn.model_selection import train_test_split
        
        results = {}
        
        # Train with all features (baseline)
        print("[Ablation] Training baseline model with all features...")
        model_full = model_class()
        # Assuming model has .train() that accepts features list
        baseline_score = self._evaluate_model(model_full, base_features)
        
        print(f"[Ablation] Baseline score: {baseline_score:.4f}")
        
        # Remove one feature at a time
        for feature in base_features:
            reduced_features = [f for f in base_features if f != feature]
            
            print(f"[Ablation] Training without {feature}...")
            model_reduced = model_class()
            reduced_score = self._evaluate_model(model_reduced, reduced_features)
            
            # Importance = performance drop
            importance = baseline_score - reduced_score
            results[feature] = {
                "baseline": baseline_score,
                "without_feature": reduced_score,
                "importance": importance,
            }
        
        return results
    
    def _evaluate_model(self, model, features: List[str]) -> float:
        """Helper to evaluate model with given features."""
        # This is a placeholder - actual implementation would train and evaluate
        # Return accuracy or other metric
        return 0.55  # Placeholder
    
    def plot_feature_importance(self, correlations: pd.DataFrame, save_path: str = "feature_importance.png"):
        """Plot feature importance."""
        plt.figure(figsize=(10, 6))
        
        plt.barh(correlations['feature'], correlations['abs_correlation'])
        plt.xlabel('Absolute Correlation with Future Return')
        plt.title('Feature Importance (Correlation Analysis)')
        plt.tight_layout()
        plt.savefig(save_path)
        print(f"[Analyzer] Plot saved to {save_path}")


def analyze_features():
    """Run feature analysis."""
    from data.fetcher import DataFetcher
    
    print("[Feature Analysis] Fetching data...")
    fetcher = DataFetcher()
    df = fetcher.fetch_ohlcv("BTC/USDT", "4h", limit=500)
    
    if df is None:
        print("Failed to fetch data")
        return
    
    analyzer = FeatureAnalyzer(df)
    
    print("\n[Feature Analysis] Calculating correlations...")
    correlations = analyzer.calculate_feature_correlation()
    
    print("\nTop Features by Correlation:")
    print(correlations.head(10).to_string(index=False))
    
    # Save report
    report = {
        "timestamp": datetime.now().isoformat(),
        "feature_correlations": correlations.to_dict('records')
    }
    
    with open("feature_analysis_report.json", 'w') as f:
        json.dump(report, f, indent=2)
    
    print("\n[Feature Analysis] Report saved to feature_analysis_report.json")


if __name__ == "__main__":
    from datetime import datetime
    analyze_features()
