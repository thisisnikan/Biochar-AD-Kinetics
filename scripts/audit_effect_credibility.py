"""Reproduce dependence, influence and readiness diagnostics from public inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from importlib.metadata import version
from pathlib import Path

import pandas as pd

from biochar_ad_kinetics.effect_diagnostics import (
    leave_one_reactor_out_effects,
    shared_control_covariance,
)
from biochar_ad_kinetics.effects import build_within_study_effect_table
from biochar_ad_kinetics.generalization import audit_generalization_readiness

ROOT = Path(__file__).resolve().parents[1]
INPUTS = [
    "data/experimental/kozlowski_2025_bmp.csv",
    "data/experimental/valentin_bialowiec_2024_parameters.csv",
]
METHOD_FILES = [
    "scripts/audit_effect_credibility.py",
    "src/biochar_ad_kinetics/effect_diagnostics.py",
    "src/biochar_ad_kinetics/effects.py",
    "src/biochar_ad_kinetics/generalization.py",
    "src/biochar_ad_kinetics/baselines.py",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/effect-credibility")
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    reactors, parameters = [pd.read_csv(ROOT / path) for path in INPUTS]
    effects = build_within_study_effect_table(reactors, parameters)
    covariance = shared_control_covariance(effects)
    influence = leave_one_reactor_out_effects(reactors)
    audit = audit_generalization_readiness(effects)
    summary = (
        influence.groupby(["study_id", "treatment", "response"], sort=True)
        .agg(
            original_percent_change=("original_percent_change", "first"),
            deletion_min_percent_change=("omitted_percent_change", "min"),
            deletion_max_percent_change=("omitted_percent_change", "max"),
            any_sign_change=("sign_changed", "any"),
            deletion_cases=("sign_changed", "size"),
            includes_unreplicated_remainder=("unreplicated_remainder", "any"),
        )
        .reset_index()
    )
    tables = {
        "within_study_effects.csv": effects,
        "shared_control_covariance.csv": covariance,
        "leave_one_reactor_out.csv": influence,
        "reactor_influence_summary.csv": summary,
        "generalization_readiness.csv": audit,
    }
    for filename, table in tables.items():
        table.to_csv(output / filename, index=False)
    known_pairs = covariance.loc[covariance["uncertainty_available"] & ~covariance["is_diagonal"]]
    report = {
        "schema_version": 1,
        "scope": "conditional_within_study_diagnostics_only",
        "input_sha256": {
            path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in INPUTS
        },
        "method_sha256": {
            path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in METHOD_FILES
        },
        "environment": {
            "python": platform.python_version(),
            **{package: version(package) for package in ("numpy", "pandas", "scipy")},
        },
        "output_sha256": {
            filename: hashlib.sha256((output / filename).read_bytes()).hexdigest()
            for filename in tables
        },
        "n_studies": int(effects["study_id"].nunique()),
        "n_effect_rows": len(effects),
        "n_effect_rows_with_uncertainty": int(effects["log_response_ratio_se"].notna().sum()),
        "n_reactor_deletion_cases": len(influence),
        "n_contrasts_with_sign_change": int(summary["any_sign_change"].sum()),
        "shared_control_correlation_range": [
            float(known_pairs["correlation"].min()),
            float(known_pairs["correlation"].max()),
        ],
        "any_response_ready_for_loso": bool(audit["ready_for_loso"].any()),
        "limitations": [
            "Known Kozlowski blank-decrease and control-dose conflicts are unresolved.",
            "Covariance is conditional on fitted estimates and independent disjoint arms.",
            "Shared blank-correction uncertainty and cross-response covariance are omitted.",
            "Deletion ranges are influence diagnostics, not confidence intervals or validation.",
            "Some deletion cases leave one treatment reactor; they are descriptive only.",
            "Published parameter-table uncertainty is unavailable; no values are imputed.",
            "No new data, cross-study pooling, causal inference or transfer test is performed.",
        ],
    }
    (output / "audit_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "n_effect_rows",
                    "n_reactor_deletion_cases",
                    "n_contrasts_with_sign_change",
                    "shared_control_correlation_range",
                    "any_response_ready_for_loso",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
