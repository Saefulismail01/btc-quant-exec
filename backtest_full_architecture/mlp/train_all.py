from __future__ import annotations

import argparse
from pathlib import Path

from trainer import (
    DEFAULT_1M_CACHE_DIR,
    DEFAULT_4H_PATH,
    add_1h_label,
    add_baseline_label,
    add_exec_aligned_label,
    prepare_common_frames,
    train_variant,
    write_validation_rows,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Train all Agent B MLP variants and export validation table")
    parser.add_argument("--csv-4h", type=Path, default=DEFAULT_4H_PATH)
    parser.add_argument("--cache-1m", type=Path, default=DEFAULT_1M_CACHE_DIR)
    parser.add_argument("--training-days", type=int, default=180)
    parser.add_argument("--models-dir", type=Path, default=Path("backtest_full_architecture/mlp/models"))
    parser.add_argument(
        "--validation-out",
        type=Path,
        default=Path("backtest_full_architecture/mlp/validation_results.csv"),
    )
    parser.add_argument("--max-forward-bars", type=int, default=7 * 24 * 60)
    args = parser.parse_args()

    features, df_1m = prepare_common_frames(args.csv_4h, args.cache_1m, training_days=args.training_days)

    baseline = train_variant(
        model_name="baseline_4h_forward_return",
        labeled_frame=add_baseline_label(features),
        model_path=args.models_dir / "baseline.joblib",
        label_type="baseline_4h_3class",
    )
    variant_a = train_variant(
        model_name="variant_a_execution_aligned",
        labeled_frame=add_exec_aligned_label(features, df_1m, max_forward_bars=args.max_forward_bars),
        model_path=args.models_dir / "variant_a.joblib",
        label_type="execution_aligned",
    )
    variant_b = train_variant(
        model_name="variant_b_1h_forward_return",
        labeled_frame=add_1h_label(features, df_1m),
        model_path=args.models_dir / "variant_b.joblib",
        label_type="one_hour_forward_binary",
    )

    rows = [baseline, variant_a, variant_b]
    write_validation_rows(args.validation_out, rows)
    print(f"validation={args.validation_out}")
    for row in rows:
        print(
            f"{row.model_name}: acc={row.accuracy_mean:.3f}±{row.accuracy_std:.3f} "
            f"f1={row.f1_mean:.3f}±{row.f1_std:.3f} folds={row.folds_used} rows={row.train_rows}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

