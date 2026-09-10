"""Run the evidence-gated Stage C material-aware fingerprint benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from biochar_ad_kinetics.material_fingerprint import assess_readiness, leave_one_study_out


def run(input_path: Path, output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(input_path)
    readiness = assess_readiness(frame)
    benchmark = leave_one_study_out(frame)

    benchmark.to_csv(output / "leave_one_study_out.csv", index=False)
    status = {
        "input": str(input_path),
        "targets": {target: item.to_dict() for target, item in readiness.items()},
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
