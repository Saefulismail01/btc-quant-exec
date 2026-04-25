"""Preflight checks for Agent D dependencies."""

from __future__ import annotations

from pathlib import Path

from .engine import EXHAUSTION_DIR, EXECUTION_DIR, PROCESSED_DIR, SIGNALS_DIR


def _status_line(path: Path, required: bool = True) -> tuple[bool, bool, str]:
    exists = path.exists()
    tag = "OK" if exists else ("MISSING" if required else "OPTIONAL_MISSING")
    return exists, required, f"[{tag}] {path}"


def print_preflight_report() -> bool:
    checks: list[tuple[bool, bool, str]] = []

    checks.append(_status_line(PROCESSED_DIR / "preprocessed_4h.parquet", required=True))
    checks.append(_status_line(PROCESSED_DIR / "preprocessed_1m.parquet", required=True))
    checks.append(_status_line(PROCESSED_DIR / "features.parquet", required=False))

    checks.append(_status_line(SIGNALS_DIR / "signals_baseline.parquet", required=False))
    checks.append(_status_line(SIGNALS_DIR / "signals_variant_a.parquet", required=False))
    checks.append(_status_line(SIGNALS_DIR / "signals_variant_b.parquet", required=False))

    checks.append(_status_line(EXECUTION_DIR / "fixed_tp_sl.py", required=False))
    checks.append(_status_line(EXECUTION_DIR / "partial_tp.py", required=False))
    checks.append(_status_line(EXECUTION_DIR / "trailing_stop.py", required=False))
    checks.append(_status_line(EXHAUSTION_DIR / "exhaustion_score.py", required=False))

    print("=== Phase 4 Preflight Report ===")
    for _, _, line in checks:
        print(line)

    hard_ready = all(exists for exists, required, _ in checks if required)
    full_ready = all(exists for exists, _, _ in checks)

    if full_ready:
        print("Status: FULL_READY (uses Agent B/C outputs).")
    elif hard_ready:
        print("Status: PARTIAL_READY (engine can run with fallback behavior).")
    else:
        print("Status: BLOCKED (processed data is missing).")

    return hard_ready
