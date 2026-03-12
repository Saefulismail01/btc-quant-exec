"""
Run script: Evolution Comparison — periode SAMA untuk ketiga konfigurasi.

Tujuan: Membuat perbandingan lintas generasi yang valid secara metodologis.
Semua konfigurasi dijalankan pada periode dan modal yang identik.

Konfigurasi:
  A) v0.1-style  : L1 BCD only  + Compounding 2%/trade
  B) v1-style    : Full L1-L4   + Compounding 2%/trade
  C) v4.4 Golden : Full L1-L4   + Fixed $1,000 × 15x

Usage:
    python backtest/scripts/run_evolution_comparison.py
    python backtest/scripts/run_evolution_comparison.py --start 2024-01-01 --end 2026-03-04
    python backtest/scripts/run_evolution_comparison.py --mode v01   # satu konfigurasi saja
    python backtest/scripts/run_evolution_comparison.py --mode v1
    python backtest/scripts/run_evolution_comparison.py --mode v44
"""

import sys
import json
import argparse
import traceback
import time
from pathlib import Path

_SCRIPT_DIR   = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent
_BACKEND_DIR  = _PROJECT_ROOT / "backend"
_V4_DIR       = _PROJECT_ROOT / "backtest" / "v4"

for p in [str(_PROJECT_ROOT), str(_BACKEND_DIR), str(_V4_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

CONFIGS = {
    "v01": dict(layer_mode="l1_only", sizing_mode="compound", label="v0.1-style (L1 only + Compound)"),
    "v1" : dict(layer_mode="full",    sizing_mode="compound", label="v1-style   (Full + Compound)"),
    "v44": dict(layer_mode="full",    sizing_mode="fixed",    label="v4.4 Golden (Full + Fixed)"),
}


def print_comparison_table(results: dict):
    print("\n" + "═" * 90)
    print("  EVOLUTION COMPARISON — PERIODE SAMA (fair comparison)")
    print("═" * 90)

    headers = ["Metrik", "v0.1-style", "v1-style", "v4.4 Golden"]
    col_w   = [28, 20, 20, 20]

    def row(label, *vals):
        parts = [f"{label:<{col_w[0]}}"]
        for v, w in zip(vals, col_w[1:]):
            parts.append(f"{v:>{w}}")
        print("  " + " │ ".join(parts))

    def divider():
        print("  " + "─" * (sum(col_w) + 3 * 3))

    print("  " + " │ ".join(f"{h:<{w}}" for h, w in zip(headers, col_w)))
    divider()

    keys = ["v01", "v1", "v44"]
    r    = {k: results.get(k, {}) for k in keys}

    def val(k, field, fmt="{:.2f}"):
        v = r[k].get(field)
        return fmt.format(v) if v is not None else "—"

    row("Net PnL (%)",
        val("v01", "net_pnl_pct",    "{:+.2f}%"),
        val("v1",  "net_pnl_pct",    "{:+.2f}%"),
        val("v44", "net_pnl_pct",    "{:+.2f}%"))
    row("Final Equity (USD)",
        val("v01", "final_equity",   "${:,.0f}"),
        val("v1",  "final_equity",   "${:,.0f}"),
        val("v44", "final_equity",   "${:,.0f}"))
    row("Win Rate (%)",
        val("v01", "win_rate_pct",   "{:.2f}%"),
        val("v1",  "win_rate_pct",   "{:.2f}%"),
        val("v44", "win_rate_pct",   "{:.2f}%"))
    row("Profit Factor",
        val("v01", "profit_factor",  "{:.3f}"),
        val("v1",  "profit_factor",  "{:.3f}"),
        val("v44", "profit_factor",  "{:.3f}"))
    row("Max Drawdown (%)",
        val("v01", "max_drawdown_pct", "{:.2f}%"),
        val("v1",  "max_drawdown_pct", "{:.2f}%"),
        val("v44", "max_drawdown_pct", "{:.2f}%"))
    row("Sharpe Ratio",
        val("v01", "sharpe_ratio",   "{:.3f}"),
        val("v1",  "sharpe_ratio",   "{:.3f}"),
        val("v44", "sharpe_ratio",   "{:.3f}"))
    row("R:R Ratio",
        val("v01", "rr_ratio",       "{:.3f}"),
        val("v1",  "rr_ratio",       "{:.3f}"),
        val("v44", "rr_ratio",       "{:.3f}"))
    row("Jumlah Trade",
        val("v01", "n_trades",       "{:.0f}"),
        val("v1",  "n_trades",       "{:.0f}"),
        val("v44", "n_trades",       "{:.0f}"))
    row("Avg Hold (candles)",
        val("v01", "avg_hold_candles", "{:.1f}"),
        val("v1",  "avg_hold_candles", "{:.1f}"),
        val("v44", "avg_hold_candles", "{:.1f}"))

    print("═" * 90)

    print("\n  Catatan metodologis:")
    print("  • v0.1 vs v1  : variabel yang berubah = jumlah layer (L1 saja vs L1+L2+L3+L4)")
    print("  • v1  vs v4.4 : variabel yang berubah = sizing method (compounding vs fixed)")
    print("  • Periode dan modal IDENTIK untuk ketiga konfigurasi → perbandingan valid.\n")


def main():
    parser = argparse.ArgumentParser(description="BTC-QUANT Evolution Comparison")
    parser.add_argument("--start",   default="2024-01-01")
    parser.add_argument("--end",     default="2026-03-04")
    parser.add_argument("--capital", default=10000.0, type=float)
    parser.add_argument("--history", default=400,     type=int)
    parser.add_argument("--mode",    default="all",
                        help="v01 | v1 | v44 | all  (default: all)")
    args = parser.parse_args()

    modes_to_run = list(CONFIGS.keys()) if args.mode == "all" else [args.mode]

    if args.mode == "all":
        print(f"\nRunning ALL {len(modes_to_run)} configurations on {args.start} → {args.end}")
        print("Estimated time: ~45–90 minutes total\n")

    results = {}
    t_total = time.time()

    try:
        from v4_evolution_engine import run_evolution
    except ImportError as e:
        print(f"Import error: {e}")
        traceback.print_exc()
        return

    for mode_key in modes_to_run:
        if mode_key not in CONFIGS:
            print(f"Unknown mode '{mode_key}'. Valid: {list(CONFIGS.keys())}")
            continue

        cfg = CONFIGS[mode_key]
        print(f"\n{'='*72}")
        print(f"  Running: {cfg['label']}")
        print(f"{'='*72}\n")

        t0 = time.time()
        try:
            summary = run_evolution(
                layer_mode       = cfg["layer_mode"],
                sizing_mode      = cfg["sizing_mode"],
                window_start     = args.start,
                window_end       = args.end,
                required_history = args.history,
                initial_capital  = args.capital,
            )
            results[mode_key] = summary
            elapsed = time.time() - t0
            print(f"\n  ✓ {cfg['label']} selesai dalam {elapsed/60:.1f} menit\n")
        except Exception as e:
            print(f"\n  ✗ {cfg['label']} GAGAL: {e}")
            traceback.print_exc()

    if len(results) == len(modes_to_run) and args.mode == "all":
        print_comparison_table(results)

        results_dir = _PROJECT_ROOT / "backtest" / "results" / "v4_evolution_results"
        ts = time.strftime("%Y%m%d_%H%M%S")
        report_path = results_dir / f"evolution_comparison_{ts}.json"
        with open(report_path, "w") as f:
            json.dump({
                "window_start"  : args.start,
                "window_end"    : args.end,
                "initial_capital": args.capital,
                "results"       : results,
            }, f, indent=2)
        print(f"  [✓] Laporan tersimpan: {report_path.name}\n")

    total_elapsed = time.time() - t_total
    print(f"\n⏱ Total waktu: {total_elapsed/60:.1f} menit")


if __name__ == "__main__":
    main()
