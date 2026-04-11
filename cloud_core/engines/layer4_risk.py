"""
Layer 4: Risk Model - ATR-based Volatility Multiplier
"""
import pandas as pd
import numpy as np


class RiskModel:
    """
    Computes risk multiplier based on ATR/Price ratio.
    Higher volatility = lower position size.
    """
    
    def __init__(self):
        pass
    
    def calculate_volatility_ratio(self, df: pd.DataFrame) -> float:
        """
        Calculate ATR14 / Close price ratio.
        
        Returns:
            Volatility ratio (e.g., 0.015 = 1.5%)
        """
        try:
            if len(df) < 14:
                return 0.02  # Default: high vol (safe)
            
            import pandas_ta as ta
            atr = ta.atr(df["High"], df["Low"], df["Close"], length=14)
            close = df["Close"].iloc[-1]
            
            if pd.isna(atr.iloc[-1]) or close == 0:
                return 0.02
            
            return atr.iloc[-1] / close
            
        except Exception:
            return 0.02
    
    def get_multiplier(self, df: pd.DataFrame) -> float:
        """
        Get L4 risk multiplier [0.0, 1.0].
        
        Stepped table:
            < 0.008  → 1.0  (very low vol)
            < 0.012  → 0.8  (medium vol)
            < 0.015  → 0.5  (high vol)
            < 0.020  → 0.2  (very high vol)
            >= 0.020 → 0.0  (extreme vol, suspend)
        """
        vol_ratio = self.calculate_volatility_ratio(df)
        
        table = [
            (0.008, 1.0),
            (0.012, 0.8),
            (0.015, 0.5),
            (0.020, 0.2),
            (float("inf"), 0.0),
        ]
        
        for threshold, mult in table:
            if vol_ratio < threshold:
                return mult
        
        return 0.0
    
    def get_risk_params(self, df: pd.DataFrame, base_sl_pct: float = 1.5) -> dict:
        """
        Calculate complete risk parameters.
        
        Returns:
            Dict with SL, TP, leverage recommendation
        """
        vol_ratio = self.calculate_volatility_ratio(df)
        l4_mult = self.get_multiplier(df)
        
        # Adjust SL based on volatility
        if vol_ratio < 0.008:
            sl_pct = base_sl_pct * 0.8  # Tighter SL in low vol
        elif vol_ratio < 0.012:
            sl_pct = base_sl_pct
        elif vol_ratio < 0.015:
            sl_pct = base_sl_pct * 1.2
        elif vol_ratio < 0.020:
            sl_pct = base_sl_pct * 1.5
        else:
            sl_pct = base_sl_pct * 2.0
        
        # TP is 2x SL (2:1 RRR)
        tp_pct = sl_pct * 2
        
        # Leverage based on volatility
        if vol_ratio < 0.010:
            leverage = 20
        elif vol_ratio < 0.015:
            leverage = 15
        elif vol_ratio < 0.020:
            leverage = 10
        else:
            leverage = 5
        
        return {
            "volatility_ratio": round(vol_ratio, 4),
            "l4_multiplier": l4_mult,
            "sl_pct": round(sl_pct, 2),
            "tp_pct": round(tp_pct, 2),
            "leverage": leverage,
            "vol_label": self._get_vol_label(vol_ratio),
        }
    
    def _get_vol_label(self, vol_ratio: float) -> str:
        """Get volatility label."""
        if vol_ratio < 0.008:
            return "very_low"
        elif vol_ratio < 0.012:
            return "low"
        elif vol_ratio < 0.015:
            return "medium"
        elif vol_ratio < 0.020:
            return "high"
        else:
            return "extreme"
