"""
╔══════════════════════════════════════════════════════════════╗
║  BTC-QUANT-BTC: DIRECTIONAL SPECTRUM SCORING  v2.1          ║
║  Independent layer votes · Continuous [-1.0, +1.0]          ║
╚══════════════════════════════════════════════════════════════╝

CHANGELOG v2.1 (fix/critical-optimizations):
----------------------------------------------
[FIX-1a] ROLLBACK bobot ke nilai yang sudah ter-validasi walk-forward:
         L1=0.30, L2=0.25, L3=0.45  ← menghasilkan +597.89% / 3 tahun
         Bobot eksperimental (0.45/0.35/0.20) belum pernah di-backtest,
         TIDAK boleh dipakai di production sampai ada validasi.

[FIX-1b] ROLLBACK threshold ACTIVE dari 0.20 → 0.55.
         Threshold 0.20 adalah "user experiment" yang tidak ter-dokumentasi
         dampaknya terhadap trade frequency dan win rate. Dengan threshold
         0.20, hampir semua sinyal jadi ACTIVE — ini tidak konsisten dengan
         data backtest (989 trade / 3 tahun = 0.87 trade/hari).

[FIX-1c] SUSPEND gate ADVISORY secara default.
         Dari backtest: 94 trade ADVISORY = -$3,121 (avg -$33.21/trade).
         Tidak ada edge di ADVISORY — dimatikan sampai ada bukti sebaliknya.

Arsitektur v2:
--------------
Setiap layer vote independen [-1, +1], tidak ada shared anchor.
L4 adalah multiplier risiko [0, 1], bukan vote arah.

Formula:
    raw_score   = l1×w1 + l2×w2 + l3×w3
    final_score = raw_score × l4_multiplier

    Bobot (harus sum = 1.0) — VALIDATED walk-forward 2023–2026:
        L1 (BCD) → 0.30  macro regime context
        L2 (EMA) → 0.25  structural trend confirmation
        L3 (AI)  → 0.45  short-term predictive, highest alpha

    Gate (VALIDATED):
        |final_score| >= 0.55  → ACTIVE    (was 0.65, turun sedikit per backtest note)
        |final_score| >= 0.10  → ADVISORY  (DISABLED — negatif ekspektansi)
        |final_score| <  0.10  → SUSPENDED
"""

from __future__ import annotations
from dataclasses import dataclass

from app.config import settings


# ════════════════════════════════════════════════════════════
#  CONFIG — VALIDATED walk-forward weights (2023–2026)
# ════════════════════════════════════════════════════════════

# [FIX-SIGNAL] REVERT ke VALIDATED walk-forward weights (2023–2026) yang menghasilkan +597.89% / 989 trades
# Weights sebelumnya (0.45/0.35/0.20) adalah eksperimental dan tidak ter-validasi
#   L1=0.30 BCD — macro regime context (slower, less weight)
#   L2=0.25 EMA — structural trend confirmation (lagging, less weight)
#   L3=0.45 MLP — short-term predictive, highest alpha (fastest, most weight)
_L1_WEIGHT = 0.30   # BCD  — macro regime, slower responsiveness
_L2_WEIGHT = 0.25   # EMA  — structural, lagging indicator
_L3_WEIGHT = 0.45   # MLP  — short-term with RSI+MACD, highest alpha

assert abs(_L1_WEIGHT + _L2_WEIGHT + _L3_WEIGHT - 1.0) < 1e-9, \
    "L1+L2+L3 weights must sum to 1.0"

# Gate thresholds — REVERT ke nilai V1 yang menghasilkan +597% / 989 trades
# ACTIVE   : |score| >= 0.20 → eksekusi (konsisten dengan V1)
# ADVISORY : |score| >= 0.10 → eksekusi (V1 menggunakan ACTIVE+ADVISORY)
# SUSPENDED: tidak ada sinyal
_ACTIVE_THRESHOLD  = 0.20   # REVERT: 0.55 terlalu ketat → hampir 0 trade
_ADVISORY_DISABLED = False  # REVERT: V1 mengeksekusi ACTIVE+ADVISORY

# L4: ATR/price ratio → risk multiplier (lookup table — SYNC ke V1)
# V1 menggunakan stepped table, bukan linear interpolation
_L4_MULT_TABLE = [
    (0.008, 1.0),          # very low vol  → full conviction
    (0.012, 0.8),          # medium vol
    (0.015, 0.5),          # high vol
    (0.020, 0.2),          # very high vol
    (float("inf"), 0.0),   # extreme vol   → suspend
]

# Linear fallback bounds (untuk backward compat)
_L4_MIN_ATR = 0.006   # dipakai compute_l4_multiplier() jika table tidak dipakai
_L4_MAX_ATR = 0.020   # SYNC ke V1: suspend mulai 2.0% (bukan 3.0%)


# ════════════════════════════════════════════════════════════
#  RESULT DATACLASS
# ════════════════════════════════════════════════════════════

@dataclass
class SpectrumResult:
    """
    Output lengkap dari DirectionalSpectrum.calculate().

    Fields:
        directional_bias    : float [-1.0, +1.0]
                              Positif = bullish, Negatif = bearish
        action              : "LONG" | "SHORT"
        conviction_pct      : abs(directional_bias) × 100
        trade_gate          : "ACTIVE" | "SUSPENDED"
                              (ADVISORY dihilangkan — negatif ekspektansi)
        position_size_pct   : % dari base_size
        l4_multiplier       : Risk multiplier yang diterapkan [0.0, 1.0]
        layer_contributions : Breakdown kontribusi per layer
        advisory_blocked    : True jika sinyal masuk ADVISORY tapi di-block
    """
    directional_bias:    float
    action:              str
    conviction_pct:      float
    trade_gate:          str
    position_size_pct:   float
    l4_multiplier:       float
    layer_contributions: dict[str, float]
    advisory_blocked:    bool = False

    def __repr__(self) -> str:
        sign = "+" if self.directional_bias >= 0 else ""
        blocked = " [ADVISORY→SUSPENDED]" if self.advisory_blocked else ""
        return (
            f"SpectrumResult("
            f"bias={sign}{self.directional_bias:.3f}, "
            f"action={self.action}, "
            f"conviction={self.conviction_pct:.1f}%, "
            f"gate={self.trade_gate}{blocked})"
        )


# ════════════════════════════════════════════════════════════
#  DIRECTIONAL SPECTRUM ENGINE
# ════════════════════════════════════════════════════════════

class DirectionalSpectrum:
    """
    v2.1: Aggregates independent layer votes into a directional bias score.

    Perubahan dari v2:
    - Bobot dikembalikan ke validated values (0.30/0.25/0.45)
    - Threshold ACTIVE dikembalikan ke 0.55
    - ADVISORY gate dinonaktifkan (negatif ekspektansi)
    - advisory_blocked flag ditambahkan untuk monitoring/logging
    """

    def __init__(self):
        self.active_threshold   = _ACTIVE_THRESHOLD
        self.advisory_disabled  = _ADVISORY_DISABLED

    @staticmethod
    def compute_l4_multiplier(vol_ratio: float) -> float:
        """
        SYNC ke V1: Convert ATR/price ratio ke risk multiplier [0.0, 1.0].

        V1 menggunakan stepped lookup table (bukan linear interpolation):
            < 0.008  → 1.0  (very low vol, full conviction)
            < 0.012  → 0.8  (medium vol)
            < 0.015  → 0.5  (high vol)
            < 0.020  → 0.2  (very high vol)
            >= 0.020 → 0.0  (extreme vol, suspend)

        Args:
            vol_ratio: ATR14 / Close price
        """
        for threshold, multiplier in _L4_MULT_TABLE:
            if vol_ratio < threshold:
                return multiplier
        return 0.0  # fallback

    def calculate(
        self,
        l1_vote: float,
        l2_vote: float,
        l3_vote: float,
        l4_multiplier: float,
        base_size: float = 5.0,
    ) -> SpectrumResult:
        """
        Hitung directional spectrum score dari independent layer votes.

        Args:
            l1_vote       : BCD vote [-1, +1]
            l2_vote       : EMA structural vote [-1, +1]
            l3_vote       : MLP AI vote [-1, +1]
            l4_multiplier : Risk multiplier dari compute_l4_multiplier()
            base_size     : Base position size (% portfolio)

        Returns:
            SpectrumResult dengan gate ACTIVE atau SUSPENDED.
            Gate ADVISORY dinonaktifkan — selalu di-convert ke SUSPENDED.
        """
        # Clamp semua input ke valid range
        l1 = max(-1.0, min(1.0, float(l1_vote)))
        l2 = max(-1.0, min(1.0, float(l2_vote)))
        l3 = max(-1.0, min(1.0, float(l3_vote)))
        l4 = max(0.0,  min(1.0, float(l4_multiplier)))

        # Weighted vote sum
        l1_contrib = _L1_WEIGHT * l1
        l2_contrib = _L2_WEIGHT * l2
        l3_contrib = _L3_WEIGHT * l3
        raw_score  = l1_contrib + l2_contrib + l3_contrib

        # Apply L4 risk multiplier
        directional_bias = round(raw_score * l4, 4)

        # Arah dari sign
        action = "LONG" if directional_bias >= 0 else "SHORT"

        # Conviction = magnitude
        conviction_pct = round(abs(directional_bias) * 100, 1)

        # Gate determination
        abs_bias      = abs(directional_bias)
        advisory_blocked = False

        if abs_bias >= self.active_threshold:
            trade_gate = "ACTIVE"
        elif abs_bias >= 0.10:
            # [FIX-1c] ADVISORY zone — block dan catat
            if self.advisory_disabled:
                trade_gate       = "SUSPENDED"
                advisory_blocked = True
            else:
                trade_gate = "ADVISORY"
        else:
            trade_gate = "SUSPENDED"

        # Position size — 0 kalau suspended
        position_size_pct = (
            round(base_size * (conviction_pct / 100), 2)
            if trade_gate == "ACTIVE"
            else 0.0
        )

        layer_contributions = {
            "l1_hmm" : round(l1_contrib,       4),
            "l2_ema" : round(l2_contrib,       4),
            "l3_ai"  : round(l3_contrib,       4),
            "l4_mult": round(l4,               4),
            "raw"    : round(raw_score,        4),
            "final"  : round(directional_bias, 4),
        }

        return SpectrumResult(
            directional_bias    = directional_bias,
            action              = action,
            conviction_pct      = conviction_pct,
            trade_gate          = trade_gate,
            position_size_pct   = position_size_pct,
            l4_multiplier       = l4,
            layer_contributions = layer_contributions,
            advisory_blocked    = advisory_blocked,
        )

    def legacy_score(self, l1: bool, l2: bool, l3: bool, l4: bool) -> int:
        """Backward compat — binary banded score 0/25/50/75/100."""
        return 25 * sum([l1, l2, l3, l4])
