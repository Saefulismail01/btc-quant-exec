"""
╔══════════════════════════════════════════════════════════════╗
║  BTC-QUANT: LAYER 1 — MARKET REGIME DETECTION (BCD)          ║
║  Bayesian Online Changepoint Detection (BOCPD) Engine        ║
║                                                              ║
║  Serves as a drop-in replacement for layer1_hmm.py           ║
║  Instead of clustering probability densities across the      ║
║  entire dataset, it explicitly detects structural breaks     ║
║  in the time series (volatility and returns).                ║
╚══════════════════════════════════════════════════════════════╝
"""

import sys
import logging
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

_BACKEND_DIR = str(Path(__file__).resolve().parent.parent.parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from utils.scaler_manager import get_scaler  # noqa: E402

warnings.filterwarnings("ignore", category=RuntimeWarning)

# ════════════════════════════════════════════════════════════
# Configuration
# ════════════════════════════════════════════════════════════

MIN_ROWS = 100
GLOBAL_TRAIN_MIN_ROWS = 100
VOL_WINDOW = 14
VOL_ZSCORE_WINDOW = 20

# BCD Sensitivity Configuration
HAZARD_RATE = 1.0 / 15.0  # Prior prob of changepoint (1 in 15 candles = 2.5 days)
BCD_PRIOR_ALPHA = 1.0     # Lower alpha = flatter prior, more sensitive to variance changes
BCD_PRIOR_BETA  = 0.1     # Lower beta = allows for smaller baseline variance
BCD_PRIOR_KAPPA = 0.1     # Lower kappa = faster adaptation of the mean

# Thresholds for labeling regimes
TRAILING_WINDOW = 36      # Last 36 candles (~6 days) for trailing z-score
BULL_ZSCORE_THRESHOLD = 0.10
BEAR_ZSCORE_THRESHOLD = 0.10

REGIME_LABELS = {
    "bull":  "Bullish Trend",
    "bear":  "Bearish Trend",
    "hv_sw": "High Volatility Sideways",
    "lv_sw": "Low Volatility Sideways",
    "unknown": "Unknown Regime",
}


# ════════════════════════════════════════════════════════════
# Core BOCPD Implementation
# ════════════════════════════════════════════════════════════

class BayesianChangepointModel:
    """
    Bayesian Online Changepoint Detection module mirroring the MarketRegimeModel API.
    """

    def __init__(self):
        self.scaler = get_scaler("bcd")
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
        self._active_features = self._all_features

        self._global_trained = False
        self._last_trained_len = 0
        
        # State tracking
        self._changepoints: list[int] = []
        self._segment_labels: dict[int, str] = {}  # segment index -> regime string
        self._current_segment_idx = 0
        
        # Keep track of probabilities
        self._R: np.ndarray | None = None  # Run length probabilities

        # ── ECONOPHYSICS Modul A: Transition Probability Matrix ──────────────
        self._transition_matrix: np.ndarray | None = None
        self._regime_bias_cache: dict = {}

    def _data_hash(self, df: pd.DataFrame) -> str:
        tail = df["Close"].tail(5).values
        return ",".join(f"{v:.2f}" for v in tail)

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate OHLCV + Microstructure features.
        Matches exactly with layer1_hmm.py to ensure feature parity.
        """
        df_feat = df.copy()

        df_feat["log_return"]   = np.log(df_feat["Close"] / df_feat["Close"].shift(1))
        df_feat["realized_vol"] = df_feat["log_return"].rolling(window=VOL_WINDOW).std()
        df_feat["hl_spread"]    = (df_feat["High"] - df_feat["Low"]) / df_feat["Close"]

        vol_mean = df_feat["Volume"].rolling(window=VOL_ZSCORE_WINDOW).mean()
        vol_std  = df_feat["Volume"].rolling(window=VOL_ZSCORE_WINDOW).std()
        df_feat["volume_zscore"] = (df_feat["Volume"] - vol_mean) / vol_std.replace(0, np.nan)
        df_feat["vol_trend"] = df_feat["realized_vol"].diff(1)

        for col in ["cvd", "open_interest", "liquidations_buy", "liquidations_sell"]:
            if col not in df_feat.columns:
                df_feat[col] = 0.0
        # I-01 Fix: Make CVD a true Cumulative Oscillator (rolling sum)
        df_feat["cvd_cum"] = df_feat["cvd"].rolling(window=120, min_periods=1).sum()
        cvd_mean = df_feat["cvd_cum"].rolling(window=20, min_periods=1).mean()
        cvd_std  = df_feat["cvd_cum"].rolling(window=20, min_periods=1).std()
        df_feat["cvd_zscore"] = (df_feat["cvd_cum"] - cvd_mean) / cvd_std.replace(0, np.nan)
        
        df_feat["oi_rate_of_change"] = df_feat["open_interest"].pct_change(fill_method=None)
        
        df_feat["liq_intensity"] = df_feat["liquidations_buy"] + df_feat["liquidations_sell"]
        liq_median = df_feat["liq_intensity"].rolling(window=50).median().replace(0, 1.0)
        df_feat["liq_intensity"] = np.log1p(df_feat["liq_intensity"] / liq_median)

        df_feat = df_feat.fillna(0)
        return df_feat

    def _run_gaussian_bocpd(self, data: np.ndarray) -> tuple[np.ndarray, list[int]]:
        """
        Executes a simplified Student-T based Bayesian Online Changepoint Detection.
        For multidimensional data, we assume independence across dimensions for simplicity 
        of the predictive posterior to keep things lightweight.
        
        Returns:
            R: Run length probability matrix (T x T)
            cps: List of detected changepoint indices
        """
        T, num_dims = data.shape
        
        # R[t, r] is the probability that the current run length is r at time t
        R = np.zeros((T + 1, T + 1))
        R[0, 0] = 1.0
        
        # Sufficent statistics for Normal-Inverse-Gamma prior per dimension
        mu_0 = np.zeros(num_dims)
        kappa_0 = np.ones(num_dims) * BCD_PRIOR_KAPPA
        alpha_0 = np.ones(num_dims) * BCD_PRIOR_ALPHA
        beta_0 = np.ones(num_dims) * BCD_PRIOR_BETA
        
        # Arrays to hold sufficient stats for all possible run lengths
        mu_T = np.tile(mu_0, (T + 1, 1))
        kappa_T = np.tile(kappa_0, (T + 1, 1))
        alpha_T = np.tile(alpha_0, (T + 1, 1))
        beta_T = np.tile(beta_0, (T + 1, 1))
        
        maxes = np.zeros(T + 1)
        cps = []
        
        for t in range(1, T + 1):
            x = data[t - 1]
            
            # Predict predictive probability of x given current run length r
            # Student-T predictive posterior (assuming diagonal covariance)
            df = 2 * alpha_T[:t]
            loc = mu_T[:t]
            scale = np.sqrt(beta_T[:t] * (kappa_T[:t] + 1) / (alpha_T[:t] * kappa_T[:t]))
            
            # Probability density for each dimension, multiply across dimensions (sum of log pdfs)
            pred_probs = np.zeros(t)
            for d in range(num_dims):
                # Using a small offset to avoid log(0)
                pdf_vals = stats.t.pdf(x[d], df=df[:, d], loc=loc[:, d], scale=scale[:, d])
                # Increase sensitivity by squaring the pdf distances or multiplying by a factor if needed
                pred_probs += np.log(np.maximum(pdf_vals, 1e-10))
                
            pred_probs = np.exp(pred_probs - np.max(pred_probs)) # Normalize
            
            # Calculate growth probabilities (run length increases by 1)
            H = HAZARD_RATE
            growth_probs = pred_probs * R[t - 1, :t] * (1 - H)
            
            # Calculate changepoint probability (run length drops to 0)
            cp_prob = np.sum(pred_probs * R[t - 1, :t] * H)
            
            # Update R matrix
            R[t, 0] = cp_prob
            R[t, 1:t+1] = growth_probs
            
            # Normalize row
            if np.sum(R[t, :t+1]) > 0:
                R[t, :t+1] /= np.sum(R[t, :t+1])
            else:
                R[t, 0] = 1.0 # Fallback
                
            # Update sufficient statistics
            x_tile = np.tile(x, (t, 1))
            
            # Update for existing runs
            kappa_T_new = kappa_T[:t] + 1
            mu_T_new = (kappa_T[:t] * mu_T[:t] + x_tile) / kappa_T_new
            alpha_T_new = alpha_T[:t] + 0.5
            beta_T_new = beta_T[:t] + 0.5 * kappa_T[:t] * (x_tile - mu_T[:t])**2 / kappa_T_new
            
            # Shift everything down by 1 (since run length increased)
            mu_T[1:t+1] = mu_T_new
            kappa_T[1:t+1] = kappa_T_new
            alpha_T[1:t+1] = alpha_T_new
            beta_T[1:t+1] = beta_T_new
            
            # Reset stats for new changepoint (r = 0)
            mu_T[0] = mu_0
            kappa_T[0] = kappa_0
            alpha_T[0] = alpha_0
            beta_T[0] = beta_0

            maxes[t] = np.argmax(R[t, :])
            
            # Look back to find changepoints (simplistic peak detection on the MAP run length)
            # Make detection faster: check if MAP run length dropped
            if t > 2 and maxes[t] < maxes[t-1] - 1: 
                cps.append(t-1)
                
        return R, sorted(list(set(cps)))

    def _label_changepoint_segments(self, df_features: pd.DataFrame, cps: list[int]) -> np.ndarray:
        """
        Takes detected changepoints and labels each segment.

        KEY FIX: Splits any segment longer than MAX_SEGMENT_LEN into equal
        sub-segments so that each one gets a meaningful z-score evaluation.
        This prevents smooth uptrends/downtrends from being averaged to zero
        and mislabeled as Sideways.

        CHANGELOG fix/critical-optimizations:
        [FIX-4a] MIN_SEGMENT_LEN guard: segmen < 6 candle (1 hari) dianggap
                 noise post-spike, bukan regime sejati. Label-nya diwarisi
                 dari segmen sebelumnya.
        """
        MAX_SEGMENT_LEN = 48  # v3: ~8 days of 4H data
        # SYNC ke V1: tidak ada MIN_SEGMENT_LEN — semua segmen diberi label sendiri
        
        N = len(df_features)
        
        # Add 0 and N to bounds
        raw_bounds = [0] + cps + [N]
        raw_bounds = sorted(list(set(raw_bounds)))
        
        # --- Phase 1: Split long segments into sub-segments ---
        expanded_bounds = [0]
        for i in range(len(raw_bounds) - 1):
            seg_start = raw_bounds[i]
            seg_end = raw_bounds[i + 1]
            seg_len = seg_end - seg_start
            
            if seg_len > MAX_SEGMENT_LEN:
                # Split into equal sub-segments of ~MAX_SEGMENT_LEN
                n_splits = max(2, seg_len // MAX_SEGMENT_LEN)
                split_size = seg_len // n_splits
                for s in range(1, n_splits):
                    expanded_bounds.append(seg_start + s * split_size)
            
            expanded_bounds.append(seg_end)
        
        expanded_bounds = sorted(list(set(expanded_bounds)))
        
        # --- Phase 2: Evaluate each sub-segment independently ---
        global_std = float(df_features["log_return"].std())
        if global_std < 1e-10:
            global_std = 1e-10
        
        global_vol_median = float(df_features["realized_vol"].median())
        
        states = np.zeros(N, dtype=np.int32)
        segment_stats = []
        
        for i in range(len(expanded_bounds) - 1):
            start   = expanded_bounds[i]
            end     = expanded_bounds[i + 1]
            seg_df  = df_features.iloc[start:end]
            seg_len = len(seg_df)

            # Use CUMULATIVE return for trend detection
            cumulative_ret = seg_df["log_return"].sum()
            trend_z = cumulative_ret / (np.sqrt(seg_len) * global_std)
            
            mean_vol = seg_df["realized_vol"].mean()
            
            segment_stats.append({
                "id": i,
                "start": start,
                "end": end,
                "cumulative_ret": cumulative_ret,
                "trend_z": trend_z,
                "mean_vol": mean_vol,
                "length": seg_len
            })
            
            states[start:end] = i
            
        # --- Phase 3: Label based on cumulative trend z-score ---
        TREND_Z_BULL = 0.20   # v3: more sensitive to bullish
        TREND_Z_BEAR = 0.30
        
        state_map = {}
        for seg in segment_stats:
            sid = seg["id"]
            tz = seg["trend_z"]

            if tz > TREND_Z_BULL:
                state_map[sid] = REGIME_LABELS["bull"]
            elif tz < -TREND_Z_BEAR:
                state_map[sid] = REGIME_LABELS["bear"]
            else:
                if seg["mean_vol"] > global_vol_median:
                    state_map[sid] = REGIME_LABELS["hv_sw"]
                else:
                    state_map[sid] = REGIME_LABELS["lv_sw"]
                        
        self.state_map = state_map
        return states

    def train_global(self, df_history: pd.DataFrame) -> bool:
        """
        Scans full history to determine optimal boundaries, and benchmark scaling.
        """
        if df_history is None or len(df_history) < GLOBAL_TRAIN_MIN_ROWS:
            return False
            
        try:
            df_prepared = self.prepare_features(df_history)
            df_features = df_prepared.dropna(subset=self._active_features)
            X_raw = df_features[self._active_features].values
            X_scaled = self.scaler.fit_transform(X_raw)
            
            # Save global return STD for stable segment labeling
            self._global_return_std = float(df_features["log_return"].std())
            
            # Run BOCPD
            R, cps = self._run_gaussian_bocpd(X_scaled)
            self._R = R
            self._changepoints = cps
            
            # Label
            states = self._label_changepoint_segments(df_features, cps)
            
            # ECONOPHYSICS Modul A: Transition matrix
            self._transition_matrix = self._compute_transition_matrix(states)
            self.get_regime_bias()  # precompute
            
            self._global_trained = True
            self._last_trained_len = len(df_history)
            
            logging.info(f"[BCD global] Trained on {len(df_history)} candles. Found {len(cps)} changepoints.")
            return True
        except Exception as e:
            logging.error(f"[BCD global] Training failed: {e}")
            return False

    def label_states(self, df_features: pd.DataFrame, hidden_states: np.ndarray) -> dict[int, str]:
        """Compatibility wrapper for testing scripts."""
        # For BCD, labels are generated during train_global or get_current_regime 
        # using _label_changepoint_segments. 
        # But if a script explicitly calls this, we just ensure _label_changepoint_segments is run.
        if hasattr(self, '_changepoints'):
            self._label_changepoint_segments(df_features, self._changepoints)
        return self.state_map

    def train_model(self, X_scaled: np.ndarray, current_len: int = 0) -> np.ndarray:
        """Compatibility wrapper"""
        R, cps = self._run_gaussian_bocpd(X_scaled)
        self._R = R
        self._changepoints = cps
        
        # We don't have df_features here to calculate Z-scores properly,
        # but the actual flow uses label_changepoint_segments where df_features is available.
        # So we just return dummy distinct states (segments).
        bounds = [0] + cps + [len(X_scaled)]
        bounds = sorted(list(set(bounds)))
        states = np.zeros(len(X_scaled), dtype=np.int32)
        for i in range(len(bounds) - 1):
            states[bounds[i]:bounds[i+1]] = i
        return states

    def get_current_regime(self, df: pd.DataFrame, funding_rate: float = 0.0) -> tuple[str, int]:
        """
        Returns the regime for the latest candle.
        """
        if df is None or len(df) < MIN_ROWS:
            return ("Data Insufficient", -1)
            
        try:
            df_prepared = self.prepare_features(df)
            df_features = df_prepared.dropna(subset=self._active_features)
            
            if len(df_features) < 10:
                return ("Data Insufficient", -1)
                
            X_raw = df_features[self._active_features].values
            
            if not self._global_trained:
                X_scaled = self.scaler.fit_transform(X_raw)
                self.train_global(df)
            else:
                X_scaled = self.scaler.transform(X_raw)
                
            # For inference, run on the recent window to find local regime
            # Or if global_trained, we could just run BOCPD continuously
            R, cps = self._run_gaussian_bocpd(X_scaled)
            self._R = R
            self._changepoints = cps
            
            states = self._label_changepoint_segments(df_features, cps)
            current_state = int(states[-1])
            
            # Recompute transition matrix and bias cache occasionally
            self._transition_matrix = self._compute_transition_matrix(states)
            self._regime_bias_cache = {}  # Invalidate cache
            
            return (self.state_map.get(current_state, REGIME_LABELS["unknown"]), current_state)
            
        except Exception as e:
            logging.error(f"Error in BCD get_current_regime: {e}")
            return (f"Error", -1)

    # ────────────────────────────────────────────────────────
    #  ECONOPHYSICS MODUL A — TRANSITION MATRIX & REGIME BIAS
    # ────────────────────────────────────────────────────────

    def _compute_transition_matrix(self, hidden_states: np.ndarray) -> np.ndarray:
        """
        SYNC ke V1: matriks transisi berbasis segment ID (integer 0,1,2...).
        """
        if not self.state_map:
            return np.zeros((1, 1))

        n = max(self.state_map.keys()) + 1 if self.state_map else 1
        trans_count = np.zeros((n, n), dtype=np.float64)

        for t in range(len(hidden_states) - 1):
            i = int(hidden_states[t])
            j = int(hidden_states[t + 1])
            if 0 <= i < n and 0 <= j < n:
                trans_count[i, j] += 1

        row_sums = trans_count.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1.0
        transition_matrix = trans_count / row_sums

        self._transition_matrix = transition_matrix
        return transition_matrix

    def _compute_expected_duration(self, state_id: int) -> float:
        if self._transition_matrix is None or state_id >= len(self._transition_matrix):
            return 0.0
        p_persist = float(self._transition_matrix[state_id, state_id])
        if p_persist >= 1.0:
            return 999.0
        return round(1.0 / max(1.0 - p_persist, 1e-6), 1)

    def get_regime_bias(self) -> dict:
        """
        SYNC ke V1: hitung regime bias per segment ID (state_map keys).
        """
        if self._transition_matrix is None or not self.state_map:
            return {}

        if self._regime_bias_cache:
            return self._regime_bias_cache

        n = len(self._transition_matrix)
        bias_report: dict = {}

        for state_id, label in self.state_map.items():
            if state_id >= n:
                continue

            row = self._transition_matrix[state_id]
            persistence = float(row[state_id])

            reversal = 0.0
            for other_id, other_label in self.state_map.items():
                if other_id == state_id:
                    continue
                if (("Bullish" in label and "Bearish" in other_label) or
                        ("Bearish" in label and "Bullish" in other_label)):
                    if other_id < n:
                        reversal += float(row[other_id])

            bias_score = float(persistence - reversal)
            expected_dur = self._compute_expected_duration(state_id)

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
        return bias_report

    def cache_info(self) -> dict:
        return {
            "trained": self._global_trained,
            "last_trained_len": self._last_trained_len,
            "engine_type": "BCD",
            "changepoints_found": len(self._changepoints),
            "transition_matrix": self._transition_matrix.tolist() if self._transition_matrix is not None else None,
            "regime_bias": self._regime_bias_cache,
        }

    def get_directional_vote(self, df: pd.DataFrame, funding_rate: float = 0.0) -> float:
        """
        Continuous directional vote [-1.0, 1.0].
        In BCD, this can be derived from the probability of the current segment 
        being explicitly Bullish or Bearish. Since segments are deterministic, 
        we can use the most likely run length regime, multiplied by its conviction. 
        """
        res_label, current_state = self.get_current_regime(df, funding_rate)
        if current_state == -1: return 0.0
        
        if res_label == REGIME_LABELS["bull"]:
            return 1.0
        elif res_label == REGIME_LABELS["bear"]:
            return -1.0
        else:
            return 0.0
            
    def get_state_sequence_raw(self, df: pd.DataFrame) -> tuple[np.ndarray | None, pd.Index | None]:
        """Compatibility function for MLP cross features."""
        if df is None or len(df) < MIN_ROWS: return None, None
        try:
            df_prepared = self.prepare_features(df)
            df_features = df_prepared.dropna(subset=self._active_features)
            X_raw = df_features[self._active_features].values
            
            if not self._global_trained:
                X_scaled = self.scaler.fit_transform(X_raw)
            else:
                X_scaled = self.scaler.transform(X_raw)
                
            R, cps = self._run_gaussian_bocpd(X_scaled)
            states = self._label_changepoint_segments(df_features, cps)
            return states, df_features.index
        except:
            return None, None
            
    def get_current_regime_posterior(self, df: pd.DataFrame, funding_rate: float = 0.0) -> tuple[str, int, np.ndarray]:
        """
        Return fake posterior since Segment is absolute. We return 1.0 for the active state
        and 0.0 for the rest, to ensure Layer 3 compatibility.
        """
        label, sid = self.get_current_regime(df, funding_rate)
        
        # Max 10 segments as pseudo states
        n_max = max(10, len(self.state_map))
        posterior = np.zeros(n_max)
        if 0 <= sid < n_max:
            posterior[sid] = 1.0
        else:
            posterior[0] = 1.0 # fallback
            
        return label, sid, posterior


# ════════════════════════════════════════════════════════════
#  STANDALONE TEST
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from data_engine import get_latest_market_data

    print("\n ⚡ BTC-QUANT · Layer 1 BCD Test (Econophysics Enabled)")
    print(" ─" * 30)

    df_ohlcv, _ = get_latest_market_data()

    if df_ohlcv is None or df_ohlcv.empty:
        print(" ⚠ No data in BTC-QUANT.db. Run data_engine.py first.")
    else:
        model = BayesianChangepointModel()

        # Test 1: Standard regime
        label, state_id = model.get_current_regime(df_ohlcv)
        print(f"\n  📊 Data rows : {len(df_ohlcv)}")
        print(f"  🏷️  Regime    : {label}  (state {state_id})")

        # Test 2: Directional Vote
        vote = model.get_directional_vote(df_ohlcv)
        print(f"\n  🎯 Directional Vote: {vote:.4f}")

        # Test 3: Raw state sequence & Posterior
        states_arr, idx = model.get_state_sequence_raw(df_ohlcv)
        if states_arr is not None:
            print(f"\n  ── State Sequence (last 5) ──")
            for i, (s, ix) in enumerate(zip(states_arr[-5:], idx[-5:])):
                print(f"    [{ix}]  state={s}  ({model.state_map.get(s,'?')})")
                
        label2, state2, posterior = model.get_current_regime_posterior(df_ohlcv)
        print(f"\n  ── Posterior Probabilities (Fake/Absolute for BCD) ──")
        for sid, prob in enumerate(posterior):
            if prob > 0:
                regime = model.state_map.get(sid, f"State {sid}")
                print(f"    State {sid} [{regime:30s}]  P={prob:.4f} ◀ CURRENT")

        # Test 4: Cache info & Econophysics Transition Bias
        info = model.cache_info()
        print(f"\n  ── Cache Info (Econophysics) ──")
        print(f"    Changepoints Found: {info['changepoints_found']}")
        
        regime_bias = info.get("regime_bias", {})
        if regime_bias:
            print(f"\n  ── Econophysics: Regime Bias ──")
            for r_label, stats in regime_bias.items():
                print(f"    {r_label[:25]:25s} | Bias: {stats['bias_score']:>5.2f} | "
                      f"E[T]: {stats['expected_duration_candles']:>4.1f}c | "
                      f"P_self: {stats['persistence']:>4.2f}")
        else:
             print("    No Regime Bias available yet.")

    print("\n  ✅ Layer 1 BCD test complete.\n")
