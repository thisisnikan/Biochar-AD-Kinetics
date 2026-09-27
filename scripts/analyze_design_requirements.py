"""Turn Sanglier variance and cycle-length evidence into experiment-design requirements.

Uses admitted, co-intervention-free cycles only, at the corrected 5.0 d horizon
(the unlocked deviation D1 of the admission analysis; disclosed, not a new
locked result). Three variance scenarios are reported because the two labs
differ and LBE contains one failed control:

- BRL: 11 bottles, 10 batches
- LBE: 7 bottles, 8 batches
- LBE_without_IV.3: the same without the failed control

Outputs (results/requirements/):
- design_variance_components.csv
- design_power_table.csv
- design_requirements.json
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd

from biochar_ad_kinetics.design_requirements import (
    design_table,
    mean_square_components,
    minimum_bottles,
)

ROOT = Path(__file__).resolve().parents[1]
ADMISSION = ROOT / "results" / "validation" / "sanglier_2022_admission.csv"
METHANE = ROOT / "results" / "intake" / "sanglier_2022_candidate.csv.gz"
STRUCTURE = ROOT / "results" / "requirements" / "sanglier_2022_structure_report.json"
OUTPUT = ROOT / "results" / "requirements"
TARGET = "methane_yield_nml_gvs"
HORIZON = 5.0
TOL = 1e-6
EFFECTS = (0.05, 0.10, 0.20)


def _write(frame: pd.DataFrame, path: Path) -> None:
    buffer = io.StringIO()
    frame.to_csv(buffer, index=False, lineterminator="\n", float_format="%.6g")
    path.write_text(buffer.getvalue(), encoding="utf-8")


def horizon_frame() -> pd.DataFrame:
    admission = pd.read_csv(ADMISSION)
    admitted = admission[admission["admitted_primary"]]
    methane = pd.read_csv(METHANE)
    at_h = methane[(methane["within_batch_days"] - HORIZON).abs() <= TOL]
    frame = admitted.merge(
        at_h[["lab", "batch_id", "bottle_id", TARGET]],
        on=["lab", "batch_id", "bottle_id"],
        validate="1:1",
    )
    if frame[TARGET].isna().any() or (frame[TARGET] <= 0).any():
        raise SystemExit("Every admitted cycle needs a positive yield at the horizon")
    frame["log_yield"] = np.log(frame[TARGET])
    frame["arm"] = frame["source_condition_inoculation"].str.replace(" ", "", regex=False)
    return frame


def build(output: Path = OUTPUT) -> dict:
    frame = horizon_frame()
    scenarios = {
        "BRL": frame[frame["lab"] == "BRL"],
        "LBE": frame[frame["lab"] == "LBE"],
        "LBE_without_IV.3": frame[(frame["lab"] == "LBE") & (frame["bottle_id"] != "IV.3")],
    }
    components = []
    tables = []
    requirements = {}
    for name, data in scenarios.items():
        comp = mean_square_components(data, "log_yield", "batch_id", "arm", "bottle_id")
        components.append({"scenario": name, **comp})
        table = design_table(comp["sigma2_unit"], comp["sigma2_residual"], EFFECTS)
        tables.append(table.assign(scenario=name))
        batches = comp["batches"]
        pessimistic_unit = max(
            (comp["ms_unit_upper95"] - comp["sigma2_residual"]) / batches, comp["sigma2_unit"]
        )
        requirements[name] = {
            f"bottles_per_arm_for_80pct_power_{round(100 * e)}pct_effect_{m}_batches": (
                minimum_bottles(comp["sigma2_unit"], comp["sigma2_residual"], e, m)
            )
            for e in EFFECTS
            for m in (1, batches)
        }
        requirements[name]["bottles_per_arm_10pct_effect_pessimistic_unit_variance"] = (
            minimum_bottles(pessimistic_unit, comp["sigma2_residual"], 0.10, batches)
        )
        requirements[name]["between_bottle_sd_percent"] = round(
            100 * float(np.expm1(np.sqrt(comp["sigma2_unit"]))), 2
        )
        requirements[name]["bottle_by_batch_sd_percent"] = round(
            100 * float(np.expm1(np.sqrt(comp["sigma2_residual"]))), 2
        )
        requirements[name]["batch_sd_percent"] = round(
            100 * float(np.expm1(np.sqrt(comp["sigma2_batch"]))), 2
        )

    structure = json.loads(STRUCTURE.read_text())
    report = {
        "status": "DESIGN_PLANNING_FROM_ONE_STUDY",
        "horizon_days": HORIZON,
        "horizon_note": "Corrected-rule horizon (deviation D1 in the admission analysis).",
        "scenarios": requirements,
        "exact_permutation_rule": "At least 4 bottles per arm are needed before an exact "
        "two-sided permutation test can reach p < 0.05 (floor 0.029); 3 per arm gives 0.10.",
        "cycle_length": {
            "long_cycles_reaching_1pct_per_day": structure["cycle_length_to_1pct_per_day"],
            "prefix_sweep_best_family": structure["prefix_sweep_for_best_family"],
        },
        "caveats": [
            "Variance components come from one study, one substrate type and one biochar.",
            (
                "Batch variance cancels only if every arm is run in every batch; a design that "
                "confounds arms with batches inherits the full batch variance."
            ),
            (
                "Power refers to a within-study contrast; cross-study prediction additionally "
                "requires independent studies, not more bottles."
            ),
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    _write(pd.DataFrame(components), output / "design_variance_components.csv")
    power = pd.concat(tables, ignore_index=True)
    power = power[["scenario"] + [c for c in power.columns if c != "scenario"]]
    _write(power, output / "design_power_table.csv")
    (output / "design_requirements.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    print(json.dumps(build(parser.parse_args().output_dir)["scenarios"], indent=2))


if __name__ == "__main__":
    main()
