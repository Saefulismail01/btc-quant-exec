"""
╔══════════════════════════════════════════════════════════════╗
║  BTC-QUANT-BTC: LAYER 2 — ICHIMOKU CLOUD ANALYSIS            ║
║  Equilibrium-Based Trend Filter · Kumo Breakout & TK Cross  ║
║  Stack: pandas_ta + numpy + pandas                          ║
║                                                             ║
║  EXPERIMENT 2026-02-28: Replacing EMA with Ichimoku        ║
║    Goal: Reduce lag and capture trend breakouts earlier.    ║
╚══════════════════════════════════════════════════════════════╝
"""

import numpy as np
import pandas as pd
import pandas_ta as ta

class IchimokuCloudModel:
    """
    Analyzes price relationship with Ichimoku components to determine
    structural equilibrium and trend breakout.
    """

    def __init__(self, tenkan: int = 9, kijun: int = 26, senkou: int = 52):
        self.tenkan = tenkan
        self.kijun = kijun
        self.senkou = senkou

    def get_directional_vote(self, df: pd.DataFrame) -> float:
        """
        v3 ARCH (Ichimoku Edition): Return a continuous directional vote in [-1.0, +1.0].

        Logic:
            1. Price vs Kumo (Cloud): +0.5 if above, -0.5 if below.
            2. TK Cross: +0.3 if Tenkan > Kijun, -0.3 if Tenkan < Kijun.
            3. Kumo Color (A vs B): +0.1 if spanA > spanB (Bullish Cloud), -0.1 otherwise.
            4. Chikou (Closing vs Price - 26): +0.1 if above, -0.1 if below.
            
        Normalisasi:
            Total raw score di-sum, lalu diproses dengan tanh() untuk saturasi halus.

        Returns:
            float in [-1.0, +1.0]
        """
        if df is None or len(df) < self.senkou + self.kijun:
            return 0.0

        # Calculate Ichimoku components
        # pandas_ta returns: ISA_9, ISB_26, ITS_9, IKS_26, ICS_26
        ichi = ta.ichimoku(df["High"], df["Low"], df["Close"], 
                           tenkan=self.tenkan, kijun=self.kijun, senkou=self.senkou)
        
        if ichi is None or len(ichi) < 2:
            return 0.0
            
        df_ichi = ichi[0] # The main components
        
        # Current values
        curr_price = float(df["Close"].iloc[-1])
        ts = float(df_ichi[f"ITS_{self.tenkan}"].iloc[-1])   # Tenkan-sen
        ks = float(df_ichi[f"IKS_{self.kijun}"].iloc[-1])    # Kijun-sen
        span_a = float(df_ichi[f"ISA_{self.tenkan}"].iloc[-1])
        span_b = float(df_ichi[f"ISB_{self.kijun}"].iloc[-1])
        
        if any(pd.isna(v) for v in [curr_price, ts, ks, span_a, span_b]):
            return 0.0

        raw_score = 0.0
        
        # 1. Price vs Cloud (Core Trend)
        kumo_top = max(span_a, span_b)
        kumo_bottom = min(span_a, span_b)
        
        if curr_price > kumo_top:
            raw_score += 0.5
        elif curr_price < kumo_bottom:
            raw_score -= 0.5
        # else: inside cloud (Neutral zones give 0.0)
            
        # 2. TK Cross (Momentum)
        if ts > ks:
            raw_score += 0.3
        elif ts < ks:
            raw_score -= 0.3
            
        # 3. Cloud Color (Future Bias)
        if span_a > span_b:
            raw_score += 0.1
        elif span_a < span_b:
            raw_score -= 0.1
            
        # 4. Proximity to Kijun (Rubber band effect)
        # If price is too far from Kijun, reduce conviction (Mean Reversion risk)
        atr = ta.atr(df["High"], df["Low"], df["Close"], length=14)
        curr_atr = float(atr.iloc[-1]) if atr is not None else curr_price * 0.01
        
        dist_ks = (curr_price - ks) / (curr_atr * 3 + 1e-9) # Normalized distance
        # No direct score add, but we'll use it to dampen the vote if extreme
        dampener = 1.0
        if abs(dist_ks) > 1.5: # More than 4.5 ATR away from Kijun
            dampener = 0.7 

        # Final smoothing
        vote = np.tanh(raw_score) * dampener
        
        return round(max(-1.0, min(1.0, vote)), 4)
