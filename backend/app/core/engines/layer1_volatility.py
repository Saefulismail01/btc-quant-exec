"""
╔══════════════════════════════════════════════════════════════╗
║  BTC-QUANT: LAYER 1 — VOLATILITY REGIME (HESTON MODEL)      ║
║  Stochastic Volatility Estimator · CPU-Only                  ║
║  Stack: numpy + pandas + scipy                               ║
║                                                              ║
║  ECONOPHYSICS Modul B                                        ║
║  Berdasarkan: Palupi, Dwi Satya (2022)                       ║
║  "Pasar Keuangan dan Proses Stokastik"                       ║
║                                                              ║
║  Model Heston (1993):                                        ║
║    dS(t) = φS(t)dt + √v(t)·S·dB_S                          ║
║    dv(t) = -γ(v - η)dt + κ√v·dB_v                          ║
║                                                              ║
║  Di mana:                                                    ║
║    v(t) = σ²(t) = variansi yang berubah terhadap waktu      ║
║    γ    = kecepatan mean-reversion volatilitas               ║
║    η    = variansi jangka panjang (long-run mean)            ║
║    κ    = volatilitas dari volatilitas (vol-of-vol)          ║
║                                                              ║
║  Relevansi untuk BTC-Quant:                                  ║
║    Volatilitas BTC tidak konstan — bisa berbeda 10x antara  ║
║    periode tenang dan krisis. Parameter Heston diestimasi    ║
║    dari realized variance historis menggunakan OLS sederhana.║
║                                                              ║
║  Output digunakan signal_service.py untuk:                  ║
║    1. SL/TP multiplier berbasis regime volatilitas          ║
║    2. Interpretasi "apakah vol sedang tinggi/normal/rendah" ║
║    3. Perkiraan berapa candle sampai vol kembali normal      ║
╚══════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import threading
import logging
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=RuntimeWarning)

# ════════════════════════════════════════════════════════════
#  KONSTANTA
# ════════════════════════════════════════════════════════════

VOL_WINDOW           = 14   # Window realized variance (sesuai layer1_hmm)
MIN_ROWS             = 50   # Minimum candle untuk estimasi

# Threshold untuk klasifikasi vol_regime
VOL_HIGH_MULTIPLIER  = 1.5  # current_vol > eta * 1.5 → "High"
VOL_LOW_MULTIPLIER   = 0.7  # current_vol < eta * 0.7 → "Low"

# Cache: re-estimasi setiap N candle baru
REESTIMATE_EVERY_N   = 12


# ════════════════════════════════════════════════════════════
#  VOLATILITY REGIME ESTIMATOR
# ════════════════════════════════════════════════════════════

class VolatilityRegimeEstimator:
    """
    Estimasi parameter Model Heston dari data historis BTC.

    Pendekatan: Method of Moments dengan OLS sederhana.
    Dari persamaan diskrit model Heston:
      Δv ≈ -γ(v - η)·Δt + noise
      dv = α + β·v  → α = γ·η, β = -γ

    OLS pada pasangan (v_t, Δv_t) memberikan estimasi γ dan η
    yang robust meski bukan Maximum Likelihood Estimation penuh.
    """

    def __init__(self):
        self._last_params: dict    = {}
        self._last_trained_len: int = 0
        self._lock = threading.Lock()

    def estimate_params(self, df: pd.DataFrame) -> dict:
        """
        Estimasi parameter Heston dari OHLCV DataFrame.

        Dari Persamaan Fokker-Planck (Palupi 2022, Materi 2):
        Evolusi rapat peluang variansi mengikuti:
          ∂P/∂t = γ∂/∂v[(v-θ)P] + (κ²/2)∂²/∂v²[vP]

        Parameter yang diestimasi:
        - gamma (γ): kecepatan mean-reversion → seberapa cepat vol kembali normal
        - eta (η):   variansi long-run → "normal level" vol untuk BTC
        - kappa (κ): vol-of-vol → seberapa volatile-nya volatilitas itu sendiri

        Returns dict:
            gamma, eta, kappa, current_vol, long_run_vol,
            vol_regime, mean_reversion_halflife_candles, interpretation
        """
        if df is None or len(df) < MIN_ROWS:
            return self._fallback_params()

        # Cache: jangan re-estimasi jika data tidak berubah signifikan
        current_len = len(df)
        with self._lock:
            if (self._last_params
                    and current_len - self._last_trained_len < REESTIMATE_EVERY_N):
                return self._last_params

        try:
            log_returns = np.log(df["Close"] / df["Close"].shift(1)).fillna(0)

            # Realized variance (proxy untuk v(t) dalam model Heston)
            realized_var = log_returns.rolling(VOL_WINDOW).var().dropna()

            if len(realized_var) < 30:
                return self._fallback_params()

            # ── Estimasi γ (gamma) dan η (eta) via OLS ───────────────────────
            # Model: dv = -γ(v - η)dt + noise
            # → Δv = (α + β·v)·Δt, di mana α = γη, β = -γ
            # Numerik: Δv_t = α + β·v_t → OLS bivariate

            dv = realized_var.diff().dropna()
            v  = realized_var.iloc[:-1]

            if len(dv) < 20 or len(v) < 20:
                return self._fallback_params()

            # OLS: dv = alpha + beta * v
            v_arr = v.values.astype(float)
            dv_arr = dv.values.astype(float)

            # Filter outlier (hanya gunakan yang < 5σ)
            z_v  = np.abs(v_arr  - np.mean(v_arr))  / (np.std(v_arr)  + 1e-12)
            z_dv = np.abs(dv_arr - np.mean(dv_arr)) / (np.std(dv_arr) + 1e-12)
            mask = (z_v < 5) & (z_dv < 5)
            v_clean  = v_arr[mask]
            dv_clean = dv_arr[mask]

            if len(v_clean) < 15:
                return self._fallback_params()

            # OLS via numpy
            A = np.column_stack([np.ones(len(v_clean)), v_clean])
            try:
                coeffs, _, _, _ = np.linalg.lstsq(A, dv_clean, rcond=None)
            except np.linalg.LinAlgError:
                return self._fallback_params()

            alpha, beta = float(coeffs[0]), float(coeffs[1])

            # γ = -β (harus positif untuk mean-reverting)
            gamma = max(-beta, 1e-6)

            # η = α/γ (long-run mean variance)
            eta = alpha / gamma if gamma > 1e-6 else float(np.mean(v_clean))
            eta = max(eta, 1e-8)   # variansi selalu positif

            # ── Estimasi κ (kappa) — vol of vol ──────────────────────────────
            # Residual dari OLS = komponen stokastik κ√v·dB_v
            # κ ≈ std(residuals) / √mean(v)
            residuals = dv_clean - (alpha + beta * v_clean)
            v_mean_sqrt = float(np.sqrt(np.mean(v_clean)))
            kappa = float(np.std(residuals)) / max(v_mean_sqrt, 1e-8)

            # ── Current & long-run volatility ─────────────────────────────────
            current_var = float(realized_var.iloc[-1])
            current_vol = float(np.sqrt(max(current_var, 0)))
            long_run_vol = float(np.sqrt(max(eta, 0)))

            # ── Vol regime classification ─────────────────────────────────────
            if long_run_vol > 0:
                vol_ratio = current_vol / long_run_vol
                if vol_ratio > VOL_HIGH_MULTIPLIER:
                    vol_regime = "High"
                elif vol_ratio < VOL_LOW_MULTIPLIER:
                    vol_regime = "Low"
                else:
                    vol_regime = "Normal"
            else:
                vol_regime = "Normal"

            # ── Mean-reversion half-life ──────────────────────────────────────
            # T½ = ln(2) / γ
            # Ini adalah waktu yang dibutuhkan vol untuk kembali setengah jalan
            # dari posisi saat ini ke long-run mean
            halflife = float(np.log(2) / gamma) if gamma > 0 else 999.0
            halflife = min(halflife, 9999.0)   # cap untuk display

            # ── Human-readable interpretation ────────────────────────────────
            if vol_regime == "High":
                interp = (
                    f"Volatilitas tinggi ({current_vol:.4f} vs long-run {long_run_vol:.4f}). "
                    f"Perkiraan kembali normal dalam ~{halflife:.1f} candle. "
                    "SL lebih lebar, TP lebih konservatif."
                )
            elif vol_regime == "Low":
                interp = (
                    f"Volatilitas rendah ({current_vol:.4f} vs long-run {long_run_vol:.4f}). "
                    f"Perkiraan meningkat dalam ~{halflife:.1f} candle. "
                    "Regime tenang, trend lebih reliable."
                )
            else:
                interp = (
                    f"Volatilitas normal ({current_vol:.4f} ~ long-run {long_run_vol:.4f}). "
                    "Gunakan SL/TP standar."
                )

            params = {
                "gamma":                             round(gamma,       6),
                "eta":                               round(eta,         8),
                "kappa":                             round(kappa,       6),
                "current_vol":                       round(current_vol, 6),
                "long_run_vol":                      round(long_run_vol,6),
                "vol_regime":                        vol_regime,
                "mean_reversion_halflife_candles":   round(halflife,    1),
                "interpretation":                    interp,
            }

            with self._lock:
                self._last_params       = params
                self._last_trained_len  = current_len

            logging.debug(
                f"[Heston] γ={gamma:.4f} η={eta:.6f} κ={kappa:.4f} "
                f"vol={current_vol:.4f} regime={vol_regime} T½={halflife:.1f}c"
            )
            return params

        except Exception as exc:
            logging.warning(f"[Heston] estimate_params failed: {exc}")
            return self._fallback_params()

    def get_sl_tp_multipliers(
        self,
        vol_regime:  str,
        halflife:    float,
        bias_score:  float = 0.5,
    ) -> dict:
        """
        Tentukan SL/TP multiplier berdasarkan kombinasi:
        - Heston vol_regime (High/Normal/Low)
        - halflife (seberapa cepat vol akan kembali normal)
        - bias_score dari Modul A (seberapa persistent regime saat ini)

        Dari teori (Palupi 2022, Materi 2 — Model Heston + PRD I-05):
        Regime-aware SL/TP adalah improvement kritis atas flat 1.5x/2.5x ATR.

        Returns:
            {
              preset_name: str,
              sl_multiplier: float,
              tp1_multiplier: float,
              tp2_multiplier: float,
              rationale: str
            }
        """

        # ── Tentukan preset base dari vol_regime ─────────────────────────────
        # UPDATED 2026-03-03: TP1 dinaikkan agar reward/risk ≥ 1.0
        # Validasi walk-forward: SL 1.5× / TP 2.0× → WR 64.7%, PF 2.26
        if vol_regime == "High" and halflife < 15:
            preset_name  = "HV-Fast-Revert"
            sl_base  = 2.0  # Wide SL (noise filtering)
            tp1_base = 1.5  # was 0.8 → R:R was 0.36, now 0.75
            tp2_base = 2.0  # was 1.2
            rationale = "Scalper-HV-Fast: Vol tinggi + noisy. SL Lebar, TP dinaikkan agar R:R sehat."

        elif vol_regime == "High" and halflife >= 15:
            preset_name  = "HV-Slow-Persist"
            sl_base  = 2.0
            tp1_base = 1.5  # was 1.0 → R:R was 0.50, now 0.75
            tp2_base = 2.5  # was 1.5, vol tinggi persistent = potensi move besar
            rationale = "Scalper-HV-Persist: Vol tinggi stabil. TP lebih lebar karena move besar."

        elif vol_regime == "Low":
            preset_name  = "LV-Trend"
            sl_base  = 1.5  # was 1.2 → terlalu ketat, WR turun. Walk-forward: 1.5× optimal
            tp1_base = 1.8  # was 1.2 → R:R was 1.0, now 1.2
            tp2_base = 2.5  # was 1.8, low vol = trend halus, biarkan jalan
            rationale = "Scalper-LV: Vol rendah, trend reliable. SL 1.5× minimum terbukti optimal."

        else:
            preset_name  = "Normal"
            sl_base  = 1.5
            tp1_base = 2.0  # was 1.0 → R:R was 0.67, now 1.33 (sesuai walk-forward)
            tp2_base = 3.0  # was 1.5
            rationale = "Scalper-Normal: Multiplier sesuai validasi walk-forward."

        # ── Penyesuaian dari Modul A bias_score ──────────────────────────────
        # Untuk scalper mode, kita tidak ingin TP terlalu jauh meskipun bias tinggi
        if bias_score > 0.6:
            tp1_mult = round(tp1_base * 1.05, 2)
            tp2_mult = round(tp2_base * 1.05, 2)
            sl_mult  = sl_base
            rationale += " + persistent bias."
        elif bias_score < 0.2:
            tp1_mult = round(tp1_base * 0.9, 2)
            tp2_mult = round(tp2_base * 0.9, 2)
            sl_mult  = round(sl_base  * 1.1, 2)
            rationale += " + unstable bias."
        else:
            tp1_mult = round(tp1_base, 2)
            tp2_mult = round(tp2_base, 2)
            sl_mult  = round(sl_base,  2)

        return {
            "preset_name":   preset_name,
            "sl_multiplier": sl_mult,
            "tp1_multiplier": tp1_mult,
            "tp2_multiplier": tp2_mult,
            "rationale":     rationale,
        }

    def _fallback_params(self) -> dict:
        """Fallback bila estimasi gagal — gunakan nilai konservatif."""
        return {
            "gamma":                           0.1,
            "eta":                             0.0004,
            "kappa":                           0.1,
            "current_vol":                     0.02,
            "long_run_vol":                    0.02,
            "vol_regime":                      "Normal",
            "mean_reversion_halflife_candles": 999.0,
            "interpretation":                  "Estimasi tidak tersedia — menggunakan fallback.",
        }


# ════════════════════════════════════════════════════════════
#  SINGLETON FACTORY
# ════════════════════════════════════════════════════════════

_vol_est: VolatilityRegimeEstimator | None = None
_vol_lock = threading.Lock()


def get_vol_estimator() -> VolatilityRegimeEstimator:
    global _vol_est
    if _vol_est is None:
        with _vol_lock:
            if _vol_est is None:
                _vol_est = VolatilityRegimeEstimator()
    return _vol_est


# ════════════════════════════════════════════════════════════
#  STANDALONE TEST
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    from pathlib import Path

    _BACKEND_DIR = str(Path(__file__).resolve().parent.parent.parent.parent)
    if _BACKEND_DIR not in sys.path:
        sys.path.insert(0, _BACKEND_DIR)

    print("\n ⚡ BTC-QUANT · Layer 1 Volatility (Heston) — Standalone Test")
    print(" ─" * 40)

    try:
        from data_engine import get_latest_market_data
        df_ohlcv, _ = get_latest_market_data()
    except Exception as e:
        print(f"  ⚠ Tidak bisa load dari DuckDB: {e}")
        df_ohlcv = None

    if df_ohlcv is None or df_ohlcv.empty:
        print("  ⚠ Tidak ada data. Jalankan data_engine.py terlebih dahulu.")
    else:
        est = get_vol_estimator()
        params = est.estimate_params(df_ohlcv)

        print(f"\n  📊 Data: {len(df_ohlcv)} candle")
        print(f"\n  ── Parameter Model Heston ──────────────────────────")
        print(f"    γ (mean-reversion speed) : {params['gamma']:.6f}")
        print(f"    η (long-run variance)    : {params['eta']:.8f}")
        print(f"    κ (vol of vol)           : {params['kappa']:.6f}")
        print(f"    σ_current (vol sekarang) : {params['current_vol']:.6f}")
        print(f"    σ_longrun (vol jk panjang): {params['long_run_vol']:.6f}")
        print(f"\n  ── Vol Regime ───────────────────────────────────────")
        print(f"    Regime    : {params['vol_regime']}")
        print(f"    Half-life : ~{params['mean_reversion_halflife_candles']} candle")
        print(f"    Interpretasi: {params['interpretation']}")

        print(f"\n  ── SL/TP Multiplier (contoh bias_score=0.6) ─────────")
        for bias in [0.1, 0.5, 0.75]:
            mults = est.get_sl_tp_multipliers(
                vol_regime = params["vol_regime"],
                halflife   = params["mean_reversion_halflife_candles"],
                bias_score = bias,
            )
            print(f"    bias={bias:.2f} → {mults['preset_name']}:"
                  f" SL×{mults['sl_multiplier']}  TP1×{mults['tp1_multiplier']}"
                  f"  TP2×{mults['tp2_multiplier']}")

    print("\n  ✅ Modul B (Heston) test selesai.\n")
