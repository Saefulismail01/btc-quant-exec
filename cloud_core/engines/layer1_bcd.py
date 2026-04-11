"""
Layer 1: Bayesian Changepoint Detection (BCD) / HMM
Detects market regime: bull, bear, sideways
"""
import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM
from typing import Tuple, Optional


class BayesianChangepointModel:
    """
    Hidden Markov Model for market regime detection.
    4 states: strong bull, weak bull, weak bear, strong bear
    """
    
    N_STATES = 4
    RANDOM_STATE = 42
    
    def __init__(self):
        self.model: Optional[GaussianHMM] = None
        self._is_fitted = False
    
    def fit(self, df: pd.DataFrame) -> bool:
        """
        Fit HMM on price data.
        
        Args:
            df: DataFrame with OHLCV data
        
        Returns:
            True if fitted successfully
        """
        try:
            # Features: log returns, volatility
            df = df.copy()
            df['returns'] = np.log(df['Close'] / df['Close'].shift(1))
            df['volatility'] = df['returns'].rolling(20).std()
            df['price_range'] = (df['High'] - df['Low']) / df['Close']
            
            # Drop NaN
            features = df[['returns', 'volatility', 'price_range']].dropna()
            
            if len(features) < 100:
                return False
            
            # Fit HMM
            self.model = GaussianHMM(
                n_components=self.N_STATES,
                covariance_type="full",
                random_state=self.RANDOM_STATE,
                n_iter=100,
            )
            self.model.fit(features.values)
            self._is_fitted = True
            return True
            
        except Exception as e:
            print(f"[BCD] Fit error: {e}")
            return False
    
    def predict_regime(self, df: pd.DataFrame) -> Tuple[str, float, np.ndarray]:
        """
        Predict current market regime.
        
        Args:
            df: DataFrame with OHLCV
        
        Returns:
            (regime_label, confidence, state_sequence)
            regime_label: "bull", "bear", "sideways"
            confidence: 0.0 to 1.0
            state_sequence: array of state IDs
        """
        if not self._is_fitted or self.model is None:
            # Fallback: simple trend detection
            return self._fallback_regime(df)
        
        try:
            # Prepare features
            df = df.copy()
            df['returns'] = np.log(df['Close'] / df['Close'].shift(1))
            df['volatility'] = df['returns'].rolling(20).std()
            df['price_range'] = (df['High'] - df['Low']) / df['Close']
            
            features = df[['returns', 'volatility', 'price_range']].dropna()
            
            if len(features) == 0:
                return self._fallback_regime(df)
            
            # Predict states
            states = self.model.predict(features.values)
            
            # Current state (last)
            current_state = states[-1]
            
            # Calculate state distribution
            unique, counts = np.unique(states, return_counts=True)
            state_dist = dict(zip(unique, counts / len(states)))
            
            # Map states to regime
            # State interpretation based on means
            means = self.model.means_
            
            # Sort states by return mean (bullish to bearish)
            state_returns = [(i, means[i][0]) for i in range(self.N_STATES)]
            state_returns.sort(key=lambda x: x[1], reverse=True)
            
            bull_states = [s[0] for s in state_returns[:2]]  # Top 2
            bear_states = [s[0] for s in state_returns[2:]]    # Bottom 2
            
            if current_state in bull_states:
                regime = "bull"
                confidence = state_dist.get(current_state, 0.5)
            elif current_state in bear_states:
                regime = "bear"
                confidence = state_dist.get(current_state, 0.5)
            else:
                regime = "sideways"
                confidence = 0.5
            
            return regime, confidence, states
            
        except Exception as e:
            print(f"[BCD] Predict error: {e}")
            return self._fallback_regime(df)
    
    def _fallback_regime(self, df: pd.DataFrame) -> Tuple[str, float, np.ndarray]:
        """Simple fallback using EMA trend."""
        if len(df) < 50:
            return "sideways", 0.5, np.array([])
        
        ema20 = df['Close'].ewm(span=20).mean().iloc[-1]
        ema50 = df['Close'].ewm(span=50).mean().iloc[-1]
        price = df['Close'].iloc[-1]
        
        if price > ema20 > ema50:
            return "bull", 0.6, np.array([0])
        elif price < ema20 < ema50:
            return "bear", 0.6, np.array([3])
        else:
            return "sideways", 0.5, np.array([1])
    
    def get_directional_vote(self, df: pd.DataFrame) -> float:
        """
        Return directional vote [-1.0, +1.0].
        
        Returns:
            +1.0 = strong bull
            -1.0 = strong bear
        """
        regime, conf, _ = self.predict_regime(df)
        
        if regime == "bull":
            return conf  # 0.5 to 1.0
        elif regime == "bear":
            return -conf  # -0.5 to -1.0
        else:
            return 0.0
    
    def get_state_sequence_raw(self, df: pd.DataFrame) -> Tuple[Optional[np.ndarray], Optional[pd.Index]]:
        """Get raw state sequence for MLP cross-feature."""
        _, _, states = self.predict_regime(df)
        
        if len(states) == 0:
            return None, None
        
        # Align with DataFrame index (skip rows with NaN in feature calc)
        df_clean = df.dropna()
        if len(df_clean) != len(states):
            # Truncate to match
            min_len = min(len(df_clean), len(states))
            df_clean = df_clean.iloc[-min_len:]
            states = states[-min_len:]
        
        return states, df_clean.index
