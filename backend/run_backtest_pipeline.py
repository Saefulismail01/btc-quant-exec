"""
╔══════════════════════════════════════════════════════════════╗
║  BTC-QUANT: BACKTEST PIPELINE RUNNER                        ║
║  Jalankan semua step PRD secara berurutan:                  ║
║  I-08 → I-00 → Modul C                                     ║
║                                                              ║
║  Usage:                                                     ║
║      cd backend                                             ║
║      python run_backtest_pipeline.py                        ║
╚══════════════════════════════════════════════════════════════╝
"""

import asyncio
import subprocess
import sys
import time
import duckdb
from pathlib import Path
from datetime import datetime

_BACKEND  = Path(__file__).resolve().parent
_ROOT     = _BACKEND.parent
_BACKTEST = _ROOT / "backtest"
_DB_PATH  = _BACKEND / "btc-quant.db"

sys.path.insert(0, str(_BACKEND))


def _log(step: str, msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"\n  [{ts}] ── {step} ──────────────────────────────")
    print(f"  {msg}")


def _count_candles() -> int:
    try:
        with duckdb.connect(str(_DB_PATH), read_only=True) as con:
            r = con.execute("SELECT COUNT(*) FROM btc_ohlcv_4h").fetchone()
            return int(r[0]) if r else 0
    except Exception:
        return 0


def _run_script(script_path: Path, label: str) -> bool:
    """Jalankan Python script sebagai subprocess, tampilkan output realtime."""
    print(f"\n  {'─'*56}")
    print(f"  ▶ {label}")
    print(f"  {'─'*56}")

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(script_path.parent),
    )
    return result.returncode == 0


def main():
    print("\n" + "═"*60)
    print("  BTC-QUANT · Backtest Pipeline Runner")
    print("  PRD: I-08 → I-00 → Modul C")
    print("═"*60)

    total_start = time.time()

    # ── Step 1: Cek data ──────────────────────────────────────────────────────
    n = _count_candles()
    _log("Step 1", f"Data existing: {n} candle")

    if n < 500:
        _log("Step 1", f"Data kurang ({n} < 500). Menjalankan backfill...")
        ok = _run_script(_BACKEND / "backfill_historical.py", "I-08: Historical Data Backfill")
        if not ok:
            print("\n  ❌ Backfill gagal. Cek koneksi Binance / proxy.")
            print("     Jalankan ulang setelah koneksi aktif:")
            print("     cd backend && python backfill_historical.py")
            sys.exit(1)
        n = _count_candles()
        _log("Step 1", f"Setelah backfill: {n} candle")
    else:
        _log("Step 1", f"✅ Data cukup ({n} candle). Skip backfill.")

    if n < 200:
        print("\n  ❌ Data masih < 200 candle setelah backfill.")
        print("     Tidak bisa melanjutkan test. Cek koneksi.")
        sys.exit(1)

    # ── Step 2: I-00 HMM Predictive Power Test ───────────────────────────────
    _log("Step 2", "Menjalankan I-00: HMM Predictive Power Test...")
    i00_script = _BACKTEST / "hmm_predictive_power_test.py"

    if not i00_script.exists():
        print(f"\n  ❌ Script tidak ditemukan: {i00_script}")
        sys.exit(1)

    ok_i00 = _run_script(i00_script, "I-00: HMM Predictive Power Test")
    if not ok_i00:
        print("\n  ⚠ I-00 selesai dengan error. Cek output di atas.")
        print("    Lanjut ke Modul C untuk laporan distribusi...")

    # Cek apakah ada hasil CSV
    i00_csv = _BACKTEST / "results" / "hmm_power_test.csv"
    if i00_csv.exists():
        import pandas as pd
        df = pd.read_csv(i00_csv)
        print(f"\n  📊 I-00 Results ({len(df)} baris):")
        print(f"  {'─'*56}")
        if not df.empty:
            cols = [c for c in ["window","regime","n_candles","mean_ret_1c_pct","win_rate_1c_pct","t_stat_1c"] if c in df.columns]
            print(df[cols].to_string(index=False, float_format="{:.3f}".format))
    else:
        print("\n  ⚠ Hasil CSV I-00 tidak ditemukan.")

    # ── Step 3: Modul C — Return Distribution Test ───────────────────────────
    _log("Step 3", "Menjalankan Modul C: Return Distribution Test...")
    modul_c = _BACKTEST / "return_distribution_test.py"

    if not modul_c.exists():
        print(f"\n  ⚠ Script tidak ditemukan: {modul_c}. Skip Modul C.")
    else:
        ok_c = _run_script(modul_c, "Modul C: Return Distribution + Ekonofisika Validation")

        # Tampilkan verdict dari decision file
        decision_md = _BACKTEST / "results" / "hmm_power_test_decision.md"
        if decision_md.exists():
            content = decision_md.read_text(encoding="utf-8")
            # Cari baris Verdict
            for line in content.splitlines():
                if "Verdict" in line and "`" in line:
                    verdict_str = line.strip()
                    print(f"\n  {'═'*56}")
                    print(f"  I-00 FINAL: {verdict_str}")
                    print(f"  {'═'*56}")
                    break

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = time.time() - total_start
    print(f"\n\n  {'═'*60}")
    print(f"  PIPELINE SELESAI  ·  ⏱ {elapsed:.0f} detik")
    print(f"  {'═'*60}")
    print(f"  Data   : {_count_candles()} candle")
    print(f"  I-00   : {str(i00_csv) if i00_csv.exists() else 'Tidak ada hasil'}")
    print(f"  Modul C: {str(_BACKTEST / 'results' / 'return_distribution_by_regime.csv')}")
    print()
    print("  Langkah berikutnya:")

    decision_md = _BACKTEST / "results" / "hmm_power_test_decision.md"
    if decision_md.exists():
        content = decision_md.read_text(encoding="utf-8")
        if "PASS" in content and "FAIL" not in content:
            print("  ✅ I-00 PASS → Lanjutkan ke I-01 (CVD fix) dan I-03 (walk-forward)")
            print("     python backtest/engine.py")
        elif "PARTIAL" in content:
            print("  ⚠ I-00 PARTIAL → Review label_states() dan BIC n_states dulu")
            print("     Lihat: backtest/results/hmm_power_test_decision.md")
        else:
            print("  ❌ I-00 FAIL → Redesign Layer 1 sebelum lanjut")
            print("     Lihat: backtest/results/hmm_power_test_decision.md")
    else:
        print("  → Lihat hasil di backtest/results/")

    print(f"  {'═'*60}\n")


if __name__ == "__main__":
    main()
