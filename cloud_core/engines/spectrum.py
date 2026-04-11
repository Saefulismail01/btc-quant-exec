"""
Directional Spectrum Scoring - Core Logic
Aggregates 4 layer votes into final signal
"""
from dataclasses import dataclass
from typing import Dict


@dataclass
class SpectrumResult:
    """Complete output from DirectionalSpectrum.calculate()"""
    directional_bias: float      # [-1.0, +1.0]
    action: str                    # "LONG" | "SHORT"
    conviction_pct: float          # |bias| * 100
    trade_gate: str                # "ACTIVE" | "ADVISORY" | "SUSPENDED"
    position_size_pct: float
    l4_multiplier: float          # Risk multiplier
    layer_contributions: Dict[str, float]
    
    def __repr__(self) -> str:
        sign = "+" if self.directional_bias >= 0 else ""
        return (
            f"SpectrumResult("
            f"bias={sign}{self.directional_bias:.3f}, "
            f"action={self.action}, "
            f"conviction={self.conviction_pct:.1f}%, "
            f"gate={self.trade_gate})"
        )


class DirectionalSpectrum:
    """
    Aggregates 4 layer votes into directional bias score.
    
    Formula:
        raw_score = L1*0.30 + L2*0.25 + L3*0.45
        final_score = raw_score * L4_multiplier
        
    Weights (validated walk-forward 2023-2026):
        L1 (BCD) = 0.30  - macro regime
        L2 (EMA) = 0.25  - structural trend
        L3 (MLP) = 0.45  - short-term predictive (highest alpha)
    """
    
    # Validated weights
    L1_WEIGHT = 0.30
    L2_WEIGHT = 0.25
    L3_WEIGHT = 0.45
    
    # Thresholds
    ACTIVE_THRESHOLD = 0.20
    ADVISORY_THRESHOLD = 0.10
    
    def __init__(self):
        pass
    
    @staticmethod
    def compute_l4_multiplier(vol_ratio: float) -> float:
        """
        Convert ATR/price ratio to risk multiplier [0.0, 1.0].
        
        Stepped lookup table:
            < 0.008  → 1.0  (very low vol)
            < 0.012  → 0.8  (medium vol)
            < 0.015  → 0.5  (high vol)
            < 0.020  → 0.2  (very high vol)
            >= 0.020 → 0.0  (extreme vol, suspend)
        """
        table = [
            (0.008, 1.0),
            (0.012, 0.8),
            (0.015, 0.5),
            (0.020, 0.2),
            (float("inf"), 0.0),
        ]
        for threshold, mult in table:
            if vol_ratio < threshold:
                return mult
        return 0.0
    
    def calculate(
        self,
        l1_vote: float,  # BCD [-1, +1]
        l2_vote: float,  # EMA [-1, +1]
        l3_vote: float,  # MLP/XGB [-1, +1]
        l4_mult: float,  # Risk [0, 1]
        base_size: float = 5.0,
    ) -> SpectrumResult:
        """
        Calculate directional spectrum from layer votes.
        
        Args:
            l1_vote: BCD vote [-1, +1]
            l2_vote: EMA vote [-1, +1]
            l3_vote: MLP/XGB vote [-1, +1]
            l4_mult: Risk multiplier [0, 1]
            base_size: Base position size %
        
        Returns:
            SpectrumResult with gate and conviction
        """
        # Clamp inputs
        l1 = max(-1.0, min(1.0, float(l1_vote)))
        l2 = max(-1.0, min(1.0, float(l2_vote)))
        l3 = max(-1.0, min(1.0, float(l3_vote)))
        l4 = max(0.0, min(1.0, float(l4_mult)))
        
        # Weighted sum
        l1_contrib = self.L1_WEIGHT * l1
        l2_contrib = self.L2_WEIGHT * l2
        l3_contrib = self.L3_WEIGHT * l3
        raw_score = l1_contrib + l2_contrib + l3_contrib
        
        # Apply L4 risk multiplier
        directional_bias = round(raw_score * l4, 4)
        
        # Determine action
        action = "LONG" if directional_bias >= 0 else "SHORT"
        
        # Conviction
        conviction_pct = round(abs(directional_bias) * 100, 1)
        
        # Gate determination
        abs_bias = abs(directional_bias)
        
        if abs_bias >= self.ACTIVE_THRESHOLD:
            trade_gate = "ACTIVE"
        elif abs_bias >= self.ADVISORY_THRESHOLD:
            trade_gate = "ADVISORY"
        else:
            trade_gate = "SUSPENDED"
        
        # Position size (0 if suspended)
        position_size_pct = (
            round(base_size * (conviction_pct / 100), 2)
            if trade_gate == "ACTIVE"
            else 0.0
        )
        
        contributions = {
            "l1_bcd": round(l1_contrib, 4),
            "l2_ema": round(l2_contrib, 4),
            "l3_ai": round(l3_contrib, 4),
            "l4_risk": round(l4, 4),
            "raw_score": round(raw_score, 4),
            "final_score": round(directional_bias, 4),
        }
        
        return SpectrumResult(
            directional_bias=directional_bias,
            action=action,
            conviction_pct=conviction_pct,
            trade_gate=trade_gate,
            position_size_pct=position_size_pct,
            l4_multiplier=l4,
            layer_contributions=contributions,
        )
