"""
Layer 3: MLP Neural Network - Next-Candle Direction Predictor
"""
import numpy as np
import pandas as pd
import pandas_ta as ta
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from typing import Tuple, Optional
import joblib
from pathlib import Path


class MLPSignalModel:
    """
    MLP-based next-candle direction predictor.
    
    Features: RSI, MACD, EMA distance, log returns, normalized ATR, CVD, funding, OI
    Target: Forward return (Bull/Neutral/Bear)
    """
    
    MIN_ROWS = 60
    HIDDEN_LAYERS = (128, 64)
    MAX_ITER = 300
    RANDOM_STATE = 42
    RETRAIN_EVERY = 48  # candles
    
    FEATURE_COLS = [
        "rsi_14",
        "macd_hist",
        "ema20_dist",
        "log_return",
        "norm_atr",
        "norm_cvd",
        "funding",
        "oi_change",
    ]
    
    def __init__(self, model_path: Optional[str] = None):
        self.model: Optional[MLPClassifier] = None
        self.scaler = StandardScaler()
        self._is_trained = False
        self._last_trained_len = 0
        self.model_path = Path(model_path) if model_path else None
        
        # Try load existing model
        if self.model_path and self.model_path.exists():
            self._load()
    
    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical features."""
        df = df.copy()
        
        # RSI
        df["rsi_14"] = ta.rsi(df["Close"], length=14)
        
        # MACD histogram
        macd_df = ta.macd(df["Close"], fast=12, slow=26, signal=9)
        if macd_df is not None and "MACDh_12_26_9" in macd_df.columns:
            df["macd_hist"] = macd_df["MACDh_12_26_9"]
        else:
            df["macd_hist"] = 0.0
        
        # EMA distance
        ema20 = ta.ema(df["Close"], length=20)
        df["ema20_dist"] = (df["Close"] - ema20) / ema20
        
        # Log returns
        df["log_return"] = np.log(df["Close"] / df["Close"].shift(1))
        
        # Normalized ATR
        atr = ta.atr(df["High"], df["Low"], df["Close"], length=14)
        df["norm_atr"] = atr / df["Close"]
        
        # CVD (Cumulative Volume Delta) - if available
        if "CVD" in df.columns:
            df["norm_cvd"] = df["CVD"] / df["Volume"]
        else:
            df["norm_cvd"] = 0.0
        
        # Funding rate - if available
        df["funding"] = df.get("Funding", 0.0)
        
        # Open Interest change - if available
        if "OI" in df.columns:
            df["oi_change"] = df["OI"].pct_change().fillna(0.0)
        else:
            df["oi_change"] = 0.0
        
        return df
    
    def _create_target(self, df: pd.DataFrame, window: int = 1) -> pd.Series:
        """
        Create target labels based on forward returns.
        
        Classes:
            2 = Bull (forward return > threshold)
            1 = Neutral
            0 = Bear (forward return < -threshold)
        """
        df = df.copy()
        
        # Forward return
        df["future_close"] = df["Close"].shift(-window)
        df["price_move_pct"] = (df["future_close"] - df["Close"]) / df["Close"]
        
        # Dynamic threshold based on volatility
        df["threshold"] = 0.5 * df["norm_atr"] * np.sqrt(window)
        
        # Vectorized label assignment
        move = df["price_move_pct"].values
        thr = df["threshold"].values
        
        labels = np.where(
            move > thr, 2,  # Bull
            np.where(move < -thr, 0, 1)  # Bear : Neutral
        )
        
        # Handle NaN
        labels = np.where(
            np.isnan(move) | np.isnan(thr),
            np.nan,
            labels
        )
        
        return pd.Series(labels, index=df.index)
    
    def train(self, df: pd.DataFrame) -> bool:
        """
        Train MLP model on historical data.
        
        Args:
            df: OHLCV DataFrame
        
        Returns:
            True if trained successfully
        """
        try:
            if len(df) < self.MIN_ROWS:
                print(f"[MLP] Insufficient data: {len(df)} < {self.MIN_ROWS}")
                return False
            
            # Prepare features
            df_feat = self._prepare_features(df)
            df_feat["target"] = self._create_target(df_feat)
            
            # Drop rows with NaN
            df_train = df_feat.dropna(subset=self.FEATURE_COLS + ["target"])
            
            if len(df_train) < 50:
                print(f"[MLP] Insufficient training rows after cleaning: {len(df_train)}")
                return False
            
            X = df_train[self.FEATURE_COLS].values
            y = df_train["target"].values.astype(int)
            
            # Check class distribution
            unique, counts = np.unique(y, return_counts=True)
            if len(unique) < 2:
                print(f"[MLP] Only {len(unique)} classes present, need at least 2")
                return False
            
            # Scale features
            X_scaled = self.scaler.fit_transform(X)
            
            # Train MLP dengan parameter yang lebih stabil
            self.model = MLPClassifier(
                hidden_layer_sizes=(32, 16),  # Simpler architecture
                activation="tanh",  # More stable than relu
                solver="adam",
                max_iter=500,  # More iterations
                early_stopping=True,
                validation_fraction=0.2,
                n_iter_no_change=20,  # Patience for early stopping
                learning_rate_init=0.001,  # Lower learning rate
                alpha=0.01,  # L2 regularization
                random_state=self.RANDOM_STATE,
                verbose=False,
            )
            
            self.model.fit(X_scaled, y)
            self._is_trained = True
            self._last_trained_len = len(df)
            
            print(f"[MLP] Trained on {len(df_train)} samples, classes: {dict(zip(unique, counts))}")
            
            # Save model
            if self.model_path:
                self._save()
            
            return True
            
        except Exception as e:
            print(f"[MLP] Train error: {e}")
            return False
    
    def predict(self, df: pd.DataFrame) -> Tuple[str, float, np.ndarray]:
        """
        Predict direction for latest candle.
        
        Args:
            df: OHLCV DataFrame
        
        Returns:
            (bias, confidence, probabilities)
            bias: "BULL", "BEAR", or "NEUTRAL"
            confidence: 50.0 to 100.0
            probabilities: [P(Bear), P(Neutral), P(Bull)]
        """
        if not self._is_trained or self.model is None:
            print("[MLP] Model not trained")
            return "NEUTRAL", 50.0, np.array([0.33, 0.34, 0.33])
        
        try:
            # Check if retrain needed
            if len(df) - self._last_trained_len >= self.RETRAIN_EVERY:
                print("[MLP] Retraining due to new data...")
                self.train(df)
            
            # Prepare latest features
            df_feat = self._prepare_features(df)
            latest = df_feat[self.FEATURE_COLS].iloc[[-1]]
            
            if latest.isna().any().any():
                print("[MLP] NaN in latest features")
                return "NEUTRAL", 50.0, np.array([0.33, 0.34, 0.33])
            
            # Scale
            X_latest = self.scaler.transform(latest.values)
            
            # Predict probabilities
            probs = self.model.predict_proba(X_latest)[0]
            
            # Map to classes (model.classes_ tells us order)
            class_map = {c: i for i, c in enumerate(self.model.classes_)}
            
            prob_bear = probs[class_map.get(0, 0)] if 0 in class_map else 0.0
            prob_neut = probs[class_map.get(1, 1)] if 1 in class_map else 0.0
            prob_bull = probs[class_map.get(2, 2)] if 2 in class_map else 0.0
            
            # Decision
            if prob_bull > prob_bear and prob_bull > prob_neut:
                bias, conf = "BULL", prob_bull * 100
            elif prob_bear > prob_bull and prob_bear > prob_neut:
                bias, conf = "BEAR", prob_bear * 100
            else:
                bias, conf = "NEUTRAL", max(prob_neut * 100, 50.0)
            
            return bias, round(conf, 1), np.array([prob_bear, prob_neut, prob_bull])
            
        except Exception as e:
            print(f"[MLP] Predict error: {e}")
            return "NEUTRAL", 50.0, np.array([0.33, 0.34, 0.33])
    
    def get_directional_vote(self, df: pd.DataFrame) -> float:
        """
        Return directional vote [-1.0, +1.0].
        
        Formula: P(Bull) - P(Bear)
        """
        bias, conf, probs = self.predict(df)
        
        if bias == "BULL":
            # Scale 50-100 to 0-1
            return (conf - 50) / 50  # 0 to 1.0
        elif bias == "BEAR":
            return -(conf - 50) / 50  # -1.0 to 0
        else:
            return 0.0
    
    def _save(self):
        """Save model and scaler."""
        try:
            if self.model_path:
                self.model_path.parent.mkdir(parents=True, exist_ok=True)
                joblib.dump({
                    "model": self.model,
                    "scaler": self.scaler,
                    "trained": self._is_trained,
                    "last_len": self._last_trained_len,
                }, self.model_path)
                print(f"[MLP] Model saved to {self.model_path}")
        except Exception as e:
            print(f"[MLP] Save error: {e}")
    
    def _load(self):
        """Load model and scaler."""
        try:
            data = joblib.load(self.model_path)
            self.model = data["model"]
            self.scaler = data["scaler"]
            self._is_trained = data["trained"]
            self._last_trained_len = data["last_len"]
            print(f"[MLP] Model loaded from {self.model_path}")
        except Exception as e:
            print(f"[MLP] Load error: {e}")
