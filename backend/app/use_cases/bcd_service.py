"""
BCD Service — wrapper around Layer 1 engines (BayesianChangepointModel / MarketRegimeModel)

Renamed from hmm_service.py → bcd_service.py to reflect that BCD is now
the default and primary Layer 1 engine.

HOTFIX  2026-02-27: Thread-safe singleton.
PHASE 3 2026-02-27: Expose get_state_sequence_raw() and
                    get_current_regime_posterior() for MLP cross-feature.
PHASE 7 2026-03-01: Added Bayesian Changepoint Detection (BCD) support.
RENAME  2026-03-04: hmm_service → bcd_service. hmm_service.py now re-exports
                    everything here for backward compatibility.
FIX-OPT-1 2026-03-04: get_regime_and_states() — single BOCPD pass that
                    returns regime + state sequence without redundant re-run.
"""
import os
import sys
import threading
from pathlib import Path

from app.core.engines.layer1_bcd import BayesianChangepointModel
# HMM engine has been moved to experimental, but let's assume we don't need it or import from there
try:
    from app.core.engines.experimental.layer1_hmm import MarketRegimeModel, RETRAIN_EVERY_N_CANDLES
except ImportError:
    MarketRegimeModel = None
    RETRAIN_EVERY_N_CANDLES = 100

import numpy as np
import pandas as pd


class Layer1EngineService:
    def __init__(self):
        engine_type = os.getenv("LAYER1_ENGINE", "BCD").upper()
        self.engine_type = engine_type
        if engine_type == "HMM":
            self._model = MarketRegimeModel()
            print("[BCDService] Initialized with HMM Engine.")
        else:
            self._model = BayesianChangepointModel()
            print("[BCDService] Initialized with BCD Engine.")

    def get_regime(self, df: pd.DataFrame, funding_rate: float = 0.0) -> tuple[str, str]:
        """
        Returns (regime_label, tag) where tag is 'bull'|'bear'|'neutral'.
        Never raises.
        """
        label, _ = self._model.get_current_regime(df, funding_rate=funding_rate)
        if "Bullish" in label:
            tag = "bull"
        elif "Bearish" in label:
            tag = "bear"
        else:
            tag = "neutral"
        return label, tag

    # ── PHASE 3 — methods ──────────────────────────────────────────────────────

    def get_state_sequence_raw(
        self,
        df: pd.DataFrame,
    ) -> tuple[np.ndarray | None, pd.Index | None]:
        """
        Returns (states_array, df_index) for MLP cross-feature injection.
        states_array: int array shape (n_valid_rows,) aligned to df_index.
        Returns (None, None) if insufficient data or model untrained.
        """
        return self._model.get_state_sequence_raw(df)

    def get_regime_with_posterior(
        self,
        df: pd.DataFrame,
        funding_rate: float = 0.0,
    ) -> tuple[str, str, float]:
        """
        Returns (regime_label, tag, confidence).
        """
        try:
            label, state_id, posterior = self._model.get_current_regime_posterior(
                df, funding_rate=funding_rate
            )

            if "Bullish" in label:
                tag = "bull"
            elif "Bearish" in label:
                tag = "bear"
            else:
                tag = "neutral"

            # Confidence = probability of the current (directional) state
            if state_id >= 0 and state_id < len(posterior):
                confidence = float(posterior[state_id])
            else:
                confidence = 0.25   # Uniform fallback

            return label, tag, confidence

        except Exception as e:
            import logging
            logging.error(f"[BCDService] Error getting posterior: {e}")
            return "Unknown Regime", "neutral", 0.25

    # ── FIX-OPT-1: single-pass (no double BOCPD) ──────────────────────────────

    def get_regime_and_states(
        self,
        df: pd.DataFrame,
        funding_rate: float = 0.0,
    ) -> tuple[str, str, float, "np.ndarray | None", "pd.Index | None"]:
        """
        FIX-OPT-1: Runs BOCPD exactly ONCE and returns everything the
        walk-forward engine needs in a single pass.

        Returns:
            (regime_label, tag, confidence, states_array, states_index)

        Walk-forward engine previously called two separate methods:
            get_regime_with_posterior()  →  1 full BOCPD run
            get_state_sequence_raw()     →  1 full BOCPD run  (redundant!)
        Now it calls only this method      →  1 BOCPD run total.

        For BCD: after get_current_regime_posterior() the model has already
        cached ._changepoints and .state_map, so we rebuild the state
        sequence from those caches without re-running BOCPD.
        """
        try:
            label, tag, confidence = self.get_regime_with_posterior(df, funding_rate)

            # ── BCD fast-path: reconstruct states from cached BOCPD results ──
            if hasattr(self._model, "_changepoints") and hasattr(self._model, "prepare_features"):
                try:
                    df_prepared = self._model.prepare_features(df)
                    df_features = df_prepared.dropna(subset=self._model._active_features)
                    states = self._model._label_changepoint_segments(
                        df_features, self._model._changepoints
                    )
                    return label, tag, confidence, states, df_features.index
                except Exception:
                    pass  # fallback to separate call below

            # ── Fallback: second call only when fast-path not available ──────
            states, idx = self.get_state_sequence_raw(df)
            return label, tag, confidence, states, idx

        except Exception as exc:
            import logging
            logging.error(f"[BCDService] get_regime_and_states error: {exc}")
            return "Unknown Regime", "neutral", 0.25, None, None

    # ── cache info ─────────────────────────────────────────────────────────────

    def get_regime_bias(self) -> dict:
        """
        ECONOPHYSICS Modul A: Delegate ke engine._model.get_regime_bias().

        Returns dict keyed by regime label dengan keys:
            persistence, reversal_prob, bias_score,
            expected_duration_candles, interpretation, next_state_probs

        Returns empty dict jika engine belum dilatih atau tidak mendukung.
        """
        try:
            if hasattr(self._model, "get_regime_bias"):
                return self._model.get_regime_bias()
            return {}
        except Exception as exc:
            import logging
            logging.warning(f"[BCDService] get_regime_bias failed: {exc}")
            return {}

    def cache_info(self) -> dict:
        """Fetch engine-specific cache information."""
        if hasattr(self._model, "cache_info"):
            return self._model.cache_info()
        else:
            return {
                "trained": getattr(self._model, "_global_trained", False),
                "last_trained_len": getattr(self._model, "_last_trained_len", 0),
                "engine_type": self.engine_type
            }


# ── Singleton — thread-safe double-check locking ──────────────────────────────
_bcd: Layer1EngineService | None = None
_bcd_lock = threading.Lock()


def get_bcd_service() -> Layer1EngineService:
    global _bcd
    if _bcd is None:
        with _bcd_lock:
            if _bcd is None:
                _bcd = Layer1EngineService()
    return _bcd


# ── Backward-compat alias (used by hmm_service.py shim) ───────────────────────
get_hmm_service = get_bcd_service
