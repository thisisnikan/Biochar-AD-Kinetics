"""Run material-aware ablation on a private, treatment-level kinetic table.

This script is designed for author-shared or otherwise non-public data. It
never embeds source values in the repository. The input CSV remains local and
must contain one row per amended treatment with control-normalized kinetic
responses and material descriptors.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

TARGETS = ("delta_ymax", "delta_rmax", "delta_lag")
FEATURE_SETS = {
    "dose_only": ("dose_pct_ts",),
    "dose_plus_pyrolysis": ("dose_pct_ts", "pyrolysis_temperature_c"),
    "chemistry_context": (
        "dose_pct_ts",
        "ph",
        "ec_us_cm",
        "carbon_pct",
        "nitrogen_pct",
        "oxygen_pct",
        "hydrogen_pct",
        "h_c_ratio",
        "o_c_ratio",
    ),
    "chemistry_plus_pyrolysis": (
        "dose_pct_ts",
        "pyrolysis_temperature_c",
        "ph",
        "ec_us_cm",
        "carbon_pct",
        "nitrogen_pct",
        "oxygen_pct",
        "hydrogen_pct",
        "h_c_ratio",
        "o_c_ratio",
    ),
}


def _ridge_predict(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    *,
    alpha: float = 1.0,
) -> np.ndarray:
    mean = x_train.mean(axis=0)
    scale = x_train.std(axis=0)
    scale[scale == 0] = 1.0
    train_scaled = (x_train - mean) / scale
    test_scaled = (x_test - mean) / scale
    train_design = np.column_stack([np.ones(len(train_scaled)), train_scaled])
    test_design = np.column_stack([np.ones(len(test_scaled)), test_scaled])
    penalty = np.eye(train_design.shape[1], dtype=float) * alpha
    penalty[0, 0] = 0.0
    beta = np.linalg.solve(
        train_design.T @ train_design + penalty,
        train_design.T @ y_train,
    )
    return test_design @ beta


def _validate_columns(frame: pd.DataFrame, group_column: str) -> None:
    required = {group_column, *TARGETS}
    for columns in FEATURE_SETS.values():
        required.update(columns)
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError("Missing private-ablation columns: " + ", ".join(missing))


def evaluate(
    frame: pd.DataFrame,
    *,
    group_column: str,
    alpha: float = 1.0,
) -> pd.DataFrame:
    """Run whole-group held-out validation with train-fold-only scaling."""
    _validate_columns(frame, group_column)
    records: list[dict[str, object]] = []
    for feature_set, columns in FEATURE_SETS.items():
        usable = frame.dropna(subset=[group_column, *columns, *TARGETS]).copy()
        for target in TARGETS:
            for held_out in sorted(usable[group_column].astype(str).unique()):
                train = usable.loc[usable[group_column].astype(str) != held_out]
                test = usable.loc[usable[group_column].astype(str) == held_out]
                prediction = _ridge_predict(
                    train.loc[:, columns].to_numpy(float),
                    train[target].to_numpy(float),
                    test.loc[:, columns].to_numpy(float),
                    alpha=alpha,
                )
                observed = test[target].to_numpy(float)
                baseline = np.full(len(test), train[target].mean(), dtype=float)
                rmse = float(np.sqrt(np.mean((observed - prediction) ** 2)))
                baseline_rmse = float(np.sqrt(np.mean((observed - baseline) ** 2)))
                records.append(
                    {
                        "validation_group": group_column,
                        "held_out": held_out,
                        "feature_set": feature_set,
                        "target": target,
                        "rmse": rmse,
                        "baseline_rmse": baseline_rmse,
                        "improvement_vs_baseline": baseline_rmse - rmse,
                        "alpha": alpha,
                    }
                )
    return pd.DataFrame(records)


def summarize(folds: pd.DataFrame) -> pd.DataFrame:
    """Aggregate fold-level results without hiding failed folds."""
    return (
        folds.groupby(["validation_group", "feature_set", "target"], as_index=False)
        .agg(
            mean_rmse=("rmse", "mean"),
            mean_baseline_rmse=("baseline_rmse", "mean"),
            mean_improvement_vs_baseline=("improvement_vs_baseline", "mean"),
            folds_beating_baseline=(
                "improvement_vs_baseline",
                lambda values: int((values > 0).sum()),
            ),
            n_folds=("improvement_vs_baseline", "size"),
        )
    )


def run(input_path: Path, output: Path, alpha: float) -> dict[str, object]:
    frame = pd.read_csv(input_path)
    output.mkdir(parents=True, exist_ok=True)
    fold_tables = [
        evaluate(frame, group_column="biochar_id", alpha=alpha),
        evaluate(frame, group_column="feedstock", alpha=alpha),
    ]
    folds = pd.concat(fold_tables, ignore_index=True)
    summary = summarize(folds)
    folds.to_csv(output / "private_feature_ablation_folds.csv", index=False)
    summary.to_csv(output / "private_feature_ablation_summary.csv", index=False)
    status = {
        "input": str(input_path),
        "alpha": alpha,
        "privacy_boundary": (
            "Input values are private and are never embedded in this script or written "
            "outside the requested local output directory."
        ),
        "validation": ["leave-one-biochar-out", "leave-one-feedstock-out"],
        "scaling": "numeric features standardized on the training fold only",
    }
    (output / "private_feature_ablation_status.json").write_text(
        json.dumps(status, indent=2) + "\n",
        encoding="utf-8",
    )
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--alpha", type=float, default=1.0)
    args = parser.parse_args()
    print(json.dumps(run(args.input, args.output, args.alpha), indent=2))


if __name__ == "__main__":
    main()
