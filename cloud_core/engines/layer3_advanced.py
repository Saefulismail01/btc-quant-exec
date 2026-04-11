"""
Layer 3 Advanced: Improved Feature Engineering + Confidence Filtering
Optimized untuk win rate > 60%
"""
import numpy as np
import pandas as pd
import pandas_ta as ta
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from typing import Tuple, Optional


class AdvancedSignalModel:
    """
    Advanced model dengan:
    - 15+ engineered features
    - Confidence-based filtering
    - Walk-forward aware training
    - Optimized untuk high win rate
    """
    
    MIN_ROWS = 100
    CONFIDENCE_THRESHOLD = 0.65  # Only trade when confidence > 65%
    
    FEATURE_COLS = [
        # Price action
        "rsi_14", "rsi_7", "rsi_slope",
        "macd_hist", "macd_signal_dist",
        "ema20_dist", "ema50_dist", "ema_ratio",
        "bb_position", "bb_width",
        # Volatility
        "atr_norm", "volatility_regime",
        # Momentum
        "mom_10", "mom_20", "price_accel",
        # Volume (if available)
        "volume_ratio", "obv_slope",
        # Trend strength
        "adx", "di_plus", "di_minus",
        # Candle patterns
        "body_ratio", "upper_shadow", "lower_shadow"
    ]
    
    def __init__(self, model_type='gbm'):
        self.model_type = model_type
        self.model = None
        self.scaler = StandardScaler()
        self._is_trained = False
        self.feature_importance = {}
    
    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Advanced feature engineering"""
        df = df.copy()
        
        # RSI dengan multiple timeframes
        df["rsi_14"] = ta.rsi(df["Close"], length=14)
        df["rsi_7"] = ta.rsi(df["Close"], length=7)
        df["rsi_slope"] = df["rsi_14"].diff(3)  # RSI momentum
        
        # MACD advanced
        macd_df = ta.macd(df["Close"], fast=12, slow=26, signal=9)
        if macd_df is not None:
            df["macd_hist"] = macd_df["MACDh_12_26_9"]
            df["macd_signal_dist"] = macd_df["MACD_12_26_9"] - macd_df["MACDs_12_26_9"]
        else:
            df["macd_hist"] = 0
            df["macd_signal_dist"] = 0
        
        # EMA distances
        ema20 = ta.ema(df["Close"], length=20)
        ema50 = ta.ema(df["Close"], length=50)
        df["ema20_dist"] = (df["Close"] - ema20) / ema20
        df["ema50_dist"] = (df["Close"] - ema50) / ema50
        df["ema_ratio"] = ema20 / ema50
        
        # Bollinger Bands
        bb = ta.bbands(df["Close"], length=20, std=2)
        if bb is not None and len(bb.columns) >= 3:
            lower_col = [c for c in bb.columns if 'BBL' in c or 'lower' in c.lower()][0] if any('BBL' in c for c in bb.columns) else bb.columns[0]
            upper_col = [c for c in bb.columns if 'BBU' in c or 'upper' in c.lower()][0] if any('BBU' in c for c in bb.columns) else bb.columns[2]
            middle_col = [c for c in bb.columns if 'BBM' in c or 'mid' in c.lower()][0] if any('BBM' in c for c in bb.columns) else bb.columns[1]
            
            lower = bb[lower_col]
            upper = bb[upper_col]
            middle = bb[middle_col]
            
            df["bb_position"] = (df["Close"] - lower) / (upper - lower).replace(0, 0.0001)
            df["bb_width"] = (upper - lower) / middle.replace(0, 0.0001)
        else:
            df["bb_position"] = 0.5
            df["bb_width"] = 0.1
        
        # Volatility
        atr = ta.atr(df["High"], df["Low"], df["Close"], length=14)
        df["atr_norm"] = atr / df["Close"]
        df["volatility_regime"] = df["atr_norm"] > df["atr_norm"].rolling(50).mean()
        
        # Momentum
        df["mom_10"] = df["Close"].pct_change(periods=10)
        df["mom_20"] = df["Close"].pct_change(periods=20)
        df["price_accel"] = df["mom_10"] - df["mom_10"].shift(5)
        
        # Volume features
        if "Volume" in df.columns:
            df["volume_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()
            obv = ta.obv(df["Close"], df["Volume"])
            df["obv_slope"] = obv.diff(5) / obv.rolling(20).mean()
        else:
            df["volume_ratio"] = 1.0
            df["obv_slope"] = 0.0
        
        # ADX - Trend strength
        try:
            adx_df = ta.adx(df["High"], df["Low"], df["Close"], length=14)
            if adx_df is not None and len(adx_df.columns) >= 3:
                # Get values by position (safer than column names)
                df["adx"] = adx_df.iloc[:, 0]  # ADX
                df["di_plus"] = adx_df.iloc[:, 1]  # DI+
                df["di_minus"] = adx_df.iloc[:, 2]  # DI-
            else:
                df["adx"] = 25
                df["di_plus"] = 20
                df["di_minus"] = 20
        except Exception:
            df["adx"] = 25
            df["di_plus"] = 20
            df["di_minus"] = 20
        
        # Candlestick patterns
        body = df["Close"] - df["Open"]
        range_ = df["High"] - df["Low"]
        df["body_ratio"] = abs(body) / range_.replace(0, 0.0001)
        df["upper_shadow"] = (df["High"] - df[["Close", "Open"]].max(axis=1)) / range_.replace(0, 0.0001)
        df["lower_shadow"] = (df[["Close", "Open"]].min(axis=1) - df["Low"]) / range_.replace(0, 0.0001)
        
        return df
    
    def train(self, df: pd.DataFrame) -> bool:
        """Train dengan target yang lebih optimalkan"""
        try:
            if len(df) < self.MIN_ROWS:
                return False
            
            df_feat = self._prepare_features(df)
            
            # Target: Direction dengan lookahead 3 candles (12h untuk 4h timeframe)
            df_feat["future_close"] = df_feat["Close"].shift(-3)
            df_feat["price_move_pct"] = (df_feat["future_close"] - df_feat["Close"]) / df_feat["Close"]
            
            # Dynamic threshold: lebih sensitif di low volatility, lebih strict di high volatility
            df_feat["threshold"] = np.where(
                df_feat["volatility_regime"],
                0.8 * df_feat["atr_norm"],  # High vol: stricter
                0.4 * df_feat["atr_norm"]   # Low vol: looser
            )
            
            move = df_feat["price_move_pct"].values
            thr = df_feat["threshold"].values
            
            # Labels: 2=Bull, 0=Bear, 1=Neutral
            labels = np.where(move > thr, 2, np.where(move < -thr, 0, 1))
            labels = np.where(np.isnan(move) | np.isnan(thr), np.nan, labels)
            df_feat["target"] = labels
            
            df_train = df_feat.dropna(subset=self.FEATURE_COLS + ["target"])
            
            if len(df_train) < 100:
                return False
            
            X = df_train[self.FEATURE_COLS].values
            y = df_train["target"].values.astype(int)
            
            # Check class distribution
            unique, counts = np.unique(y, return_counts=True)
            print(f"[Advanced] Class distribution: {dict(zip(unique, counts))}")
            
            # Scale
            X_scaled = self.scaler.fit_transform(X)
            
            # Train model
            if self.model_type == 'gbm':
                self.model = GradientBoostingClassifier(
                    n_estimators=200,
                    max_depth=5,
                    learning_rate=0.05,
                    min_samples_split=10,
                    random_state=42
                )
            else:
                self.model = RandomForestClassifier(
                    n_estimators=200,
                    max_depth=8,
                    min_samples_split=5,
                    random_state=42,
                    n_jobs=-1
                )
            
            self.model.fit(X_scaled, y)
            self._is_trained = True
            
            # Store feature importance
            if hasattr(self.model, 'feature_importances_'):
                self.feature_importance = dict(zip(self.FEATURE_COLS, self.model.feature_importances_))
                print(f"[Advanced] Trained. Top features: {sorted(self.feature_importance.items(), key=lambda x: -x[1])[:5]}")
            
            return True
            
        except Exception as e:
            print(f"[Advanced] Train error: {e}")
            return False
    
    def predict(self, df: pd.DataFrame) -> Tuple[str, float, np.ndarray]:
        """Predict dengan confidence"""
        if not self._is_trained or self.model is None:
            return "NEUTRAL", 50.0, np.array([0.33, 0.34, 0.33])
        
        try:
            df_feat = self._prepare_features(df)
            latest = df_feat[self.FEATURE_COLS].iloc[[-1]]
            
            if latest.isna().any().any():
                return "NEUTRAL", 50.0, np.array([0.33, 0.34, 0.33])
            
            X_latest = self.scaler.transform(latest.values)
            probs = self.model.predict_proba(X_latest)[0]
            
            prob_bear, prob_neut, prob_bull = probs[0], probs[1], probs[2]
            
            # Confidence thresholding
            max_prob = max(prob_bear, prob_neut, prob_bull)
            
            if max_prob < self.CONFIDENCE_THRESHOLD:
                return "NEUTRAL", round(max_prob * 100, 1), np.array([prob_bear, prob_neut, prob_bull])
            
            if prob_bull > prob_bear and prob_bull > prob_neut:
                return "BULL", round(prob_bull * 100, 1), probs
            elif prob_bear > prob_bull and prob_bear > prob_neut:
                return "BEAR", round(prob_bear * 100, 1), probs
            else:
                return "NEUTRAL", round(prob_neut * 100, 1), probs
                
        except Exception as e:
            print(f"[Advanced] Predict error: {e}")
            return "NEUTRAL", 50.0, np.array([0.33, 0.34, 0.33])
    
    def get_directional_vote(self, df: pd.DataFrame) -> float:
        """Return vote dengan confidence weighting"""
        bias, conf, _ = self.predict(df)
        
        if bias == "BULL":
            return (conf - 50) / 50
        elif bias == "BEAR":
            return -(conf - 50) / 50
        return 0.0
    
    def should_trade(self, df: pd.DataFrame) -> Tuple[bool, str, float]:
        """High-level: should we trade? Returns (should_trade, direction, confidence)"""
        bias, conf, probs = self.predict(df)
        
        if bias == "NEUTRAL":
            return False, "NEUTRAL", conf
        
        # Additional filters
        df_feat = self._prepare_features(df)
        latest = df_feat.iloc[-1]
        
        # Don't trade if ADX < 20 (no clear trend)
        if latest["adx"] < 20:
            return False, "NO_TREND", conf
        
        # Don't trade if BB width too high (choppy market)
        if latest["bb_width"] > 0.1:
            return False, "CHOPPY", conf
        
        return True, bias, conf
