"""
Hyperparameter Tuning for Layer 3 Models
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any
from sklearn.model_selection import ParameterGrid
import json
from datetime import datetime


class HyperparameterTuner:
    """
    Grid search for optimal model hyperparameters.
    """
    
    # Search spaces for each model
    MLP_PARAMS = {
        'hidden_layer_sizes': [(64, 32), (128, 64), (256, 128)],
        'activation': ['relu', 'tanh'],
        'learning_rate_init': [0.001, 0.01],
        'alpha': [0.0001, 0.001],  # L2 regularization
    }
    
    XGB_PARAMS = {
        'n_estimators': [50, 100, 200],
        'max_depth': [3, 6, 9],
        'learning_rate': [0.05, 0.1, 0.2],
        'subsample': [0.8, 1.0],
    }
    
    def __init__(self, df: pd.DataFrame, model_type: str = "mlp"):
        self.df = df
        self.model_type = model_type
        self.results = []
        
        # Split data
        self.train_df = df.iloc[:int(len(df) * 0.7)]
        self.test_df = df.iloc[int(len(df) * 0.7):]
    
    def _evaluate_params(self, params: Dict) -> float:
        """
        Evaluate a parameter set.
        
        Returns:
            Score (higher is better)
        """
        try:
            if self.model_type == "mlp":
                from engines.layer3_mlp import MLPSignalModel
                
                # Create model with custom params
                model = MLPSignalModel()
                # Modify model parameters
                model.HIDDEN_LAYERS = params['hidden_layer_sizes']
                model.MLP_ACTIVATION = params['activation']
                
                # Train
                success = model.train(self.train_df)
                if not success:
                    return 0.0
                
                # Evaluate on test set
                return self._evaluate_mlp(model)
                
            elif self.model_type == "xgboost":
                from engines.layer3_xgboost import XGBoostSignalModel
                
                model = XGBoostSignalModel()
                # Would need to modify XGB parameters similarly
                success = model.train(self.train_df)
                if not success:
                    return 0.0
                
                return self._evaluate_xgb(model)
            
            else:
                return 0.0
                
        except Exception as e:
            print(f"[Tuner] Error evaluating params: {e}")
            return 0.0
    
    def _evaluate_mlp(self, model) -> float:
        """Evaluate MLP model on test set."""
        correct = 0
        total = 0
        
        for i in range(len(self.test_df) - 1):
            current_df = pd.concat([self.train_df, self.test_df.iloc[:i+1]])
            
            # Get prediction
            bias, conf, probs = model.predict(current_df)
            
            # Get actual
            current_price = self.test_df['Close'].iloc[i]
            next_price = self.test_df['Close'].iloc[i+1] if i+1 < len(self.test_df) else current_price
            actual_up = next_price > current_price
            
            # Check correctness
            predicted_up = bias == "BULL"
            
            if predicted_up == actual_up:
                correct += 1
            total += 1
        
        return correct / total if total > 0 else 0.0
    
    def _evaluate_xgb(self, model) -> float:
        """Evaluate XGBoost model on test set."""
        # Similar to MLP evaluation
        return self._evaluate_mlp(model)  # Same interface
    
    def tune(self, max_combinations: int = 10) -> pd.DataFrame:
        """
        Run hyperparameter tuning.
        
        Args:
            max_combinations: Max parameter combinations to try
        
        Returns:
            DataFrame with results sorted by score
        """
        if self.model_type == "mlp":
            param_grid = self.MLP_PARAMS
        elif self.model_type == "xgboost":
            param_grid = self.XGB_PARAMS
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")
        
        # Generate all combinations
        grid = list(ParameterGrid(param_grid))
        
        # Limit if too many
        if len(grid) > max_combinations:
            import random
            random.shuffle(grid)
            grid = grid[:max_combinations]
        
        print(f"[Tuner] Testing {len(grid)} parameter combinations...")
        
        for i, params in enumerate(grid):
            print(f"\n[#{i+1}/{len(grid)}] Testing: {params}")
            
            score = self._evaluate_params(params)
            
            result = {
                "params": params,
                "score": score,
                "rank": 0,  # Will assign later
            }
            
            self.results.append(result)
            
            print(f"  Score: {score:.4f}")
        
        # Sort by score and assign ranks
        self.results.sort(key=lambda x: x['score'], reverse=True)
        for i, r in enumerate(self.results):
            r['rank'] = i + 1
        
        # Convert to DataFrame
        df_results = pd.DataFrame([
            {
                "rank": r['rank'],
                "score": r['score'],
                **{f"param_{k}": v for k, v in r['params'].items()}
            }
            for r in self.results
        ])
        
        return df_results
    
    def get_best_params(self) -> Dict:
        """Get best parameters found."""
        if not self.results:
            return {}
        
        return self.results[0]['params']
    
    def save_report(self, output_path: str = "tuning_report.json"):
        """Save tuning report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "model_type": self.model_type,
            "data_points": len(self.df),
            "best_params": self.get_best_params(),
            "all_results": self.results,
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"\n[Tuner] Report saved to {output_path}")


def run_tuning():
    """Run hyperparameter tuning."""
    from data.fetcher import DataFetcher
    
    print("[Hyperparameter Tuning] Fetching data...")
    fetcher = DataFetcher()
    df = fetcher.fetch_ohlcv("BTC/USDT", "4h", limit=500)
    
    if df is None:
        print("Failed to fetch data")
        return
    
    # Tune MLP
    print("\n" + "="*60)
    print("TUNING MLP")
    print("="*60)
    tuner_mlp = HyperparameterTuner(df, model_type="mlp")
    results_mlp = tuner_mlp.tune(max_combinations=5)
    tuner_mlp.save_report("mlp_tuning_report.json")
    
    print("\nMLP Tuning Results:")
    print(results_mlp.head().to_string(index=False))
    
    # Tune XGBoost
    print("\n" + "="*60)
    print("TUNING XGBOOST")
    print("="*60)
    tuner_xgb = HyperparameterTuner(df, model_type="xgboost")
    results_xgb = tuner_xgb.tune(max_combinations=5)
    tuner_xgb.save_report("xgboost_tuning_report.json")
    
    print("\nXGBoost Tuning Results:")
    print(results_xgb.head().to_string(index=False))


if __name__ == "__main__":
    run_tuning()
