"""
Cloud Core Runner - Main entry point for testing
"""
import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env
load_dotenv()

from signal_service import SignalService
from execution.paper_executor import PaperExecutor


def test_signal(ai_model: str = "mlp"):
    """Test signal generation."""
    print(f"\n{'='*60}")
    print(f"TESTING SIGNAL GENERATION ({ai_model.upper()})")
    print(f"{'='*60}\n")
    
    service = SignalService(ai_model=ai_model)
    signal = service.generate_signal(symbol="BTC/USDT", timeframe="4h")
    
    if signal:
        print(f"\nGenerated Signal:")
        print(f"  Symbol: {signal.symbol}")
        print(f"  Price: ${signal.price:,.2f}")
        print(f"  Timestamp: {signal.timestamp}")
        print(f"\nLayer Votes:")
        print(f"  L1 (BCD): {signal.l1_vote:+.3f}")
        print(f"  L2 (EMA): {signal.l2_vote:+.3f}")
        print(f"  L3 (AI):  {signal.l3_vote:+.3f}")
        print(f"  L4 (Risk): {signal.l4_mult:.3f}")
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
        print(f"\nModel: {signal.model_used}")
    else:
        print("Failed to generate signal")
    
    return signal


def test_paper_trade():
    """Test paper trading."""
    print(f"\n{'='*60}")
    print("TESTING PAPER TRADING")
    print(f"{'='*60}\n")
    
    # Create executor
    executor = PaperExecutor(
        initial_balance=10000.0,
        save_path="./data/paper_state.json"
    )
    
    # Print initial stats
    executor.print_summary()
    
    # Generate signal
    service = SignalService(ai_model="mlp")
    signal = service.generate_signal()
    
    if signal and signal.trade_gate == "ACTIVE":
        print(f"\nSignal is ACTIVE - executing paper trade...")
        
        # Calculate SL/TP prices
        if signal.action == "LONG":
            sl_price = signal.price * (1 - signal.sl_pct / 100)
            tp_price = signal.price * (1 + signal.tp_pct / 100)
        else:
            sl_price = signal.price * (1 + signal.sl_pct / 100)
            tp_price = signal.price * (1 - signal.tp_pct / 100)
        
        # Open position
        position = executor.open_position(
            symbol=signal.symbol,
            side=signal.action,
            price=signal.price,
            size_usdt=100.0,  # Small size for test
            leverage=signal.leverage,
            sl_price=sl_price,
            tp_price=tp_price,
        )
        
        if position:
            print(f"\nPosition opened: {position.id}")
    else:
        print(f"\nSignal gate: {signal.trade_gate if signal else 'N/A'} - no trade")
    
    # Print final stats
    executor.print_summary()


def run_backtest(ai_model: str = "mlp"):
    """Run walk-forward backtest."""
    print(f"\n{'='*60}")
    print(f"RUNNING BACKTEST ({ai_model.upper()})")
    print(f"{'='*60}\n")
    
    # Fetch data
    from data.fetcher import DataFetcher
    
    fetcher = DataFetcher()
    df = fetcher.fetch_ohlcv(symbol="BTC/USDT", timeframe="4h", limit=1000)
    
    if df is None:
        print("Failed to fetch data")
        return
    
    # Run backtest
    service = SignalService(ai_model=ai_model)
    results = service.run_backtest(df, verbose=True)
    
    # Analyze results
    print(f"\n{'='*60}")
    print("BACKTEST RESULTS")
    print(f"{'='*60}\n")
    
    total_signals = len(results)
    active_signals = len(results[results["gate"] == "ACTIVE"])
    advisory_signals = len(results[results["gate"] == "ADVISORY"])
    suspended_signals = len(results[results["gate"] == "SUSPENDED"])
    
    print(f"Total Signals: {total_signals}")
    print(f"  ACTIVE: {active_signals} ({active_signals/total_signals*100:.1f}%)")
    print(f"  ADVISORY: {advisory_signals} ({advisory_signals/total_signals*100:.1f}%)")
    print(f"  SUSPENDED: {suspended_signals} ({suspended_signals/total_signals*100:.1f}%)")
    
    print(f"\nBias Statistics:")
    print(f"  Mean Bias: {results['bias'].mean():+.4f}")
    print(f"  Std Bias: {results['bias'].std():.4f}")
    print(f"  Max Bullish: {results['bias'].max():+.4f}")
    print(f"  Max Bearish: {results['bias'].min():+.4f}")
    
    print(f"\nConviction Statistics:")
    print(f"  Mean Conviction: {results['conviction'].mean():.2f}%")
    print(f"  Max Conviction: {results['conviction'].max():.2f}%")


def compare_models():
    """Compare MLP vs XGBoost."""
    print(f"\n{'='*60}")
    print("COMPARING MLP vs XGBOOST")
    print(f"{'='*60}\n")
    
    # Fetch data
    from data.fetcher import DataFetcher
    
    fetcher = DataFetcher()
    df = fetcher.fetch_ohlcv(symbol="BTC/USDT", timeframe="4h", limit=500)
    
    if df is None:
        print("Failed to fetch data")
        return
    
    # Test MLP
    print("Testing MLP...")
    service_mlp = SignalService(ai_model="mlp")
    results_mlp = service_mlp.run_backtest(df.copy())
    
    # Test XGBoost
    print("\nTesting XGBoost...")
    service_xgb = SignalService(ai_model="xgboost")
    results_xgb = service_xgb.run_backtest(df.copy())
    
    # Compare
    print(f"\n{'='*60}")
    print("COMPARISON RESULTS")
    print(f"{'='*60}\n")
    
    print(f"MLP:")
    print(f"  Mean Bias: {results_mlp['bias'].mean():+.4f}")
    print(f"  Mean Conviction: {results_mlp['conviction'].mean():.2f}%")
    print(f"  ACTIVE signals: {len(results_mlp[results_mlp['gate'] == 'ACTIVE'])}")
    
    print(f"\nXGBoost:")
    print(f"  Mean Bias: {results_xgb['bias'].mean():+.4f}")
    print(f"  Mean Conviction: {results_xgb['conviction'].mean():.2f}%")
    print(f"  ACTIVE signals: {len(results_xgb[results_xgb['gate'] == 'ACTIVE'])}")


def main():
    parser = argparse.ArgumentParser(description="Cloud Core Runner")
    parser.add_argument(
        "command",
        choices=["signal", "paper", "backtest", "compare"],
        help="Command to run"
    )
    parser.add_argument(
        "--model",
        choices=["mlp", "xgboost"],
        default="mlp",
        help="AI model to use (default: mlp)"
    )
    
    args = parser.parse_args()
    
    if args.command == "signal":
        test_signal(ai_model=args.model)
    elif args.command == "paper":
        test_paper_trade()
    elif args.command == "backtest":
        run_backtest(ai_model=args.model)
    elif args.command == "compare":
        compare_models()


if __name__ == "__main__":
    main()
