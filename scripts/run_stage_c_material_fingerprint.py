"""Run the evidence-gated Stage C material-aware fingerprint benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from biochar_ad_kinetics.material_fingerprint import assess_readiness, leave_one_study_out


def summarize_hypothesis(benchmark: pd.DataFrame) -> dict[str, object]:
    """Summarize whether Stage C beats the training-study mean baseline."""
    evaluated = benchmark.loc[benchmark["status"].eq("evaluated")].copy()
    targets: dict[str, object] = {}
    for target, group in evaluated.groupby("target", sort=True):
        improvements = group["rmse_improvement_vs_baseline"].astype(float)
        n_positive = int(improvements.gt(0).sum())
        targets[str(target)] = {
            "n_held_out_studies": len(group),
            "n_folds_beating_baseline": n_positive,
            "mean_rmse_improvement_vs_baseline": float(improvements.mean()),
            "hypothesis_supported": n_positive == len(group),
        }

    primary_targets = [name for name in ("delta_potential", "delta_max_rate") if name in targets]
    primary_supported = bool(primary_targets) and all(
        bool(targets[name]["hypothesis_supported"]) for name in primary_targets
    )
    return {
        "hypothesis": (
            "Dose plus biochar processing temperature predicts held-out-study kinetic effects "
            "better than the training-study mean baseline."
        ),
        "primary_targets": primary_targets,
        "primary_hypothesis_supported": primary_supported,
        "decision_rule": (
            "Support requires lower RMSE than baseline in every held-out study for each primary target."
        ),
        "targets": targets,
    }


def run(input_path: Path, output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(input_path)
    readiness = assess_readiness(frame)
    benchmark = leave_one_study_out(frame)

    benchmark.to_csv(output / "leave_one_study_out.csv", index=False)
    hypothesis = summarize_hypothesis(benchmark)
    (output / "hypothesis_test.json").write_text(
        json.dumps(hypothesis, indent=2) + "\n",
        encoding="utf-8",
    )
    status = {
        "input": str(input_path),
        "targets": {target: item.to_dict() for target, item in readiness.items()},
        "hypothesis_test": hypothesis,
        "scientific_boundary": (
            "Transfer performance is only reported per kinetic target when at least three "
            "independent studies contain that target and the required features."
        ),
    }
    (output / "stage_c_status.json").write_text(
        json.dumps(status, indent=2) + "\n",
        encoding="utf-8",
    )
    return status


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
        default=Path("results/stage-c-material-aware"),
    )
    args = parser.parse_args()
    print(json.dumps(run(args.input, args.output), indent=2))


if __name__ == "__main__":
    main()
