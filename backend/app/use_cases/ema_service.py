"""
EMA Service — Singleton wrapper untuk Layer 2 Structural Analysis.

CHANGELOG fix/critical-optimizations:
--------------------------------------
[FIX-2] Fix inkonsistensi EMA vs Ichimoku.

Sebelumnya kode menjalankan EMAStructureModel tapi docstring di
DirectionalSpectrum mengatakan "L2 is now powered by Ichimoku Cloud."
Ini adalah split personality yang berbahaya — dokumentasi vs implementasi
tidak konsisten.

Keputusan: TETAP pakai EMAStructureModel sebagai default production.
Alasan:
  - EMA adalah layer yang ter-validasi di backtest +597%
  - Ichimoku (layer2_ichimoku.py) sudah ada tapi belum di-backtest
  - Komentar "Experiment 2026-02-28" di ichimoku file mengkonfirmasi
    bahwa ia belum production-ready

Ichimoku tersedia sebagai OPSIONAL via USE_ICHIMOKU env variable,
sehingga bisa di-A/B test tanpa mengubah kode production:
    USE_ICHIMOKU=true  → pakai IchimokuCloudModel
    USE_ICHIMOKU=false → pakai EMAStructureModel (default)

Ini memungkinkan backtest isolated: jalankan pipeline dua kali dengan
env variable berbeda dan bandingkan equity curve.
"""

import os
import sys
import threading
from pathlib import Path

import pandas as pd

from app.core.engines.layer2_ema import EMAStructureModel
# [FIX-2] Import Ichimoku secara opsional — tidak crash kalau belum diinstall
_USE_ICHIMOKU = os.getenv("USE_ICHIMOKU", "false").strip().lower() == "true"
if _USE_ICHIMOKU:
    try:
        from app.core.engines.layer2_ichimoku import IchimokuCloudModel
        _ichimoku_available = True
    except ImportError:
        _ichimoku_available = False
        _USE_ICHIMOKU = False
else:
    _ichimoku_available = False


class EMAService:
    """
    Layer 2 service wrapper.

    Mode aktif ditentukan oleh env variable USE_ICHIMOKU:
        False (default) → EMAStructureModel  [VALIDATED, production-safe]
        True            → IchimokuCloudModel  [EXPERIMENTAL, butuh backtest]

    Kedua model mengekspos get_directional_vote() dengan signature identik
    sehingga bisa di-swap tanpa mengubah signal_service.py.
    """

    def __init__(self):
        if _USE_ICHIMOKU and _ichimoku_available:
            self._model   = IchimokuCloudModel()
            self._mode    = "ichimoku"
        else:
            self._model   = EMAStructureModel()
            self._mode    = "ema"

    @property
    def mode(self) -> str:
        """Kembalikan mode aktif: 'ema' atau 'ichimoku'."""
        return self._mode

    def get_alignment(
        self, df: pd.DataFrame, trend_short: str
    ) -> tuple[bool, str, str]:
        """
        Kembalikan (is_aligned, label, detail).

        Untuk kompatibilitas dengan signal_service.py yang masih memakai
        tuple 3-elemen dari get_alignment().

        Jika mode=ichimoku, is_aligned diturunkan dari vote kontinu:
            vote >  0.15 → aligned (bull)
            vote < -0.15 → aligned (bear)
            lainnya      → not aligned
        """
        try:
            if self._mode == "ema":
                return self._model.get_ema_alignment(df, trend_short)

            # Ichimoku path — adaptasi output ke format tuple 3-elemen
            vote  = self._model.get_directional_vote(df)
            is_bull = trend_short == "BULL"

            if is_bull:
                is_aligned = vote > 0.15
                label  = "Bullish Confirmed (Ichimoku)" if is_aligned else "Bullish Weak (Ichimoku)"
                detail = f"Ichimoku vote={vote:+.3f}"
            else:
                is_aligned = vote < -0.15
                label  = "Bearish Confirmed (Ichimoku)" if is_aligned else "Bearish Weak (Ichimoku)"
                detail = f"Ichimoku vote={vote:+.3f}"

            return is_aligned, label, detail

        except Exception as exc:
            return False, f"L2 Error ({self._mode})", str(exc)

    def get_directional_vote(self, df: pd.DataFrame) -> float:
        """
        Kembalikan continuous vote [-1, +1] langsung dari model.
        Dipakai di Spectrum v2 jika signal_service diupdate ke full-vote mode.
        """
        try:
            if self._mode == "ema":
                return self._model.get_directional_vote(df)
            return self._model.get_directional_vote(df)
        except Exception:
            return 0.0

    def is_ichimoku(self) -> bool:
        return self._mode == "ichimoku"


# ── Singleton ─────────────────────────────────────────────────────────────────

_ema:      EMAService | None = None
_ema_lock: threading.Lock    = threading.Lock()


def get_ema_service() -> EMAService:
    """
    Return module-level singleton EMAService.

    Mode ditentukan saat pertama kali dipanggil berdasarkan env USE_ICHIMOKU.
    Untuk switch mode: restart server + set env variable.
    """
    global _ema
    if _ema is None:
        with _ema_lock:
            if _ema is None:
                _ema = EMAService()
    return _ema
