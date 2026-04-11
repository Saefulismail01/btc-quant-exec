"""
Model Evaluator - Find the Best Model
======================================
Comprehensive evaluation framework to determine which model performs best
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import json

# Import models (assumes engines folder exists)
try:
    from engines.layer1_bcd import BayesianChangepointModel
    from engines.layer2_ema import EMASignalModel
    from engines.layer3_mlp import MLPSignalModel
    from engines.layer3_xgboost import XGBoostSignalModel
    from engines.layer3_randomforest import RandomForestSignalModel
    from engines.layer3_lightgbm import LightGBMSignalModel
    from engines.layer3_lstm import LSTMSignalModel
    from engines.layer3_advanced import AdvancedSignalModel
    from engines.layer3_rules import RuleBasedSignalModel
    from engines.layer3_logistic import LogisticSignalModel
    from engines.layer4_risk import RiskModel
    from engines.spectrum import DirectionalSpectrum
except ImportError:
    print("[Evaluator] Note: Import from engines folder failed. Use exec() method instead.")


@dataclass
class ModelScore:
    """Complete scorecard for a model"""
    model_name: str
    
    # Directional Accuracy
    directional_accuracy: float  # % correct direction
    long_accuracy: float  # % correct when predicting long
    short_accuracy: float  # % correct when predicting short
    
    # Signal Quality
    signal_frequency: float  # % of time signal is ACTIVE
    avg_conviction: float  # average conviction %
    conviction_consistency: float  # std dev of conviction
    
    # Risk Metrics (simulated)
    simulated_sharpe: float  # risk-adjusted returns
    max_drawdown: float  # worst peak-to-trough
    win_rate: float  # % winning signals
    profit_factor: float  # gross profit / gross loss
    
    # Layer Contribution
    l1_contribution: float  # correlation with final bias
    l2_contribution: float
    l3_contribution: float
    
    # Overall Score
    total_score: float = 0.0
    rank: int = 0


class ModelEvaluator:
    """
    Evaluate and compare models to find the best one
    """
    
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.results = {}
        
        # Shared layers
        self.l1 = BayesianChangepointModel()
        self.l2 = EMASignalModel()
        self.l4 = RiskModel()
        self.spectrum = DirectionalSpectrum()
        
        # Models to evaluate
        self.models = {
            'mlp': MLPSignalModel(),
            'xgboost': XGBoostSignalModel(),
            'random_forest': RandomForestSignalModel(),
            'lightgbm': LightGBMSignalModel(),
            'lstm': LSTMSignalModel(),
            'advanced_gbm': AdvancedSignalModel(model_type='gbm'),
            'rule_based': RuleBasedSignalModel(),
            'logistic': LogisticSignalModel(),
            'ensemble_avg': None,  # Average of MLP and XGB
        }
    
    def _calculate_directional_accuracy(self, predictions: np.ndarray, actuals: np.ndarray) -> Tuple[float, float, float]:
        """Calculate overall, long, and short accuracy"""
        overall = np.mean(predictions == actuals) * 100
        
        long_mask = predictions > 0
        short_mask = predictions < 0
        
        long_acc = np.mean(predictions[long_mask] == actuals[long_mask]) * 100 if np.any(long_mask) else 0
        short_acc = np.mean(predictions[short_mask] == actuals[short_mask]) * 100 if np.any(short_mask) else 0
        
        return overall, long_acc, short_acc
    
    def _simulate_returns(self, df: pd.DataFrame, biases: np.ndarray, 
                         sl_pct: float = 1.5, tp_pct: float = 3.0) -> Dict:
        """
        Simulate trading returns based on signals
        Simplified: enter on signal, hold until next signal or SL/TP
        """
        returns = []
        in_trade = False
        entry_price = 0
        position_type = 0  # 1 for long, -1 for short
        
        for i in range(len(biases) - 1):
            current_price = df['Close'].iloc[i]
            next_price = df['Close'].iloc[i + 1]
            
            # Entry logic
            if not in_trade and abs(biases[i]) >= 0.2:  # ACTIVE signal
                in_trade = True
                entry_price = current_price
                position_type = 1 if biases[i] > 0 else -1
            
            # Exit logic
            if in_trade:
                price_change_pct = (next_price - entry_price) / entry_price * 100
                
                if position_type == 1:  # Long
                    pnl = price_change_pct
                    if pnl <= -sl_pct or pnl >= tp_pct or biases[i+1] * biases[i] < 0:
                        returns.append(pnl)
                        in_trade = False
                else:  # Short
                    pnl = -price_change_pct
                    if pnl <= -sl_pct or pnl >= tp_pct or biases[i+1] * biases[i] < 0:
                        returns.append(pnl)
                        in_trade = False
        
        returns = np.array(returns)
        
        if len(returns) == 0:
            return {
                'sharpe': 0,
                'max_dd': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'total_trades': 0
            }
        
        # Calculate metrics
        sharpe = np.mean(returns) / (np.std(returns) + 1e-6) * np.sqrt(252)  # Annualized
        cumulative = np.cumsum(returns)
        max_dd = np.max(np.maximum.accumulate(cumulative) - cumulative) if len(cumulative) > 0 else 0
        win_rate = np.mean(returns > 0) * 100
        
        gross_profit = np.sum(returns[returns > 0])
        gross_loss = abs(np.sum(returns[returns < 0]))
        profit_factor = gross_profit / (gross_loss + 1e-6)
        
        return {
            'sharpe': sharpe,
            'max_dd': max_dd,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_trades': len(returns)
        }
    
    def evaluate_model(self, model_name: str, verbose: bool = True) -> ModelScore:
        """Evaluate a single model comprehensively"""
        if verbose:
            print(f"\n{'='*60}")
            print(f"EVALUATING: {model_name.upper()}")
            print(f"{'='*60}")
        
        # Get model
        if model_name == 'ensemble_avg':
            model_mlp = self.models['mlp']
            model_xgb = self.models['xgboost']
        else:
            model = self.models[model_name]
        
        # Train
        if model_name == 'ensemble_avg':
            model_mlp.train(self.df)
            model_xgb.train(self.df)
            self.l1.fit(self.df)
        else:
            model.train(self.df)
            self.l1.fit(self.df)
        
        # Collect predictions
        test_start = int(len(self.df) * 0.7)
        predictions = []
        actuals = []
        convictions = []
        biases = []
        l1_votes = []
        l2_votes = []
        l3_votes = []
        
        for i in range(test_start, len(self.df) - 1):
            current_df = self.df.iloc[:i+1]
            
            l1_vote = self.l1.get_directional_vote(current_df)
            l2_vote = self.l2.get_directional_vote(current_df)
            
            if model_name == 'ensemble_avg':
                l3_vote_mlp = model_mlp.get_directional_vote(current_df)
                l3_vote_xgb = model_xgb.get_directional_vote(current_df)
                l3_vote = (l3_vote_mlp + l3_vote_xgb) / 2
            else:
                l3_vote = model.get_directional_vote(current_df)
            
            raw_score = l1_vote * 0.30 + l2_vote * 0.25 + l3_vote * 0.45
            l4_mult = self.l4.get_multiplier(current_df)
            directional_bias = raw_score * l4_mult
            
            # Actual direction
            current_price = self.df['Close'].iloc[i]
            next_price = self.df['Close'].iloc[i+1]
            actual_direction = 1 if next_price > current_price else -1
            
            predictions.append(np.sign(directional_bias))
            actuals.append(actual_direction)
            biases.append(directional_bias)
            l1_votes.append(l1_vote)
            l2_votes.append(l2_vote)
            l3_votes.append(l3_vote)
            
            # Conviction
            convictions.append(abs(directional_bias) * 100)
        
        predictions = np.array(predictions)
        actuals = np.array(actuals)
        biases = np.array(biases)
        convictions = np.array(convictions)
        
        # Calculate metrics
        dir_acc, long_acc, short_acc = self._calculate_directional_accuracy(predictions, actuals)
        
        # Signal frequency (ACTIVE signals)
        active_signals = np.sum(np.abs(biases) >= 0.2)
        signal_freq = active_signals / len(biases) * 100
        
        # Simulate returns
        sim_results = self._simulate_returns(self.df.iloc[test_start:], biases)
        
        # Layer contributions (correlation with final bias)
        l1_corr = abs(np.corrcoef(l1_votes, biases)[0,1]) if len(l1_votes) > 1 else 0
        l2_corr = abs(np.corrcoef(l2_votes, biases)[0,1]) if len(l2_votes) > 1 else 0
        l3_corr = abs(np.corrcoef(l3_votes, biases)[0,1]) if len(l3_votes) > 1 else 0
        
        score = ModelScore(
            model_name=model_name,
            directional_accuracy=dir_acc,
            long_accuracy=long_acc,
            short_accuracy=short_acc,
            signal_frequency=signal_freq,
            avg_conviction=np.mean(convictions),
            conviction_consistency=np.std(convictions),
            simulated_sharpe=sim_results['sharpe'],
            max_drawdown=sim_results['max_dd'],
            win_rate=sim_results['win_rate'],
            profit_factor=sim_results['profit_factor'],
            l1_contribution=l1_corr,
            l2_contribution=l2_corr,
            l3_contribution=l3_corr
        )
        
        if verbose:
            print(f"Directional Accuracy: {dir_acc:.2f}%")
            print(f"  Long: {long_acc:.2f}% | Short: {short_acc:.2f}%")
            print(f"Signal Frequency: {signal_freq:.1f}%")
            print(f"Avg Conviction: {np.mean(convictions):.1f}%")
            print(f"Simulated Sharpe: {sim_results['sharpe']:.2f}")
            print(f"Max Drawdown: {sim_results['max_dd']:.2f}%")
            print(f"Win Rate: {sim_results['win_rate']:.1f}%")
            print(f"Profit Factor: {sim_results['profit_factor']:.2f}")
            print(f"Total Trades: {sim_results['total_trades']}")
        
        return score
    
    def rank_models(self) -> List[ModelScore]:
        """Evaluate all models and rank them"""
        scores = []
        
        for model_name in self.models.keys():
            score = self.evaluate_model(model_name)
            scores.append(score)
        
        # Calculate total score (weighted average of key metrics)
        for score in scores:
            # Weights: accuracy 30%, sharpe 25%, win rate 20%, profit factor 15%, signal freq 10%
            score.total_score = (
                score.directional_accuracy * 0.30 +
                max(0, score.simulated_sharpe) * 10 * 0.25 +  # Scale sharpe
                score.win_rate * 0.20 +
                min(score.profit_factor, 5) * 5 * 0.15 +  # Cap profit factor at 5
                score.signal_frequency * 0.10
            )
        
        # Sort by total score
        scores.sort(key=lambda x: x.total_score, reverse=True)
        
        # Assign ranks
        for i, score in enumerate(scores):
            score.rank = i + 1
        
        return scores
    
    def generate_report(self, output_file: str = "model_evaluation_report.json"):
        """Generate comprehensive evaluation report"""
        scores = self.rank_models()
        
        # Print report
        print("\n" + "="*80)
        print("MODEL EVALUATION REPORT - FINAL RANKINGS")
        print("="*80)
        
        for score in scores:
            print(f"\n#{score.rank}: {score.model_name.upper()}")
            print(f"  Total Score: {score.total_score:.2f}")
            print(f"  Directional Accuracy: {score.directional_accuracy:.2f}%")
            print(f"  Simulated Sharpe: {score.simulated_sharpe:.2f}")
            print(f"  Win Rate: {score.win_rate:.1f}%")
            print(f"  Profit Factor: {score.profit_factor:.2f}")
            print(f"  Signal Frequency: {score.signal_frequency:.1f}%")
        
        # Winner
        winner = scores[0]
        print(f"\n{'='*80}")
        print(f"🏆 RECOMMENDED MODEL: {winner.model_name.upper()}")
        print(f"{'='*80}")
        
        # Save to JSON
        report = {
            'timestamp': datetime.now().isoformat(),
            'dataset_size': len(self.df),
            'winner': winner.model_name,
            'models': [
                {
                    'rank': s.rank,
                    'name': s.model_name,
                    'total_score': round(s.total_score, 2),
                    'directional_accuracy': round(s.directional_accuracy, 2),
                    'long_accuracy': round(s.long_accuracy, 2),
                    'short_accuracy': round(s.short_accuracy, 2),
                    'signal_frequency': round(s.signal_frequency, 2),
                    'avg_conviction': round(s.avg_conviction, 2),
                    'simulated_sharpe': round(s.simulated_sharpe, 2),
                    'max_drawdown': round(s.max_drawdown, 2),
                    'win_rate': round(s.win_rate, 2),
                    'profit_factor': round(s.profit_factor, 2),
                    'l3_contribution': round(s.l3_contribution, 3)
                }
                for s in scores
            ]
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Report saved to: {output_file}")
        
        return scores


def main():
    """Run model evaluation - auto fetch if CSV not found"""
    import os
    
    # Try to load CSV first
    csv_files = [f for f in os.listdir('.') if f.endswith('.csv') and 'btc' in f.lower()]
    
    if csv_files:
        csv_file = csv_files[0]  # Use first matching CSV
        print(f"Loading CSV: {csv_file}")
        df = pd.read_csv(csv_file, index_col=0, parse_dates=True)
        df.columns = [col.capitalize() if col.lower() in ['open', 'high', 'low', 'close', 'volume'] else col for col in df.columns]
        print(f"Loaded {len(df)} rows from {csv_file}")
    else:
        print("No CSV found. Fetching from Binance...")
        from data.fetcher import DataFetcher
        fetcher = DataFetcher()
        df = fetcher.fetch_ohlcv('BTC/USDT', '4h', limit=1000)
        if df is None:
            print("Failed to fetch data. Exiting.")
            return None
        df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    
    # Run evaluation
    print(f"\nDataset: {len(df)} candles from {df.index[0]} to {df.index[-1]}")
    evaluator = ModelEvaluator(df)
    scores = evaluator.generate_report()
    
    return scores


if __name__ == "__main__":
    main()
