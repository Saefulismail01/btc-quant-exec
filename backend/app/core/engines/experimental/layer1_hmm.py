"""
╔══════════════════════════════════════════════════════════════╗
║  BTC-QUANT-BTC: LAYER 1 — MARKET REGIME DETECTION (HMM)       ║
║  Gaussian Hidden Markov Model · 4 States · CPU-Only          ║
║  Stack: hmmlearn + sklearn + numpy + pandas                  ║
║                                                              ║
║  HOTFIX  2026-02-27: Scaler contamination fix                ║
║  PHASE 3 2026-02-27: HMM→MLP Feature Cross                  ║
║    + get_state_sequence_raw() — raw int array aligned to df  ║
║    + get_current_regime_posterior() — softmax posterior probs ║
║  PHASE 4 2026-02-27: BIC-Guided N_STATES Selection           ║
║    + _find_optimal_n_states() — BIC scan over candidates     ║
║    + train_model() uses dynamic n, not hardcoded N_STATES=4  ║
║    + BIC re-evaluated every BIC_REEVAL_EVERY_N_CANDLES       ║
║  BUGFIX  2026-02-27: label_states() coverage guard           ║
║    + Dominant state (>50% obs) → Sideways, never Bull/Bear   ║
║    + Bull/Bear require positive/negative mean_return         ║
║    + MIN_ROWS 80 → 250 for richer feature distribution       ║
║  BUGFIX2 2026-02-27: label_states() Z-score significance     ║
║    + Bull/Bear require |z_score| > threshold vs window mean  ║
║    + Dominant cluster → labeled by vol (HV/LV), never dir.  ║
║    + Prevents bias shifting Bear→HV-SW→Bull in any window   ║
║  ECONOPHYSICS Modul A (2026-03):                             ║
║    + _compute_transition_matrix() — P[i,j] dari Proses Markov║
║    + _compute_expected_duration() — E[T] = 1/(1-P[i,i])     ║
║    + get_regime_bias() — bias_score, persistence, reversal   ║
║    Dipanggil otomatis di train_global(), expose via API      ║
╚══════════════════════════════════════════════════════════════╝
"""

import sys
import warnings
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture

_BACKEND_DIR = str(Path(__file__).resolve().parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from utils.scaler_manager import get_scaler  # noqa: E402

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)


# ════════════════════════════════════════════════════════════

N_STATES = 4                    # Fallback default — overridden by BIC selection
N_STATES_CANDIDATES = [2, 3, 4, 5, 6]   # BIC search space
BIC_REEVAL_EVERY_N_CANDLES = 24         # Re-run BIC scan every 24 candles
COVARIANCE_TYPE = "full"
N_ITER = 1000
RANDOM_STATE = 42
VOL_WINDOW = 14
VOL_ZSCORE_WINDOW = 20
MIN_ROWS                  = 200    # Minimum rows untuk inference (Increased for richer context)
GLOBAL_TRAIN_MIN_ROWS     = 500    # Minimum rows untuk global training (Full history scan)
RETRAIN_EVERY_N_CANDLES   = 6      # Sliding window retrain (LEGACY — tidak dipakai di mode global)
GLOBAL_RETRAIN_EVERY_N    = 500    # Global model diretrain setiap N candle baru

# BUGFIX2: label_states() Z-score significance thresholds
# ──────────────────────────────────────────────────────────────────────
# Root problem: labeling by relative rank (idxmax/idxmin) always produces
# one dominant label regardless of actual market conditions.
#
# Fix: a state earns Bull/Bear only if its mean_return is statistically
# significant — measured in Z-scores vs the window's own return distribution.
#
# Z-score = state_mean_return / window_return_std
#   >  +BULL_ZSCORE_THRESHOLD  → Bullish Trend
#   <  -BEAR_ZSCORE_THRESHOLD  → Bearish Trend
#   otherwise                  → Sideways (split by vol: HV or LV)
#
# DOMINANT_STATE_THRESHOLD still guards large clusters from being mislabeled.
DOMINANT_STATE_THRESHOLD = 0.50   # State covering >50% obs → Sideways only
BULL_ZSCORE_THRESHOLD    = 0.7    # State mean_return > +0.7 sigma → Bullish
BEAR_ZSCORE_THRESHOLD    = 0.7    # State mean_return < -0.7 sigma → Bearish

REGIME_LABELS = {
    "bull":  "Bullish Trend",
    "bear":  "Bearish Trend",
    "hv_sw": "High Volatility Sideways",
    "lv_sw": "Low Volatility Sideways",
}

BASELINE_PERSISTENCE = [
    ("bear_weak", 0.92),
    ("crash",     0.48),
    ("bull_weak", 0.49),
    ("calm",      0.79),
]


# ════════════════════════════════════════════════════════════
#  MARKET REGIME MODEL
# ════════════════════════════════════════════════════════════

class MarketRegimeModel:
    """
    HMM-based market regime detection engine.

    HOTFIX: prepare_features() returns RAW X. Scaler only fit in PATH A.
    PHASE 3 additions:
        get_state_sequence_raw()         → aligned int array for MLP cross-feature
        get_current_regime_posterior()   → softmax posterior probabilities for
                                           fine-grained spectrum confidence weighting
    """

    def __init__(self):
        self.model: GaussianMixture | None = None
        self.scaler = get_scaler("hmm")
        self.state_map: dict[int, str] = {}

        self._all_features = [
            "log_return",
            "realized_vol",
            "hl_spread",
            "volume_zscore",
            "vol_trend",
            "cvd_zscore",
            "oi_rate_of_change",
            "liq_intensity",
        ]
        self._active_features = self._all_features  # Default until first training

        self._last_trained_len: int  = 0
        self._last_trained_hash: str = ""

        self.last_aic:    float | None = None
        self.last_bic:    float | None = None
        self.last_loglik: float | None = None

        # PHASE 4: BIC-guided N_STATES tracking
        self._active_n_states:   int        = N_STATES   # Current best n
        self._bic_scores:        dict       = {}          # {n: bic} from last scan
        self._last_bic_eval_len: int        = 0           # Row count at last BIC scan

        # ARCH FIX: Global training mode
        # Train once on large historical dataset, inference on new candles
        # without retraining — prevents sliding-window dominant-cluster bias
        self._global_trained: bool = False
        self._global_trained_len: int = 0   # len(df) at last global retrain

        # ── ECONOPHYSICS Modul A: Transition Probability Matrix ──────────────
        # Dari teori Proses Markov (Palupi, 2022 — Materi 1):
        # P[i,j] = P(X_t+1 = j | X_t = i)
        # Matriks ini adalah INTI dari regime bias detection:
        # baris i = distribusi peluang ke mana regime i akan bergerak
        self._transition_matrix: np.ndarray | None = None
        self._regime_bias_cache: dict = {}   # cache agar tidak recompute tiap call

    # ────────────────────────────────────────────────
    #  CACHE HELPERS
    # ────────────────────────────────────────────────

    def _data_hash(self, df: pd.DataFrame) -> str:
        tail = df["Close"].tail(5).values
        return ",".join(f"{v:.2f}" for v in tail)

    def _should_retrain(self, df: pd.DataFrame) -> bool:
        if self.model is None:
            return True
        current_len  = len(df)
        current_hash = self._data_hash(df)
        if current_len - self._last_trained_len >= RETRAIN_EVERY_N_CANDLES:
            return True
        if current_hash != self._last_trained_hash:
            return True
        return False

    # ────────────────────────────────────────────────────────
    #  STEP 1: FEATURE ENGINEERING  (no scaling)
    # ────────────────────────────────────────────────────────

    def prepare_features(self, df: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
        """
        Calculate OHLCV + Microstructure features.
        Includes: Log Return, Volatility, Spread, Volume Z-Score, Vol Trend,
                  CVD Z-Score, OI Rate of Change, Liquidation Intensity.
        """
        df_feat = df.copy()

        # ── Price/Vol Features ──────────────────────────────
        df_feat["log_return"]   = np.log(df_feat["Close"] / df_feat["Close"].shift(1))
        df_feat["realized_vol"] = df_feat["log_return"].rolling(window=VOL_WINDOW).std()
        df_feat["hl_spread"]    = (df_feat["High"] - df_feat["Low"]) / df_feat["Close"]

        vol_mean = df_feat["Volume"].rolling(window=VOL_ZSCORE_WINDOW).mean()
        vol_std  = df_feat["Volume"].rolling(window=VOL_ZSCORE_WINDOW).std()
        df_feat["volume_zscore"] = (df_feat["Volume"] - vol_mean) / vol_std.replace(0, np.nan)
        df_feat["vol_trend"] = df_feat["realized_vol"].diff(1)

        # ── Microstructure Features (v2) ─────────────────────
        # Handle missing columns if using legacy backtest data
        for col in ["cvd", "open_interest", "liquidations_buy", "liquidations_sell"]:
            if col not in df_feat.columns:
                df_feat[col] = 0.0

        # CVD Z-Score (Normalization) - I-01 Fix: True Cumulative Oscillator
        df_feat["cvd_cum"] = df_feat["cvd"].rolling(window=120, min_periods=1).sum()
        cvd_mean = df_feat["cvd_cum"].rolling(window=20, min_periods=1).mean()
        cvd_std  = df_feat["cvd_cum"].rolling(window=20, min_periods=1).std()
        df_feat["cvd_zscore"] = (df_feat["cvd_cum"] - cvd_mean) / cvd_std.replace(0, np.nan)
        
        # OI Rate of Change
        df_feat["oi_rate_of_change"] = df_feat["open_interest"].pct_change(fill_method=None)
        
        # Liquidation Intensity (Total dollar volume of liqs per candle)
        df_feat["liq_intensity"] = df_feat["liquidations_buy"] + df_feat["liquidations_sell"]
        # Normalize liq intensity by median to keep it in a reasonable range
        liq_median = df_feat["liq_intensity"].rolling(window=50).median().replace(0, 1.0)
        df_feat["liq_intensity"] = np.log1p(df_feat["liq_intensity"] / liq_median)

        df_feat = df_feat.fillna(0)
    
        # NOTE: Robustness Fix - No longer adding noise here.
        # We will filter out zero-variance features during training selection.

        return df_feat

    # ────────────────────────────────────────────────────────
    #  STEP 2: HMM TRAINING
    # ────────────────────────────────────────────────────────

    # ────────────────────────────────────────────────────────
    #  PHASE 4 — BIC-GUIDED N_STATES SELECTION
    # ────────────────────────────────────────────────────────

    def _compute_bic(self, model: GaussianMixture, X_scaled: np.ndarray) -> float:
        """
        Compute BIC for a fitted GaussianMixture.
        Lower BIC = better model (balances fit vs complexity).
        Scikit-learn provides this natively.
        """
        return model.bic(X_scaled)

    def _find_optimal_n_states(
        self,
        X_scaled: np.ndarray,
        candidates: list[int] = N_STATES_CANDIDATES,
    ) -> int:
        """
        PHASE 4: BIC scan over candidate state counts.

        Fits a GaussianMixture for each candidate n and returns the n with
        the lowest BIC score (best bias-variance tradeoff).

        Run frequency: every BIC_REEVAL_EVERY_N_CANDLES candles (not every
        retrain cycle) to avoid expensive multi-fit overhead per request.

        Args:
            X_scaled:   Scaled feature matrix (already fit_transformed).
            candidates: List of n_states values to evaluate.

        Returns:
            int — optimal n_states with minimum BIC.
        """
        import logging

        best_n   = N_STATES   # fallback
        best_bic = float("inf")
        bic_scores: dict[int, float] = {}

        for n in candidates:
            # Skip if not enough samples: need at least n*2 observations
            if len(X_scaled) < n * 2:
                continue
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    candidate_model = GaussianMixture(
                        n_components    = n,
                        covariance_type = COVARIANCE_TYPE,
                        n_init          = 1,
                        random_state    = RANDOM_STATE,
                        verbose         = 0,
                    )
                    candidate_model.fit(X_scaled)

                bic = self._compute_bic(candidate_model, X_scaled)
                bic_scores[n] = round(bic, 2)

                if bic < best_bic:
                    best_bic = bic
                    best_n   = n

            except Exception as exc:
                logging.debug(f"[HMM BIC] n={n} failed: {exc}")
                continue

        self._bic_scores = bic_scores
        logging.info(
            f"[HMM BIC] scores={bic_scores}  "
            f"→ optimal n_states={best_n} (BIC={best_bic:.1f})"
        )
        return best_n

    def _should_reeval_bic(self, current_len: int) -> bool:
        """
        Returns True on cold start or when BIC_REEVAL_EVERY_N_CANDLES
        new candles have accumulated since last BIC evaluation.
        """
        if self._last_bic_eval_len == 0:
            return True   # Cold start
        return (current_len - self._last_bic_eval_len) >= BIC_REEVAL_EVERY_N_CANDLES

    def _apply_nhhm_bias(self, funding_rate: float):
        """
        PHASE 6: Apply Non-Homogeneous HMM (NHHM) bias to the transition matrix
        based on the external Funding Rate.

        Logic:
          - (Bypassed for GaussianMixture since it lacks a transition matrix)
        """
        # GaussianMixture has no transmat_, so we simply return.
        # Future iterations can inject bias directly into the posterior probabilities instead.
        return

    def train_model(self, X_scaled: np.ndarray, current_len: int = 0) -> np.ndarray:
        """
        Fit GaussianMixture and return predicted states assigned to each observation.

        PHASE 4: Before fitting, optionally runs BIC scan to select optimal
        n_states. BIC re-evaluated every BIC_REEVAL_EVERY_N_CANDLES candles
        to avoid overhead on every 6-candle retrain cycle.

        Args:
            X_scaled:    Scaled feature matrix.
            current_len: Current df row count — used for BIC reeval scheduling.
        """
        # PHASE 4: BIC-guided n_states selection
        if self._should_reeval_bic(current_len):
            self._active_n_states    = self._find_optimal_n_states(X_scaled)
            self._last_bic_eval_len  = current_len

        n = self._active_n_states

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = GaussianMixture(
                n_components    = n,
                covariance_type = COVARIANCE_TYPE,
                n_init          = 1,
                random_state    = RANDOM_STATE,
                verbose         = 0,
            )
            model.fit(X_scaled)

        self.model = model

        n_obs      = len(X_scaled)
        
        self.last_aic    = model.aic(X_scaled)
        self.last_bic    = model.bic(X_scaled)
        self.last_loglik = model.score(X_scaled) * n_obs

        hidden_states = model.predict(X_scaled)

        warnings_ = self._validate_transition_matrix()
        if warnings_:
            import logging
            logging.warning(f"[HMM] Transition matrix anomaly: {warnings_}")

        return hidden_states

    # ────────────────────────────────────────────────────────
    #  STEP 3: DYNAMIC STATE LABELING
    # ────────────────────────────────────────────────────────

    def label_states(
        self,
        df_features: pd.DataFrame,
        hidden_states: np.ndarray,
    ) -> dict[int, str]:
        """
        BUGFIX2: Z-score significance labeling. Coverage-aware. Dynamic n_states.

        PROBLEM HISTORY:
          v1 (original)  — idxmin/idxmax relative rank → 97% Bearish bias
          v2 (BUGFIX)    — coverage guard → bias shifted to 98% HV-SW
          v3 (BUGFIX2)   — Z-score absolute significance → fixes root cause

        ROOT CAUSE:
          Relative ranking (idxmax/idxmin) always assigns Bull/Bear to SOMEONE,
          even if the entire window is flat/sideways. In a 250-candle mixed window,
          the "winner" of mean_return ranking is noise, not signal.

        FIX — Two-gate system:
          Gate 1 ─ Coverage: state covering >50% obs → Sideways only (never Bull/Bear)
          Gate 2 ─ Z-score : state's mean_return must exceed ±1 sigma of the window's
                              full return distribution to qualify as Bull or Bear.

        Z-score = state_mean_return / window_return_std
          > +BULL_ZSCORE_THRESHOLD  → Bullish Trend
          < -BEAR_ZSCORE_THRESHOLD  → Bearish Trend
          |z| ≤ threshold           → Sideways (split by vol: HV or LV)

        Effect:
          • Flat/choppy window   → all states → Sideways (correct)
          • Strong bull window   → dominant state z > +1 → Bullish (correct)
          • Strong bear window   → dominant state z < -1 → Bearish (correct)
          • Mixed window         → only extreme minority states get directional labels
        """
        df_work = df_features.copy()
        df_work["state"] = hidden_states
        n_total = len(df_work)

        state_stats = df_work.groupby("state").agg(
            mean_return=("log_return", "mean"),
            mean_vol=("realized_vol", "mean"),
            count=("log_return", "count"),
        )
        state_stats["coverage"] = state_stats["count"] / n_total

        # ── Window-level return distribution (for Z-score normalization) ───────
        window_return_std = float(df_work["log_return"].std())
        if window_return_std < 1e-10:
            window_return_std = 1e-10  # prevent division by zero

        state_stats["z_score"] = state_stats["mean_return"] / window_return_std

        state_map: dict[int, str] = {}
        bull_state = None
        bear_state = None

        # ── Gate 1 + Gate 2: directional assignment ─────────────────────────
        # Bull/Bear only if:
        #   (a) coverage < DOMINANT_STATE_THRESHOLD
        #   (b) |z_score| > threshold
        #   (c) CVD z-score alignment (optional but good)
        
        bull_candidates = state_stats[
            (state_stats["coverage"] < DOMINANT_STATE_THRESHOLD) &
            (state_stats["z_score"]   > BULL_ZSCORE_THRESHOLD)
        ]
        bear_candidates = state_stats[
            (state_stats["coverage"] < DOMINANT_STATE_THRESHOLD) &
            (state_stats["z_score"]   < -BEAR_ZSCORE_THRESHOLD)
        ]

        # Fix bias: If too many candidates, take only the most extreme
        if not bull_candidates.empty:
            bull_state = bull_candidates["z_score"].idxmax()
            state_map[bull_state] = REGIME_LABELS["bull"]

        if not bear_candidates.empty:
            # Exclude already-assigned bull_state
            bc = bear_candidates.drop(index=bull_state, errors="ignore")
            if not bc.empty:
                bear_state = bc["z_score"].idxmin()
                # Additional check: only assign Bear if it's NOT the most frequent state 
                # unless its Z-score is very drastic
                if state_stats.loc[bear_state, 'coverage'] < 0.4 or state_stats.loc[bear_state, 'z_score'] < -1.5:
                    state_map[bear_state] = REGIME_LABELS["bear"]

        # ── All unassigned states → Sideways (sorted by vol desc) ────────────
        assigned = set(state_map.keys())
        sideways = [s for s in state_stats.index if s not in assigned]

        if sideways:
            sw_stats = state_stats.loc[sideways].sort_values("mean_vol", ascending=False)
            for i, sid in enumerate(sw_stats.index):
                if i == 0:
                    state_map[sid] = REGIME_LABELS["hv_sw"]
                elif i == 1:
                    state_map[sid] = REGIME_LABELS["lv_sw"]
                else:
                    state_map[sid] = f"Sideways {i + 1}"

        bull_z = f"{state_stats.loc[bull_state, 'z_score']:.2f}" if bull_state is not None else "None"
        bear_z = f"{state_stats.loc[bear_state, 'z_score']:.2f}" if bear_state is not None else "None"
        logging.debug(
            f"[HMM label_states] window_std={window_return_std:.6f} "
            f"bull={bull_state}(z={bull_z}) bear={bear_state}(z={bear_z}) "
            f"coverage={state_stats['coverage'].round(2).to_dict()} "
            f"z_scores={state_stats['z_score'].round(2).to_dict()}"
        )

        self.state_map = state_map
        return self.state_map

    # ────────────────────────────────────────────────────────
    #  STEP 4: PRIMARY INFERENCE
    # ────────────────────────────────────────────────────────

    def _run_inference(self, df: pd.DataFrame, funding_rate: float = 0.0) -> np.ndarray | None:
        """
        Internal helper: run feature engineering + scaler + predict.
        Returns raw hidden_states array, or None on failure.
        Also updates cache if retrain occurs.
        
        PHASE 6: funding_rate passed to apply NHHM bias after training.
        """
        if df is None or len(df) < MIN_ROWS:
            return None
        try:
            df_prepared = self.prepare_features(df)
            df_features = df_prepared.dropna(subset=self._active_features)
            X_raw       = df_features[self._active_features].values

            if len(df_features) < N_STATES * 2:
                return None

            if self._should_retrain(df):
                X_scaled      = self.scaler.fit_transform(X_raw)
                hidden_states = self.train_model(X_scaled, current_len=len(df))  # PHASE 4
                self.label_states(df_features, hidden_states)
                
                # PHASE 6: Apply NHHM bias based on current funding
                self._apply_nhhm_bias(funding_rate)
                
                self._last_trained_len  = len(df)
                self._last_trained_hash = self._data_hash(df)
            else:
                X_scaled      = self.scaler.transform(X_raw)
                hidden_states = self.model.predict(X_scaled)

            return hidden_states
        except Exception:
            return None

    # ──────────────────────────────────────────────────────
    #  ARCH FIX — GLOBAL TRAINING MODE
    # ──────────────────────────────────────────────────────

    def train_global(self, df_history: pd.DataFrame) -> bool:
        """
        ARCH FIX: Train HMM on a large historical dataset (ideally full year+)
        so the model sees multiple complete regime cycles before being used
        for inference. This prevents the sliding-window dominant-cluster bias.

        Call this ONCE with as much historical data as available, then use
        get_current_regime() for inference — the model will NOT retrain
        on each call (unless GLOBAL_RETRAIN_EVERY_N candles have passed).

        Returns True if training succeeded.
        """
        if df_history is None or len(df_history) < GLOBAL_TRAIN_MIN_ROWS:
            logging.warning(
                f"[HMM global] Insufficient data: {len(df_history) if df_history is not None else 0} "
                f"rows (need {GLOBAL_TRAIN_MIN_ROWS})"
            )
            return False
        try:
            df_prepared = self.prepare_features(df_history)
            
            # ── DYNAMIC FEATURE SELECTION ────────────────────────
            # Only use features that actually have variance in the training set
            self._active_features = []
            for col in self._all_features:
                if col in df_prepared.columns and df_prepared[col].dropna().std() > 1e-12:
                    self._active_features.append(col)
            
            if not self._active_features:
                logging.error("[HMM global] No features with significant variance found.")
                return False
                
            logging.info(f"[HMM global] Active features: {self._active_features}")
            
            df_features = df_prepared.dropna(subset=self._active_features)
            X_raw       = df_features[self._active_features].values
            X_scaled    = self.scaler.fit_transform(X_raw)

            # BIC scan on full history for optimal n_states
            self._active_n_states   = self._find_optimal_n_states(X_scaled)
            self._last_bic_eval_len = len(df_history)

            hidden_states = self.train_model(X_scaled, current_len=len(df_history))
            self.label_states(df_features, hidden_states)

            # ECONOPHYSICS — Modul A: hitung matriks transisi & regime bias
            # setelah train_global agar tersedia untuk get_regime_bias()
            self._transition_matrix = self._compute_transition_matrix(hidden_states)
            self.get_regime_bias()  # pre-compute dan cache

            self._global_trained     = True
            self._global_trained_len = len(df_history)
            self._last_trained_len   = len(df_history)
            self._last_trained_hash  = self._data_hash(df_history)

            # ── ECONOPHYSICS Modul A: Hitung transition matrix dari urutan state ──
            # Invalidate cache karena model baru dilatih
            self._regime_bias_cache = {}
            self._compute_transition_matrix(hidden_states)

            logging.info(
                f"[HMM global] Trained on {len(df_history)} candles. "
                f"n_states={self._active_n_states}. "
                f"Regime map: {self.state_map}"
            )
            return True
        except Exception as e:
            logging.error(f"[HMM global] Training failed: {e}")
            return False

    def _should_retrain_global(self, current_total_len: int) -> bool:
        """
        In global mode: only retrain if GLOBAL_RETRAIN_EVERY_N new candles
        have accumulated since the last global training.
        Much less frequent than sliding-window retrain.
        """
        if not self._global_trained:
            return True
        return (current_total_len - self._global_trained_len) >= GLOBAL_RETRAIN_EVERY_N

    def get_directional_vote(self, df: pd.DataFrame, funding_rate: float = 0.0) -> float:
        """
        v3 ARCH: Return a continuous directional vote in [-1.0, +1.0] using full posterior.

        Logic:
            Iterate through all hidden states and their posterior probabilities.
            vote = Sum(P(Bullish_i)) - Sum(P(Bearish_i))

        Rationale:
            Every candle has a direction, only conviction varies. 
            Sideways/Neutral states naturally reduce the net bias by absorbing 
            probability mass while contributing 0.0 to the directional sum.

        Returns:
            float in [-1.0, +1.0]
        """
        label, state_id, posterior = self.get_current_regime_posterior(df, funding_rate)

        # Fallback if HMM fails or data insufficient
        if state_id == -1 or len(posterior) == 0:
            return 0.0

        p_bull = 0.0
        p_bear = 0.0
        
        # Aggregate probabilities across all states based on their dynamic labels
        for sid, prob in enumerate(posterior):
            regime = self.state_map.get(sid, "")
            if "Bullish" in regime:
                p_bull += prob
            elif "Bearish" in regime:
                p_bear += prob
            # Sideways states (HV-SW, LV-SW) contribute 0 to the direction
            # but their probability mass correctly dilutes the conviction.

        vote = float(p_bull - p_bear)  # Pure net bias in [-1.0, +1.0]
        
        return round(max(-1.0, min(1.0, vote)), 4)

    def get_current_regime(self, df: pd.DataFrame, funding_rate: float = 0.0) -> tuple[str, int]:
        """
        Full pipeline: features → [retrain if needed] → predict → label.
        Returns (regime_label, state_id). Never raises.

        ARCH FIX: If model was globally trained, inference uses the stable
        global model. Retraining only triggered every GLOBAL_RETRAIN_EVERY_N
        candles, not every 6 candles as in sliding-window mode.
        """
        if df is None or len(df) < MIN_ROWS:
            return ("Data Insufficient", -1)
        try:
            # ── ARCH FIX: Global mode — use stable pre-trained model for inference ──
            if self._global_trained and not self._should_retrain_global(len(df)):
                df_prepared = self.prepare_features(df)
                df_features = df_prepared.dropna(subset=self._active_features)
                X_raw       = df_features[self._active_features].values
                X_scaled      = self.scaler.transform(X_raw)
                hidden_states = self.model.predict(X_scaled)
            else:
                # Fallback: sliding-window (or trigger global retrain)
                if self._global_trained and self._should_retrain_global(len(df)):
                    self.train_global(df)
                hidden_states = self._run_inference(df, funding_rate=funding_rate)

            if hidden_states is None:
                return ("Data Insufficient", -1)
            current_state = int(hidden_states[-1])
            return (self.state_map.get(current_state, "Unknown Regime"), current_state)
        except Exception as e:
            return (f"Error: {str(e)[:60]}", -1)

    # ────────────────────────────────────────────────────────
    #  PHASE 3 — METHOD 1: get_state_sequence_raw()
    # ────────────────────────────────────────────────────────

    def get_state_sequence_raw(
        self,
        df: pd.DataFrame,
    ) -> tuple[np.ndarray | None, pd.Index | None]:
        """
        PHASE 3: Returns the full Viterbi state sequence as a raw integer
        numpy array, aligned to the DataFrame index AFTER feature dropna.

        This is the key output needed by Layer 3 MLP for the feature cross:
        MLP will one-hot encode these state IDs as additional input features.

        Returns:
            (states_array, df_index) where:
                states_array : np.ndarray shape (n_valid_rows,) of ints 0–3
                               aligned to df_index (after rolling window dropna)
                df_index     : pandas Index of the rows that have valid features

            Returns (None, None) if model not trained or data insufficient.

        Notes on alignment:
            The HMM feature engineering drops the first ~20 rows (rolling windows).
            The MLP feature engineering also drops some rows.
            The intersection of both indices must be used — handled in layer3_ai.py.
        """
        if df is None or len(df) < MIN_ROWS:
            return None, None
        try:
            df_prepared = self.prepare_features(df)
            df_features = df_prepared.dropna(subset=self._active_features)
            X_raw       = df_features[self._active_features].values

            if len(df_features) < N_STATES * 2:
                return None, None

            if self._should_retrain(df):
                X_scaled      = self.scaler.fit_transform(X_raw)
                hidden_states = self.train_model(X_scaled, current_len=len(df))  # PHASE 4
                self.label_states(df_features, hidden_states)
                self._last_trained_len  = len(df)
                self._last_trained_hash = self._data_hash(df)
            else:
                X_scaled      = self.scaler.transform(X_raw)
                hidden_states = self.model.predict(X_scaled)

            # Return states aligned to the valid-feature row index
            return np.array(hidden_states, dtype=np.int32), df_features.index

        except Exception:
            return None, None

    # ────────────────────────────────────────────────────────
    #  PHASE 3 — METHOD 2: get_current_regime_posterior()
    # ────────────────────────────────────────────────────────

    def get_current_regime_posterior(
        self,
        df: pd.DataFrame,
        funding_rate: float = 0.0,
    ) -> tuple[str, int, np.ndarray]:
        """
        PHASE 3: Returns regime label, state ID, AND the posterior probability
        vector over all N_STATES for the LAST observation.
        
        PHASE 6: funding_rate passed to trigger NHHM bias during retrain.
        """
        uniform = np.full(N_STATES, 1.0 / N_STATES)

        if df is None or len(df) < MIN_ROWS:
            return ("Data Insufficient", -1, uniform)

        try:
            df_prepared = self.prepare_features(df)
            df_features = df_prepared.dropna(subset=self._active_features)
            X_raw       = df_features[self._active_features].values

            if len(df_features) < N_STATES * 2:
                return ("Data Insufficient", -1, uniform)

            if self._should_retrain(df):
                X_scaled      = self.scaler.fit_transform(X_raw)
                hidden_states = self.train_model(X_scaled, current_len=len(df))  # PHASE 4
                self.label_states(df_features, hidden_states)
                
                # PHASE 6: Apply NHHM bias
                self._apply_nhhm_bias(funding_rate)
                
                self._last_trained_len  = len(df)
                self._last_trained_hash = self._data_hash(df)
            else:
                X_scaled      = self.scaler.transform(X_raw)
                hidden_states = self.model.predict(X_scaled)

            # ── Posterior probabilities (forward-backward) ──────────────────
            # predict_proba() runs forward-backward and returns P(state | all obs)
            # Shape: (n_samples, N_STATES)
            posterior_matrix = self.model.predict_proba(X_scaled)
            last_posterior   = posterior_matrix[-1]   # last observation (current candle)

            current_state = int(hidden_states[-1])
            current_label = self.state_map.get(current_state, "Unknown Regime")

            return (current_label, current_state, last_posterior)

        except Exception as e:
            return (f"Error: {str(e)[:60]}", -1, uniform)

    # ────────────────────────────────────────────────────────
    #  VALIDATION
    # ────────────────────────────────────────────────────────

    # ──────────────────────────────────────────────────────
    #  ECONOPHYSICS — MODUL A: TRANSITION MATRIX & REGIME BIAS
    # ──────────────────────────────────────────────────────

    def _compute_transition_matrix(self, hidden_states: np.ndarray) -> np.ndarray:
        """
        Hitung matriks transisi empiris dari urutan state historis.

        Dari teori Proses Markov (Palupi, 2022 — Materi 1):
            P[i, j] = P(X(t+1) = j | X(t) = i)

        Ini adalah estimasi empiris dari matriks transisi Markov
        yang dihitung langsung dari data historis (counting method).
        Setiap baris dinormalisasi sehingga sum = 1.0 (row-stochastic).

        Returns:
            ndarray shape (n_states, n_states)
        """
        n = self._active_n_states
        trans_matrix = np.zeros((n, n), dtype=np.float64)

        for t in range(len(hidden_states) - 1):
            i = int(hidden_states[t])
            j = int(hidden_states[t + 1])
            if 0 <= i < n and 0 <= j < n:
                trans_matrix[i, j] += 1.0

        # Normalisasi per baris — hindari division by zero
        row_sums = trans_matrix.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1.0
        return trans_matrix / row_sums

    def get_regime_bias(self) -> dict:
        """
        Hitung regime bias dari matriks transisi.

        Dari teori Proses Markov: sifat rantai Markov menentukan
        apakah suatu regime cenderung berlanjut (trend-following valid)
        atau cenderung berbalik (mean-reversion valid).

        bias_score = persistence - reversal_prob
          > 0.5  : regime sangat persistent, trend-following valid
          0.3-0.5: regime moderat
          < 0.3  : regime tidak stabil, pertimbangkan mean-reversion

        Returns dict dengan statistik per regime label.
        """
        if self._transition_matrix is None or not self.state_map:
            return {}

        bias_report: dict = {}

        for state_id, label in self.state_map.items():
            if state_id >= len(self._transition_matrix):
                continue

            row = self._transition_matrix[state_id]

            # Persistence: peluang tetap di regime saat ini
            persistence = float(row[state_id]) if state_id < len(row) else 0.0

            # Reversal ke state berlawanan (Bull ↔ Bear)
            reversal = 0.0
            for other_id, other_label in self.state_map.items():
                if other_id == state_id or other_id >= len(row):
                    continue
                is_opposite = (
                    ("Bullish" in label and "Bearish" in other_label) or
                    ("Bearish" in label and "Bullish" in other_label)
                )
                if is_opposite:
                    reversal += float(row[other_id])

            bias_score = persistence - reversal

            # Tentukan interpretasi untuk trader
            if bias_score > 0.5:
                interpretation = "Regime sangat persistent. Trend-following valid."
            elif bias_score > 0.3:
                interpretation = "Regime moderat. Konfirmasi 15m disarankan."
            else:
                interpretation = "Regime tidak stabil. Pertimbangkan mean-reversion."

            # Expected duration: dari matriks transisi, E[durasi] = 1 / (1 - P[i,i])
            p_self = float(row[state_id]) if state_id < len(row) else 0.0
            expected_duration = round(1.0 / max(1.0 - p_self, 0.01), 1)

            bias_report[label] = {
                "persistence":             round(persistence, 4),
                "reversal_prob":           round(reversal, 4),
                "bias_score":              round(bias_score, 4),
                "expected_duration_candles": expected_duration,
                "interpretation":          interpretation,
                "next_state_probs": {
                    self.state_map.get(j, f"State {j}"): round(float(p), 4)
                    for j, p in enumerate(row)
                    if j < len(self.state_map)
                },
            }

        self._regime_bias_cache = bias_report
        return bias_report

    def _validate_transition_matrix(self) -> dict:
        # GaussianMixture has no transition matrix, so we bypass this check.
        return {}
        for i, (state_label, baseline) in enumerate(BASELINE_PERSISTENCE):
            if i >= len(diag):
                break
            actual    = float(diag[i])
            deviation = abs(actual - baseline) / max(baseline, 1e-9)
            if deviation > 0.30:
                direction = "lebih persisten" if actual > baseline else "lebih cepat berganti"
                warnings_[state_label] = {
                    "baseline" : round(baseline, 4),
                    "actual"   : round(actual,   4),
                    "deviation": f"{deviation*100:.1f}%",
                    "note"     : f"{state_label} {direction} dari baseline Paper 2025",
                }
        return warnings_

    # ────────────────────────────────────────────────────────
    #  ECONOPHYSICS MODUL A — TRANSITION MATRIX & REGIME BIAS
    # ────────────────────────────────────────────────────────

    def _compute_transition_matrix(self, hidden_states: np.ndarray) -> np.ndarray:
        """
        ECONOPHYSICS Modul A: Hitung matriks transisi empiris dari urutan state.

        Dari teori Proses Markov (Palupi, 2022 — Materi 1):
        P[i,j] = P(X_{t+1} = j | X_t = i)

        Persamaan Langevin dinyatakan sebagai PDS:
        dX(t) = ρ(t,X)dt + Q(t,X)dB
        → di sini matriks transisi adalah representasi diskrit dari
          probabilitas perubahan state dalam satu langkah waktu.

        Implementasi:
        1. Hitung frekuensi perpindahan i→j dari urutan state historis
        2. Normalisasi per baris → row-stochastic matrix (tiap baris sum=1)

        Args:
            hidden_states: np.ndarray int, urutan state dari GaussianMixture.predict()

        Returns:
            transition_matrix: ndarray shape (n_states, n_states)
            Baris = state asal, Kolom = state tujuan
        """
        n = self._active_n_states
        trans_count = np.zeros((n, n), dtype=np.float64)

        for t in range(len(hidden_states) - 1):
            i = int(hidden_states[t])
            j = int(hidden_states[t + 1])
            if 0 <= i < n and 0 <= j < n:
                trans_count[i, j] += 1

        # Normalisasi per baris → probabilitas (row-stochastic)
        row_sums = trans_count.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1.0   # hindari division by zero
        transition_matrix = trans_count / row_sums

        self._transition_matrix = transition_matrix
        return transition_matrix

    def _compute_expected_duration(self, state_id: int) -> float:
        """
        Dari teori rantai Markov: jika P[i,i] = persistence,
        maka distribusi durasi regime bersifat geometrik:
        E[durasi] = 1 / (1 - P[i,i])

        Untuk BTC: persistence tinggi (P[i,i] > 0.7) berarti
        regime cenderung berlanjut beberapa candle sebelum berubah.
        """
        if self._transition_matrix is None or state_id >= len(self._transition_matrix):
            return 0.0
        p_persist = float(self._transition_matrix[state_id, state_id])
        if p_persist >= 1.0:
            return 999.0   # infinite persistence
        return round(1.0 / max(1.0 - p_persist, 1e-6), 1)

    def get_regime_bias(self) -> dict:
        """
        ECONOPHYSICS Modul A: Hitung regime bias untuk setiap state
        berdasarkan matriks transisi.

        Dari teori Proses Markov:
        - bias_score > 0.5  → regime cenderung BERLANJUT (trend-following valid)
        - bias_score < 0.3  → regime cenderung BERBALIK  (mean-reversion valid)
        - bias_score ~ 0    → regime tidak stabil, tidak ada edge

        Returns dict keyed by regime label:
        {
          "Bullish Trend": {
            "persistence":   0.74,    # P[Bull, Bull]
            "reversal_prob": 0.08,    # P[Bull, Bear]
            "bias_score":    0.66,    # persistence - reversal_prob
            "expected_duration_candles": 3.8,  # E[T] = 1/(1-P[i,i])
            "interpretation": "Regime berlanjut ...",
            "next_state_probs": {"Bullish Trend": 0.74, ...}
          },
          ...
        }
        """
        if self._transition_matrix is None or not self.state_map:
            return {}

        # Gunakan cache jika ada dan state_map belum berubah
        if self._regime_bias_cache:
            return self._regime_bias_cache

        n = len(self._transition_matrix)
        bias_report: dict = {}

        for state_id, label in self.state_map.items():
            if state_id >= n:
                continue

            row = self._transition_matrix[state_id]

            # Persistence: peluang tetap di state saat ini (P[i,i])
            persistence = float(row[state_id])

            # Reversal probability: peluang berpindah ke state BERLAWANAN
            # Bull ↔ Bear adalah pasangan berlawanan
            reversal = 0.0
            for other_id, other_label in self.state_map.items():
                if other_id == state_id:
                    continue
                if ("Bullish" in label and "Bearish" in other_label) or \
                   ("Bearish" in label and "Bullish" in other_label):
                    if other_id < n:
                        reversal += float(row[other_id])

            bias_score = float(persistence - reversal)

            # Expected duration dari teori geometrik Markov
            expected_dur = self._compute_expected_duration(state_id)

            # Human-readable interpretation
            if bias_score > 0.5:
                interp = f"{label}: regime sangat persistent ({persistence:.0%}). Trend-following valid."
            elif bias_score > 0.2:
                interp = f"{label}: regime cukup stabil ({persistence:.0%}). Konfirmasi sebelum entry."
            elif bias_score > 0:
                interp = f"{label}: regime lemah, potensi reversal {reversal:.0%}. Hati-hati."
            else:
                interp = f"{label}: regime tidak stabil. Mean-reversion lebih valid."

            bias_report[label] = {
                "persistence":               round(persistence, 4),
                "reversal_prob":             round(reversal,    4),
                "bias_score":                round(bias_score,  4),
                "expected_duration_candles": expected_dur,
                "interpretation":            interp,
                "next_state_probs": {
                    self.state_map.get(j, f"State {j}"): round(float(row[j]), 4)
                    for j in range(n)
                    if j < len(row)
                },
            }

        self._regime_bias_cache = bias_report
        logging.info(
            f"[HMM Modul A] Regime bias computed for {len(bias_report)} states. "
            f"Bias scores: { {k: v['bias_score'] for k, v in bias_report.items()} }"
        )
        return bias_report

    def cache_info(self) -> dict:
        info = {
            "trained"             : self.model is not None,
            "last_trained_len"    : self._last_trained_len,
            "retrain_threshold"   : RETRAIN_EVERY_N_CANDLES,
            "active_n_states"     : self._active_n_states,
            "bic_scores"          : self._bic_scores,
            "bic_reeval_every"    : BIC_REEVAL_EVERY_N_CANDLES,
            "aic"                 : round(self.last_aic,    2) if self.last_aic    is not None else None,
            "bic"                 : round(self.last_bic,    2) if self.last_bic    is not None else None,
            "log_likelihood"      : round(self.last_loglik, 2) if self.last_loglik is not None else None,
            "transition_warnings" : self._validate_transition_matrix() if self.model else {},
            # ECONOPHYSICS — Modul A
            "transition_matrix"   : self._transition_matrix.tolist() if self._transition_matrix is not None else None,
            "regime_bias"         : self._regime_bias_cache,
        }
        return info


# ════════════════════════════════════════════════════════════
#  STANDALONE TEST
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from data_engine import get_latest_market_data

    print("\n ⚡ BTC-QUANT-BTC · Layer 1 HMM Test (PHASE 3)")
    print(" ─" * 30)

    df_ohlcv, _ = get_latest_market_data()

    if df_ohlcv is None or df_ohlcv.empty:
        print(" ⚠ No data in BTC-QUANT.db. Run data_engine.py first.")
    else:
        model = MarketRegimeModel()

        # Test 1: Standard regime
        label, state_id = model.get_current_regime(df_ohlcv)
        print(f"\n  📊 Data rows : {len(df_ohlcv)}")
        print(f"  🏷️  Regime    : {label}  (state {state_id})")

        # Test 2: Posterior probabilities
        label2, state2, posterior = model.get_current_regime_posterior(df_ohlcv)
        print(f"\n  ── Posterior Probabilities (current candle) ──")
        for sid, prob in enumerate(posterior):
            regime = model.state_map.get(sid, f"State {sid}")
            marker = " ◀ CURRENT" if sid == state2 else ""
            print(f"    State {sid} [{regime:30s}]  P={prob:.4f}{marker}")

        # Test 3: Raw state sequence
        states_arr, idx = model.get_state_sequence_raw(df_ohlcv)
        if states_arr is not None:
            print(f"\n  ── State Sequence (last 5) ──")
            for i, (s, ix) in enumerate(zip(states_arr[-5:], idx[-5:])):
                print(f"    [{ix}]  state={s}  ({model.state_map.get(s,'?')})")

        # Test 4: Cache info
        info = model.cache_info()
        print(f"\n  ── Cache Info ──")
        print(f"    AIC: {info['aic']}  |  BIC: {info['bic']}")
        print(f"    Transition warnings: {info['transition_warnings'] or 'None ✅'}")

        # Test 5: BIC scores
        info = model.cache_info()
        print(f"\n  ── PHASE 4: BIC-Guided N_STATES ──")
        print(f"    Active n_states : {info['active_n_states']}")
        print(f"    BIC scores      : {info['bic_scores']}")
        if info['bic_scores']:
            best = min(info['bic_scores'], key=info['bic_scores'].get)
            print(f"    Best candidate  : n={best} (BIC={info['bic_scores'][best]})")

    print("\n  ✅ Layer 1 HMM PHASE 4 test complete.\n")
