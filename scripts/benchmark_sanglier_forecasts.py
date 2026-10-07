"""Compare existing exploratory kinetic forecasts with prefix-only baselines.

Reuses the committed structure audit's rounded endpoint errors; does not refit
or choose a winning kinetic family using full-cycle AICc. Only existing long
cycles are scored. Their observed final time supplies the retrospective horizon.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from biochar_ad_kinetics.forecast_benchmark import paired_bottle_comparison, prefix_baselines

ROOT = Path(__file__).resolve().parents[1]
INPUTS = {
    "methane": ROOT / "results/intake/sanglier_2022_candidate.csv.gz",
    "structure": ROOT / "results/requirements/sanglier_2022_structure_by_cycle.csv",
}
OUTPUT = ROOT / "results/forecasting"
KEYS = ["lab", "batch_id", "bottle_id"]
TARGET = "methane_yield_nml_gvs"


def build(output: Path = OUTPUT) -> dict:
    methane = pd.read_csv(INPUTS["methane"])
    existing = pd.read_csv(INPUTS["structure"])
    kinetic = existing.rename(
        columns={"family": "method", "final_relative_error": "relative_error"}
    )
    columns = KEYS + ["cut_days", "method", "relative_error"]
    rows = []
    cycles = {key: cycle for key, cycle in methane.groupby(KEYS, sort=True)}
    # Existing structure eligibility is reused, including its R7 fault exclusions.
    for record in existing.drop_duplicates(KEYS + ["cut_days"]).itertuples():
        key = (record.lab, record.batch_id, record.bottle_id)
        cycle = cycles[key].dropna(subset=[TARGET]).sort_values("within_batch_days")
        t = cycle["within_batch_days"].to_numpy(float)
        y = cycle[TARGET].to_numpy(float)
        if y[-1] <= 0 or not np.isfinite(y[-1]):
            raise ValueError(f"Nonpositive endpoint prevents relative scoring: {key}")
        if not np.isclose(t[-1], record.last_day):
            raise ValueError(f"Structure horizon differs from source: {key}")
        for method, prediction in prefix_baselines(t, y, record.cut_days, t[-1]).items():
            rows.append(
                dict(zip(KEYS, key, strict=True))
                | {
                    "cut_days": record.cut_days,
                    "method": method,
                    "relative_error": (prediction - y[-1]) / y[-1],
                }
            )
    scores = pd.concat([kinetic[columns], pd.DataFrame(rows)], ignore_index=True)
    summaries = []
    populations = {
        "all_long_cycles": scores,
        "without_failing_controls": scores[~scores["bottle_id"].isin(["IV.2", "IV.3"])],
    }
    for population, frame in populations.items():
        for reference in ("persistence", "recent_rate"):
            summaries.append(
                paired_bottle_comparison(frame, reference).assign(population=population)
            )
    summary = pd.concat(summaries, ignore_index=True)
    output.mkdir(parents=True, exist_ok=True)
    for name, frame in (("scores.csv", scores), ("summary.csv", summary)):
        frame.to_csv(output / name, index=False, float_format="%.9g", lineterminator="\n")
    def hash_file(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()
    report = {
        "status": "EXPLORATORY_WITHIN_STUDY_PAIRED_FORECAST_BENCHMARK",
        "seed": 20261006,
        "bootstrap_draws": 5000,
        "input_sha256": {name: hash_file(path) for name, path in INPUTS.items()},
        "method_sha256": {
            str(path.relative_to(ROOT)): hash_file(path)
            for path in (
                Path(__file__),
                ROOT / "src/biochar_ad_kinetics/forecast_benchmark.py",
                ROOT / "src/biochar_ad_kinetics/kinetic_structure.py",
                ROOT / "scripts/analyze_sanglier_2022_kinetic_structure.py",
            )
        },
        "output_sha256": {name: hash_file(output / name) for name in ("scores.csv", "summary.csv")},
        "score_rows": len(scores),
        "limitations": [
            "Existing kinetic endpoint errors have six significant digits; no model refit.",
            "Long-cycle selection and final-time horizons are retrospective and outcome-aware.",
            "All methods use identical cycles within a cutoff; cutoff populations may differ.",
            "Equal-bottle summaries average absolute relative errors within bottle first.",
            "Bootstrap retains repeated cycles and stratifies by lab, but omits shared batch shocks.",
            "Conditional intervals omit source-unit, optimizer and model-selection uncertainty.",
            "Kinetic forecasts include parameter-bound fits; predictive error does not establish parameter identifiability.",
            "Source unit conflicts remain unresolved; no causal or cross-study validation claim.",
            "Failing-control exclusion is a sensitivity analysis; primary results retain them.",
        ],
    }
    (output / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    print(json.dumps(build(parser.parse_args().output_dir), indent=2))
