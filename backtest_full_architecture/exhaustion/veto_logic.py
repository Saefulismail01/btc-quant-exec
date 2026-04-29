"""Veto / size-reduction logic based on exhaustion score."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Decision = Literal["ALLOW", "REDUCE", "VETO"]


@dataclass(frozen=True)
class VetoDecision:
    """Decision payload for downstream sizing logic."""

    decision: Decision
    size_multiplier: float
    reason: str


def get_veto_decision(exhaustion_score: float) -> VetoDecision:
    """Map exhaustion score to entry decision according to task definition."""
    if exhaustion_score > 0.7:
        return VetoDecision("VETO", 0.0, "exhaustion_score > 0.7")
    if exhaustion_score > 0.5:
        return VetoDecision("REDUCE", 0.5, "0.5 < exhaustion_score <= 0.7")
    return VetoDecision("ALLOW", 1.0, "exhaustion_score <= 0.5")
