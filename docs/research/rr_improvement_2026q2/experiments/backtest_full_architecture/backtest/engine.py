"""Phase 4 backtest engine for Agent D."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import util
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from .config import EXPERIMENT_DIR, RESULTS_DIR, BacktestConfig, WalkForwardConfig, get_configuration_matrix
from .metrics import conditional_win_rates, summarize_trades


PROCESSED_DIR = EXPERIMENT_DIR / "data" / "processed"
SIGNALS_DIR = EXPERIMENT_DIR / "signals"
EXECUTION_DIR = EXPERIMENT_DIR / "execution"
EXHAUSTION_DIR = EXPERIMENT_DIR / "exhaustion"


@dataclass
class BacktestPaths:
    preprocessed_4h: Path = PROCESSED_DIR / "preprocessed_4h.parquet"
    preprocessed_1m: Path = PROCESSED_DIR / "preprocessed_1m.parquet"
    features: Path = PROCESSED_DIR / "features.parquet"


class BacktestEngine:
    """Backtest engine running the 6 configuration matrix with walk-forward splits."""

    def __init__(self, paths: BacktestPaths | None = None, wf_cfg: WalkForwardConfig | None = None) -> None:
        self.paths = paths or BacktestPaths()
        self.wf_cfg = wf_cfg or WalkForwardConfig()
        self.df_4h, self.df_1m = self._load_inputs()

    def _load_inputs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        if not self.paths.preprocessed_4h.exists():
            raise FileNotFoundError(f"Missing required file: {self.paths.preprocessed_4h}")
        if not self.paths.preprocessed_1m.exists():
            raise FileNotFoundError(f"Missing required file: {self.paths.preprocessed_1m}")

        df_4h = pd.read_parquet(self.paths.preprocessed_4h)
        df_1m = pd.read_parquet(self.paths.preprocessed_1m)

        df_4h["datetime"] = pd.to_datetime(df_4h["datetime"], utc=True, errors="coerce")
        df_1m["datetime"] = pd.to_datetime(df_1m["datetime"], utc=True, errors="coerce")
        df_4h = df_4h.dropna(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
        df_1m = df_1m.dropna(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
        return df_4h, df_1m

    def _walk_forward_slices(self) -> list[tuple[int, int, int, int]]:
        n = len(self.df_4h)
        cfg = self.wf_cfg
        if n < cfg.min_bars_required:
            raise ValueError(f"Not enough bars for walk-forward. Need >= {cfg.min_bars_required}, got {n}")

        slices: list[tuple[int, int, int, int]] = []
        train_start = 0
        train_end = cfg.train_bars
        while train_end + cfg.test_bars <= n:
            test_start = train_end
            test_end = test_start + cfg.test_bars
            slices.append((train_start, train_end, test_start, test_end))
            train_end += cfg.step_bars
        return slices

    @staticmethod
    def _load_optional_module(path: Path) -> Any | None:
        if not path.exists():
            return None
        spec = util.spec_from_file_location(path.stem, path)
        if spec is None or spec.loader is None:
            return None
        mod = util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _resolve_signal_series(self, config: BacktestConfig, test_df: pd.DataFrame) -> pd.Series:
        signal_path = SIGNALS_DIR / f"signals_{config.mlp_variant}.parquet"
        if signal_path.exists():
            sig = pd.read_parquet(signal_path)
            sig["datetime"] = pd.to_datetime(sig["datetime"], utc=True, errors="coerce")
            merged = test_df[["datetime"]].merge(sig[["datetime", "signal"]], on="datetime", how="left")
            return merged["signal"].fillna(0.0)

        col_name = f"signal_{config.mlp_variant}"
        if col_name in test_df.columns:
            return test_df[col_name].fillna(0.0)

        # Fallback heuristic to keep engine runnable while waiting for Agent B output.
        if "l2_vote" in test_df.columns:
            return np.sign(test_df["l2_vote"].fillna(0.0))
        return pd.Series(np.zeros(len(test_df)), index=test_df.index, dtype=float)

    def _resolve_exhaustion_score(self, test_df: pd.DataFrame) -> pd.Series:
        module = self._load_optional_module(EXHAUSTION_DIR / "exhaustion_score.py")
        if module and hasattr(module, "compute_exhaustion_score"):
            fn: Callable[[pd.DataFrame], pd.Series] = module.compute_exhaustion_score
            score = fn(test_df)
            return score.clip(0.0, 1.0).fillna(0.0)
        if "exhaustion_score" in test_df.columns:
            return test_df["exhaustion_score"].clip(0.0, 1.0).fillna(0.0)
        return pd.Series(np.zeros(len(test_df)), index=test_df.index, dtype=float)

    @staticmethod
    def _bucket_volatility(vol_ratio: float) -> str:
        if vol_ratio < 0.8:
            return "low"
        if vol_ratio > 1.2:
            return "high"
        return "normal"

    @staticmethod
    def _bucket_exhaustion(score: float) -> str:
        if score > 0.7:
            return "high"
        if score > 0.5:
            return "mid"
        return "low"

    def _fallback_trade_simulation(self, side: float, bar_now: pd.Series, bar_next: pd.Series, size: float) -> dict[str, Any]:
        entry = float(bar_now["Close"])
        exit_price = float(bar_next["Close"])
        raw_ret = (exit_price / entry - 1.0) * float(np.sign(side))
        return {
            "exit_price": exit_price,
            "pnl_pct": raw_ret * size,
            "exit_type": "next_bar_close",
            "holding_minutes": 240.0,
        }

    def _simulate_trade(self, config: BacktestConfig, side: float, bar_now: pd.Series, bar_next: pd.Series, size: float) -> dict[str, Any]:
        module_path = EXECUTION_DIR / f"{config.exit_strategy}.py"
        module = self._load_optional_module(module_path)
        if module and hasattr(module, "simulate_trade"):
            fn: Callable[..., dict[str, Any]] = module.simulate_trade
            result = fn(
                entry_price=float(bar_now["Close"]),
                side=side,
                bar_now=bar_now,
                bar_next=bar_next,
                one_minute_df=self.df_1m,
                size=size,
            )
            return result
        return self._fallback_trade_simulation(side=side, bar_now=bar_now, bar_next=bar_next, size=size)

    def run_configuration(self, config: BacktestConfig) -> tuple[pd.DataFrame, dict[str, Any]]:
        trades: list[dict[str, Any]] = []
        for _, _, test_start, test_end in self._walk_forward_slices():
            test_df = self.df_4h.iloc[test_start:test_end].copy().reset_index(drop=True)
            signals = self._resolve_signal_series(config, test_df)
            exhaustion = self._resolve_exhaustion_score(test_df)

            for i in range(len(test_df) - 1):
                side = float(signals.iloc[i])
                if side == 0.0:
                    continue

                score = float(exhaustion.iloc[i])
                if config.exhaustion_mode == "veto" and score > 0.7:
                    continue
                size = 0.5 if score > 0.5 else 1.0

                bar_now = test_df.iloc[i]
                bar_next = test_df.iloc[i + 1]
                sim = self._simulate_trade(config, side=side, bar_now=bar_now, bar_next=bar_next, size=size)

                trades.append(
                    {
                        "config": config.name,
                        "entry_time": bar_now["datetime"],
                        "exit_time": bar_next["datetime"],
                        "side": side,
                        "size": size,
                        "entry_price": float(bar_now["Close"]),
                        "exit_price": float(sim["exit_price"]),
                        "pnl_pct": float(sim["pnl_pct"]),
                        "exit_type": sim.get("exit_type", "unknown"),
                        "holding_minutes": float(sim.get("holding_minutes", 240.0)),
                        "l1_regime": bar_now.get("l1_regime", "unknown"),
                        "l4_volatility_bucket": self._bucket_volatility(float(bar_now.get("l4_volatility_ratio", 1.0))),
                        "exhaustion_bucket": self._bucket_exhaustion(score),
                    }
                )

        trades_df = pd.DataFrame(trades)
        base = summarize_trades(trades_df)
        result = {"config": config.name, **base.to_dict(), **conditional_win_rates(trades_df)}
        return trades_df, result

    def run_all(self) -> pd.DataFrame:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        all_results: list[dict[str, Any]] = []

        for config in get_configuration_matrix():
            trades_df, row = self.run_configuration(config)
            all_results.append(row)
            trades_out = RESULTS_DIR / f"trades_{config.name}.csv"
            trades_df.to_csv(trades_out, index=False)

        comparison = pd.DataFrame(all_results).sort_values("ev", ascending=False).reset_index(drop=True)
        comparison_out = RESULTS_DIR / "comparison.csv"
        comparison.to_csv(comparison_out, index=False)
        return comparison


def run_backtest_engine() -> Path:
    engine = BacktestEngine()
    engine.run_all()
    return RESULTS_DIR / "comparison.csv"


if __name__ == "__main__":
    out = run_backtest_engine()
    print("Phase 4 complete.")
    print(f"Engine output at: {out}")
