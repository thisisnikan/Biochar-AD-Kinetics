"""Independent dose-response checks using published kinetic parameters.

This module deliberately validates only the dose-response layer. It does not
reconstruct reactor trajectories or treat table-level kinetic estimates as raw
observations.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MODEL_DEGREES = {
    "dose_invariant": 0,
    "log_linear_dose": 1,
    "log_quadratic_dose": 2,
}
TARGETS = ("potential_ml_g_vs", "max_rate_ml_g_vs_day")


def _validate_parameter_table(frame: pd.DataFrame) -> None:
    required = {"dose_g_l", *TARGETS, "source_doi", "data_origin"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing external-validation columns: {', '.join(sorted(missing))}")
    if len(frame) < 5 or frame["dose_g_l"].nunique() != len(frame):
        raise ValueError("External dose validation needs at least five unique dose conditions")
    if frame[["dose_g_l", *TARGETS]].isna().any().any():
        raise ValueError("Dose and kinetic targets must be complete")
    if (frame["dose_g_l"] < 0).any() or (frame[list(TARGETS)] <= 0).any().any():
        raise ValueError("Dose must be non-negative and kinetic targets must be positive")


def compare_external_dose_responses(frame: pd.DataFrame) -> pd.DataFrame:
    """Compare dose-response forms by leave-one-dose-out prediction.

    Models are fitted to log kinetic parameters against ``log1p(dose)``. The
    quadratic candidate is the exploratory response form used by this
    project. With only five independent dose conditions, held-out error is the
    primary criterion and no mechanistic or causal inference is attempted.
    """

    _validate_parameter_table(frame)
    frame = frame.sort_values("dose_g_l").reset_index(drop=True)
    transformed_dose = np.log1p(frame["dose_g_l"].to_numpy(float))
    rows: list[dict[str, float | int | str]] = []

    for target in TARGETS:
        observed = frame[target].to_numpy(float)
        for model, degree in MODEL_DEGREES.items():
            held_out_predictions = np.empty_like(observed)
            for held_out in range(len(frame)):
                train_mask = np.arange(len(frame)) != held_out
                coefficients = np.polyfit(
                    transformed_dose[train_mask], np.log(observed[train_mask]), degree
                )
                held_out_predictions[held_out] = np.exp(
                    np.polyval(coefficients, transformed_dose[held_out])
                )

            residual = observed - held_out_predictions
            rows.append(
                {
                    "response": target,
                    "model": model,
                    "parameters": degree + 1,
                    "n_doses": len(frame),
                    "leave_one_dose_out_rmse": float(np.sqrt(np.mean(residual**2))),
                    "leave_one_dose_out_mae": float(np.mean(np.abs(residual))),
                    "mean_absolute_percentage_error": float(
                        100 * np.mean(np.abs(residual / observed))
                    ),
                }
            )

    result = pd.DataFrame(rows)
    result["rank_by_held_out_rmse"] = result.groupby("response")[
        "leave_one_dose_out_rmse"
    ].rank(method="min")
    return result.sort_values(["response", "rank_by_held_out_rmse"]).reset_index(drop=True)
