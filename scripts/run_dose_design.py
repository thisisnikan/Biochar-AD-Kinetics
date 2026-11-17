"""Search dose-experiment designs with the frozen surrogate (simulation only).

Protocol: data/validation/dose_design_v1.json (committed before this script ran).
Outputs: results/dose-design/{scenarios,maximin,agreement}.csv and report.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

from biochar_ad_kinetics.dose_design import correct_form, dose_grid, share_selected

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "data/validation/dose_design_v1.json"
OUTPUT = ROOT / "results/dose-design"
FULL_SIM = ROOT / "results/stage-a-power/recovery.csv"
TRUTHS = ("constant", "monotone", "optimum_5", "optimum_10", "optimum_20", "optimum_40")
EXISTING = {
    "minimum_gate": ((0, 5, 10, 20), 3),
    "narrow_five_dose": ((0, 2, 4, 6, 8), 3),
    "wide_six_dose": ((0, 2, 4, 8, 30, 70), 3),
    "dense_eight_dose": ((0, 5, 10, 15, 20, 25, 30, 40), 3),
}


def _rng(seed: int, *parts) -> np.random.Generator:
    return np.random.default_rng([seed, zlib.crc32("|".join(map(str, parts)).encode())])


def designs(spec: dict):
    space = spec["design_space"]
    for budget in space["budgets_reactors"]:
        for k in range(4, 13):
            r = budget // k
            if r < 2:
                continue
            for highest in space["highest_dose_g_l"]:
                for spacing in space["spacing"]:
                    yield budget, k, r, highest, spacing


def build(output: Path = OUTPUT) -> dict:
    spec = json.loads(SPEC.read_text())
    n, seed = spec["simulations_per_scenario"], spec["seed"]
    rows = []
    for budget, k, r, highest, spacing in designs(spec):
        doses = dose_grid(k, highest, spacing)
        for gain in spec["gains"]:
            for sd in spec["reactor_log_sd"]:
                for truth in TRUTHS:
                    rng = _rng(seed, budget, k, highest, spacing, gain, sd, truth)
                    share = share_selected(doses, r, truth, gain, sd, n, rng)
                    rows.append(
                        {
                            "budget": budget,
                            "doses": k,
                            "replicates": r,
                            "reactors_used": k * r,
                            "highest_dose_g_l": highest,
                            "spacing": spacing,
                            "dose_grid_g_l": " ".join(f"{d:.3g}" for d in doses),
                            "gain": gain,
                            "reactor_log_sd": sd,
                            "truth": truth,
                            "share_correct": share[correct_form(truth)],
                            "share_quadratic": share["quadratic"],
                        }
                    )
    scenarios = pd.DataFrame(rows)
    keys = [
        "budget",
        "doses",
        "replicates",
        "highest_dose_g_l",
        "spacing",
        "gain",
        "reactor_log_sd",
    ]
    worst = (
        scenarios.groupby(keys)
        .agg(
            worst_case_correct=("share_correct", "min"),
            worst_truth=("share_correct", lambda s: scenarios.loc[s.idxmin(), "truth"]),
            dose_grid_g_l=("dose_grid_g_l", "first"),
        )
        .reset_index()
    )
    false_curv = (
        scenarios[scenarios.truth.isin(["constant", "monotone"])]
        .groupby(keys)["share_quadratic"]
        .max()
        .rename("max_false_curvature")
    )
    worst = worst.join(false_curv, on=keys)
    maximin = (
        worst.sort_values(["worst_case_correct", "doses"], ascending=[False, True])
        .groupby(["budget", "gain", "reactor_log_sd"])
        .head(1)
        .sort_values(["gain", "reactor_log_sd", "budget"])
    )
    per_truth = (
        scenarios.merge(maximin[keys], on=keys)
        .pivot_table(index=keys, columns="truth", values="share_correct")
        .reset_index()
    )
    maximin = maximin.merge(per_truth, on=keys)

    # Agreement with the trajectory-level simulation for the existing designs.
    full = pd.read_csv(FULL_SIM)
    full = full[(full.rule == "parsimony_10pct_all_doses")]
    agree = []
    name_map = {
        "no_dose_effect": "constant",
        "log_linear": "monotone",
        "log_quadratic": "optimum_8",
    }
    for design, (doses, r) in EXISTING.items():
        for sd in (0.03, 0.07):
            for full_truth, truth in name_map.items():
                rng = _rng(seed, "agreement", design, sd, truth)
                x_truth = "optimum_8" if truth == "optimum_8" else truth
                share = share_selected(np.array(doses, float), r, x_truth, 0.15, sd, n, rng)
                ref = full[
                    (full.design == design)
                    & (full.truth == full_truth)
                    & np.isclose(full.reactor_log_sd, sd)
                ]["share_correct"]
                agree.append(
                    {
                        "design": design,
                        "reactor_log_sd": sd,
                        "truth": truth,
                        "surrogate_share_correct": share[correct_form(x_truth)],
                        "trajectory_share_correct": float(ref.iloc[0]),
                        "trajectory_simulations": 24,
                    }
                )
    agreement = pd.DataFrame(agree)

    output.mkdir(parents=True, exist_ok=True)
    scenarios.to_csv(output / "scenarios.csv", index=False, float_format="%.4g")
    worst.to_csv(output / "designs.csv", index=False, float_format="%.4g")
    maximin.to_csv(output / "maximin.csv", index=False, float_format="%.4g")
    agreement.to_csv(output / "agreement.csv", index=False, float_format="%.4g")
    reach = {}
    for (gain, sd), part in maximin.groupby(["gain", "reactor_log_sd"]):
        ok = part[part.worst_case_correct >= 0.80]
        reach[f"gain_{gain}_sd_{sd}"] = int(ok.budget.min()) if len(ok) else None
    report = {
        "spec_id": spec["spec_id"],
        "status": "SIMULATION_ONLY_NOT_EXPERIMENTAL_VALIDATION",
        "designs_searched": int(worst[keys[:5]].drop_duplicates().shape[0]),
        "scenarios": len(scenarios),
        "smallest_budget_reaching_0_80_worst_case": reach,
        "input_sha256": {
            "spec": hashlib.sha256(SPEC.read_bytes()).hexdigest(),
            "trajectory_recovery": hashlib.sha256(FULL_SIM.read_bytes()).hexdigest(),
        },
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    print(json.dumps(build(parser.parse_args().output_dir), indent=2))


if __name__ == "__main__":
    main()
