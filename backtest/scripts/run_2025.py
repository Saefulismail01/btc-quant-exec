import sys
import traceback
from pathlib import Path

# Try importing the engine
try:
    from engine import BacktestEngine
except ImportError:
    # If run from root directory
    sys.path.insert(0, str(Path(__file__).parent))
    from engine import BacktestEngine

def run_backtest_2025():
    year = 2025
    print(f"\n🚀 Initializing Backtest for {year} (YTD)...")
    
    # Check if data exists
    data_path = Path(__file__).parent / "data" / f"BTC_USDT_4h_{year}.csv"
    if not data_path.exists():
        print(f"❌ Data file not found: {data_path}")
        print(f"Please run 'python backtest/fetch_data.py' first.")
        return
        
    try:
        # Initialize engine with $1000 starting capital
        engine = BacktestEngine(year=year, initial_capital=1000.0)
        
        # Run simulation
        engine.run()
        
        print(f"\n✅ Backtest {year} completed successfully.")
        print(f"📄 Detailed logs saved to: backtest/logs/backtest_{year}.log")
        
    except Exception as e:
        print(f"\n❌ An error occurred during backtesting:")
        traceback.print_exc()

if __name__ == "__main__":
    import time
    start = time.time()
    
    run_backtest_2025()
    
    elapsed = time.time() - start
    print(f"⏱️ Total execution time: {elapsed:.2f} seconds")
