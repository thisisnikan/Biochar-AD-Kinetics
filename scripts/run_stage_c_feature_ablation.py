"""Compare evidence-gated Stage C feature sets with whole-study validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from biochar_ad_kinetics.material_fingerprint import (
    TARGET_COLUMNS,
    assess_target_readiness,
    leave_one_study_out,
)

FEATURE_SETS = {
    "dose_only": ("dose_g_l",),
    "dose_plus_temperature": ("dose_g_l", "material_process_temperature_c"),
    "rich_surface_context": (
        "dose_g_l",
        "material_process_temperature_c",
        "surface_area_m2_g",
        "pore_volume_cm3_g",
    ),
}


def summarize_feature_set(
    frame: pd.DataFrame,
    name: str,
    features: tuple[str, ...],
) -> tuple[pd.DataFrame, dict[str, object]]:
    benchmark = leave_one_study_out(frame, numeric_features=features)
    evaluated = benchmark.loc[benchmark["status"].eq("evaluated")].copy()
    target_summary: dict[str, object] = {}

    for target in TARGET_COLUMNS:
        readiness = assess_target_readiness(
            frame,
            target,
            numeric_features=features,
        )
        target_rows = evaluated.loc[evaluated["target"].eq(target)]
        if target_rows.empty:
            target_summary[target] = {
                "eligible": readiness.eligible,
                "n_studies": readiness.n_studies,
                "n_rows": readiness.n_rows,
                "reason": readiness.reason,
            }
            continue
        improvements = target_rows["rmse_improvement_vs_baseline"].astype(float)
        target_summary[target] = {
            "eligible": True,
            "n_studies": readiness.n_studies,
            "n_rows": readiness.n_rows,
            "n_folds": len(target_rows),
            "n_folds_beating_baseline": int(improvements.gt(0).sum()),
            "mean_rmse_improvement_vs_baseline": float(improvements.mean()),
            "median_rmse_improvement_vs_baseline": float(improvements.median()),
        }

    benchmark.insert(0, "feature_set", name)
    return benchmark, {
        "feature_set": name,
        "numeric_features": list(features),
        "targets": target_summary,
    }


def run(input_path: Path, output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(input_path)
    all_benchmarks: list[pd.DataFrame] = []
    summaries: dict[str, object] = {}

    for name, features in FEATURE_SETS.items():
        benchmark, summary = summarize_feature_set(frame, name, features)
        all_benchmarks.append(benchmark)
        summaries[name] = summary

    combined = pd.concat(all_benchmarks, ignore_index=True, sort=False)
    combined.to_csv(output / "feature_ablation_loso.csv", index=False)

    result = {
        "input": str(input_path),
        "hypothesis": (
            "Adding material descriptors improves whole-study transfer beyond dose-only "
            "and dose-plus-temperature baselines."
        ),
        "feature_sets": summaries,
        "scientific_boundary": (
            "A richer feature set is not evaluated unless at least three independent studies "
            "contain the target and every requested descriptor. Missing descriptors are not "
            "silently imputed because study-specific missingness could leak study identity."
        ),
    }
    (output / "feature_ablation_summary.json").write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("results/batch-stage-ab/kinetic_fingerprints.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/stage-c-feature-ablation"),
    )
    args = parser.parse_args()
    print(json.dumps(run(args.input, args.output), indent=2))


if __name__ == "__main__":
    main()
