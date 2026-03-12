import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_ta as ta

# Ensure console handles UTF-8 for borders and symbols
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

# Add backend directory to sys.path so we can import models directly
backend_dir = str(Path(__file__).parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from engines.layer1_hmm import MarketRegimeModel
from engines.layer2_ichimoku import IchimokuCloudModel
from utils.spectrum import DirectionalSpectrum

# ════════════════════════════════════════════════════════════
# LOGGER SETUP
# ════════════════════════════════════════════════════════════

def setup_logger(year: int):
    log_file = Path(__file__).parent / "logs" / f"backtest_{year}.log"
    log_file.parent.mkdir(exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(f"backtest_{year}")
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()
        
    formatter = logging.Formatter('%(message)s')
    
    # File handler
    file_handler = logging.FileHandler(log_file, mode='w')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

# ════════════════════════════════════════════════════════════
# BACKTEST ENGINE
# ════════════════════════════════════════════════════════════

class BacktestEngine:
    def __init__(self, year: int, initial_capital: float = 1000.0):
        self.year = year
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.logger = setup_logger(year)
        
        # Load dataset
        self.data_path = Path(__file__).parent / "data" / f"BTC_USDT_4h_{year}.csv"
        if not self.data_path.exists():
            raise FileNotFoundError(f"Data for {year} not found at {self.data_path}")
            
        self.df_full = pd.read_csv(self.data_path, index_col=0, parse_dates=True)
        self.df_full.rename(columns={
            "open": "Open", "high": "High", "low": "Low",
            "close": "Close", "volume": "Volume",
        }, inplace=True)
        
        # Models
        self.hmm_model = MarketRegimeModel()
        self.ichi_model = IchimokuCloudModel(tenkan=9, kijun=26, senkou=52)
        self.spectrum_calc = DirectionalSpectrum()
        
        # Performance Tracking
        self.trades = []
        self.peak_capital = initial_capital
        self.max_drawdown = 0.0
        
        # Current Position
        self.position = None  # None, "LONG", "SHORT"
        self.entry_price = 0.0
        self.position_size_usd = 0.0
        self.stop_loss = 0.0
        self.take_profit_1 = 0.0
        self.take_profit_2 = 0.0
        self.leverage = 1
        
        self.logger.info(f"╔════════════════════════════════════════════════════════════╗")
        self.logger.info(f"║ BACKTEST ENGINE: BTC-QUANT-BTC QUANTITATIVE STRATEGY         ║")
        self.logger.info(f"║ Trading Year  : {self.year}                                         ║")
        self.logger.info(f"║ Base Capital  : ${self.initial_capital:,.2f}                                  ║")
        self.logger.info(f"║ Total Candles : {len(self.df_full)} (4H timeframe)                         ║")
        self.logger.info(f"╚════════════════════════════════════════════════════════════╝\n")

    def run(self):
        # BUGFIX: Increased warmup from 100 → 250 to match HMM MIN_ROWS=250.
        # With 100 candles, HMM had insufficient feature diversity causing Bearish bias.
        warmup_period = 250
        
        if len(self.df_full) < warmup_period + 10:
            self.logger.error("Insufficient data for backtest.")
            return

        self.logger.info(f"Warming up models with first {warmup_period} candles...")
        
        for i in range(warmup_period, len(self.df_full) - 1):
            # Sliding window of warmup_period candles up to current index
            df_window = self.df_full.iloc[i-warmup_period : i+1].copy()
            current_time = df_window.index[-1].strftime("%Y-%m-%d %H:%M")
            next_candle = self.df_full.iloc[i+1] # The next 4H candle we will execute on
            
            # 1. Indicator Calculation (Layer 4 Risk)
            df_window["ATR14"] = ta.atr(df_window["High"], df_window["Low"], df_window["Close"], length=14)
            
            curr_row  = df_window.iloc[-1]
            price_now = float(curr_row["Close"])
            atr14     = float(curr_row["ATR14"])
            
            if pd.isna(atr14):
                continue
                
            # 2. Layer 1: HMM Regime (Continuous Vote)
            l1_vote = self.hmm_model.get_directional_vote(df_window)
            
            # 3. Layer 2: Ichimoku Structure (Continuous Vote)
            l2_vote = self.ichi_model.get_directional_vote(df_window)
            
            # 4. Layer 3: AI Inference (Simulated for backtesting)
            # Using MACD Histogram as a proxy for AI directional conviction
            macd = ta.macd(df_window["Close"])
            if macd is not None and "MACDh_12_26_9" in macd.columns:
                macd_hist = float(macd["MACDh_12_26_9"].iloc[-1])
                # Normalize MACD hist to [-1, 1] using tanh (proxied AI)
                l3_vote = float(pd.Series([macd_hist / (atr14 + 1e-9)]).apply(np.tanh).iloc[0])
            else:
                l3_vote = 0.0
            
            # 5. Layer 4: Volatility (Multiplier)
            vol_ratio = atr14 / price_now if price_now else 0.0
            l4_mult   = self.spectrum_calc.compute_l4_multiplier(vol_ratio)
            
            # Calculate dynamic leverage based on ATR ratio (Risk Control)
            leverage = (2 if vol_ratio > 0.015 else 3 if vol_ratio > 0.012 else 5 if vol_ratio > 0.008 else 7)
            
            # 6. Spectrum Calculation (Continuous Aggregation)
            spectrum = self.spectrum_calc.calculate(
                l1_vote       = l1_vote,
                l2_vote       = l2_vote,
                l3_vote       = l3_vote,
                l4_multiplier = l4_mult,
                base_size     = 5.0
            )
            
            # Log periodic status (every ~15 days based on 4H = 6 per day)
            if i % 90 == 0:
                self.logger.info(f"[{current_time}] Price: ${price_now:,.0f} | Cap: ${self.capital:,.0f} | Bias: {spectrum.directional_bias:+.3f} ({spectrum.trade_gate})")
            
            # 7. Manage open positions (Check SL / TP / Soft Exit)
            if self.position is not None:
                # Soft exit logic: exit if sign reverses or gate is SUSPENDED
                self._manage_position(curr_row, current_time, spectrum.trade_gate, spectrum.directional_bias)
                
            # 8. Execute New Entry (Next candle Open)
            if self.position is None and spectrum.trade_gate == "ACTIVE":
                action = spectrum.action # "LONG" or "SHORT"
                
                # Execute at next candle's Open price
                entry_price = float(next_candle["Open"])
                
                # Risk parameters
                risk_atr = atr14 * 1.5
                if action == "SHORT":
                    sl = entry_price + risk_atr
                    tp1 = entry_price - risk_atr * 1.5
                    tp2 = entry_price - risk_atr * 2.5
                else:
                    sl = entry_price - risk_atr
                    tp1 = entry_price + risk_atr * 1.5
                    tp2 = entry_price + risk_atr * 2.5
                
                # Sizing based on current capital
                size_usd = self.capital * (spectrum.position_size_pct / 100.0)
                
                self.position = action
                self.entry_price = entry_price
                self.position_size_usd = size_usd
                self.leverage = leverage
                self.stop_loss = sl
                self.take_profit_1 = tp1
                self.take_profit_2 = tp2
                
                self.logger.info(f"\n🟢 ENTRY {action} @ ${entry_price:,.0f} | [{current_time}]")
                self.logger.info(f"   Bias: {spectrum.directional_bias:+.3f} | Size: ${size_usd:,.0f} ({spectrum.position_size_pct:.1f}%) | Lev: {leverage}x")
                self.logger.info(f"   SL: ${sl:,.0f} | TP1: ${tp1:,.0f} | TP2: ${tp2:,.0f}")
                
        # Close out any remaining position at end of backtest
        if self.position is not None:
            last_candle = self.df_full.iloc[-1]
            last_time = self.df_full.index[-1].strftime("%Y-%m-%d %H:%M")
            self._close_position(float(last_candle["Close"]), last_time, "End of Backtest")
            
        self._print_summary()

    def _manage_position(self, curr_row: pd.Series, time_str: str, spectrum_gate: str, directional_bias: float):
        high = float(curr_row["High"])
        low = float(curr_row["Low"])
        close = float(curr_row["Close"])
        
        # 1. Check Hard Stop Loss (High/Low hit SL)
        if self.position == "LONG" and low <= self.stop_loss:
            self._close_position(self.stop_loss, time_str, "Stop Loss (Hit Hard)")
            return
            
        if self.position == "SHORT" and high >= self.stop_loss:
            self._close_position(self.stop_loss, time_str, "Stop Loss (Hit Hard)")
            return
            
        # 2. Check Hard TP2
        if self.position == "LONG" and high >= self.take_profit_2:
            self._close_position(self.take_profit_2, time_str, "Take Profit 2")
            return
            
        if self.position == "SHORT" and low <= self.take_profit_2:
            self._close_position(self.take_profit_2, time_str, "Take Profit 2")
            return

        # 3. Soft Exit: Spectrum went to SUSPENDED or sign reversed
        # Sign reversal: LONG but bias < 0, or SHORT but bias > 0
        sign_reversed = (self.position == "LONG" and directional_bias < 0) or \
                        (self.position == "SHORT" and directional_bias > 0)
                        
        if spectrum_gate == "SUSPENDED" or sign_reversed:
            exit_reason = f"Soft Exit ({spectrum_gate}/Rev={sign_reversed})"
            self._close_position(close, time_str, exit_reason)
            return
            
    def _close_position(self, exit_price: float, time_str: str, reason: str):
        # Calculate PnL percentage mapping to leveraged size
        if self.position == "LONG":
            unleveraged_pct = (exit_price - self.entry_price) / self.entry_price
        else:
            unleveraged_pct = (self.entry_price - exit_price) / self.entry_price
            
        # Raw PnL logic: PnL = Position Size * Unleverage_pct * Leverage
        # Note: Size USD already accounts for max capital allocation.
        pnl_usd = self.position_size_usd * unleveraged_pct * self.leverage
        
        # Update capital
        self.capital += pnl_usd
        
        # Track drawdown
        if self.capital > self.peak_capital:
            self.peak_capital = self.capital
        
        drawdown = (self.peak_capital - self.capital) / self.peak_capital * 100
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown
            
        is_win = pnl_usd > 0
        icon = "📈" if is_win else "📉"
        
        self.logger.info(f"🔴 EXIT {self.position} @ ${exit_price:,.0f} | [{time_str}] | {reason}")
        self.logger.info(f"   {icon} PnL: ${pnl_usd:+,.2f} ({unleveraged_pct * self.leverage * 100:+.2f}%) | New Cap: ${self.capital:,.2f}")
        
        # Save trade 
        self.trades.append({
            "action": self.position,
            "entry": self.entry_price,
            "exit": exit_price,
            "pnl_usd": pnl_usd,
            "win": is_win,
            "reason": reason
        })
        
        # Reset position state
        self.position = None

    def _print_summary(self):
        self.logger.info(f"\n============================================================")
        self.logger.info(f"🔥 BACKTEST RESULTS - {self.year}")
        self.logger.info(f"============================================================")
        
        total_trades = len(self.trades)
        if total_trades == 0:
            self.logger.info("No trades executed.")
            return
            
        wins = len([t for t in self.trades if t["win"]])
        losses = total_trades - wins
        win_rate = (wins / total_trades) * 100
        net_pct = ((self.capital - self.initial_capital) / self.initial_capital) * 100
        
        gross_profit = sum([t["pnl_usd"] for t in self.trades if t["pnl_usd"] > 0])
        gross_loss = abs(sum([t["pnl_usd"] for t in self.trades if t["pnl_usd"] < 0]))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        self.logger.info(f"  Initial Capital  : ${self.initial_capital:,.2f}")
        self.logger.info(f"  Final Capital    : ${self.capital:,.2f}")
        self.logger.info(f"  Net Profit       : ${self.capital - self.initial_capital:+,.2f} ({net_pct:+.2f}%)")
        self.logger.info(f"  Max Drawdown     : {self.max_drawdown:.2f}%")
        self.logger.info(f"  Profit Factor    : {profit_factor:.2f}")
        self.logger.info(f"")
        self.logger.info(f"  Total Trades     : {total_trades}")
        self.logger.info(f"  Win Rate         : {win_rate:.1f}% ({wins} W / {losses} L)")
        self.logger.info(f"")
        self.logger.info(f"  Buy & Hold Return: {((self.df_full['Close'].iloc[-1] - self.df_full['Close'].iloc[0]) / self.df_full['Close'].iloc[0] * 100):.2f}%")
        self.logger.info(f"============================================================\n")
