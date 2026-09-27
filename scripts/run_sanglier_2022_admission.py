"""Apply the frozen Sanglier admission spec before any outcome contrast.

Reads only adjudication metadata and cycle durations; the methane volume, flow
and yield columns are dropped before the admission function is called, and the
function itself rejects them. Writes:

- results/validation/sanglier_2022_admission.csv
- results/validation/sanglier_2022_admission_report.json (includes the spec
  SHA-256 that the locked evaluation must match, and the leakage audit)
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import pandas as pd

from biochar_ad_kinetics.validation_admission import (
    OUTCOME_COLUMNS,
    admit_cycles,
    file_sha256,
    leakage_audit,
    load_spec,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "data" / "validation" / "sanglier_2022_validation_spec.json"
ADJUDICATION = ROOT / "results" / "validation" / "sanglier_2022_treatment_adjudication.csv"
METHANE = ROOT / "results" / "intake" / "sanglier_2022_candidate.csv.gz"
OUTPUT = ROOT / "results" / "validation"


def cycle_durations() -> pd.DataFrame:
    metadata_only = [c for c in pd.read_csv(METHANE, nrows=0).columns if c not in OUTCOME_COLUMNS]
    methane = pd.read_csv(METHANE, usecols=metadata_only)
    return (
        methane.groupby(["lab", "batch_id", "bottle_id"], as_index=False)["within_batch_days"]
        .max()
        .rename(columns={"within_batch_days": "last_within_batch_days"})
    )


def overall_decision(spec: dict, summary: dict) -> str:
    """Derive the admission decision from the spec roles and admitted units."""

    if summary["admitted_cycles"] == 0:
        return "still_quarantined"
    if spec["dataset_roles"]["locked_external_validation"]["status"] == "admitted":
        return "admitted_for_narrow_validation_task"
    return "partially_admissible"


def build(output: Path = OUTPUT) -> dict:
    spec = load_spec(SPEC)
    leakage = leakage_audit(ROOT, spec)
    if not leakage["passed"]:
        raise SystemExit(f"Leakage audit failed closed: {leakage['hits']}")
    adjudication = pd.read_csv(ADJUDICATION)
    admission, summary = admit_cycles(adjudication, spec, cycle_durations())
    report = {
        "status": "ADMISSION_FROZEN_BEFORE_OUTCOME_CONTRASTS",
        "spec_path": SPEC.relative_to(ROOT).as_posix(),
        "spec_sha256": file_sha256(SPEC),
        "input_sha256": {
            p.relative_to(ROOT).as_posix(): file_sha256(p) for p in (ADJUDICATION, METHANE)
        },
        "dataset_role_decision": {
            "overall": overall_decision(spec, summary),
            "locked_external_validation": spec["dataset_roles"]["locked_external_validation"][
                "status"
            ],
            "admitted_category": "exploratory (preregistered, within-study question A)",
        },
        "leakage_audit": leakage,
        **summary,
    }
    output.mkdir(parents=True, exist_ok=True)
    buffer = io.StringIO()
    admission.to_csv(buffer, index=False, lineterminator="\n")
    (output / "sanglier_2022_admission.csv").write_text(buffer.getvalue(), encoding="utf-8")
    (output / "sanglier_2022_admission_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    report = build(parser.parse_args().output_dir)
    print(json.dumps({k: report[k] for k in ("windows", "horizon_days", "admitted_cycles")}))


if __name__ == "__main__":
    main()
