"""
╔══════════════════════════════════════════════════════════════╗
║  BTC-QUANT-BTC: LAYER 3 — AI SIGNAL INTELLIGENCE               ║
║  MLP Neural Network · Next-Candle Direction Predictor         ║
║  Stack: sklearn MLPClassifier + pandas_ta + numpy             ║
║                                                              ║
║  HOTFIX  2026-02-27: Scaler contamination / data leakage fix  ║
║  PHASE 3 2026-02-27: HMM→MLP Feature Cross                  ║
║    prepare_data() now accepts optional hmm_states array.     ║
║    If provided, one-hot encodes 4 regime states as extra     ║
║    features: hmm_state_0 … hmm_state_3 (total features: 9)  ║
║    MLP architecture auto-scales input size accordingly.      ║
╚══════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import hashlib
import logging
import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pandas_ta as ta
from sklearn.neural_network import MLPClassifier

logger = logging.getLogger(__name__)

_BACKEND_DIR = str(Path(__file__).resolve().parent.parent.parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from utils.scaler_manager import get_scaler  # noqa: E402


# ════════════════════════════════════════════════════════════
#  CONSTANTS
# ════════════════════════════════════════════════════════════

MIN_ROWS = 60
MLP_HIDDEN_LAYERS_BASE    = (128, 64)   # Used when NO HMM features (8 inputs)
MLP_HIDDEN_LAYERS_CROSS   = (256, 128)  # Used WITH HMM features (12 inputs)
MLP_ACTIVATION   = "relu"
MLP_SOLVER       = "adam"
MLP_MAX_ITER     = 300
MLP_RANDOM_STATE = 42

MLP_RETRAIN_EVERY_N_CANDLES   = 48    # time-based retrain fallback
MLP_VOL_SPIKE_RETRAIN_RATIO   = 2.0   # [FIX-5b] retrain if current_vol/long_run_vol > 2x
MLP_FORWARD_RETURN_WINDOW     = 1     # [OPT-A] 1-candle (4H) target — analisis data: trade hold<=2c WR=65.3% avg=$47, hold>2c WR=46.8% avg=-$27. Window 3 terlalu lambat untuk scalping 4H.
FALLBACK_RESULT  = ("NEUTRAL", 50.0)

# Persistence paths
_MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "infrastructure" / "model_cache"
_MLP_MODEL_PATH  = _MODEL_DIR / "mlp_model.joblib"
_MLP_SCALER_PATH = _MODEL_DIR / "mlp_scaler.joblib"
_MLP_META_PATH   = _MODEL_DIR / "mlp_meta.joblib"

N_HMM_STATES = 4   # Must match layer1_hmm.N_STATES

# [FIX-5a] fgi DIHAPUS — autocorrelation palsu di 4H timeframe
_TECH_FEATURE_COLS = [
    "rsi_14",
    "macd_hist",
    "ema20_dist",
    "log_return",
    "norm_atr",
    "norm_cvd",
    "funding",
    "oi_change",
    # "fgi" REMOVED [FIX-5a]: FGI update harian, tapi MLP di 4H.
    # Nilai sama di 6 candle berturut = autocorrelation palsu.
    # FGI tetap dipakai sebagai sentiment_adj di signal_service.
]

# One-hot HMM feature columns (4) — added when hmm_states provided
_HMM_FEATURE_COLS = [f"hmm_state_{i}" for i in range(N_HMM_STATES)]

# Combined (9) — used when cross-feature is active
_ALL_FEATURE_COLS = _TECH_FEATURE_COLS + _HMM_FEATURE_COLS


# ════════════════════════════════════════════════════════════
#  SIGNAL INTELLIGENCE MODEL
# ════════════════════════════════════════════════════════════

class SignalIntelligenceModel:
    """
    MLP-based next-candle direction predictor.

    HOTFIX: Scaler contamination fixed — X_train and X_latest scaled separately.

    PHASE 3: HMM→MLP Feature Cross.
        - prepare_data() accepts optional hmm_states: np.ndarray (int, shape n)
          aligned to df.index after HMM feature dropna.
        - If provided, one-hot encodes regime as 4 additional binary features.
        - MLP input size: 5 (tech only) or 9 (tech + HMM regime).
        - Architecture scales with input: (64,32) base or (128,64) with cross.
        - is_cross_enabled flag tracks whether cross features are active.
    """

    def __init__(self):
        self.model: MLPClassifier | None = None
        self.scaler = get_scaler("mlp")
        self.is_cross_enabled: bool = False   # PHASE 3: True when HMM features used
        
        # Caching state
        self._is_trained: bool = False
        self._last_trained_len: int = 0
        self._data_hash: str = ""

        # Try to load persisted model from disk
        self._load_from_disk()

    # ────────────────────────────────────────────────────────
    #  PERSISTENCE
    # ────────────────────────────────────────────────────────

    def _compute_data_hash(self, df: pd.DataFrame) -> str:
        """Lightweight fingerprint of OHLCV data for cache invalidation."""
        key = f"{len(df)}_{df['Close'].iloc[-1]}_{df['Close'].iloc[0]}_{df.index[-1]}"
        return hashlib.md5(key.encode()).hexdigest()[:12]

    def _save_to_disk(self):
        """Persist model, scaler, and metadata via joblib."""
        try:
            _MODEL_DIR.mkdir(parents=True, exist_ok=True)
            joblib.dump(self.model, _MLP_MODEL_PATH)
            # Scaler may contain a threading lock — save only the fitted params
            try:
                joblib.dump(self.scaler, _MLP_SCALER_PATH)
            except (TypeError, AttributeError):
                # If scaler has unpicklable attrs (RLock), skip scaler persistence
                pass
            meta = {
                "is_trained": self._is_trained,
                "last_trained_len": self._last_trained_len,
                "data_hash": self._data_hash,
                "is_cross_enabled": bool(self.is_cross_enabled),
                "feature_signature": _ALL_FEATURE_COLS if self.is_cross_enabled else _TECH_FEATURE_COLS,
            }
            joblib.dump(meta, _MLP_META_PATH)
            logger.debug(f"[MLP] Model persisted to {_MODEL_DIR}")
        except Exception as exc:
            logger.debug(f"[MLP] Persist skipped: {exc}")

    def _load_from_disk(self):
        """Load persisted model if available."""
        try:
            if _MLP_MODEL_PATH.exists() and _MLP_META_PATH.exists() and _MLP_SCALER_PATH.exists():
                self.model = joblib.load(_MLP_MODEL_PATH)
                self.scaler = joblib.load(_MLP_SCALER_PATH)
                meta = joblib.load(_MLP_META_PATH)
                self._is_trained = meta.get("is_trained", False)
                self._last_trained_len = meta.get("last_trained_len", 0)
                self._data_hash = meta.get("data_hash", "")
                self.is_cross_enabled = meta.get("is_cross_enabled", False)
                
                # Signature check — if features changed, invalidate cache
                cached_sig = meta.get("feature_signature", [])
                current_sig = _ALL_FEATURE_COLS if self.is_cross_enabled else _TECH_FEATURE_COLS
                if cached_sig != current_sig:
                    logger.info(f"[MLP] Cache signature mismatch. Forcing retrain.")
                    self.model = None
                    self._is_trained = False
                else:
                    logger.info(f"[MLP] Loaded persisted model (trained_len={self._last_trained_len})")
            elif _MLP_MODEL_PATH.exists() or _MLP_META_PATH.exists() or _MLP_SCALER_PATH.exists():
                logger.info("[MLP] Incomplete persisted artifacts detected. Forcing retrain.")
                self.model = None
                self._is_trained = False
        except Exception as exc:
            logger.warning(f"[MLP] Failed to load persisted model: {exc!r}")
            self.model = None
            self._is_trained = False

    def cache_info(self) -> dict:
        """Return MLP training cache status."""
        return {
            "engine": "MLP",
            "is_trained": self._is_trained,
            "last_trained_len": self._last_trained_len,
            "data_hash": self._data_hash,
            "retrain_every_n": MLP_RETRAIN_EVERY_N_CANDLES,
            "model_persisted": _MLP_MODEL_PATH.exists(),
            "is_cross_enabled": self.is_cross_enabled,
        }

    # ────────────────────────────────────────────────────────
    #  STEP 1: FEATURE ENGINEERING
    # ────────────────────────────────────────────────────────

    def prepare_data(
        self,
        df: pd.DataFrame,
        hmm_states: np.ndarray | None = None,
        hmm_index: pd.Index | None    = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, pd.DataFrame]:
        """
        Calculate features and target from OHLCV.
        Optionally injects one-hot HMM regime features (PHASE 3 cross-feature).

        Args:
            df:         OHLCV DataFrame
            hmm_states: Optional int array of HMM state IDs from layer1_hmm.
                        Shape (n,) aligned to hmm_index.
                        If None, model uses 5 technical features only.
            hmm_index:  pd.Index of the rows corresponding to hmm_states.
                        Must be provided together with hmm_states.

        Returns:
            (X_train_raw, Y, X_latest_raw, df_train)
            X_train_raw:  Raw features for training rows — shape (n-1, 5 or 9)
            Y:            Binary target (0/1) for training rows
            X_latest_raw: Raw features for last row (inference) — shape (1, 5 or 9)
            df_train:     DataFrame of training rows with all features

        PHASE 3 alignment logic:
            HMM and MLP have different valid-row windows after rolling dropna.
            The intersection of their indices is used to align HMM states
            to MLP feature rows. Rows not present in hmm_index get
            hmm_state = -1 (all-zero one-hot) as a safe fallback.
        """
        df_feat = df.copy()

        # ── Technical features ──────────────────────────────────────────────
        df_feat["rsi_14"] = ta.rsi(df_feat["Close"], length=14)

        macd_df = ta.macd(df_feat["Close"], fast=12, slow=26, signal=9)
        if macd_df is not None and "MACDh_12_26_9" in macd_df.columns:
            df_feat["macd_hist"] = macd_df["MACDh_12_26_9"]
        else:
            df_feat["macd_hist"] = 0.0

        ema20 = ta.ema(df_feat["Close"], length=20)
        df_feat["ema20_dist"] = (df_feat["Close"] - ema20) / ema20

        df_feat["log_return"] = np.log(df_feat["Close"] / df_feat["Close"].shift(1))

        atr = ta.atr(df_feat["High"], df_feat["Low"], df_feat["Close"], length=14)
        df_feat["norm_atr"] = atr / df_feat["Close"]

        # ── Microstructure features ─────────────────────────────────────────
        # CVD is already in df_feat (from repository join)
        df_feat["norm_cvd"] = df_feat["CVD"] / df_feat["Volume"] if "CVD" in df_feat.columns else 0.0
        df_feat["funding"]  = df_feat["Funding"] if "Funding" in df_feat.columns else 0.0
        if "OI" in df_feat.columns:
            df_feat["oi_change"] = df_feat["OI"].pct_change().fillna(0.0)
        else:
            df_feat["oi_change"] = 0.0

        # [FIX-5a] fgi dihapus dari fitur MLP

        # ── SMART TARGET: FORWARD RETURN [FIX-5c] ───────────────────────────
        # Ganti next-1-candle ke forward N-candle return.
        # N=3 (12 jam di 4H) memberi lebih banyak candle melewati threshold,
        # sehingga distribusi Bull/Bear/Neutral lebih balanced untuk training.
        # Threshold diskala dengan sqrt(N) sesuai teori random walk.
        W = MLP_FORWARD_RETURN_WINDOW
        df_feat["future_close"]    = df_feat["Close"].shift(-W)
        df_feat["price_move_pct"]  = (
            (df_feat["future_close"] - df_feat["Close"]) / df_feat["Close"]
        )
        # ── SMART TARGET: FORWARD RETURN [FIX-5c] — VECTORIZED [FIX-OPT-3] ──
        # Previously used .apply(_get_smart_label, axis=1) — Python loop per row.
        # Now uses numpy vectorized ops: identical logic, ~50-100× faster.
        df_feat["target_threshold"] = 0.5 * df_feat["norm_atr"] * (W ** 0.5)
        _move  = df_feat["price_move_pct"].values
        _thr   = df_feat["target_threshold"].values
        _nan   = np.isnan(_move) | np.isnan(_thr)
        _label = np.where(_move > _thr, 2,            # BULL
                 np.where(_move < -_thr, 0, 1))       # BEAR else NEUTRAL
        _label = _label.astype(float)
        _label[_nan] = np.nan
        df_feat["target"] = _label


        # ── PHASE 3: Inject HMM one-hot features ────────────────────────────
        use_cross = (
            hmm_states is not None
            and hmm_index is not None
            and len(hmm_states) == len(hmm_index)
        )

        if use_cross:
            # Build a Series mapping index → state_id
            state_series = pd.Series(
                hmm_states,
                index=hmm_index,
                name="hmm_state_id",
            )

            # Align to df_feat index; rows not in hmm_index → state -1 (unknown)
            aligned_states = state_series.reindex(df_feat.index, fill_value=-1)

            # One-hot encode: state 0–3 → columns hmm_state_0 … hmm_state_3
            # State -1 (unknown/not in HMM window) → all zeros (safe fallback)
            for i in range(N_HMM_STATES):
                df_feat[f"hmm_state_{i}"] = (aligned_states == i).astype(float)

            active_feat_cols = _ALL_FEATURE_COLS    # 9 features
            self.is_cross_enabled = True
        else:
            active_feat_cols      = _TECH_FEATURE_COLS  # 5 features
            self.is_cross_enabled = False

        # ── Extract last row for inference BEFORE dropna ─────────────────────
        last_row = df_feat[active_feat_cols].iloc[[-1]]
        if last_row.isna().any().any():
            raise ValueError(
                "Last row has NaN features — insufficient data for inference."
            )
        X_latest_raw = last_row.values   # shape (1, 5 or 9)

        # ── Drop last row (no target) + drop NaN rows ────────────────────────
        df_train = df_feat.iloc[:-1].dropna(subset=active_feat_cols + ["target"])
        if df_train.empty:
            raise ValueError("No valid training rows after feature calculation.")

        X_train_raw = df_train[active_feat_cols].values  # shape (n-1, 5 or 9)
        Y           = df_train["target"].values

        return X_train_raw, Y, X_latest_raw, df_train

    # ────────────────────────────────────────────────────────
    #  STEP 2: MLP TRAINING
    # ────────────────────────────────────────────────────────

    def train_model(self, X_scaled: np.ndarray, Y: np.ndarray) -> bool:
        """
        Train MLPClassifier.
        Architecture scales with input feature count:
            5 features (tech only)  → (64, 32)
            9 features (cross)      → (128, 64)
        """
        try:
            if len(np.unique(Y)) < 2 or len(Y) < 10:
                return False

            # Select architecture based on feature count
            n_features = X_scaled.shape[1]
            hidden_layers = (
                MLP_HIDDEN_LAYERS_CROSS
                if n_features > len(_TECH_FEATURE_COLS)
                else MLP_HIDDEN_LAYERS_BASE
            )

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self.model = MLPClassifier(
                    hidden_layer_sizes  = hidden_layers,
                    activation          = MLP_ACTIVATION,
                    solver              = MLP_SOLVER,
                    max_iter            = MLP_MAX_ITER,
                    early_stopping      = True,
                    validation_fraction = 0.15,
                    random_state        = MLP_RANDOM_STATE,
                    verbose             = False,
                )
                self.model.fit(X_scaled, Y)
            return True
        except Exception:
            return False

    # ────────────────────────────────────────────────────────
    #  STEP 3: INFERENCE
    # ────────────────────────────────────────────────────────

    def get_directional_vote(
        self,
        df: pd.DataFrame,
        hmm_states: np.ndarray | None = None,
        hmm_index: pd.Index | None    = None,
    ) -> float:
        """
        v3 ARCH: Return a continuous directional vote in [-1.0, +1.0].

        Logic:
            vote = P(Bullish) - P(Bearish)

        Rationale:
            Direct use of softmax output provides a linear conviction 
            spectrum. 0.5/0.5 split → 0.0 (uncertain). 
            100% Bullish → +1.0. 100% Bearish → -1.0.

        Returns:
            float in [-1.0, +1.0]
        """
        bias, conf_pct = self.get_ai_confidence(df, hmm_states, hmm_index)
        
        # Convert (Bias, 50-100%) back to [-1, 1]
        direction = 1.0 if bias == "BULL" else (-1.0 if bias == "BEAR" else 0.0)
        vote = direction * (conf_pct - 50.0) / 50.0
        
        return round(max(-1.0, min(1.0, vote)), 4)

    def get_ai_confidence(
        self,
        df: pd.DataFrame,
        hmm_states: np.ndarray | None = None,
        hmm_index: pd.Index | None    = None,
    ) -> tuple[str, float]:
        """
        Full pipeline: features → train → predict → return confidence.

        Returns:
            ("BULL" | "BEAR" | "NEUTRAL", confidence_pct)
            confidence_pct in [50.0, 100.0]
        """
        if df is None or len(df) < MIN_ROWS:
            return FALLBACK_RESULT

        try:
            # 1. Feature engineering (with optional HMM cross)
            X_train_raw, Y, X_latest_raw, _ = self.prepare_data(
                df,
                hmm_states = hmm_states,
                hmm_index  = hmm_index,
            )

            current_len  = len(df)
            current_hash = self._compute_data_hash(df)

            # [FIX-5b] Event-triggered retrain: vol spike
            _vol_spike = False
            try:
                from engines.layer1_volatility import get_vol_estimator as _get_vol_est
                _vp = _get_vol_est().estimate_params(df)
                _cur_vol = float(_vp.get("current_vol", 0))
                _lr_vol  = float(_vp.get("long_run_vol", 1e-6))
                if _lr_vol > 0 and (_cur_vol / _lr_vol) > MLP_VOL_SPIKE_RETRAIN_RATIO:
                    _vol_spike = True
                    logger.info("[MLP] Vol spike detected (%.2fx long-run). Forcing retrain.",
                                _cur_vol / _lr_vol)
            except Exception:
                pass

            needs_retrain = (
                not self._is_trained
                or self.model is None
                or (current_len - self._last_trained_len) >= MLP_RETRAIN_EVERY_N_CANDLES
                or current_len < self._last_trained_len
                or _vol_spike   # [FIX-5b]
            )

            if needs_retrain:
                # 2. Fit scaler on training rows only
                X_train_scaled  = self.scaler.fit_transform(X_train_raw)

                # 3. Train MLP
                success = self.train_model(X_train_scaled, Y)
                if not success:
                    return FALLBACK_RESULT
                    
                self._is_trained = True
                self._last_trained_len = current_len
                self._data_hash = current_hash

                # 3b. Persist to disk for restart recovery
                self._save_to_disk()
                logger.info(f"[MLP] Retrained: len={current_len}, hash={current_hash}")
            else:
                logger.debug(f"[MLP] Cache hit: {current_len - self._last_trained_len} new candles < {MLP_RETRAIN_EVERY_N_CANDLES} threshold")

            # 4. Scale inference row (no refit)
            X_latest_scaled = self.scaler.transform(X_latest_raw)

            # 5. Predict (3 classes: 0=Bear, 1=Neutral, 2=Bull)
            probabilities = self.model.predict_proba(X_latest_scaled)[0]
            
            # Ensure we handle classes correctly (if model trained on fewer than 3 during window)
            class_map = {c: i for i, c in enumerate(self.model.classes_)}
            
            prob_bear = probabilities[class_map[0]] if 0 in class_map else 0.0
            prob_neut = probabilities[class_map[1]] if 1 in class_map else 0.0
            prob_bull = probabilities[class_map[2]] if 2 in class_map else 0.0

            # Decision Logic:
            # We only want BULL or BEAR if it significantly outweighs NEUTRAL
            if prob_bull > prob_bear and prob_bull > prob_neut:
                bias, confidence = "BULL", prob_bull * 100
            elif prob_bear > prob_bull and prob_bear > prob_neut:
                bias, confidence = "BEAR", prob_bear * 100
            else:
                bias, confidence = "NEUTRAL", prob_neut * 100 if 1 in class_map else 50.0

            confidence = max(50.0, min(100.0, confidence))
            return (bias, round(confidence, 1))

        except Exception:
            return FALLBACK_RESULT

    # ────────────────────────────────────────────────────────
    #  UTILITY
    # ────────────────────────────────────────────────────────

    def get_model_info(self) -> dict:
        info = {
            "name": "MLP Neural Net",
            "is_trained": bool(self._is_trained and self.model is not None),
        }
        if self.model is not None:
            info["iterations"]    = getattr(self.model, "n_iter_", 0)
            info["loss"]          = round(getattr(self.model, "loss_", 4), 4)
            info["layers"]        = list(self.model.hidden_layer_sizes)
            info["features_in"]   = getattr(self.model, "n_features_in_", 0)
            info["feature_cross"] = self.is_cross_enabled
            if self._is_trained:
                info["last_trained_len"] = self._last_trained_len
                info["data_hash"] = self._data_hash
                info["retrain_threshold"] = MLP_RETRAIN_EVERY_N_CANDLES
                info["model_persisted"] = _MLP_MODEL_PATH.exists()
        return info


# ════════════════════════════════════════════════════════════
#  STANDALONE TEST
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from data_engine import get_latest_market_data
    # Layer 1 engine is now in app/core/engines
    from app.core.engines.layer1_bcd import BayesianChangepointModel as MarketRegimeModel

    print("\n ⚡ BTC-QUANT-BTC · Layer 3 AI Signal Intelligence Test (PHASE 3)")
    print(" ─" * 30)

    df_ohlcv, _ = get_latest_market_data()

    if df_ohlcv is None or df_ohlcv.empty:
        print(" ⚠ No data in BTC-QUANT.db. Run data_engine.py first.")
    else:
        # ── Test WITHOUT cross features ──
        print("\n  [Mode A] 5 features (technical only)")
        model_a = SignalIntelligenceModel()
        bias_a, conf_a = model_a.get_ai_confidence(df_ohlcv)
        print(f"    Bias={bias_a}  Confidence={conf_a}%  CrossEnabled={model_a.is_cross_enabled}")
        info_a = model_a.get_model_info()
        print(f"    Architecture={info_a['layers']}  features_in={info_a.get('features_in', 0)}")

        # ── Test WITH HMM cross features ──
        print("\n  [Mode B] 9 features (technical + HMM regime one-hot)")
        hmm_model = MarketRegimeModel()
        states_arr, states_idx = hmm_model.get_state_sequence_raw(df_ohlcv)

        if states_arr is not None:
            model_b = SignalIntelligenceModel()
            bias_b, conf_b = model_b.get_ai_confidence(
                df_ohlcv,
                hmm_states = states_arr,
                hmm_index  = states_idx,
            )
            print(f"    Bias={bias_b}  Confidence={conf_b}%  CrossEnabled={model_b.is_cross_enabled}")
            info_b = model_b.get_model_info()
            print(f"    Architecture={info_b['layers']}  features_in={info_b.get('features_in', 0)}")
            print(f"\n  Δ Confidence: {conf_b - conf_a:+.1f}% (cross vs base)")
        else:
            print("    ⚠ HMM state sequence unavailable — cross test skipped.")

    print("\n  ✅ Layer 3 AI PHASE 3 test complete.\n")
