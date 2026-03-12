"""
AI Service — thin wrapper around SignalIntelligenceModel.

HOTFIX  2026-02-27: Thread-safe singleton.
PHASE 3 2026-02-27: get_confidence() now accepts optional hmm_states and
                    hmm_index for HMM→MLP feature cross injection.
"""
import sys
import threading
from pathlib import Path

from app.core.engines.layer3_ai import SignalIntelligenceModel

import numpy as np
import pandas as pd


class AIService:
    def __init__(self):
        self._model = SignalIntelligenceModel()

    def get_confidence(
        self,
        df: pd.DataFrame,
        hmm_states: np.ndarray | None = None,
        hmm_index: pd.Index | None    = None,
    ) -> tuple[str, float]:
        """
        Returns (bias, confidence_pct).
        bias = 'BULL' | 'BEAR' | 'NEUTRAL'
        confidence_pct = 50.0 – 100.0
        Never raises.

        PHASE 3: Pass hmm_states + hmm_index to enable HMM feature cross.
        If either is None, falls back to 5-feature (technical only) mode.
        """
        return self._model.get_ai_confidence(
            df,
            hmm_states = hmm_states,
            hmm_index  = hmm_index,
        )

    def is_cross_enabled(self) -> bool:
        """PHASE 3: True if last inference used HMM cross features."""
        return self._model.is_cross_enabled

    def cache_info(self) -> dict:
        """Fetch caching and training state info of the MLP model."""
        return self._model.get_model_info()


# Singleton — thread-safe double-check locking
_ai: AIService | None = None
_ai_lock = threading.Lock()


def get_ai_service() -> AIService:
    global _ai
    if _ai is None:
        with _ai_lock:
            if _ai is None:
                _ai = AIService()
    return _ai
