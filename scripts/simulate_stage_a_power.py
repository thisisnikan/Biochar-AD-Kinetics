"""Simulate how reliably the Stage A dose-holdout test recovers a known truth.

Usage::

    python scripts/simulate_stage_a_power.py --simulations 40 --workers 8

Every simulation has its own seed derived from the scenario, so results do not
depend on the number of workers.
"""

from __future__ import annotations

import argparse
import json
import zlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from biochar_ad_kinetics.stage_a_power import (
    DESIGNS,
    REFERENCE_DOSE_G_L,
    TRUTH_TO_MODEL,
    recovery_table,
    score_simulation,
    simulate_design,
    truth_parameters,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "results" / "stage-a-power"
BASE_SEED = 20261115
EFFECT_AT_REFERENCE = 0.15
REACTOR_LOG_SD = (0.03, 0.07)
RULES = {
    "lowest_rmse_all_doses": ("all", 0.0),
    "parsimony_10pct_all_doses": ("all", 0.10),
    "parsimony_20pct_all_doses": ("all", 0.20),
    "lowest_rmse_interior_doses": ("interior", 0.0),
    "parsimony_10pct_interior_doses": ("interior", 0.10),
}


def _run(task: tuple[str, str, float, int]) -> dict[str, object]:
    design_name, truth, reactor_log_sd, index = task
    design = next(item for item in DESIGNS if item.name == design_name)
    key = f"{design_name}|{truth}|{reactor_log_sd}|{index}".encode()
    rng = np.random.default_rng([BASE_SEED, zlib.crc32(key)])
    frame = simulate_design(
        design, truth_parameters(truth, EFFECT_AT_REFERENCE), reactor_log_sd, rng
    )
    return {
        "design": design_name,
        "truth": truth,
        "reactor_log_sd": reactor_log_sd,
        "simulation": index,
        **score_simulation(frame),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--simulations", type=int, default=40)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    tasks = [
        (design.name, truth, sd, index)
        for design in DESIGNS
        for truth in TRUTH_TO_MODEL
        for sd in REACTOR_LOG_SD
        for index in range(args.simulations)
    ]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(_run, tasks, chunksize=4))
    simulations = pd.DataFrame(rows).sort_values(
        ["design", "truth", "reactor_log_sd", "simulation"]
    )
    simulations.to_csv(
        args.output / "simulations.csv", index=False, float_format="%.6g", lineterminator="\n"
    )
    recovery = recovery_table(simulations, RULES)
    recovery.to_csv(
        args.output / "recovery.csv", index=False, float_format="%.4g", lineterminator="\n"
    )
    report = {
        "status": "SIMULATION_ONLY_NOT_EXPERIMENTAL_VALIDATION",
        "base_seed": BASE_SEED,
        "simulations_per_scenario": args.simulations,
        "effect_on_methane_potential_at_reference_dose": EFFECT_AT_REFERENCE,
        "reference_dose_g_l": REFERENCE_DOSE_G_L,
        "reactor_log_sd": list(REACTOR_LOG_SD),
        "designs": {
            design.name: {
                "doses_g_l": list(design.doses_g_l),
                "replicates": design.replicates,
                "note": design.note,
            }
            for design in DESIGNS
        },
        "rules": {name: {"folds": folds, "margin": margin} for name, (folds, margin) in RULES.items()},
    }
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(recovery.to_string())


if __name__ == "__main__":
    main()
