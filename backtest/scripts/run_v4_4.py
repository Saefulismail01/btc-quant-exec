"""
Run script untuk v4.4 Breakeven Lock Engine.

Usage:
    python backtest/scripts/run_v4_4.py
    python backtest/scripts/run_v4_4.py --start 2024-01-01 --end 2026-03-04
    python backtest/scripts/run_v4_4.py --start 2026-01-01 --end 2026-03-04  # sprint window
"""

import sys
import argparse
import traceback
from pathlib import Path

# ── Path setup: project root harus di sys.path ─────────────────────────────────
_SCRIPT_DIR   = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent
_BACKEND_DIR  = _PROJECT_ROOT / "backend"
_V4_DIR       = _PROJECT_ROOT / "backtest" / "v4"

for p in [str(_PROJECT_ROOT), str(_BACKEND_DIR), str(_V4_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

def main():
    parser = argparse.ArgumentParser(description="BTC-Quant v4.4 — Breakeven Lock Engine")
    parser.add_argument("--start",   default="2024-01-01", help="Start date YYYY-MM-DD (default: 2024-01-01)")
    parser.add_argument("--end",     default="2026-03-04", help="End date   YYYY-MM-DD (default: 2026-03-04)")
    parser.add_argument("--capital", default=10000.0,      type=float, help="Initial capital USD (default: 10000)")
    parser.add_argument("--history", default=400,          type=int,   help="Warmup candles (default: 400)")
    args = parser.parse_args()

    print("=" * 72)
    print("  BTC-QUANT v4.4 — BREAKEVEN LOCK ENGINE")
    print(f"  Window  : {args.start}  →  {args.end}")
    print(f"  Capital : ${args.capital:,.0f}")
    print("=" * 72)
    print()

    try:
        from v4_4_engine import run_v4_4
        run_v4_4(
            window_start     = args.start,
            window_end       = args.end,
            required_history = args.history,
            initial_capital  = args.capital,
        )
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print(f"   Pastikan working directory adalah project root.")
        print(f"   Coba: cd {_PROJECT_ROOT} && python backtest/scripts/run_v4_4.py")
        traceback.print_exc()
    except Exception as e:
        print(f"❌ Runtime error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    import time
    t0 = time.time()
    main()
    print(f"\n⏱ Total: {time.time()-t0:.0f}s")
