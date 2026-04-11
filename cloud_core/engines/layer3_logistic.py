"""
Layer 3: Logistic Regression with Polynomial Features
Simple linear model dengan feature expansion
"""
import numpy as np
import pandas as pd
import pandas_ta as ta
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.feature_selection import SelectKBest, f_classif
from typing import Tuple


class LogisticSignalModel:
    """
    Logistic Regression dengan polynomial features.
    Simpler than MLP, often more interpretable and stable.
    """
    
    MIN_ROWS = 80
    FEATURE_COLS = ["rsi_14", "macd_hist", "ema20_dist", "log_return", "norm_atr"]
    
    def __init__(self, confidence_threshold=0.60):
        self.model = None
        self.scaler = StandardScaler()
        self.poly = PolynomialFeatures(degree=2, include_bias=False)
        self.selector = SelectKBest(f_classif, k=10)
        self._is_trained = False
        self.confidence_threshold = confidence_threshold
    
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
    
    def train(self, df: pd.DataFrame) -> bool:
        """Train logistic regression"""
        try:
            if len(df) < self.MIN_ROWS:
                return False
            
            df_feat = self._prepare_features(df)
            
            # Target - 3 candles ahead
            df_feat["future_close"] = df_feat["Close"].shift(-3)
            df_feat["price_move_pct"] = (df_feat["future_close"] - df_feat["Close"]) / df_feat["Close"]
            df_feat["threshold"] = 0.5 * df_feat["norm_atr"]
            
            move = df_feat["price_move_pct"].values
            thr = df_feat["threshold"].values
            labels = np.where(move > thr, 2, np.where(move < -thr, 0, 1))
            labels = np.where(np.isnan(move) | np.isnan(thr), np.nan, labels)
            df_feat["target"] = labels
            
            df_train = df_feat.dropna(subset=self.FEATURE_COLS + ["target"])
            
            if len(df_train) < 50:
                return False
            
            X = df_train[self.FEATURE_COLS].values
            y = df_train["target"].values.astype(int)
            
            # Scale
            X_scaled = self.scaler.fit_transform(X)
            
            # Polynomial features
            X_poly = self.poly.fit_transform(X_scaled)
            
            # Feature selection
            X_selected = self.selector.fit_transform(X_poly, y)
            
            # Train Logistic Regression
            self.model = LogisticRegression(
                multi_class='multinomial',
                solver='lbfgs',
                max_iter=1000,
                C=1.0,  # Regularization
                random_state=42
            )
            
            self.model.fit(X_selected, y)
            self._is_trained = True
            
            print(f"[Logistic] Trained on {len(df_train)} samples, features: {X_selected.shape[1]}")
            return True
            
        except Exception as e:
            print(f"[Logistic] Train error: {e}")
            return False
    
    def predict(self, df: pd.DataFrame) -> Tuple[str, float, np.ndarray]:
        """Predict direction"""
        if not self._is_trained or self.model is None:
            return "NEUTRAL", 50.0, np.array([0.33, 0.34, 0.33])
        
        try:
            df_feat = self._prepare_features(df)
            latest = df_feat[self.FEATURE_COLS].iloc[[-1]]
            
            if latest.isna().any().any():
                return "NEUTRAL", 50.0, np.array([0.33, 0.34, 0.33])
            
            X_latest = self.scaler.transform(latest.values)
            X_poly = self.poly.transform(X_latest)
            X_selected = self.selector.transform(X_poly)
            
            probs = self.model.predict_proba(X_selected)[0]
            
            prob_bear, prob_neut, prob_bull = probs[0], probs[1], probs[2]
            
            # Confidence thresholding
            max_prob = max(prob_bear, prob_neut, prob_bull)
            
            if max_prob < self.confidence_threshold:
                return "NEUTRAL", round(max_prob * 100, 1), probs
            
            if prob_bull > prob_bear and prob_bull > prob_neut:
                return "BULL", round(prob_bull * 100, 1), probs
            elif prob_bear > prob_bull and prob_bear > prob_neut:
                return "BEAR", round(prob_bear * 100, 1), probs
            else:
                return "NEUTRAL", round(prob_neut * 100, 1), probs
                
        except Exception as e:
            print(f"[Logistic] Predict error: {e}")
            return "NEUTRAL", 50.0, np.array([0.33, 0.34, 0.33])
    
    def get_directional_vote(self, df: pd.DataFrame) -> float:
        """Return vote [-1.0, +1.0]"""
        bias, conf, _ = self.predict(df)
        
        if bias == "BULL":
            return (conf - 50) / 50
        elif bias == "BEAR":
            return -(conf - 50) / 50
        return 0.0
