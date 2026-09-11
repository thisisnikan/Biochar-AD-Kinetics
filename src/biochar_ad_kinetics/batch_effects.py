"""Matched-control effect extraction for batch kinetic summaries.

This is kept separate from trajectory fitting so effect definitions remain
explicit and testable. Positive values mean improvement relative to the matched
control: higher potential/rate, or shorter lag/t50/t90.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_MATCH_COLUMNS = (
    "study_id",
    "experiment_id",
    "temperature_c",
    "substrate_id",
    "inoculum_id",
)


def relative_gain(treated: float, control: float) -> float:
    """Return (treated - control) / control, guarding zero baselines."""
    if not np.isfinite(control) or abs(control) < 1e-12:
        return float("nan")
    return float((treated - control) / control)


def relative_reduction(treated: float, control: float) -> float:
    """Return (control - treated) / control, so shorter times are positive."""
    if not np.isfinite(control) or abs(control) < 1e-12:
        return float("nan")
    return float((control - treated) / control)


def extract_matched_control_effects(
    frame: pd.DataFrame,
    fits: pd.DataFrame,
    *,
    control_group_columns: tuple[str, ...] = DEFAULT_MATCH_COLUMNS,
) -> pd.DataFrame:
    """Compute per-reactor kinetic effects against matched control means."""
    required_meta = {
        "reactor_id",
        "treatment_id",
        "dose_g_l",
        "is_control",
        *control_group_columns,
    }
    missing_meta = required_meta.difference(frame.columns)
    if missing_meta:
        raise ValueError(
            "Missing columns for matched-control effects: "
            + ", ".join(sorted(missing_meta))
        )

    required_fit = {
        "reactor_id",
        "selected",
        "model",
        "potential",
        "max_rate",
        "lag_days",
        "t50_days",
        "t90_days",
    }
    missing_fit = required_fit.difference(fits.columns)
    if missing_fit:
        raise ValueError("Missing fit columns: " + ", ".join(sorted(missing_fit)))

    meta = frame.drop_duplicates("reactor_id").copy()
    selected = fits.loc[fits["selected"].astype(bool)].copy()
    merged = selected.merge(meta, on="reactor_id", how="left", validate="one_to_one")

    rows: list[dict[str, object]] = []
    for key, group in merged.groupby(list(control_group_columns), dropna=False, sort=True):
        controls = group.loc[group["is_control"].astype(bool)]
        treated = group.loc[~group["is_control"].astype(bool)]
        if controls.empty or treated.empty:
            continue

        metrics = ["potential", "max_rate", "lag_days", "t50_days", "t90_days"]
        baseline = controls[metrics].mean()
        key_tuple = key if isinstance(key, tuple) else (key,)
        control_group_id = "::".join(str(value) for value in key_tuple)
        control_models = ",".join(sorted(set(controls["model"].astype(str))))

        for _, row in treated.iterrows():
            rows.append(
                {
                    "study_id": str(row["study_id"]),
                    "experiment_id": str(row["experiment_id"]),
                    "treatment_id": str(row["treatment_id"]),
                    "reactor_id": str(row["reactor_id"]),
                    "control_group_id": control_group_id,
                    "dose_g_l": float(row["dose_g_l"]),
                    "delta_potential": relative_gain(
                        float(row["potential"]), float(baseline["potential"])
                    ),
                    "delta_max_rate": relative_gain(
                        float(row["max_rate"]), float(baseline["max_rate"])
                    ),
                    "delta_lag": relative_reduction(
                        float(row["lag_days"]), float(baseline["lag_days"])
                    ),
                    "delta_t50": relative_reduction(
                        float(row["t50_days"]), float(baseline["t50_days"])
                    ),
                    "delta_t90": relative_reduction(
                        float(row["t90_days"]), float(baseline["t90_days"])
                    ),
                    "treated_model": str(row["model"]),
                    "control_model": control_models,
                }
            )

    return pd.DataFrame(rows)
