"""
Signal Service - Generate trading signals from 4-layer ensemble
"""
import pandas as pd
from typing import Dict, Optional, Literal
from dataclasses import dataclass
from datetime import datetime

from engines.layer1_bcd import BayesianChangepointModel
from engines.layer2_ema import EMASignalModel
from engines.layer3_mlp import MLPSignalModel
from engines.layer3_xgboost import XGBoostSignalModel
from engines.layer4_risk import RiskModel
from engines.spectrum import DirectionalSpectrum, SpectrumResult
from data.fetcher import DataFetcher


@dataclass
class SignalResult:
    """Complete signal output."""
    timestamp: datetime
    symbol: str
    price: float
    
    # Layer votes
    l1_vote: float  # BCD [-1, 1]
    l2_vote: float  # EMA [-1, 1]
    l3_vote: float  # MLP/XGB [-1, 1]
    l4_mult: float  # Risk [0, 1]
    
    # Spectrum output
    directional_bias: float  # [-1, 1]
    action: str  # LONG / SHORT
    conviction_pct: float
    trade_gate: str  # ACTIVE / ADVISORY / SUSPENDED
    position_size_pct: float
    
    # Risk params
    sl_pct: float
    tp_pct: float
    leverage: int
    
    # Model info
    model_used: str  # "mlp" or "xgboost"
    
    def __repr__(self) -> str:
        sign = "+" if self.directional_bias >= 0 else ""
        return (
            f"Signal({self.symbol} @ {self.price:,.0f} | "
            f"bias={sign}{self.directional_bias:.3f} | "
            f"conviction={self.conviction_pct:.1f}% | "
            f"gate={self.trade_gate} | "
            f"action={self.action})"
        )
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON/DB storage."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "price": self.price,
            "l1_vote": self.l1_vote,
            "l2_vote": self.l2_vote,
            "l3_vote": self.l3_vote,
            "l4_mult": self.l4_mult,
            "directional_bias": self.directional_bias,
            "action": self.action,
            "conviction_pct": self.conviction_pct,
            "trade_gate": self.trade_gate,
            "position_size_pct": self.position_size_pct,
            "sl_pct": self.sl_pct,
            "tp_pct": self.tp_pct,
            "leverage": self.leverage,
            "model_used": self.model_used,
        }


class SignalService:
    """
    Generate trading signals using 4-layer ensemble architecture.
    
    Layers:
        L1: BCD (Bayesian Changepoint Detection) - Macro regime
        L2: EMA - Structural trend confirmation
        L3: MLP or XGBoost - Short-term predictive (highest weight 45%)
        L4: ATR Risk - Volatility-based position sizing
    """
    
    def __init__(
        self,
        ai_model: Literal["mlp", "xgboost"] = "mlp",
        model_path: Optional[str] = None,
    ):
        self.ai_model_type = ai_model
        
        # Initialize layers
        self.l1_bcd = BayesianChangepointModel()
        self.l2_ema = EMASignalModel()
        self.l4_risk = RiskModel()
        self.spectrum = DirectionalSpectrum()
        
        # L3 AI model (MLP or XGBoost)
        if ai_model == "xgboost":
            self.l3_ai = XGBoostSignalModel(model_path=model_path)
        else:
            self.l3_ai = MLPSignalModel(model_path=model_path)
        
        self.data_fetcher = DataFetcher()
        
        print(f"[SignalService] Initialized with {ai_model.upper()} model")
    
    def generate_signal(
        self,
        symbol: str = "BTC/USDT",
        timeframe: str = "4h",
        train_if_needed: bool = True,
    ) -> Optional[SignalResult]:
        """
        Generate trading signal.
        
        Args:
            symbol: Trading pair
            timeframe: Candle timeframe
            train_if_needed: Train model if not trained
        
        Returns:
            SignalResult or None if error
        """
        try:
            # Fetch data
            df = self.data_fetcher.fetch_ohlcv(symbol, timeframe, limit=500)
            if df is None or len(df) < 100:
                print("[SignalService] Insufficient data")
                return None
            
            # Train AI model if needed
            if train_if_needed and not getattr(self.l3_ai, '_is_trained', False):
                print("[SignalService] Training AI model...")
                self.l3_ai.train(df)
            
            # Get L1 vote (BCD)
            self.l1_bcd.fit(df)  # Refit on latest data
            l1_vote = self.l1_bcd.get_directional_vote(df)
            
            # Get L2 vote (EMA)
            l2_vote = self.l2_ema.get_directional_vote(df)
            
            # Get L3 vote (AI)
            l3_vote = self.l3_ai.get_directional_vote(df)
            
            # Get L4 multiplier (Risk)
            l4_mult = self.l4_risk.get_multiplier(df)
            
            # Calculate spectrum
            spectrum = self.spectrum.calculate(
                l1_vote=l1_vote,
                l2_vote=l2_vote,
                l3_vote=l3_vote,
                l4_mult=l4_mult,
                base_size=5.0,
            )
            
            # Get risk parameters
            risk_params = self.l4_risk.get_risk_params(df)
            
            # Create result
            price = df["Close"].iloc[-1]
            
            return SignalResult(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                price=price,
                l1_vote=l1_vote,
                l2_vote=l2_vote,
                l3_vote=l3_vote,
                l4_mult=l4_mult,
                directional_bias=spectrum.directional_bias,
                action=spectrum.action,
                conviction_pct=spectrum.conviction_pct,
                trade_gate=spectrum.trade_gate,
                position_size_pct=spectrum.position_size_pct,
                sl_pct=risk_params["sl_pct"],
                tp_pct=risk_params["tp_pct"],
                leverage=risk_params["leverage"],
                model_used=self.ai_model_type,
            )
            
        except Exception as e:
            print(f"[SignalService] Error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def run_backtest(
        self,
        df: pd.DataFrame,
        verbose: bool = False,
    ) -> pd.DataFrame:
        """
        Run walk-forward backtest on historical data.
        
        Args:
            df: OHLCV DataFrame
            verbose: Print progress
        
        Returns:
            DataFrame with signals at each bar
        """
        signals = []
        
        # Train on first 60% of data
        train_size = int(len(df) * 0.6)
        df_train = df.iloc[:train_size]
        df_test = df.iloc[train_size:]
        
        print(f"[Backtest] Training on {len(df_train)} candles...")
        self.l3_ai.train(df_train)
        
        print(f"[Backtest] Testing on {len(df_test)} candles...")
        
        # Walk-forward
        for i in range(len(df_test)):
            # Use data up to current point
            current_df = df.iloc[:train_size + i + 1]
            
            # Regenerate signal
            if i % 12 == 0:  # Retrain every 12 candles (48h)
                self.l1_bcd.fit(current_df)
            
            l1_vote = self.l1_bcd.get_directional_vote(current_df)
            l2_vote = self.l2_ema.get_directional_vote(current_df)
            l3_vote = self.l3_ai.get_directional_vote(current_df)
            l4_mult = self.l4_risk.get_multiplier(current_df)
            
            spectrum = self.spectrum.calculate(l1_vote, l2_vote, l3_vote, l4_mult)
            
            price = current_df["Close"].iloc[-1]
            timestamp = current_df.index[-1]
            
            signals.append({
                "timestamp": timestamp,
                "price": price,
                "l1_vote": l1_vote,
                "l2_vote": l2_vote,
                "l3_vote": l3_vote,
                "l4_mult": l4_mult,
                "bias": spectrum.directional_bias,
                "action": spectrum.action,
                "conviction": spectrum.conviction_pct,
                "gate": spectrum.trade_gate,
            })
            
            if verbose and i % 50 == 0:
                print(f"[Backtest] {i}/{len(df_test)} - bias={spectrum.directional_bias:.3f}")
        
        return pd.DataFrame(signals)
