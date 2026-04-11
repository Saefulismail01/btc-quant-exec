"""
Layer 3 Alternative: XGBoost Direction Predictor
Faster training, handles class imbalance better than MLP
"""
import numpy as np
import pandas as pd
import pandas_ta as ta
import xgboost as xgb
from sklearn.preprocessing import StandardScaler
from typing import Tuple, Optional
import joblib
from pathlib import Path


class XGBoostSignalModel:
    """
    XGBoost-based next-candle direction predictor.
    Alternative to MLP with better handling of imbalanced classes.
    """
    
    MIN_ROWS = 60
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
        "volatility_20",
        "price_momentum",
    ]
    
    def __init__(self, model_path: Optional[str] = None):
        self.model: Optional[xgb.XGBClassifier] = None
        self.scaler = StandardScaler()
        self._is_trained = False
        self._last_trained_len = 0
        self.model_path = Path(model_path) if model_path else None
        
        if self.model_path and self.model_path.exists():
            self._load()
    
    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical features (same as MLP + extra)."""
        df = df.copy()
        
        # Basic features (same as MLP)
        df["rsi_14"] = ta.rsi(df["Close"], length=14)
        
        macd_df = ta.macd(df["Close"], fast=12, slow=26, signal=9)
        if macd_df is not None and "MACDh_12_26_9" in macd_df.columns:
            df["macd_hist"] = macd_df["MACDh_12_26_9"]
        else:
            df["macd_hist"] = 0.0
        
        ema20 = ta.ema(df["Close"], length=20)
        df["ema20_dist"] = (df["Close"] - ema20) / ema20
        
        df["log_return"] = np.log(df["Close"] / df["Close"].shift(1))
        
        atr = ta.atr(df["High"], df["Low"], df["Close"], length=14)
        df["norm_atr"] = atr / df["Close"]
        
        # Extra features for XGBoost
        df["volatility_20"] = df["log_return"].rolling(20).std()
        df["price_momentum"] = df["Close"].pct_change(periods=5)
        
        if "CVD" in df.columns:
            df["norm_cvd"] = df["CVD"] / df["Volume"]
        else:
            df["norm_cvd"] = 0.0
        
        df["funding"] = df.get("Funding", 0.0)
        
        if "OI" in df.columns:
            df["oi_change"] = df["OI"].pct_change().fillna(0.0)
        else:
            df["oi_change"] = 0.0
        
        return df
    
    def _create_target(self, df: pd.DataFrame, window: int = 1) -> pd.Series:
        """Create target labels."""
        df = df.copy()
        df["future_close"] = df["Close"].shift(-window)
        df["price_move_pct"] = (df["future_close"] - df["Close"]) / df["Close"]
        df["threshold"] = 0.5 * df["norm_atr"] * np.sqrt(window)
        
        move = df["price_move_pct"].values
        thr = df["threshold"].values
        
        labels = np.where(
            move > thr, 2,
            np.where(move < -thr, 0, 1)
        )
        
        labels = np.where(np.isnan(move) | np.isnan(thr), np.nan, labels)
        return pd.Series(labels, index=df.index)
    
    def train(self, df: pd.DataFrame) -> bool:
        """Train XGBoost model."""
        try:
            if len(df) < self.MIN_ROWS:
                print(f"[XGB] Insufficient data: {len(df)} < {self.MIN_ROWS}")
                return False
            
            df_feat = self._prepare_features(df)
            df_feat["target"] = self._create_target(df_feat)
            
            df_train = df_feat.dropna(subset=self.FEATURE_COLS + ["target"])
            
            if len(df_train) < 50:
                print(f"[XGB] Insufficient training rows: {len(df_train)}")
                return False
            
            X = df_train[self.FEATURE_COLS].values
            y = df_train["target"].values.astype(int)
            
            unique, counts = np.unique(y, return_counts=True)
            if len(unique) < 2:
                print(f"[XGB] Only {len(unique)} classes")
                return False
            
            # Scale
            X_scaled = self.scaler.fit_transform(X)
            
            # XGBoost with class balancing
            scale_pos_weight = dict(zip(unique, [max(counts) / c for c in counts]))
            
            self.model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.1,
                objective='multi:softprob',
                num_class=3,
                eval_metric='mlogloss',
                random_state=42,
                use_label_encoder=False,
            )
            
            self.model.fit(X_scaled, y)
            self._is_trained = True
            self._last_trained_len = len(df)
            
            print(f"[XGB] Trained on {len(df_train)} samples")
            
            if self.model_path:
                self._save()
            
            return True
            
        except Exception as e:
            print(f"[XGB] Train error: {e}")
            return False
    
    def predict(self, df: pd.DataFrame) -> Tuple[str, float, np.ndarray]:
        """Predict direction."""
        if not self._is_trained or self.model is None:
            return "NEUTRAL", 50.0, np.array([0.33, 0.34, 0.33])
        
        try:
            if len(df) - self._last_trained_len >= self.RETRAIN_EVERY:
                print("[XGB] Retraining...")
                self.train(df)
            
            df_feat = self._prepare_features(df)
            latest = df_feat[self.FEATURE_COLS].iloc[[-1]]
            
            if latest.isna().any().any():
                return "NEUTRAL", 50.0, np.array([0.33, 0.34, 0.33])
            
            X_latest = self.scaler.transform(latest.values)
            probs = self.model.predict_proba(X_latest)[0]
            
            prob_bear, prob_neut, prob_bull = probs[0], probs[1], probs[2]
            
            if prob_bull > prob_bear and prob_bull > prob_neut:
                bias, conf = "BULL", prob_bull * 100
            elif prob_bear > prob_bull and prob_bear > prob_neut:
                bias, conf = "BEAR", prob_bear * 100
            else:
                bias, conf = "NEUTRAL", max(prob_neut * 100, 50.0)
            
            return bias, round(conf, 1), probs
            
        except Exception as e:
            print(f"[XGB] Predict error: {e}")
            return "NEUTRAL", 50.0, np.array([0.33, 0.34, 0.33])
    
    def get_directional_vote(self, df: pd.DataFrame) -> float:
        """Return vote [-1.0, +1.0]."""
        bias, conf, _ = self.predict(df)
        
        if bias == "BULL":
            return (conf - 50) / 50
        elif bias == "BEAR":
            return -(conf - 50) / 50
        return 0.0
    
    def _save(self):
        try:
            if self.model_path:
                self.model_path.parent.mkdir(parents=True, exist_ok=True)
                joblib.dump({
                    "model": self.model,
                    "scaler": self.scaler,
                    "trained": self._is_trained,
                    "last_len": self._last_trained_len,
                }, self.model_path)
                print(f"[XGB] Model saved")
        except Exception as e:
            print(f"[XGB] Save error: {e}")
    
    def _load(self):
        try:
            data = joblib.load(self.model_path)
            self.model = data["model"]
            self.scaler = data["scaler"]
            self._is_trained = data["trained"]
            self._last_trained_len = data["last_len"]
            print(f"[XGB] Model loaded")
        except Exception as e:
            print(f"[XGB] Load error: {e}")
