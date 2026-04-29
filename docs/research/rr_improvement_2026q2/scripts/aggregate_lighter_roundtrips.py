"""
Aggregate Lighter fill-level CSV into round-trip episodes (position flat -> flat).

Read-only. Used for Area D (holding time, streak proxy) — not identical to live_trades.

Usage:
  python aggregate_lighter_roundtrips.py [path/to/export.csv]
  python aggregate_lighter_roundtrips.py  # default CSV
  python aggregate_lighter_roundtrips.py export.csv --episode-window-utc 2026-04-20 2026-04-24
      # episode fully inside [start 00:00 UTC, end 23:59:59.999 UTC]; both inclusive calendar days
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CSV = ROOT / "lighter-trade-export-2026-04-24T01_03_31.715Z-UTC.csv"


def _signed_delta(side: str, size: float) -> float:
    if side.startswith("Open Long"):
        return size
    if side.startswith("Close Long"):
        return -size
    if side.startswith("Open Short"):
        return -size
    if side.startswith("Close Short"):
        return size
    raise ValueError(side)


def _parse_pnl(val) -> float:
    if val == "-" or val is None or (isinstance(val, float) and pd.isna(val)):
        return 0.0
    return float(val)


@dataclass
class Episode:
    t_open: pd.Timestamp
    t_close: pd.Timestamp
    pnl_usd: float = 0.0
    max_abs_pos: float = 0.0
    dominant_side: str = ""  # LONG or SHORT (by sign at peak)

    closes: list[tuple[pd.Timestamp, float]] = field(default_factory=list)


def aggregate_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"], utc=True)
    df["Size"] = df["Size"].astype(float)
    df["pnl_fill"] = df["Closed PnL"].apply(_parse_pnl)
    df = df.sort_values("Date").reset_index(drop=True)

    pos = 0.0
    ep: Episode | None = None
    episodes: list[Episode] = []

    for _, row in df.iterrows():
        side = str(row["Side"])
        sz = float(row["Size"])
        d = row["Date"]
        dpos = _signed_delta(side, sz)

        if ep is None and abs(pos) < 1e-12 and abs(pos + dpos) > 1e-12:
            ep = Episode(t_open=d, t_close=d, dominant_side="LONG" if dpos > 0 else "SHORT")

        if ep is not None:
            ep.t_close = d
            ep.max_abs_pos = max(ep.max_abs_pos, abs(pos + dpos))
            if side.startswith("Close"):
                ep.pnl_usd += row["pnl_fill"]
                ep.closes.append((d, row["pnl_fill"]))

        pos += dpos

        if ep is not None and abs(pos) < 1e-10:
            ep.t_close = d
            episodes.append(ep)
            ep = None

    incomplete_tail = ep is not None
    if incomplete_tail:
        episodes.append(ep)

    rows = []
    for i, e in enumerate(episodes):
        hold_h = (e.t_close - e.t_open).total_seconds() / 3600.0
        complete = not (incomplete_tail and i == len(episodes) - 1)
        rows.append(
            {
                "episode_idx": i + 1,
                "t_open": e.t_open,
                "t_close": e.t_close,
                "hold_hours": hold_h,
                "pnl_usd": round(e.pnl_usd, 6),
                "win": e.pnl_usd > 0,
                "side": e.dominant_side,
                "complete": complete,
            }
        )
    return pd.DataFrame(rows)


def _window_filter(
    ep: pd.DataFrame,
    start_day: str,
    end_day: str,
) -> pd.DataFrame:
    """Keep complete episodes with t_open and t_close inside UTC calendar inclusive range."""
    start = pd.Timestamp(start_day + "T00:00:00", tz="UTC")
    end = pd.Timestamp(end_day + "T23:59:59.999999", tz="UTC")
    done = ep[ep["complete"]].copy()
    m = (done["t_open"] >= start) & (done["t_close"] <= end)
    return done.loc[m]


def main():
    p = argparse.ArgumentParser(description="Aggregate Lighter fills to round-trip episodes.")
    p.add_argument("csv", nargs="?", type=Path, default=DEFAULT_CSV, help="Lighter trade export CSV")
    p.add_argument(
        "--episode-window-utc",
        nargs=2,
        metavar=("START", "END"),
        help="Inclusive UTC calendar days YYYY-MM-DD; episode must satisfy t_open>=START 00:00 and t_close<=END end-of-day",
    )
    args = p.parse_args()
    path = args.csv
    if not path.exists():
        print("Missing:", path)
        sys.exit(1)
    ep = aggregate_csv(path)
    print("Source:", path)
    print("Episodes (all):", len(ep))
    print(ep.to_string(index=False))
    done = ep[ep["complete"]]
    if len(done):
        print("\n--- complete episodes only ---")
        print("n:", len(done))
        print("win_rate:", done["win"].mean())
        print("total_pnl_usd:", done["pnl_usd"].sum())
        print("median_hold_h:", done["hold_hours"].median())
    if args.episode_window_utc:
        w = _window_filter(ep, args.episode_window_utc[0], args.episode_window_utc[1])
        print(
            f"\n--- episode window UTC {args.episode_window_utc[0]} .. {args.episode_window_utc[1]} "
            "(complete, fully inside) ---"
        )
        print("n:", len(w))
        if len(w):
            print("win_rate:", w["win"].mean())
            print("total_pnl_usd:", w["pnl_usd"].sum())
            print("median_hold_h:", w["hold_hours"].median())
            print(w[["episode_idx", "t_open", "t_close", "pnl_usd", "win", "side"]].to_string(index=False))


if __name__ == "__main__":
    main()
