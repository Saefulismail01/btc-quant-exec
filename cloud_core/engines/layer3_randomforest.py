"""
Layer 3 Alternative: Random Forest
Ensemble of decision trees, robust and interpretable
"""
import numpy as np
import pandas as pd
import pandas_ta as ta
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from typing import Tuple, Optional


class RandomForestSignalModel:
    """
    Random Forest-based direction predictor.
    Pros: Robust, less overfitting, feature importance
    """
    
    MIN_ROWS = 60
    FEATURE_COLS = ["rsi_14", "macd_hist", "ema20_dist", "log_return", "norm_atr", "volatility_20", "price_momentum"]
    
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
        
        # Extra features for RF
        df["volatility_20"] = df["log_return"].rolling(20).std()
        df["price_momentum"] = df["Close"].pct_change(periods=5)
        
        return df
    
    def train(self, df: pd.DataFrame) -> bool:
        """Train Random Forest"""
        try:
            if len(df) < self.MIN_ROWS:
                return False
            
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
            
            df_train = df_feat.dropna(subset=self.FEATURE_COLS + ["target"])
            
            if len(df_train) < 50:
                return False
            
            X = df_train[self.FEATURE_COLS].values
            y = df_train["target"].values.astype(int)
            
            # Check class distribution
            unique, counts = np.unique(y, return_counts=True)
            if len(unique) < 2:
                print(f"[RF] Only {len(unique)} classes")
                return False
            
            # Scale
            X_scaled = self.scaler.fit_transform(X)
            
            # Train Random Forest
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42,
                n_jobs=-1  # Use all cores
            )
            
            self.model.fit(X_scaled, y)
            self._is_trained = True
            
            # Print feature importance
            importances = dict(zip(self.FEATURE_COLS, self.model.feature_importances_))
            print(f"[RF] Trained. Feature importance: {importances}")
            return True
            
        except Exception as e:
            print(f"[RF] Train error: {e}")
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
            probs = self.model.predict_proba(X_latest)[0]
            
            # Map probabilities to classes
            classes = self.model.classes_
            prob_dict = {c: 0.0 for c in [0, 1, 2]}
            for i, c in enumerate(classes):
                prob_dict[c] = probs[i]
            
            prob_bear = prob_dict[0]
            prob_neut = prob_dict[1]
            prob_bull = prob_dict[2]
            
            if prob_bull > prob_bear and prob_bull > prob_neut:
                return "BULL", round(prob_bull * 100, 1), np.array([prob_bear, prob_neut, prob_bull])
            elif prob_bear > prob_bull and prob_bear > prob_neut:
                return "BEAR", round(prob_bear * 100, 1), np.array([prob_bear, prob_neut, prob_bull])
            else:
                return "NEUTRAL", round(max(prob_neut * 100, 50.0), 1), np.array([prob_bear, prob_neut, prob_bull])
                
        except Exception as e:
            print(f"[RF] Predict error: {e}")
            return "NEUTRAL", 50.0, np.array([0.33, 0.34, 0.33])
    
    def get_directional_vote(self, df: pd.DataFrame) -> float:
        """Return vote [-1.0, +1.0]"""
        bias, conf, _ = self.predict(df)
        
        if bias == "BULL":
            return (conf - 50) / 50
        elif bias == "BEAR":
            return -(conf - 50) / 50
        return 0.0
    
    def get_feature_importance(self) -> Optional[dict]:
        """Get feature importance if trained"""
        if not self._is_trained or self.model is None:
            return None
        return dict(zip(self.FEATURE_COLS, self.model.feature_importances_))
