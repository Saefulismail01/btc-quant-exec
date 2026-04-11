"""
Layer 3 Alternative: LSTM (Long Short-Term Memory)
Deep learning for time series sequence prediction
"""
import numpy as np
import pandas as pd
import pandas_ta as ta
from typing import Tuple, Optional
from sklearn.preprocessing import StandardScaler


class LSTMSignalModel:
    """
    LSTM-based next-candle direction predictor.
    Good for capturing temporal patterns in price data.
    """
    
    MIN_ROWS = 100  # LSTM needs more data
    SEQUENCE_LENGTH = 20  # Lookback window
    FEATURE_COLS = ["rsi_14", "macd_hist", "ema20_dist", "log_return", "norm_atr"]
    
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self._is_trained = False
    
    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical features"""
        df = df.copy()
        
        df["rsi_14"] = ta.rsi(df["Close"], length=14)
        
        macd_df = ta.macd(df["Close"], fast=12, slow=26, signal=9)
        df["macd_hist"] = macd_df["MACDh_12_26_9"] if macd_df is not None else 0.0
        
        ema20 = ta.ema(df["Close"], length=20)
        df["ema20_dist"] = (df["Close"] - ema20) / ema20
        df["log_return"] = np.log(df["Close"] / df["Close"].shift(1))
        
        atr = ta.atr(df["High"], df["Low"], df["Close"], length=14)
        df["norm_atr"] = atr / df["Close"]
        
        return df
    
    def _create_sequences(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Create sequences for LSTM input"""
        df_feat = self._prepare_features(df)
        
        # Target
        df_feat["future_close"] = df_feat["Close"].shift(-1)
        df_feat["price_move_pct"] = (df_feat["future_close"] - df_feat["Close"]) / df_feat["Close"]
        df_feat["threshold"] = 0.5 * df_feat["norm_atr"]
        
        move = df_feat["price_move_pct"].values
        thr = df_feat["threshold"].values
        labels = np.where(move > thr, 2, np.where(move < -thr, 0, 1))
        labels = np.where(np.isnan(move) | np.isnan(thr), np.nan, labels)
        df_feat["target"] = labels
        
        # Clean data
        df_clean = df_feat.dropna(subset=self.FEATURE_COLS + ["target"])
        
        if len(df_clean) < self.SEQUENCE_LENGTH + 10:
            return None, None
        
        # Scale
        features = df_clean[self.FEATURE_COLS].values
        features_scaled = self.scaler.fit_transform(features)
        
        # Create sequences
        X, y = [], []
        for i in range(self.SEQUENCE_LENGTH, len(features_scaled)):
            X.append(features_scaled[i - self.SEQUENCE_LENGTH:i])
            y.append(int(df_clean["target"].iloc[i]))
        
        return np.array(X), np.array(y)
    
    def train(self, df: pd.DataFrame) -> bool:
        """Train LSTM model"""
        try:
            # Try to use TensorFlow if available
            try:
                import tensorflow as tf
                from tensorflow.keras.models import Sequential
                from tensorflow.keras.layers import LSTM, Dense, Dropout
                from tensorflow.keras.optimizers import Adam
                TF_AVAILABLE = True
            except ImportError:
                print("[LSTM] TensorFlow not available, using fallback")
                TF_AVAILABLE = False
            
            if not TF_AVAILABLE:
                # Fallback: use simple heuristic
                self._is_trained = True
                return True
            
            X, y = self._create_sequences(df)
            if X is None or len(X) < 50:
                return False
            
            # Build LSTM
            self.model = Sequential([
                LSTM(64, return_sequences=True, input_shape=(self.SEQUENCE_LENGTH, len(self.FEATURE_COLS))),
                Dropout(0.2),
                LSTM(32, return_sequences=False),
                Dropout(0.2),
                Dense(16, activation="relu"),
                Dense(3, activation="softmax")  # Bear, Neutral, Bull
            ])
            
            self.model.compile(
                optimizer=Adam(learning_rate=0.001),
                loss="sparse_categorical_crossentropy",
                metrics=["accuracy"]
            )
            
            # Train
            self.model.fit(X, y, epochs=50, batch_size=32, verbose=0, validation_split=0.2)
            self._is_trained = True
            print(f"[LSTM] Trained on {len(X)} sequences")
            return True
            
        except Exception as e:
            print(f"[LSTM] Train error: {e}")
            return False
    
    def predict(self, df: pd.DataFrame) -> Tuple[str, float, np.ndarray]:
        """Predict direction"""
        if not self._is_trained:
            return "NEUTRAL", 50.0, np.array([0.33, 0.34, 0.33])
        
        try:
            # Prepare latest sequence
            df_feat = self._prepare_features(df)
            latest = df_feat[self.FEATURE_COLS].tail(self.SEQUENCE_LENGTH)
            
            if len(latest) < self.SEQUENCE_LENGTH or latest.isna().any().any():
                return "NEUTRAL", 50.0, np.array([0.33, 0.34, 0.33])
            
            # Scale
            X_latest = self.scaler.transform(latest.values)
            X_latest = X_latest.reshape(1, self.SEQUENCE_LENGTH, len(self.FEATURE_COLS))
            
            # Predict
            if self.model is not None:
                probs = self.model.predict(X_latest, verbose=0)[0]
            else:
                # Fallback heuristic
                returns = df["Close"].pct_change().tail(5)
                momentum = returns.mean()
                if momentum > 0.001:
                    probs = np.array([0.2, 0.3, 0.5])
                elif momentum < -0.001:
                    probs = np.array([0.5, 0.3, 0.2])
                else:
                    probs = np.array([0.33, 0.34, 0.33])
            
            prob_bear, prob_neut, prob_bull = probs[0], probs[1], probs[2]
            
            if prob_bull > prob_bear and prob_bull > prob_neut:
                return "BULL", round(prob_bull * 100, 1), probs
            elif prob_bear > prob_bull and prob_bear > prob_neut:
                return "BEAR", round(prob_bear * 100, 1), probs
            else:
                return "NEUTRAL", round(max(prob_neut * 100, 50.0), 1), probs
                
        except Exception as e:
            print(f"[LSTM] Predict error: {e}")
            return "NEUTRAL", 50.0, np.array([0.33, 0.34, 0.33])
    
    def get_directional_vote(self, df: pd.DataFrame) -> float:
        """Return vote [-1.0, +1.0]"""
        bias, conf, _ = self.predict(df)
        
        if bias == "BULL":
            return (conf - 50) / 50
        elif bias == "BEAR":
            return -(conf - 50) / 50
        return 0.0
