from __future__ import annotations

import argparse
from pathlib import Path

from trainer import (
    DEFAULT_1M_CACHE_DIR,
    DEFAULT_4H_PATH,
    add_1h_label,
    prepare_common_frames,
    train_variant,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Train Variant B MLP (1H forward-return label)")
    parser.add_argument("--csv-4h", type=Path, default=DEFAULT_4H_PATH)
    parser.add_argument("--cache-1m", type=Path, default=DEFAULT_1M_CACHE_DIR)
    parser.add_argument("--training-days", type=int, default=180)
    parser.add_argument("--output", type=Path, default=Path("backtest_full_architecture/mlp/models/variant_b.joblib"))
    args = parser.parse_args()

    features, df_1m = prepare_common_frames(args.csv_4h, args.cache_1m, training_days=args.training_days)
    labeled = add_1h_label(features, df_1m)
    result = train_variant(
        model_name="variant_b_1h_forward_return",
        labeled_frame=labeled,
        model_path=args.output,
        label_type="one_hour_forward_binary",
    )
    print(f"saved={args.output} f1={result.f1_mean:.3f} acc={result.accuracy_mean:.3f} rows={result.train_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

