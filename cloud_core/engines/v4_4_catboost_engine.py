"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  BTC-QUANT: v4.4 CATBOOST ENGINE                                             ║
║  Base: v4.4 Golden Model dengan L3 diganti CatBoost                        ║
║                                                                              ║
║  Status: HYBRID (6-Layer dengan CatBoost L3)                                 ║
║                                                                              ║
║  Karakteristik:                                                              ║
║    - L1: BCD Regime Detection                                                  ║
║    - L2: EMA Alignment                                                         ║
║    - L3: CatBoost AI (5 Causal Features)                                      ║
║    - L4: Volatility Multiplier                                                ║
║    - L5: Directional Spectrum                                                 ║
║    - L6: Trade Gate                                                           ║
║                                                                              ║
║  Trade Plan:                                                                 ║
║    - Position: Fixed $1,000 × 15x = $15,000 notional                        ║
║    - SL: 1.333% | TP: 0.71%                                                   ║
║    - Max Hold: 6 candles (24 jam)                                             ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

import numpy as np
import pandas as pd
import pandas_ta as ta

# Add paths
_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "backend"))

# Import CatBoost
from cloud_core.experiments.models import CatBoostSignalModel
from cloud_core.experiments.feature_engineering import compute_bcd_regimes

# ══════════════════════════════════════════════════════════════════════════════
#  TRADE PLAN CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

POSITION_USD = 1_000.0          # Fixed position size per trade
LEVERAGE = 15.0                 # Fixed 15x leverage
NOTIONAL = POSITION_USD * LEVERAGE  # $15,000

FEE_RATE = 0.0004               # 0.04% taker fee per leg
FEE_USD = NOTIONAL * FEE_RATE * 2   # $12 per round-trip

SL_PCT = 0.01333                # 1.333% SL dari entry
TP_MIN_PCT = 0.0071             # 0.71% TP target dari entry
MAX_HOLD_CANDLES = 6            # Safety net: 6 candles = 24 jam

# ══════════════════════════════════════════════════════════════════════════════
#  CAUSAL FEATURES (from ablation study)
# ══════════════════════════════════════════════════════════════════════════════

CAUSAL_FEATURES = [
    'rsi_14',
    'macd_hist',
    'ema20_dist',
    'log_return',
    'norm_atr',
    'bcd_regime'  # Categorical feature for regime context
]

# Categorical features for CatBoost
CATEGORICAL_FEATURES = ['bcd_regime']

# ══════════════════════════════════════════════════════════════════════════════
#  SETUP LOGGING
# ══════════════════════════════════════════════════════════════════════════════

_RESULTS_DIR = _PROJECT_ROOT / "backtest" / "results" / "v4_4_catboost"
_LOGS_DIR = _PROJECT_ROOT / "backtest" / "logs" / "v4_4_catboost"
_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
_LOGS_DIR.mkdir(parents=True, exist_ok=True)

_LOG_FILE = _LOGS_DIR / f"v4_4_catboost_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("v4_4_catboost")


# ══════════════════════════════════════════════════════════════════════════════
#  DIRECTIONAL SPECTRUM (L5)
# ══════════════════════════════════════════════════════════════════════════════

class DirectionalSpectrum:
    """
    L5: Directional Spectrum - aggregates L1-L4 signals
    """
    def __init__(self):
        self.l1_weight = 1.0
        self.l2_weight = 0.8
        self.l3_weight = 1.2  # CatBoost lebih di-weight
        self.l4_weight = 0.6
    
    def calculate(self, l1_vote: float, l2_vote: float, l3_vote: float, 
                  l4_mult: float, confidence_threshold: float = 5.0) -> 'SpectrumResult':
        """
        Calculate directional spectrum from layer votes.
        """
        # Weighted sum
        raw_score = (
            l1_vote * self.l1_weight +
            l2_vote * self.l2_weight +
            l3_vote * self.l3_weight +
            l4_mult * self.l4_weight
        )
        
        # Normalize
        total_weight = self.l1_weight + self.l2_weight + self.l3_weight + self.l4_weight
        normalized_score = raw_score / total_weight if total_weight > 0 else 0
        
        # Determine bias and gate
        if normalized_score > 0.3:
            bias = "BULL"
            gate = "ACTIVE" if normalized_score > 0.5 else "ADVISORY"
        elif normalized_score < -0.3:
            bias = "BEAR"
            gate = "ACTIVE" if normalized_score < -0.5 else "ADVISORY"
        else:
            bias = "NEUTRAL"
            gate = "BLOCKED"
        
        # Confidence (0-100)
        confidence = min(100.0, abs(normalized_score) * 100 + 50)
        
        return SpectrumResult(
            directional_bias=bias,
            raw_score=normalized_score,
            confidence=confidence,
            trade_gate=gate,
            l1_contrib=l1_vote * self.l1_weight,
            l2_contrib=l2_vote * self.l2_weight,
            l3_contrib=l3_vote * self.l3_weight,
            l4_contrib=l4_mult * self.l4_weight
        )
    
    def compute_l4_multiplier(self, vol_ratio: float) -> float:
        """
        L4: Volatility multiplier - dampens signals in high volatility.
        """
        if vol_ratio < 0.005:      # < 0.5% ATR
            return 1.0
        elif vol_ratio < 0.01:     # 0.5-1% ATR
            return 0.8
        elif vol_ratio < 0.02:     # 1-2% ATR
            return 0.6
        else:                      # > 2% ATR
            return 0.4


@dataclass
class SpectrumResult:
    directional_bias: str
    raw_score: float
    confidence: float
    trade_gate: str
    l1_contrib: float
    l2_contrib: float
    l3_contrib: float
    l4_contrib: float


# ══════════════════════════════════════════════════════════════════════════════
#  BCD REGIME DETECTION (L1)
# ══════════════════════════════════════════════════════════════════════════════

def get_bcd_regime(df: pd.DataFrame) -> Tuple[str, float]:
    """
    L1: BCD Regime Detection using trend analysis.
    Returns (tag, confidence)
    """
    close = df["Close"]
    ema20 = df["EMA20"] if "EMA20" in df.columns else ta.ema(close, length=20)
    ema50 = df["EMA50"] if "EMA50" in df.columns else ta.ema(close, length=50)
    
    if len(close) < 50:
        return "neutral", 0.5
    
    # Trend detection
    price_now = float(close.iloc[-1])
    ema20_now = float(ema20.iloc[-1])
    ema50_now = float(ema50.iloc[-1])
    
    if ema20_now > ema50_now and price_now > ema20_now:
        return "bull", 0.8
    elif ema20_now < ema50_now and price_now < ema20_now:
        return "bear", 0.8
    else:
        return "neutral", 0.5


def detect_regime(row) -> str:
    """
    Row-wise regime detection for feature engineering.
    Uses EMA alignment to classify regime.
    """
    if 'EMA20' not in row or 'EMA50' not in row or 'Close' not in row:
        return "neutral"
    
    ema20 = row['EMA20']
    ema50 = row['EMA50']
    price = row['Close']
    
    if pd.isna(ema20) or pd.isna(ema50) or pd.isna(price):
        return "neutral"
    
    if ema20 > ema50 and price > ema20:
        return "bull"
    elif ema20 < ema50 and price < ema20:
        return "bear"
    else:
        return "neutral"


# ══════════════════════════════════════════════════════════════════════════════
#  EMA ALIGNMENT (L2)
# ══════════════════════════════════════════════════════════════════════════════

def get_ma_trend(df: pd.DataFrame) -> str:
    """
    L2: EMA Alignment - determine trend direction.
    """
    close = df["Close"]
    ema20 = df["EMA20"] if "EMA20" in df.columns else ta.ema(close, length=20)
    ema50 = df["EMA50"] if "EMA50" in df.columns else ta.ema(close, length=50)
    
    if len(close) < 50:
        return "NEUTRAL"
    
    price_now = float(close.iloc[-1])
    ema20_now = float(ema20.iloc[-1])
    ema50_now = float(ema50.iloc[-1])
    
    if ema20_now > ema50_now and price_now > ema20_now:
        return "BULL"
    elif ema20_now < ema50_now and price_now < ema20_now:
        return "BEAR"
    elif price_now > ema50_now:
        return "BULL"
    else:
        return "BEAR"


def get_ema_alignment(df: pd.DataFrame, trend: str) -> Tuple[bool, float]:
    """
    Check if EMAs are aligned with trend.
    Returns (aligned, confidence)
    """
    close = df["Close"]
    ema20 = df["EMA20"] if "EMA20" in df.columns else ta.ema(close, length=20)
    ema50 = df["EMA50"] if "EMA50" in df.columns else ta.ema(close, length=50)
    
    if len(close) < 50:
        return False, 0.0
    
    price_now = float(close.iloc[-1])
    ema20_now = float(ema20.iloc[-1])
    ema50_now = float(ema50.iloc[-1])
    
    if trend == "BULL":
        aligned = ema20_now > ema50_now and price_now > ema20_now
    else:
        aligned = ema20_now < ema50_now and price_now < ema20_now
    
    confidence = 1.0 if aligned else 0.0
    return aligned, confidence


# ══════════════════════════════════════════════════════════════════════════════
#  CATBOOST L3 LAYER
# ══════════════════════════════════════════════════════════════════════════════

def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare causal features for CatBoost.
    """
    df = df.copy()
    
    # EMAs
    if "EMA20" not in df.columns:
        df["EMA20"] = ta.ema(df["Close"], length=20)
    if "EMA50" not in df.columns:
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
    
    # BCD Regime Detection (categorical feature)
    df["bcd_regime"] = df.apply(detect_regime, axis=1)
    
    return df


def train_catboost_model(train_df: pd.DataFrame) -> Optional[CatBoostSignalModel]:
    """
    Train CatBoost model on training data.
    """
    model = CatBoostSignalModel(
        depth=6,
        learning_rate=0.05,
        iterations=500
    )
    
    success = model.train(train_df)
    if not success:
        return None
    
    return model


def get_catboost_signal(model: CatBoostSignalModel, df: pd.DataFrame) -> Tuple[str, float]:
    """
    Get signal from CatBoost model.
    Returns (bias, confidence)
    """
    bias, confidence, probs = model.predict(df)
    return bias, confidence


# ══════════════════════════════════════════════════════════════════════════════
#  PnL CALCULATION & EXIT LOGIC
# ══════════════════════════════════════════════════════════════════════════════

def calc_pnl(side: str, entry: float, exit_price: float) -> float:
    """
    PnL = Notional × price_return − fee
    """
    if side == "LONG":
        price_return = (exit_price - entry) / entry
    else:
        price_return = (entry - exit_price) / entry
    return round(NOTIONAL * price_return - FEE_USD, 2)


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


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN WALKFORWARD ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def run_walkforward_v4_4_catboost(
    df: pd.DataFrame,
    window_start: str = "2020-01-01",
    window_end: str = "2026-03-04",
    train_size: int = 500,
    test_size: int = 100,
    step_size: int = 50,
    max_windows: int = 50
) -> Dict:
    """
    Run walkforward v4.4 CatBoost engine.
    """
    log.info("\n" + "="*72)
    log.info("  BTC-QUANT v4.4 CATBOOST ENGINE - WALKFORWARD")
    log.info("="*72)
    log.info(f"  Window: {window_start} → {window_end}")
    log.info(f"  Train: {train_size} | Test: {test_size} | Step: {step_size}")
    log.info(f"  SL: {SL_PCT*100:.3f}% | TP: {TP_MIN_PCT*100:.3f}% | Max Hold: {MAX_HOLD_CANDLES}")
    log.info("="*72)
    
    # Prepare features
    df = prepare_features(df)
    
    # Filter to window
    df = df[df.index >= window_start]
    df = df[df.index <= window_end]
    df = df.dropna()
    
    if len(df) < train_size + test_size:
        log.error(f"Insufficient data: {len(df)} samples")
        return {}
    
    # Generate windows
    windows = []
    start_idx = train_size
    
    while start_idx + train_size + test_size <= len(df):
        end_train = start_idx + train_size
        end_test = end_train + test_size
        
        windows.append({
            'train_start': start_idx,
            'train_end': end_train,
            'test_start': end_train,
            'test_end': end_test
        })
        
        start_idx += step_size
    
    windows = windows[:max_windows]
    log.info(f"Generated {len(windows)} windows")
    
    # Initialize components
    spectrum = DirectionalSpectrum()
    all_results = []
    
    # Process each window
    for i, window in enumerate(windows):
        log.info(f"\n--- Window {i+1}/{len(windows)} ---")
        
        train_df = df.iloc[window['train_start']:window['train_end']].copy()
        test_df = df.iloc[window['test_start']:window['test_end']].copy()
        
        log.info(f"Train: {train_df.index[0].date()} → {train_df.index[-1].date()}")
        log.info(f"Test: {test_df.index[0].date()} → {test_df.index[-1].date()}")
        
        # Train CatBoost
        log.info("Training CatBoost L3...")
        catboost_model = train_catboost_model(train_df)
        
        if catboost_model is None:
            log.warning("CatBoost training failed, skipping window")
            continue
        
        log.info("CatBoost training complete")
        
        # Simulate trading
        trades = []
        position = None
        
        for j in range(len(test_df)):
            # Build history up to current point
            hist_start = max(0, window['test_start'] + j - train_size)
            hist_end = window['test_start'] + j + 1
            df_hist = df.iloc[hist_start:hist_end].copy()
            
            if len(df_hist) < 50:
                continue
            
            price_now = float(df_hist["Close"].iloc[-1])
            
            # Check for position exit
            if position is not None:
                entry = position["entry"]
                side = position["side"]
                sl = position["sl"]
                tp = position["tp"]
                entry_idx_in_test = position["entry_idx"]
                holding = j - entry_idx_in_test
                
                # Get next candle for exit check
                if j + 1 < len(test_df):
                    next_candle = test_df.iloc[j]
                    c_high = float(next_candle["High"])
                    c_low = float(next_candle["Low"])
                    c_close = float(next_candle["Close"])
                    
                    exit_price, exit_type = check_sl_tp(side, sl, tp, c_high, c_low, c_close)
                    
                    if exit_price is not None:
                        # Close position
                        pnl = calc_pnl(side, entry, exit_price)
                        trades.append({
                            'side': side,
                            'entry': entry,
                            'exit': exit_price,
                            'exit_type': exit_type,
                            'pnl': pnl,
                            'holding': holding + 1,
                            'window': i + 1
                        })
                        position = None
                        continue
                    
                    # Check max hold
                    if holding >= MAX_HOLD_CANDLES - 1:
                        exit_price = c_close
                        pnl = calc_pnl(side, entry, exit_price)
                        trades.append({
                            'side': side,
                            'entry': entry,
                            'exit': exit_price,
                            'exit_type': "TIME_EXIT",
                            'pnl': pnl,
                            'holding': holding + 1,
                            'window': i + 1
                        })
                        position = None
                        continue
                
                continue
            
            # ENTRY SECTION - 6 Layer Stack
            # L1: BCD Regime
            regime, bcd_conf = get_bcd_regime(df_hist)
            l1_vote = bcd_conf if regime == "bull" else (-bcd_conf if regime == "bear" else 0)
            
            # L2: EMA Alignment
            trend = get_ma_trend(df_hist)
            aligned, ema_conf = get_ema_alignment(df_hist, trend)
            l2_vote = ema_conf if aligned else (-ema_conf * 0.5)
            
            # L3: CatBoost AI
            try:
                catboost_bias, catboost_conf = get_catboost_signal(catboost_model, df_hist)
                conf_norm = (max(50.0, min(100.0, catboost_conf)) - 50.0) / 50.0
                l3_vote = conf_norm if catboost_bias == "BULL" else (-conf_norm if catboost_bias == "BEAR" else 0)
            except Exception as e:
                log.warning(f"CatBoost prediction failed: {e}")
                l3_vote = 0
            
            # L4: Volatility Multiplier
            atr14 = float(df_hist["ATR14"].dropna().iloc[-1]) if df_hist["ATR14"].dropna().size else 0.01
            vol_ratio = atr14 / price_now if price_now > 0 else 0.001
            l4_mult = spectrum.compute_l4_multiplier(vol_ratio)
            
            # L5: Directional Spectrum
            spec = spectrum.calculate(l1_vote, l2_vote, l3_vote, l4_mult, 5.0)
            
            # L6: Trade Gate
            if spec.trade_gate not in ("ACTIVE", "ADVISORY"):
                continue
            
            # Filter: Skip ADVISORY SHORT in bear regime
            if spec.trade_gate == "ADVISORY" and spec.directional_bias == "BEAR" and regime == "bear":
                continue
            
            # Set SL/TP
            side = spec.directional_bias
            if side == "LONG":
                sl = price_now * (1.0 - SL_PCT)
                tp = price_now * (1.0 + TP_MIN_PCT)
            else:
                sl = price_now * (1.0 + SL_PCT)
                tp = price_now * (1.0 - TP_MIN_PCT)
            
            # Open position
            position = {
                "side": side,
                "entry": price_now,
                "sl": sl,
                "tp": tp,
                "entry_idx": j,
                "entry_time": test_df.index[j].isoformat(),
                "regime": regime,
                "confidence": spec.confidence
            }
            
            log.info(f"  🟢 OPEN {side} @ {price_now:,.0f} | SL={sl:,.0f} TP={tp:,.0f} | conf={spec.confidence:.1f}%")
        
        # Calculate window metrics
        if trades:
            n_trades = len(trades)
            wins = sum(1 for t in trades if t['pnl'] > 0)
            win_rate = wins / n_trades * 100
            total_pnl = sum(t['pnl'] for t in trades)
            avg_pnl = total_pnl / n_trades
            
            n_sl = sum(1 for t in trades if t['exit_type'] == "SL")
            n_tp = sum(1 for t in trades if t['exit_type'] in ("TP", "TRAIL_TP"))
            n_time = sum(1 for t in trades if t['exit_type'] == "TIME_EXIT")
            
            log.info(f"  Window {i+1} Results:")
            log.info(f"    Trades: {n_trades} | Win Rate: {win_rate:.1f}%")
            log.info(f"    Total PnL: ${total_pnl:,.2f} | Avg: ${avg_pnl:.2f}")
            log.info(f"    SL: {n_sl} | TP: {n_tp} | Time Exit: {n_time}")
            
            all_results.append({
                'window': i + 1,
                'n_trades': n_trades,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'avg_pnl': avg_pnl,
                'n_sl': n_sl,
                'n_tp': n_tp,
                'n_time_exit': n_time
            })
    
    # Summary
    if all_results:
        total_trades = sum(r['n_trades'] for r in all_results)
        avg_win_rate = sum(r['win_rate'] for r in all_results) / len(all_results)
        total_pnl = sum(r['total_pnl'] for r in all_results)
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
        
        log.info("\n" + "="*72)
        log.info("  WALKFORWARD SUMMARY - v4.4 CATBOOST")
        log.info("="*72)
        log.info(f"  Windows: {len(all_results)}")
        log.info(f"  Total Trades: {total_trades}")
        log.info(f"  Avg Win Rate: {avg_win_rate:.1f}%")
        log.info(f"  Total PnL: ${total_pnl:,.2f}")
        log.info(f"  Avg Trade: ${avg_pnl:.2f}")
        log.info("="*72)
        
        return {
            'windows': len(all_results),
            'total_trades': total_trades,
            'avg_win_rate': avg_win_rate,
            'total_pnl': total_pnl,
            'avg_trade': avg_pnl,
            'window_results': all_results
        }
    else:
        log.error("No results from any window")
        return {}


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='v4.4 CatBoost Engine')
    parser.add_argument('--data', type=str,
                        default='backtest/data/BTC_USDT_5m_2020_2026_with_real_orderflow.csv',
                        help='Path to historical data CSV')
    parser.add_argument('--start', type=str, default='2020-01-01', help='Start date')
    parser.add_argument('--end', type=str, default='2026-03-04', help='End date')
    parser.add_argument('--windows', type=int, default=50, help='Max windows')
    
    args = parser.parse_args()
    
    # Load data
    df = pd.read_csv(args.data)
    
    # Rename columns to uppercase (standard OHLCV)
    column_mapping = {}
    for col in df.columns:
        if col.lower() in ['open', 'high', 'low', 'close', 'volume']:
            column_mapping[col] = col.capitalize()
    if column_mapping:
        df = df.rename(columns=column_mapping)
    
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.set_index('datetime')
    elif 'timestamp' in df.columns:
        try:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        except:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')
    
    if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    
    # Run
    results = run_walkforward_v4_4_catboost(
        df=df,
        window_start=args.start,
        window_end=args.end,
        max_windows=args.windows
    )
    
    # Save
    output_path = _RESULTS_DIR / f"v4_4_catboost_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    log.info(f"\nResults saved to: {output_path}")
