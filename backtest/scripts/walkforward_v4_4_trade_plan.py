"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  WALKFORWARD v4.4 TRADE PLAN                                                 ║
║  Integrasi Golden Model v4.4 dengan Walkforward Validation                   ║
║                                                                              ║
║  Periode: 2020-2026                                                          ║
║  Trade Plan: v4.4 (6-layer entry, SL 1.333%, TP 0.71%, max 6 candles)        ║
║  Walkforward: Train=500, Test=100, Step=50                                     ║
║                                                                              ║
║  Models:                                                                     ║
║    1. Baseline v4.4 (8 fitur)                                                ║
║    2. Causal v4.4 (5 fitur validated)                                        ║
║    3. CatBoost Causal (5 fitur)                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import time
import logging
import argparse
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict

import numpy as np
import pandas as pd
import pandas_ta as ta
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

# Add paths
_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "cloud_core"))
sys.path.insert(0, str(_PROJECT_ROOT / "cloud_core" / "experiments"))

from cloud_core.experiments.models import CatBoostSignalModel
from cloud_core.experiments.feature_engineering import compute_bcd_regimes

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

# Trade Plan v4.4 Constants
POSITION_USD = 1_000.0          # Fixed position size per trade
LEVERAGE = 15.0                 # Fixed 15x leverage
NOTIONAL = POSITION_USD * LEVERAGE  # $15,000
FEE_RATE = 0.0004               # 0.04% taker fee per leg
FEE_USD = NOTIONAL * FEE_RATE * 2   # $12 per round-trip
SL_PCT = 0.01333                # 1.333% SL dari entry
TP_MIN_PCT = 0.0071             # 0.71% TP target dari entry
MAX_HOLD_CANDLES = 6            # Safety net: 6 candles = 24 jam

# Walkforward Config
TRAIN_SIZE = 500
TEST_SIZE = 100
STEP_SIZE = 50
MAX_WINDOWS = 50

# Causal Features (from ablation study)
CAUSAL_FEATURES = [
    'rsi_14',
    'macd_hist',
    'ema20_dist',
    'log_return',
    'norm_atr'
]

# All Features (baseline)
ALL_FEATURES = [
    'rsi_14',
    'macd_hist',
    'ema20_dist',
    'log_return',
    'norm_atr',
    'norm_cvd',
    'funding',
    'oi_change'
]

# ══════════════════════════════════════════════════════════════════════════════
#  SETUP LOGGING
# ══════════════════════════════════════════════════════════════════════════════

_RESULTS_DIR = _PROJECT_ROOT / "backtest" / "results" / "walkforward_v4_4"
_LOGS_DIR = _PROJECT_ROOT / "backtest" / "logs" / "walkforward_v4_4"
_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
_LOGS_DIR.mkdir(parents=True, exist_ok=True)

_LOG_FILE = _LOGS_DIR / f"walkforward_v4_4_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("walkforward_v4_4")


# ══════════════════════════════════════════════════════════════════════════════
#  DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Trade:
    """Represents a single trade"""
    entry_time: str
    exit_time: str
    side: str
    entry_price: float
    exit_price: float
    sl: float
    tp: float
    exit_type: str
    pnl: float
    holding_candles: int
    window_id: int


@dataclass
class WindowResult:
    """Results from a single walkforward window"""
    window_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    n_trades: int
    win_rate: float
    profit_factor: float
    total_pnl: float
    avg_trade: float
    max_drawdown: float
    n_sl: int
    n_tp: int
    n_time_exit: int
    test_accuracy: float


# ══════════════════════════════════════════════════════════════════════════════
#  DATA LOADING
# ══════════════════════════════════════════════════════════════════════════════

def load_historical_data(data_path: str) -> pd.DataFrame:
    """Load historical OHLCV data."""
    log.info(f"Loading data from {data_path}")
    df = pd.read_csv(data_path)
    
    # Rename columns to uppercase
    column_mapping = {
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close',
        'volume': 'Volume',
        'datetime': 'datetime',
        'timestamp': 'timestamp'
    }
    df = df.rename(columns=column_mapping)
    
    # Set datetime as index
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.set_index('datetime')
    elif 'timestamp' in df.columns:
        try:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        except (ValueError, TypeError):
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')
    
    # Ensure timezone-naive
    if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    
    # Sort by index
    df = df.sort_index()
    
    log.info(f"Loaded {len(df)} candles | {df.index[0]} → {df.index[-1]}")
    return df


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add technical indicators to dataframe."""
    df = df.copy()
    
    # EMAs
    df["EMA20"] = ta.ema(df["Close"], length=20)
    df["EMA50"] = ta.ema(df["Close"], length=50)
    
    # RSI
    df["rsi_14"] = ta.rsi(df["Close"], length=14)
    
    # MACD
    macd = ta.macd(df["Close"], fast=12, slow=26, signal=9)
    df["macd_hist"] = macd["MACDh_12_26_9"] if macd is not None else 0
    
    # ATR
    df["ATR14"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)
    df["norm_atr"] = df["ATR14"] / df["Close"]
    
    # Log returns
    df["log_return"] = np.log(df["Close"] / df["Close"].shift(1))
    
    # EMA distance
    df["ema20_dist"] = (df["Close"] - df["EMA20"]) / df["EMA20"]
    
    # Normalized features for order flow (if available)
    if 'cvd' in df.columns:
        df["norm_cvd"] = df["cvd"] / df["Close"]
    else:
        df["norm_cvd"] = 0.0
        
    if 'funding_rate' in df.columns:
        df["funding"] = df["funding_rate"]
    else:
        df["funding"] = 0.0
        
    if 'open_interest' in df.columns:
        df["oi_change"] = df["open_interest"].pct_change().fillna(0)
    else:
        df["oi_change"] = 0.0
    
    return df


# ══════════════════════════════════════════════════════════════════════════════
#  TRADE EXECUTION LOGIC (v4.4 Style)
# ══════════════════════════════════════════════════════════════════════════════

def check_sl_tp(
    side: str,
    sl: float,
    tp: float,
    c_high: float,
    c_low: float,
    c_close: float
) -> Tuple[Optional[float], Optional[str]]:
    """
    Cek apakah SL atau TP kena di candle ini.
    Return (exit_price, exit_type) atau (None, None) jika tidak ada hit.
    Priority: SL > TP
    """
    if side == "LONG":
        if c_low <= sl:
            return sl, "SL"
        if c_high >= tp:
            return (c_close, "TRAIL_TP") if c_close >= tp else (tp, "TP")
    else:  # SHORT
        if c_high >= sl:
            return sl, "SL"
        if c_low <= tp:
            return (c_close, "TRAIL_TP") if c_close <= tp else (tp, "TP")
    return None, None


def calc_pnl(side: str, entry: float, exit_price: float) -> float:
    """
    PnL = Notional × price_return − fee
    """
    if side == "LONG":
        price_return = (exit_price - entry) / entry
    else:
        price_return = (entry - exit_price) / entry
    return round(NOTIONAL * price_return - FEE_USD, 2)


def execute_trade(
    side: str,
    entry_price: float,
    entry_idx: int,
    df_window: pd.DataFrame,
    window_id: int
) -> Trade:
    """
    Execute a trade and manage exit according to v4.4 rules.
    """
    # Set SL/TP
    if side == "LONG":
        sl = entry_price * (1.0 - SL_PCT)
        tp = entry_price * (1.0 + TP_MIN_PCT)
    else:
        sl = entry_price * (1.0 + SL_PCT)
        tp = entry_price * (1.0 - TP_MIN_PCT)
    
    entry_time = df_window.index[entry_idx].isoformat()
    
    # Simulate holding
    for holding in range(1, MAX_HOLD_CANDLES + 1):
        current_idx = entry_idx + holding
        if current_idx >= len(df_window):
            # Out of data - exit at last close
            exit_price = float(df_window["Close"].iloc[-1])
            return Trade(
                entry_time=entry_time,
                exit_time=df_window.index[-1].isoformat(),
                side=side,
                entry_price=entry_price,
                exit_price=exit_price,
                sl=sl,
                tp=tp,
                exit_type="TIME_EXIT",
                pnl=calc_pnl(side, entry_price, exit_price),
                holding_candles=holding,
                window_id=window_id
            )
        
        # Get next candle
        next_candle = df_window.iloc[current_idx]
        c_high = float(next_candle["High"])
        c_low = float(next_candle["Low"])
        c_close = float(next_candle["Close"])
        
        # Check SL/TP
        exit_price, exit_type = check_sl_tp(side, sl, tp, c_high, c_low, c_close)
        
        if exit_price is not None:
            return Trade(
                entry_time=entry_time,
                exit_time=df_window.index[current_idx].isoformat(),
                side=side,
                entry_price=entry_price,
                exit_price=exit_price,
                sl=sl,
                tp=tp,
                exit_type=exit_type,
                pnl=calc_pnl(side, entry_price, exit_price),
                holding_candles=holding,
                window_id=window_id
            )
        
        # Check max hold
        if holding >= MAX_HOLD_CANDLES:
            exit_price = c_close
            return Trade(
                entry_time=entry_time,
                exit_time=df_window.index[current_idx].isoformat(),
                side=side,
                entry_price=entry_price,
                exit_price=exit_price,
                sl=sl,
                tp=tp,
                exit_type="TIME_EXIT",
                pnl=calc_pnl(side, entry_price, exit_price),
                holding_candles=holding,
                window_id=window_id
            )
    
    # Fallback - should not reach here
    exit_price = float(df_window["Close"].iloc[min(entry_idx + MAX_HOLD_CANDLES, len(df_window) - 1)])
    return Trade(
        entry_time=entry_time,
        exit_time=df_window.index[min(entry_idx + MAX_HOLD_CANDLES, len(df_window) - 1)].isoformat(),
        side=side,
        entry_price=entry_price,
        exit_price=exit_price,
        sl=sl,
        tp=tp,
        exit_type="TIME_EXIT",
        pnl=calc_pnl(side, entry_price, exit_price),
        holding_candles=MAX_HOLD_CANDLES,
        window_id=window_id
    )


# ══════════════════════════════════════════════════════════════════════════════
#  MODEL SIGNAL GENERATION
# ══════════════════════════════════════════════════════════════════════════════

def generate_signals_catboost(
    model: CatBoostSignalModel,
    df: pd.DataFrame,
    feature_list: List[str]
) -> List[Tuple[int, str, float]]:
    """
    Generate signals using CatBoost model.
    Returns list of (index, bias, confidence)
    """
    signals = []
    
    for i in range(len(df)):
        # Prepare features up to current point
        df_hist = df.iloc[:i+1].copy()
        
        try:
            bias, confidence, _ = model.predict(df_hist)
            signals.append((i, bias, confidence))
        except Exception as e:
            log.warning(f"Prediction failed at index {i}: {e}")
            signals.append((i, "NEUTRAL", 50.0))
    
    return signals


def generate_signals_rule_based(
    df: pd.DataFrame,
    use_causal_only: bool = True
) -> List[Tuple[int, str, float]]:
    """
    Generate signals using rule-based approach (v4.4 style).
    Simple EMA + RSI strategy for baseline comparison.
    """
    signals = []
    features = CAUSAL_FEATURES if use_causal_only else ALL_FEATURES
    
    for i in range(len(df)):
        if i < 50:  # Need history
            signals.append((i, "NEUTRAL", 50.0))
            continue
        
        row = df.iloc[i]
        
        # Simple scoring
        score = 0
        
        # RSI signal
        if 'rsi_14' in features and 'rsi_14' in row:
            rsi = row['rsi_14']
            if rsi < 30:
                score += 2  # Oversold - bullish
            elif rsi > 70:
                score -= 2  # Overbought - bearish
        
        # MACD signal
        if 'macd_hist' in features and 'macd_hist' in row:
            macd = row['macd_hist']
            if macd > 0:
                score += 1
            else:
                score -= 1
        
        # EMA trend
        if 'ema20_dist' in features and 'ema20_dist' in row:
            ema_dist = row['ema20_dist']
            if ema_dist > 0:
                score += 1
            else:
                score -= 1
        
        # Convert score to signal
        if score >= 2:
            signals.append((i, "BULL", 70.0))
        elif score <= -2:
            signals.append((i, "BEAR", 70.0))
        else:
            signals.append((i, "NEUTRAL", 50.0))
    
    return signals


# ══════════════════════════════════════════════════════════════════════════════
#  WALKFORWARD ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def run_walkforward_window(
    df: pd.DataFrame,
    train_start: int,
    train_end: int,
    test_start: int,
    test_end: int,
    window_id: int,
    model_type: str = "rule_causal",
    feature_list: List[str] = None
) -> WindowResult:
    """
    Run a single walkforward window.
    """
    log.info(f"\n--- Window {window_id} ---")
    log.info(f"Train: {df.index[train_start].date()} → {df.index[train_end-1].date()}")
    log.info(f"Test: {df.index[test_start].date()} → {df.index[test_end-1].date()}")
    
    # Split data
    train_df = df.iloc[train_start:train_end].copy()
    test_df = df.iloc[test_start:test_end].copy()
    
    # Generate signals
    if model_type == "catboost":
        # Train CatBoost model
        model = CatBoostSignalModel(
            depth=6,
            learning_rate=0.05,
            iterations=500
        )
        
        log.info("Training CatBoost...")
        train_success = model.train(train_df)
        
        if not train_success:
            log.warning("CatBoost training failed, skipping window")
            return None
        
        log.info("Generating signals...")
        signals = generate_signals_catboost(model, test_df, feature_list or CAUSAL_FEATURES)
    elif model_type == "rule_causal":
        signals = generate_signals_rule_based(test_df, use_causal_only=True)
    elif model_type == "rule_all":
        signals = generate_signals_rule_based(test_df, use_causal_only=False)
    else:
        log.error(f"Unknown model type: {model_type}")
        return None
    
    # Execute trades
    trades = []
    in_position = False
    entry_idx = None
    
    for idx, bias, confidence in signals:
        if in_position:
            # Check if we should exit on this candle
            continue
        
        # Entry logic
        if bias == "BULL" and confidence >= 60:
            trade = execute_trade("LONG", float(test_df["Close"].iloc[idx]), idx, test_df, window_id)
            trades.append(trade)
        elif bias == "BEAR" and confidence >= 60:
            trade = execute_trade("SHORT", float(test_df["Close"].iloc[idx]), idx, test_df, window_id)
            trades.append(trade)
    
    # Calculate metrics
    if not trades:
        log.warning("No trades in window")
        return WindowResult(
            window_id=window_id,
            train_start=df.index[train_start].isoformat(),
            train_end=df.index[train_end-1].isoformat(),
            test_start=df.index[test_start].isoformat(),
            test_end=df.index[test_end-1].isoformat(),
            n_trades=0,
            win_rate=0.0,
            profit_factor=0.0,
            total_pnl=0.0,
            avg_trade=0.0,
            max_drawdown=0.0,
            n_sl=0,
            n_tp=0,
            n_time_exit=0,
            test_accuracy=0.0
        )
    
    # Calculate metrics
    n_trades = len(trades)
    winning_trades = [t for t in trades if t.pnl > 0]
    losing_trades = [t for t in trades if t.pnl <= 0]
    
    win_rate = len(winning_trades) / n_trades * 100 if n_trades > 0 else 0
    
    gross_profit = sum(t.pnl for t in winning_trades)
    gross_loss = abs(sum(t.pnl for t in losing_trades))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    total_pnl = sum(t.pnl for t in trades)
    avg_trade = total_pnl / n_trades if n_trades > 0 else 0
    
    # Exit type counts
    n_sl = sum(1 for t in trades if t.exit_type == "SL")
    n_tp = sum(1 for t in trades if t.exit_type in ["TP", "TRAIL_TP"])
    n_time_exit = sum(1 for t in trades if t.exit_type == "TIME_EXIT")
    
    # Calculate accuracy based on correct directional prediction
    # (BULL when price goes up, BEAR when price goes down)
    correct_predictions = 0
    total_predictions = 0
    
    for trade in trades:
        if trade.exit_price > trade.entry_price and trade.side == "LONG":
            correct_predictions += 1
        elif trade.exit_price < trade.entry_price and trade.side == "SHORT":
            correct_predictions += 1
        total_predictions += 1
    
    test_accuracy = correct_predictions / total_predictions * 100 if total_predictions > 0 else 0
    
    # Max drawdown (simplified)
    equity = 10000.0
    peak = equity
    max_dd = 0.0
    
    for trade in trades:
        equity += trade.pnl
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100
        if dd > max_dd:
            max_dd = dd
    
    result = WindowResult(
        window_id=window_id,
        train_start=df.index[train_start].isoformat(),
        train_end=df.index[train_end-1].isoformat(),
        test_start=df.index[test_start].isoformat(),
        test_end=df.index[test_end-1].isoformat(),
        n_trades=n_trades,
        win_rate=win_rate,
        profit_factor=profit_factor,
        total_pnl=total_pnl,
        avg_trade=avg_trade,
        max_drawdown=max_dd,
        n_sl=n_sl,
        n_tp=n_tp,
        n_time_exit=n_time_exit,
        test_accuracy=test_accuracy
    )
    
    log.info(f"Window {window_id} Results:")
    log.info(f"  Trades: {n_trades} | Win Rate: {win_rate:.1f}%")
    log.info(f"  Total PnL: ${total_pnl:,.2f} | Avg Trade: ${avg_trade:.2f}")
    log.info(f"  SL: {n_sl} | TP: {n_tp} | Time Exit: {n_time_exit}")
    
    return result


def run_full_walkforward(
    df: pd.DataFrame,
    model_type: str = "rule_causal",
    feature_list: List[str] = None
) -> Dict:
    """
    Run full walkforward validation across all windows.
    """
    log.info("\n" + "="*72)
    log.info(f"  WALKFORWARD v4.4 TRADE PLAN - {model_type.upper()}")
    log.info("="*72)
    log.info(f"  Period: {df.index[0].date()} → {df.index[-1].date()}")
    log.info(f"  Trade Plan: v4.4 (SL {SL_PCT*100:.2f}%, TP {TP_MIN_PCT*100:.2f}%, Max {MAX_HOLD_CANDLES} candles)")
    log.info(f"  Walkforward: Train={TRAIN_SIZE}, Test={TEST_SIZE}, Step={STEP_SIZE}")
    log.info(f"  Features: {feature_list or CAUSAL_FEATURES}")
    log.info("="*72)
    
    # Generate windows
    windows = []
    start_idx = TRAIN_SIZE
    
    while start_idx + TRAIN_SIZE + TEST_SIZE <= len(df):
        end_train = start_idx + TRAIN_SIZE
        end_test = end_train + TEST_SIZE
        
        windows.append({
            'train_start': start_idx,
            'train_end': end_train,
            'test_start': end_train,
            'test_end': end_test
        })
        
        start_idx += STEP_SIZE
    
    log.info(f"Generated {len(windows)} walkforward windows")
    windows = windows[:MAX_WINDOWS]
    log.info(f"Processing first {len(windows)} windows")
    
    # Run each window
    results = []
    all_trades = []
    
    for i, window in enumerate(windows):
        result = run_walkforward_window(
            df=df,
            train_start=window['train_start'],
            train_end=window['train_end'],
            test_start=window['test_start'],
            test_end=window['test_end'],
            window_id=i+1,
            model_type=model_type,
            feature_list=feature_list
        )
        
        if result:
            results.append(result)
    
    # Aggregate results
    if not results:
        log.error("No valid results from any window")
        return {}
    
    total_trades = sum(r.n_trades for r in results)
    total_pnl = sum(r.total_pnl for r in results)
    avg_win_rate = sum(r.win_rate for r in results) / len(results)
    avg_profit_factor = sum(r.profit_factor for r in results) / len(results) if any(r.profit_factor != 0 for r in results) else 0
    avg_accuracy = sum(r.test_accuracy for r in results) / len(results)
    
    log.info("\n" + "="*72)
    log.info("  WALKFORWARD SUMMARY")
    log.info("="*72)
    log.info(f"  Windows Completed: {len(results)}")
    log.info(f"  Total Trades: {total_trades}")
    log.info(f"  Total PnL: ${total_pnl:,.2f}")
    log.info(f"  Avg Win Rate: {avg_win_rate:.1f}%")
    log.info(f"  Avg Profit Factor: {avg_profit_factor:.2f}")
    log.info(f"  Avg Test Accuracy: {avg_accuracy:.1f}%")
    log.info("="*72)
    
    return {
        'model_type': model_type,
        'windows': len(results),
        'total_trades': total_trades,
        'total_pnl': total_pnl,
        'avg_win_rate': avg_win_rate,
        'avg_profit_factor': avg_profit_factor,
        'avg_accuracy': avg_accuracy,
        'window_results': [vars(r) for r in results]
    }


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='Walkforward v4.4 Trade Plan')
    parser.add_argument('--data', type=str, 
                        default='backtest/data/BTC_USDT_5m_2020_2026_with_real_orderflow.csv',
                        help='Path to historical data CSV')
    parser.add_argument('--model', type=str, default='rule_causal',
                        choices=['rule_causal', 'rule_all', 'catboost'],
                        help='Model type to use')
    parser.add_argument('--output', type=str, default=None,
                        help='Output JSON file path')
    
    args = parser.parse_args()
    
    # Load data
    df = load_historical_data(args.data)
    
    # Add indicators
    df = add_technical_indicators(df)
    
    # Filter to 2020-2026
    df = df[df.index >= '2020-01-01']
    df = df[df.index <= '2026-03-04']
    
    # Select feature list based on model
    if args.model == 'rule_causal':
        feature_list = CAUSAL_FEATURES
    elif args.model == 'rule_all':
        feature_list = ALL_FEATURES
    else:
        feature_list = CAUSAL_FEATURES
    
    # Run walkforward
    results = run_full_walkforward(df, model_type=args.model, feature_list=feature_list)
    
    # Save results
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = _RESULTS_DIR / f"walkforward_{args.model}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    log.info(f"\nResults saved to: {output_path}")
    
    return results


if __name__ == "__main__":
    main()
