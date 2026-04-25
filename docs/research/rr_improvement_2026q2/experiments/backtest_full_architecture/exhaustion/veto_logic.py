"""Veto/reduce-size helpers based on exhaustion score."""

from __future__ import annotations

from typing import Literal

import pandas as pd

Decision = Literal["ALLOW", "REDUCE", "VETO"]


def decide_exhaustion_action(score: float) -> Decision:
    if score > 0.7:
        return "VETO"
    if score > 0.5:
        return "REDUCE"
    return "ALLOW"


def size_multiplier_from_score(score: float) -> float:
    action = decide_exhaustion_action(score)
    if action == "VETO":
        return 0.0
    if action == "REDUCE":
        return 0.5
    return 1.0


def apply_veto_logic(scores: pd.Series) -> pd.DataFrame:
    """Vectorized helper useful for diagnostics/reporting."""
    clipped = pd.to_numeric(scores, errors="coerce").fillna(0.0).clip(0.0, 1.0)
    actions = clipped.apply(decide_exhaustion_action)
    multipliers = clipped.apply(size_multiplier_from_score)
    return pd.DataFrame(
        {
            "exhaustion_score": clipped,
            "decision": actions,
            "size_multiplier": multipliers,
            "is_veto": actions.eq("VETO"),
        }
    )

