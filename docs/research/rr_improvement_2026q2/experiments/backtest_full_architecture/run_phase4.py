"""Agent D runner for Phase 4 backtest engine."""

from __future__ import annotations

from pathlib import Path

from backtest.engine import run_backtest_engine
from backtest.preflight import print_preflight_report


def main() -> int:
    ready = print_preflight_report()
    if not ready:
        print("Phase 4 preflight not fully ready. Running in fallback-compatible mode.")

    out_path = run_backtest_engine()
    print("Phase 4 complete.")
    print(f"Engine output at: {Path(out_path).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
