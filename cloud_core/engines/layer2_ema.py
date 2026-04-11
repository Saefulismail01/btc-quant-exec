"""
Layer 2: EMA Structural Trend Confirmation
"""
import pandas as pd
import numpy as np


class EMASignalModel:
    """
    EMA-based trend confirmation.
    Uses EMA 20/50/200 for multi-timeframe trend alignment.
    """
    
    def __init__(self):
        pass
    
    def analyze(self, df: pd.DataFrame) -> dict:
        """
        Analyze trend using EMA structure.
        
        Args:
            df: OHLCV DataFrame
        
        Returns:
            Dict with trend info
        """
        if len(df) < 200:
            return {
                "trend": "insufficient_data",
                "vote": 0.0,
                "strength": 0.0,
            }
        
        # Calculate EMAs
        ema20 = df['Close'].ewm(span=20, adjust=False).mean()
        ema50 = df['Close'].ewm(span=50, adjust=False).mean()
        ema200 = df['Close'].ewm(span=200, adjust=False).mean()
        
        # Current values
        close = df['Close'].iloc[-1]
        e20 = ema20.iloc[-1]
        e50 = ema50.iloc[-1]
        e200 = ema200.iloc[-1]
        
        # Previous values (for momentum)
        e20_prev = ema20.iloc[-5] if len(ema20) >= 5 else e20
        
        # Trend determination
        bullish_structure = close > e20 > e50 > e200
        bearish_structure = close < e20 < e50 < e200
        
        # EMA slope (momentum)
        ema20_rising = e20 > e20_prev
        ema20_falling = e20 < e20_prev
        
        # Calculate vote
        if bullish_structure and ema20_rising:
            vote = 1.0
            trend = "strong_bull"
            strength = min((close - e200) / e200 * 100, 1.0)
        elif bullish_structure:
            vote = 0.6
            trend = "bull"
            strength = 0.6
        elif bearish_structure and ema20_falling:
            vote = -1.0
            trend = "strong_bear"
            strength = min((e200 - close) / e200 * 100, 1.0)
        elif bearish_structure:
            vote = -0.6
            trend = "bear"
            strength = 0.6
        else:
            # Mixed structure
            if close > e200:
                vote = 0.3
                trend = "weak_bull"
                strength = 0.3
            elif close < e200:
                vote = -0.3
                trend = "weak_bear"
                strength = 0.3
            else:
                vote = 0.0
                trend = "sideways"
                strength = 0.0
        
        return {
            "trend": trend,
            "vote": vote,
            "strength": strength,
            "close": close,
            "ema20": e20,
            "ema50": e50,
            "ema200": e200,
            "bullish_structure": bullish_structure,
            "bearish_structure": bearish_structure,
        }
    
    def get_directional_vote(self, df: pd.DataFrame) -> float:
        """
        Return directional vote [-1.0, +1.0].
        
        Returns:
            +1.0 = strong uptrend
            -1.0 = strong downtrend
        """
        result = self.analyze(df)
        return result["vote"]
