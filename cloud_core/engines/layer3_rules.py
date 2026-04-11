"""
Layer 3: Rule-Based Technical Ensemble
Non-ML approach using weighted technical indicators
"""
import numpy as np
import pandas as pd
import pandas_ta as ta
from typing import Tuple


class RuleBasedSignalModel:
    """
    Rule-based model menggunakan kombinasi indikator teknikal.
    Tidak perlu training - pure logic-based.
    """
    
    def __init__(self):
        self._is_trained = True  # Always "trained" - no training needed
    
    def _calculate_score(self, df: pd.DataFrame) -> Tuple[float, dict]:
        """
        Calculate composite score based on multiple indicators.
        Returns (score, debug_info)
        """
        if len(df) < 50:
            return 0.0, {}
        
        latest = df.iloc[-1]
        
        scores = {}
        
        # 1. RSI Score (0-100 -> -1 to +1)
        rsi = ta.rsi(df["Close"], length=14).iloc[-1]
        if pd.isna(rsi):
            scores['rsi'] = 0
        else:
            # RSI < 30 = oversold (bullish), RSI > 70 = overbought (bearish)
            scores['rsi'] = (50 - rsi) / 50  # 30->+0.4, 70->-0.4
        
        # 2. MACD Score
        macd_df = ta.macd(df["Close"], fast=12, slow=26, signal=9)
        if macd_df is not None:
            hist = macd_df["MACDh_12_26_9"].iloc[-1]
            signal_line = macd_df["MACDs_12_26_9"].iloc[-1]
            macd_line = macd_df["MACD_12_26_9"].iloc[-1]
            
            # MACD above signal and histogram positive = bullish
            if not pd.isna(hist):
                scores['macd'] = np.sign(hist) * min(abs(hist) / abs(signal_line) if signal_line != 0 else 0, 1)
            else:
                scores['macd'] = 0
        else:
            scores['macd'] = 0
        
        # 3. EMA Alignment Score
        ema9 = ta.ema(df["Close"], length=9).iloc[-1]
        ema20 = ta.ema(df["Close"], length=20).iloc[-1]
        ema50 = ta.ema(df["Close"], length=50).iloc[-1]
        
        if not any(pd.isna([ema9, ema20, ema50])):
            # Bullish alignment: 9 > 20 > 50
            if ema9 > ema20 > ema50:
                scores['ema'] = 1.0
            # Bearish alignment: 9 < 20 < 50
            elif ema9 < ema20 < ema50:
                scores['ema'] = -1.0
            else:
                scores['ema'] = 0.0
        else:
            scores['ema'] = 0
        
        # 4. Bollinger Bands Score
        bb = ta.bbands(df["Close"], length=20, std=2)
        if bb is not None and len(bb.columns) >= 3:
            close = latest["Close"]
            # Handle different column naming conventions
            upper_col = [c for c in bb.columns if 'BBU' in c or 'upper' in c.lower()][0] if any('BBU' in c for c in bb.columns) else bb.columns[2]
            lower_col = [c for c in bb.columns if 'BBL' in c or 'lower' in c.lower()][0] if any('BBL' in c for c in bb.columns) else bb.columns[0]
            
            upper = bb[upper_col].iloc[-1]
            lower = bb[lower_col].iloc[-1]
            
            if not pd.isna(upper) and not pd.isna(lower) and (upper - lower) > 0:
                # Close to lower band = bullish (mean reversion)
                # Close to upper band = bearish
                position = (close - lower) / (upper - lower)
                scores['bb'] = (0.5 - position) * 2  # 0->+1, 1->-1, 0.5->0
            else:
                scores['bb'] = 0
        else:
            scores['bb'] = 0
        
        # 5. ADX Trend Strength Score
        try:
            adx_df = ta.adx(df["High"], df["Low"], df["Close"], length=14)
            if adx_df is not None and len(adx_df.columns) >= 3:
                # Get the values safely
                adx_values = adx_df.iloc[-1].values
                if len(adx_values) >= 3:
                    adx = adx_values[0]  # ADX value
                    di_plus = adx_values[1]  # DI+
                    di_minus = adx_values[2]  # DI-
                    
                    if not any(pd.isna([adx, di_plus, di_minus])):
                        if adx > 25:  # Strong trend
                            scores['adx'] = 1 if di_plus > di_minus else -1
                        else:
                            scores['adx'] = 0
                    else:
                        scores['adx'] = 0
                else:
                    scores['adx'] = 0
            else:
                scores['adx'] = 0
        except Exception:
            scores['adx'] = 0
        
        # 6. Volume Confirmation (if available)
        if "Volume" in df.columns:
            vol_sma = df["Volume"].rolling(20).mean().iloc[-1]
            curr_vol = latest["Volume"]
            
            if not pd.isna(vol_sma) and vol_sma > 0:
                vol_ratio = curr_vol / vol_sma
                # High volume = more confidence
                scores['volume'] = min((vol_ratio - 1) * 0.5, 0.5)
            else:
                scores['volume'] = 0
        else:
            scores['volume'] = 0
        
        # Weighted composite
        weights = {
            'rsi': 0.20,
            'macd': 0.20,
            'ema': 0.25,
            'bb': 0.15,
            'adx': 0.15,
            'volume': 0.05
        }
        
        composite = sum(scores[k] * weights[k] for k in scores)
        
        return composite, scores
    
    def predict(self, df: pd.DataFrame) -> Tuple[str, float, np.ndarray]:
        """
        Predict direction based on rules.
        Returns: (bias, confidence, probabilities)
        """
        score, details = self._calculate_score(df)
        
        # Convert score to probability
        # Score range approximately -1 to +1
        prob_neutral = max(0, 1 - abs(score) * 2)
        prob_bull = max(0, (score + 1) / 2 - prob_neutral / 2)
        prob_bear = max(0, 1 - prob_bull - prob_neutral)
        
        # Normalize
        total = prob_bull + prob_neutral + prob_bear
        if total > 0:
            prob_bull /= total
            prob_neutral /= total
            prob_bear /= total
        
        probs = np.array([prob_bear, prob_neutral, prob_bull])
        
        # Determine bias
        max_prob = max(prob_bull, prob_neutral, prob_bear)
        confidence = round(max_prob * 100, 1)
        
        if prob_bull > prob_neutral and prob_bull > prob_bear:
            return "BULL", confidence, probs
        elif prob_bear > prob_neutral and prob_bear > prob_bull:
            return "BEAR", confidence, probs
        else:
            return "NEUTRAL", confidence, probs
    
    def get_directional_vote(self, df: pd.DataFrame) -> float:
        """Return vote [-1.0, +1.0]"""
        bias, conf, _ = self.predict(df)
        
        if bias == "BULL":
            return (conf - 50) / 50
        elif bias == "BEAR":
            return -(conf - 50) / 50
        return 0.0
    
    def train(self, df: pd.DataFrame) -> bool:
        """No training needed for rule-based model"""
        return True
