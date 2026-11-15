"""Operating characteristics of the Stage A dose-holdout test, by simulation.

Stage A ranks three dose-response candidates by mean whole-dose-held-out RMSE.
Before real Stage A data exist, this module asks how often that procedure would
recover a known truth for realistic designs. Reactor trajectories are simulated
from the package's own model and scored by the unmodified
``leave_one_dose_out`` routine, so the result describes the procedure that will
actually be run. Simulation cannot validate the model against experiments.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from .analysis import leave_one_dose_out
from .model import BatchCondition, KineticParameters, cumulative_methane

MODEL_ORDER = ("constant_gompertz", "log_linear_dose_temperature", "global_dose_temperature")
TRUTH_TO_MODEL = {
    "no_dose_effect": "constant_gompertz",
    "log_linear": "log_linear_dose_temperature",
    "log_quadratic": "global_dose_temperature",
}
REFERENCE_DOSE_G_L = 8.0
STAGE_A_DECISION_FOLDS = "all"
STAGE_A_PARSIMONY_MARGIN = 0.10
BASELINE = KineticParameters(
    potential_0=350.0,
    rate_0=65.0,
    lag_days=0.5,
    potential_linear=0.0,
    potential_quadratic=0.0,
    rate_linear=0.0,
    rate_quadratic=0.0,
    q10=1.0,
)


@dataclass(frozen=True)
class Design:
    """A single-temperature dose series with replicated reactors."""

    name: str
    doses_g_l: tuple[float, ...]
    replicates: int
    note: str


DESIGNS: tuple[Design, ...] = (
    Design("minimum_gate", (0, 5, 10, 20), 3, "Smallest design that passes the Stage A gate"),
    Design("narrow_five_dose", (0, 2, 4, 6, 8), 3, "Dose grid of Valentin & Białowiec (2024)"),
    Design("wide_six_dose", (0, 2, 4, 8, 30, 70), 3, "Wide grid with a high-dose arm"),
    Design("dense_eight_dose", (0, 5, 10, 15, 20, 25, 30, 40), 3, "Dense grid to 40 g/L"),
)


def truth_parameters(truth: str, effect_at_reference: float) -> KineticParameters:
    """Return generating parameters for one truth.

    ``effect_at_reference`` is the fractional change in methane potential at
    ``REFERENCE_DOSE_G_L``; the maximum rate changes by twice that on the log
    scale. The log-quadratic truth peaks at the reference dose and returns
    toward baseline at high dose.
    """
    if truth not in TRUTH_TO_MODEL:
        raise ValueError(f"Unknown truth: {truth}")
    if truth == "no_dose_effect":
        return BASELINE
    x_ref = float(np.log1p(REFERENCE_DOSE_G_L))
    gain = float(np.log1p(effect_at_reference))
    if truth == "log_linear":
        return replace(BASELINE, potential_linear=gain / x_ref, rate_linear=2 * gain / x_ref)
    return replace(
        BASELINE,
        potential_linear=2 * gain / x_ref,
        potential_quadratic=-gain / x_ref**2,
        rate_linear=4 * gain / x_ref,
        rate_quadratic=-2 * gain / x_ref**2,
    )


def simulate_design(
    design: Design,
    parameters: KineticParameters,
    reactor_log_sd: float,
    rng: np.random.Generator,
    reading_sd_ml_g_vs: float = 2.0,
    duration_days: int = 21,
) -> pd.DataFrame:
    """Simulate daily cumulative methane for every reactor in a design."""
    time = np.arange(0.0, duration_days + 1.0, 1.0)
    frames = []
    for dose in design.doses_g_l:
        for replicate in range(1, design.replicates + 1):
            reactor = replace(
                parameters,
                potential_0=parameters.potential_0 * float(np.exp(rng.normal(0, reactor_log_sd))),
                rate_0=parameters.rate_0 * float(np.exp(rng.normal(0, reactor_log_sd))),
            )
            methane = cumulative_methane(time, BatchCondition(float(dose), 37.0), reactor)
            methane = methane + rng.normal(0, reading_sd_ml_g_vs, len(time))
            identifier = f"dose{dose:g}_r{replicate}"
            frames.append(
                pd.DataFrame(
                    {
                        "batch_id": identifier,
                        "time_days": time,
                        "dose_g_l": float(dose),
                        "temperature_c": 37.0,
                        "methane_ml_g_vs": methane,
                        "validation_reactor_id": identifier,
                        "validation_dose_id": f"dose{dose:g}",
                    }
                )
            )
    return pd.concat(frames, ignore_index=True)


def score_simulation(frame: pd.DataFrame) -> dict[str, float]:
    """Run the real dose-holdout routine and return mean RMSE per candidate.

    ``all`` averages every held-out dose (the Stage A primary metric);
    ``interior`` averages only doses inside the tested range.
    """
    validation = leave_one_dose_out(frame)
    scores: dict[str, float] = {}
    for label, subset in (
        ("all", validation),
        ("interior", validation.loc[~validation["is_boundary_condition"]]),
    ):
        means = subset.groupby("model")["rmse_ml_g_vs"].mean()
        for model in MODEL_ORDER:
            scores[f"{label}__{model}"] = float(means[model])
    return scores


def select_model(scores: dict[str, float], folds: str, parsimony_margin: float) -> str:
    """Pick the simplest candidate unless a more complex one is clearly better.

    Candidates are visited from simplest to most complex. A more complex
    candidate replaces the current choice only if its mean held-out RMSE is
    lower by more than ``parsimony_margin`` (a fraction of the current RMSE).
    A margin of zero is the plain lowest-RMSE rule.
    """
    chosen = MODEL_ORDER[0]
    for model in MODEL_ORDER[1:]:
        if scores[f"{folds}__{model}"] < (1 - parsimony_margin) * scores[f"{folds}__{chosen}"]:
            chosen = model
    return chosen


def recovery_table(
    simulations: pd.DataFrame, rules: dict[str, tuple[str, float]]
) -> pd.DataFrame:
    """Summarize how often each decision rule selects each candidate."""
    rows = []
    group_columns = ["design", "truth", "reactor_log_sd"]
    for keys, group in simulations.groupby(group_columns, sort=True):
        design, truth, reactor_log_sd = keys
        for rule, (folds, margin) in rules.items():
            selected = group.apply(
                lambda row, f=folds, m=margin: select_model(row.to_dict(), f, m), axis=1
            )
            shares = selected.value_counts(normalize=True)
            rows.append(
                {
                    "design": design,
                    "truth": truth,
                    "reactor_log_sd": reactor_log_sd,
                    "rule": rule,
                    "simulations": len(group),
                    "share_correct": float(shares.get(TRUTH_TO_MODEL[truth], 0.0)),
                    **{f"share_{model}": float(shares.get(model, 0.0)) for model in MODEL_ORDER},
                }
            )
    return pd.DataFrame(rows)


def stage_a_decision(mean_rmse_by_model: dict[str, float]) -> dict[str, object]:
    """Apply the frozen Stage A decision rule to mean whole-dose-held-out RMSEs."""
    missing = set(MODEL_ORDER).difference(mean_rmse_by_model)
    if missing:
        raise ValueError(f"Missing Stage A candidates: {', '.join(sorted(missing))}")
    scores = {
        f"{STAGE_A_DECISION_FOLDS}__{model}": float(mean_rmse_by_model[model])
        for model in MODEL_ORDER
    }
    return {
        "rule": "simplest candidate unless a more complex one lowers mean "
        "whole-dose-held-out RMSE by more than the parsimony margin",
        "parsimony_margin": STAGE_A_PARSIMONY_MARGIN,
        "selected_model": select_model(
            scores, STAGE_A_DECISION_FOLDS, STAGE_A_PARSIMONY_MARGIN
        ),
        "lowest_rmse_model": min(MODEL_ORDER, key=lambda model: mean_rmse_by_model[model]),
        "specification": "data/validation/stage_a_dose_v1.json",
    }
