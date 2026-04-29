"""
Daily SL Freeze Rule Analysis
==============================
Rule: Jika ada trade SL di suatu hari kalender (UTC+7),
      semua trade berikutnya di hari yang SAMA di-skip
      sampai jam 07:00 WIB (00:00 UTC) keesokan harinya.

Aturan yang disimulasikan:
  - Scan trades secara kronologis per hari (WIB = UTC+7)
  - Jika ada SL hit → catat tanggal freeze
  - Semua trade yang entry_time di tanggal yang sama SETELAH SL itu → di-skip (dihapus dari hasil)
  - Pending limit orders (MISS) tidak dihitung karena sudah tidak fill
"""

from pathlib import Path
import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────
_BASE = Path(__file__).resolve().parent.parent
_DIR  = _BASE / "results" / "pullback_v3"
_TAG  = "pullback_v3_20260428_160421"

FILES = {
    "market"    : _DIR / f"{_TAG}_market_trades.csv",
    "pb1_w1"    : _DIR / f"{_TAG}_pb1pct_w1_trades.csv",
    "pb2_w1"    : _DIR / f"{_TAG}_pb2pct_w1_trades.csv",
    "pb3_w1"    : _DIR / f"{_TAG}_pb3pct_w1_trades.csv",
    "pb3_w2"    : _DIR / f"{_TAG}_pb3pct_w2_trades.csv",
    "pb5_w1"    : _DIR / f"{_TAG}_pb5pct_w1_trades.csv",
    "pb5_w2"    : _DIR / f"{_TAG}_pb5pct_w2_trades.csv",
}

LABELS = {
    "market" : "BASELINE (market)",
    "pb1_w1" : "Pullback 0.10% w=1c",
    "pb2_w1" : "Pullback 0.20% w=1c",
    "pb3_w1" : "Pullback 0.30% w=1c",
    "pb3_w2" : "Pullback 0.30% w=2c  ← rekomendasi",
    "pb5_w1" : "Pullback 0.50% w=1c",
    "pb5_w2" : "Pullback 0.50% w=2c  ★ best raw",
}

TZ_WIB = "Asia/Jakarta"   # UTC+7


# ── Core function ─────────────────────────────────────────────────────────────

def apply_freeze_rule(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Terapkan freeze rule ke DataFrame trades.
    Return: (df_after_freeze, df_frozen)
    """
    # Hanya proses trades yang punya pnl (bukan MISS)
    df = df.copy()
    df["entry_time"] = pd.to_datetime(df["entry_time"], utc=True)

    # Konversi ke WIB untuk menentukan "hari yang sama"
    df["entry_wib"]  = df["entry_time"].dt.tz_convert(TZ_WIB)
    df["entry_date"] = df["entry_wib"].dt.date

    # Hanya trade yang actually executed (punya pnl)
    executed = df[df["pnl_usd"].notna()].copy().reset_index(drop=True)
    missed   = df[df["pnl_usd"].isna()].copy()

    frozen_dates: set = set()   # tanggal WIB yang sudah kena freeze
    frozen_idx:   list = []
    kept_idx:     list = []

    for idx, row in executed.iterrows():
        date = row["entry_date"]

        if date in frozen_dates:
            # Trade ini di-skip karena hari ini sudah freeze
            frozen_idx.append(idx)
            continue

        # Trade ini jalan — cek apakah ini SL
        kept_idx.append(idx)
        if row["exit_type"] == "SL":
            frozen_dates.add(date)   # freeze sisa hari ini

    df_kept   = executed.loc[kept_idx]
    df_frozen = executed.loc[frozen_idx]

    # Gabungkan kembali dengan missed trades (mereka sudah "tidak masuk" jadi tidak relevan)
    df_final = pd.concat([df_kept, missed], ignore_index=True)
    df_final = df_final.sort_values("entry_time").reset_index(drop=True)

    return df_kept, df_frozen


def calc_stats(trades: pd.DataFrame, label: str) -> dict:
    pnls   = trades["pnl_usd"].dropna().tolist()
    if not pnls:
        return {"label": label, "n": 0}

    wins   = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gw     = sum(wins)
    gl     = abs(sum(losses))
    aw     = gw / len(wins)   if wins   else 0
    al     = gl / len(losses) if losses else 0

    n_sl    = (trades["exit_type"] == "SL").sum()
    n_tp    = (trades["exit_type"] == "TP").sum()
    n_trail = (trades["exit_type"] == "TRAIL_TP").sum()
    n_time  = (trades["exit_type"] == "TIME_EXIT").sum()

    return {
        "label"  : label,
        "n"      : len(pnls),
        "wr"     : round(len(wins) / len(pnls) * 100, 2),
        "net"    : round(sum(pnls), 2),
        "avg_win": round(aw, 2),
        "avg_los": round(-al, 2),
        "rr"     : round(aw / al if al > 0 else 0, 3),
        "pf"     : round(gw / gl if gl > 0 else 0, 3),
        "npt"    : round(sum(pnls) / len(pnls), 2),
        "n_sl"   : int(n_sl),
        "n_tp"   : int(n_tp),
        "n_trail": int(n_trail),
        "n_time" : int(n_time),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 78)
    print("  DAILY SL FREEZE RULE ANALYSIS")
    print("  Rule: SL hit → freeze sisa hari (WIB) → resume jam 07:00 WIB keesokan")
    print("=" * 78)

    results = []

    for key, fpath in FILES.items():
        df = pd.read_csv(fpath)
        label = LABELS[key]

        # Stats tanpa freeze (raw)
        executed_all = df[df["pnl_usd"].notna()]
        s_raw = calc_stats(executed_all, label)

        # Stats dengan freeze
        df_kept, df_frozen = apply_freeze_rule(df)
        s_frz = calc_stats(df_kept, label)

        n_frozen     = len(df_frozen)
        frozen_pnl   = df_frozen["pnl_usd"].sum() if len(df_frozen) > 0 else 0
        sl_days_raw  = s_raw["n_sl"]

        results.append({
            "key"       : key,
            "label"     : label,
            "raw"       : s_raw,
            "freeze"    : s_frz,
            "n_frozen"  : n_frozen,
            "frozen_pnl": round(frozen_pnl, 2),
            "sl_days"   : sl_days_raw,
        })

        # Detail print per config
        print(f"\n  {'─'*76}")
        print(f"  {label}")
        print(f"  {'─'*76}")
        print(f"  {'Metric':<22} {'Tanpa Freeze':>14} {'Dengan Freeze':>14} {'Delta':>10}")
        print(f"  {'─'*62}")

        def row(name, k):
            rv = s_raw.get(k, 0)
            fv = s_frz.get(k, 0)
            dv = fv - rv if isinstance(rv, (int, float)) else "—"
            prefix = "$" if k in ("net","npt","avg_win","avg_los") else ""
            suffix = "%" if k == "wr" else ""
            rv_s = f"{prefix}{rv:,.2f}{suffix}" if isinstance(rv, float) else f"{rv}"
            fv_s = f"{prefix}{fv:,.2f}{suffix}" if isinstance(fv, float) else f"{fv}"
            dv_s = f"{dv:+.2f}" if isinstance(dv, float) else f"{dv:+d}" if isinstance(dv, int) else "—"
            print(f"  {name:<22} {rv_s:>14} {fv_s:>14} {dv_s:>10}")

        row("Trades", "n")
        row("Win Rate", "wr")
        row("Net PnL", "net")
        row("Net/trade", "npt")
        row("R:R", "rr")
        row("Profit Factor", "pf")
        row("SL count", "n_sl")

        pct_frozen = n_frozen / s_raw["n"] * 100 if s_raw["n"] > 0 else 0
        print(f"\n  Trades difreeze  : {n_frozen} ({pct_frozen:.1f}% dari total)")
        print(f"  PnL trades frozen: ${frozen_pnl:,.2f}  (ini yg sebelumnya 'terpaksa' diambil)")

    # ── Summary comparison table ───────────────────────────────────────────────
    print("\n\n" + "=" * 78)
    print("  SUMMARY: WR & Net/trade — Raw vs +FreezeRule")
    print("=" * 78)
    print(f"  {'Config':<30} {'WR raw':>8} {'WR frz':>8} {'ΔWR':>7}  {'N/T raw':>9} {'N/T frz':>9} {'ΔN/T':>8}  {'Frozen%':>8}")
    print("  " + "─" * 74)
    for r in results:
        rw = r["raw"]
        fw = r["freeze"]
        dwr  = fw.get("wr",  0) - rw.get("wr",  0)
        dnpt = fw.get("npt", 0) - rw.get("npt", 0)
        n_frz_pct = r["n_frozen"] / rw["n"] * 100 if rw["n"] > 0 else 0
        print(
            f"  {r['label'][:30]:<30}"
            f" {rw.get('wr',0):>7.2f}%"
            f" {fw.get('wr',0):>7.2f}%"
            f" {dwr:>+6.2f}%"
            f"  ${rw.get('npt',0):>8.2f}"
            f"  ${fw.get('npt',0):>8.2f}"
            f" {dnpt:>+7.2f}"
            f"  {n_frz_pct:>7.1f}%"
        )

    # ── Best config setelah freeze ─────────────────────────────────────────────
    valid = [r for r in results if r["freeze"].get("n", 0) > 0]
    best_npt = max(valid, key=lambda r: r["freeze"].get("npt", 0))
    best_net = max(valid, key=lambda r: r["freeze"].get("net", 0))

    print(f"\n  ★ Best Net/trade setelah freeze : {best_npt['label']}")
    print(f"    WR={best_npt['freeze']['wr']}%  Net/trade=${best_npt['freeze']['npt']:+.2f}  PF={best_npt['freeze']['pf']}  Trades={best_npt['freeze']['n']}")
    print(f"\n  ★ Best absolute Net PnL setelah freeze: {best_net['label']}")
    print(f"    Net PnL=${best_net['freeze']['net']:,.2f}  Trades={best_net['freeze']['n']}")
    print("\n" + "=" * 78)


if __name__ == "__main__":
    main()
