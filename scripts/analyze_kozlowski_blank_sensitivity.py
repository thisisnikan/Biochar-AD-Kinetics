"""Rerun the Kozłowski benchmark under labelled blank-correction alternatives.

Usage::

    python scripts/analyze_kozlowski_blank_sensitivity.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from biochar_ad_kinetics.blank_sensitivity import run_blank_sensitivity, summarize

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "data" / "experimental" / "kozlowski_2025_bmp.csv"
INTAKE = ROOT / "data" / "experimental" / "kozlowski_2025_reactor_observations.csv.gz"
DEFAULT_OUTPUT = ROOT / "results" / "blank-sensitivity"
EFFECT_COLUMNS = [
    "scenario",
    "treatment",
    "response",
    "treatment_estimate",
    "control_estimate",
    "percent_change",
    "percent_change_ci95_low",
    "percent_change_ci95_high",
    "n_treatment_reactors",
    "n_control_reactors",
    "low_replication",
]
RANKING_COLUMNS = [
    "scenario",
    "treatment",
    "model",
    "n_reactors",
    "mean_holdout_rmse_ml_g_vs",
    "rank_by_holdout_rmse",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    results = run_blank_sensitivity(pd.read_csv(BENCHMARK), pd.read_csv(INTAKE))
    tables = {
        "rankings.csv": results["rankings"][RANKING_COLUMNS],
        "effects.csv": results["effects"][EFFECT_COLUMNS],
        "final_yields.csv": results["final_yields"],
    }
    for name, table in tables.items():
        table.to_csv(args.output / name, index=False, float_format="%.6g", lineterminator="\n")
    report = summarize(results)
    report["max_abs_final_yield_change_percent"] = round(
        report["max_abs_final_yield_change_percent"], 3
    )
    report["max_abs_effect_shift_percentage_points"] = round(
        report["max_abs_effect_shift_percentage_points"], 3
    )
    report["input_sha256"] = {
        BENCHMARK.name: _sha256(BENCHMARK),
        INTAKE.name: _sha256(INTAKE),
    }
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
