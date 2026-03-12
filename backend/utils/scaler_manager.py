"""
╔══════════════════════════════════════════════════════════════╗
║  BTC-QUANT-BTC: THREAD-SAFE SCALER MANAGER                     ║
║  Fixes scaler contamination & race condition bugs            ║
╚══════════════════════════════════════════════════════════════╝

Solves two critical bugs found in audit:
    Bug #1 — Scaler contamination: fit_transform called unconditionally
             in prepare_features(), corrupting PATH B (cache path).
    Bug #3 — Race condition: singleton pattern not thread-safe.

Usage:
    scaler = ThreadSafeScalerManager()

    # Training path (fit + transform):
    X_scaled = scaler.fit_transform(X)

    # Inference path (transform only, uses fitted params):
    X_scaled = scaler.transform(X)

    # Thread-safe singleton for shared use across services:
    scaler = get_scaler("hmm")
    scaler = get_scaler("mlp")
"""

import threading
import numpy as np
from sklearn.preprocessing import StandardScaler


class ThreadSafeScalerManager:
    """
    A thread-safe wrapper around sklearn's StandardScaler.

    Guarantees:
        - fit_transform() and transform() are mutually exclusive via RLock.
        - is_fitted property prevents transform() on an unfitted scaler.
        - Separate scaler instances per model (HMM vs MLP) via registry.
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self._scaler = StandardScaler()
        self._lock = threading.RLock()
        self._fitted = False

    @property
    def is_fitted(self) -> bool:
        return self._fitted

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        """
        Fit the scaler on X, then transform X.
        Always used during training / retrain path.
        Thread-safe.
        """
        with self._lock:
            result = self._scaler.fit_transform(X)
            self._fitted = True
            return result

    def transform(self, X: np.ndarray) -> np.ndarray:
        """
        Transform X using already-fitted scaler parameters.
        Used on inference / cache path — never refits.
        Raises RuntimeError if scaler has not been fitted yet.
        Thread-safe.
        """
        with self._lock:
            if not self._fitted:
                raise RuntimeError(
                    f"[ScalerManager:{self.name}] transform() called before fit. "
                    "Call fit_transform() during training first."
                )
            return self._scaler.transform(X)

    def fit(self, X: np.ndarray) -> "ThreadSafeScalerManager":
        """Fit only (no transform). Useful for explicit separation."""
        with self._lock:
            self._scaler.fit(X)
            self._fitted = True
        return self

    def reset(self):
        """Reset scaler to unfitted state (e.g., before full retrain)."""
        with self._lock:
            self._scaler = StandardScaler()
            self._fitted = False


# ════════════════════════════════════════════════════════════
#  SCALER REGISTRY — one instance per named model
# ════════════════════════════════════════════════════════════

_registry: dict[str, ThreadSafeScalerManager] = {}
_registry_lock = threading.Lock()


def get_scaler(name: str) -> ThreadSafeScalerManager:
    """
    Return (or create) the named ThreadSafeScalerManager.

    Usage:
        hmm_scaler = get_scaler("hmm")
        mlp_scaler = get_scaler("mlp")

    The registry ensures each model always gets its own
    isolated scaler instance, preventing cross-model contamination.
    """
    if name not in _registry:
        with _registry_lock:
            # Double-check locking
            if name not in _registry:
                _registry[name] = ThreadSafeScalerManager(name=name)
    return _registry[name]
