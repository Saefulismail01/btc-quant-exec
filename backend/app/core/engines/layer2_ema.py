"""
╔══════════════════════════════════════════════════════════════╗
║  BTC-QUANT-BTC: LAYER 2 — EMA STRUCTURAL ANALYSIS            ║
║  Trend-Following Filter · EMA20 & EMA50 Alignment           ║
║  Stack: pandas_ta + numpy + pandas                          ║
║                                                             ║
║  PHASE 5 2026-02-27: Extraction from signal_service.py     ║
║    Standalone engine for architectural consistency.          ║
╚══════════════════════════════════════════════════════════════╝
"""

import numpy as np
import pandas as pd
import pandas_ta as ta

class EMAStructureModel:
    """
    Analyzes price relationship with EMA20 and EMA50 to determine
    structural trend alignment.
    """

    def __init__(self, ema_fast: int = 20, ema_slow: int = 50):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow

    def get_ema_alignment(self, df: pd.DataFrame, trend_short: str) -> tuple[bool, str, str]:
        """
        Calculates alignment between price, fast EMA, and slow EMA.
        
        Returns:
            (is_aligned: bool, label: str, detail: str)
        """
        if df is None or len(df) < self.ema_slow:
            return False, "Insufficient Data", "Wait for more candles"

        # Ensure indicators exist
        df_work = df.copy()
        fast_col = f"EMA{self.ema_fast}"
        slow_col = f"EMA{self.ema_slow}"
        
        if fast_col not in df_work.columns:
            df_work[fast_col] = ta.ema(df_work["Close"], length=self.ema_fast)
        if slow_col not in df_work.columns:
            df_work[slow_col] = ta.ema(df_work["Close"], length=self.ema_slow)

        curr = df_work.iloc[-1]
        price = float(curr["Close"])
        ema_f = float(curr[fast_col])
        ema_s = float(curr[slow_col])

        is_bull = trend_short == "BULL"
        
        if is_bull:
            # Bullish Structural Alignment: Price > EMA20 > EMA50
            is_aligned = (ema_f > ema_s) and (price > ema_f)
            label = "Bullish Confirmed" if is_aligned else "Bullish Weak/Correction"
            detail = f"{fast_col} > {slow_col} & Price > {fast_col}" if is_aligned else "EMA Cross or Price below Fast EMA"
        else:
            # Bearish Structural Alignment: Price < EMA20 < EMA50
            is_aligned = (ema_f < ema_s) and (price < ema_f)
            label = "Bearish Confirmed" if is_aligned else "Bearish Weak/Correction"
            detail = f"{fast_col} < {slow_col} & Price < {fast_col}" if is_aligned else "EMA Cross or Price above Fast EMA"

        return is_aligned, label, detail

    def get_directional_vote(self, df: pd.DataFrame) -> float:
        """
        v3 ARCH: Return a continuous directional vote in [-1.0, +1.0].

        Logic:
            1. Calculate distance from price to EMA50.
            2. Normalize distance using ATR (Average True Range).
            3. Apply tanh() for smooth saturation at [-1, +1].
            4. Apply structural multiplier (EMA20 vs EMA50 alignment).

        Rationale:
            Closer to EMA50 = lower confidence. 
            Strong trend alignment (Price > EMA20 > EMA50) preserves conviction.
            Structural breaks (Price between EMAs) reduce conviction smoothly.

        Returns:
            float in [-1.0, +1.0]
        """
        if df is None or len(df) < self.ema_slow:
            return 0.0

        df_work = df.copy()
        fast_col = f"EMA{self.ema_fast}"
        slow_col = f"EMA{self.ema_slow}"

        if fast_col not in df_work.columns:
            df_work[fast_col] = ta.ema(df_work["Close"], length=self.ema_fast)
        if slow_col not in df_work.columns:
            df_work[slow_col] = ta.ema(df_work["Close"], length=self.ema_slow)
        
        # Need ATR for normalization
        if "ATR_14" not in df_work.columns:
            df_work["ATR_14"] = ta.atr(df_work["High"], df_work["Low"], df_work["Close"], length=14)

        curr  = df_work.iloc[-1]
        price = float(curr["Close"])
        ema_f = float(curr[fast_col])
        ema_s = float(curr[slow_col])
        atr   = float(curr.get("ATR_14", price * 0.01)) # fallback to 1% price

        if any(pd.isna(v) for v in [price, ema_f, ema_s]) or ema_s == 0:
            return 0.0

        # 1. Distance-based raw bias
        # Normalization Factor: how many ATRs away from EMA50?
        # Typically 2-3 ATRs is a strong move.
        atr_factor = 1.5
        dist_raw   = (price - ema_s) / (atr * atr_factor + 1e-9)
        
        # 2. Smooth saturation using tanh
        vote_cont = np.tanh(dist_raw)

        # 3. Structural alignment multiplier
        # Full alignment (Price > Fast > Slow or Price < Fast < Slow) -> 1.0
        # Partial alignment (Price between EMAs or EMAs crossed) -> 0.4 - 0.7
        is_bull_align = (price > ema_f > ema_s)
        is_bear_align = (price < ema_f < ema_s)
        
        if (vote_cont > 0 and is_bull_align) or (vote_cont < 0 and is_bear_align):
            struct_mult = 1.0
        elif (ema_f > ema_s and vote_cont > 0) or (ema_f < ema_s and vote_cont < 0):
            struct_mult = 0.7  # price corrected below/above fast EMA but trend holds
        else:
            struct_mult = 0.4  # EMAs crossed or heavy divergence
            
        vote = vote_cont * struct_mult
        
        return round(max(-1.0, min(1.0, vote)), 4)
