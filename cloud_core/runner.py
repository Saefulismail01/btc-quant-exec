"""
Cloud Core Runner - Main entry point for testing
"""
"""
Cloud Core Research Runner
CLI for experimenting with core signal generation engine
"""
import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env
load_dotenv()

from signal_service import SignalService
from experiments import (
    run_model_comparison,
    analyze_features,
    run_tuning,
)


def test_signal(ai_model: str = "mlp"):
    """Test signal generation."""
    print(f"\n{'='*60}")
    print(f"SIGNAL GENERATION TEST ({ai_model.upper()})")
    print(f"{'='*60}\n")
    
    service = SignalService(ai_model=ai_model)
    signal = service.generate_signal(symbol="BTC/USDT", timeframe="4h")
    
    if signal:
        print(f"\nGenerated Signal:")
        print(f"  Symbol: {signal.symbol}")
        print(f"  Price: ${signal.price:,.2f}")
        print(f"  Timestamp: {signal.timestamp}")
        print(f"\nLayer Votes:")
        print(f"  L1 (BCD): {signal.l1_vote:+.3f} [Weight: 30%]")
        print(f"  L2 (EMA): {signal.l2_vote:+.3f} [Weight: 25%]")
        print(f"  L3 (AI):  {signal.l3_vote:+.3f} [Weight: 45%] ← GATEKEEPER")
        print(f"  L4 (Risk): {signal.l4_mult:.3f} [Multiplier]")
        print(f"\nSpectrum Output:")
        print(f"  Directional Bias: {signal.directional_bias:+.3f}")
        print(f"  Action: {signal.action}")
        print(f"  Conviction: {signal.conviction_pct:.1f}%")
        print(f"  Trade Gate: {signal.trade_gate}")
        print(f"  Position Size: {signal.position_size_pct:.2f}%")
        print(f"\nRisk Parameters:")
        print(f"  SL: {signal.sl_pct:.2f}%")
        print(f"  TP: {signal.tp_pct:.2f}%")
        print(f"  Leverage: {signal.leverage}x")
        print(f"\nModel Used: {signal.model_used}")
        
        if signal.trade_gate == "ACTIVE":
            print(f"\n✅ SIGNAL IS ACTIVE - Can Enter Trade")
        elif signal.trade_gate == "ADVISORY":
            print(f"\n⚠️  ADVISORY - Reduce Size, Wait for Confirmation")
        else:
            print(f"\n❌ SUSPENDED - Do Not Trade")
    else:
        print("❌ Failed to generate signal")
    
    return signal


def run_backtest(ai_model: str = "mlp"):
    """Run walk-forward backtest."""
    print(f"\n{'='*60}")
    print(f"WALK-FORWARD BACKTEST ({ai_model.upper()})")
    print(f"{'='*60}\n")
    
    from data.fetcher import DataFetcher
    
    fetcher = DataFetcher()
    df = fetcher.fetch_ohlcv(symbol="BTC/USDT", timeframe="4h", limit=1000)
    
    if df is None:
        print("❌ Failed to fetch data")
        return
    
    service = SignalService(ai_model=ai_model)
    results = service.run_backtest(df, verbose=True)
    
    # Analyze results
    print(f"\n{'='*60}")
    print("BACKTEST ANALYSIS")
    print(f"{'='*60}\n")
    
    total_signals = len(results)
    active_signals = len(results[results["gate"] == "ACTIVE"])
    advisory_signals = len(results[results["gate"] == "ADVISORY"])
    suspended_signals = len(results[results["gate"] == "SUSPENDED"])
    
    long_signals = len(results[results["action"] == "LONG"])
    short_signals = len(results[results["action"] == "SHORT"])
    
    print(f"Total Signals Generated: {total_signals}")
    print(f"\nGate Distribution:")
    print(f"  🟢 ACTIVE:    {active_signals:3d} ({active_signals/total_signals*100:5.1f}%) - Can trade")
    print(f"  🟡 ADVISORY:  {advisory_signals:3d} ({advisory_signals/total_signals*100:5.1f}%) - Caution")
    print(f"  🔴 SUSPENDED: {suspended_signals:3d} ({suspended_signals/total_signals*100:5.1f}%) - No trade")
    print(f"\nDirection Distribution:")
    print(f"  📈 LONG:  {long_signals:3d} ({long_signals/total_signals*100:5.1f}%)")
    print(f"  📉 SHORT: {short_signals:3d} ({short_signals/total_signals*100:5.1f}%)")
    
    print(f"\nSignal Quality Metrics:")
    print(f"  Mean Bias:     {results['bias'].mean():+.4f}")
    print(f"  Bias StdDev:   {results['bias'].std():.4f}")
    print(f"  Max Bullish:   {results['bias'].max():+.4f}")
    print(f"  Max Bearish:   {results['bias'].min():+.4f}")
    print(f"  Mean Conviction: {results['conviction'].mean():.2f}%")
    print(f"  Max Conviction:  {results['conviction'].max():.2f}%")


def compare_models():
    """Run comprehensive model comparison."""
    print(f"\n{'='*60}")
    print("MODEL COMPARISON: MLP vs XGBoost")
    print(f"{'='*60}\n")
    
    print("This will compare both models on same dataset.")
    print("Metrics: Directional accuracy, bias magnitude, signal distribution\n")
    
    run_model_comparison()


def analyze_feature_importance():
    """Analyze feature importance for L3 models."""
    print(f"\n{'='*60}")
    print("FEATURE IMPORTANCE ANALYSIS")
    print(f"{'='*60}\n")
    
    print("Analyzing which features correlate most with future returns...\n")
    
    analyze_features()


def tune_hyperparameters():
    """Run hyperparameter tuning."""
    print(f"\n{'='*60}")
    print("HYPERPARAMETER TUNING")
    print(f"{'='*60}\n")
    
    print("Finding optimal hyperparameters for L3 models...\n")
    
    run_tuning()


def main():
    parser = argparse.ArgumentParser(
        description="Cloud Core Research Runner - Experiment with signal generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python runner.py signal --model mlp        Generate signal with MLP
  python runner.py backtest --model xgboost  Run backtest with XGBoost
  python runner.py compare                    Compare MLP vs XGBoost
  python runner.py features                 Analyze feature importance
  python runner.py tune                       Tune hyperparameters
        """
    )
    
    parser.add_argument(
        "command",
        choices=["signal", "backtest", "compare", "features", "tune"],
        help="Command to run"
    )
    parser.add_argument(
        "--model",
        choices=["mlp", "xgboost"],
        default="mlp",
        help="AI model for L3 (default: mlp)"
    )
    
    args = parser.parse_args()
    
    if args.command == "signal":
        test_signal(ai_model=args.model)
    elif args.command == "backtest":
        run_backtest(ai_model=args.model)
    elif args.command == "compare":
        compare_models()
    elif args.command == "features":
        analyze_feature_importance()
    elif args.command == "tune":
        tune_hyperparameters()


if __name__ == "__main__":
    main()
    print("\n" + "="*60)
    print("Research complete. Check generated reports for details.")
    print("="*60)
