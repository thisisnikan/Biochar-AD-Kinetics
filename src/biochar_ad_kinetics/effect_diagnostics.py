"""Dependence and unit-level sensitivity for existing within-study effects.

No pooling, hypothesis test or new validation dataset is introduced here.
Kinetic estimates are conditional on the current fitting and blank correction.
"""

from __future__ import annotations

from itertools import combinations_with_replacement

import numpy as np
import pandas as pd

from .effects import RESPONSES, _reactor_kinetic_estimates


def shared_control_covariance(effects: pd.DataFrame) -> pd.DataFrame:
    """Return within-study/response blocks of delta-method covariance.

    For two distinct treatment means using the *same* independent control
    sample, Cov(log(T_i/C), log(T_j/C)) = SD(C)^2 / (n_C mean(C)^2).
    The diagonal additionally includes SD(T)^2 / (n_T mean(T)^2).
    See Lajeunesse (2011), doi:10.1890/11-0423.1.

    A control label must identify one actual shared control group within each
    study and response. Treatment samples must be disjoint; paired designs,
    reused bottles and cross-response covariances require raw joint data.
    Missing summary uncertainty remains unavailable, never zero-imputed.
    """
    required = {
        "study_id",
        "response",
        "treatment",
        "control",
        "treatment_estimate",
        "control_estimate",
        "treatment_sd",
        "control_sd",
        "n_treatment_reactors",
        "n_control_reactors",
    }
    if not required.issubset(effects):
        raise ValueError(f"Missing covariance columns: {sorted(required.difference(effects))}")
    keys = ["study_id", "response", "treatment"]
    if effects[keys + ["control"]].isna().any().any():
        raise ValueError("Covariance identities must be complete")
    if effects.duplicated(keys).any():
        raise ValueError("One effect per study, response and treatment is required")

    def variance(row: pd.Series, arm: str) -> float:
        mean, sd, n = (float(row[c]) for c in (f"{arm}_estimate", f"{arm}_sd", f"n_{arm}_reactors"))
        if not np.isfinite([mean, sd, n]).all():
            return np.nan
        if mean <= 0 or sd < 0 or n < 2 or n != int(n):
            raise ValueError("Covariance requires positive means, nonnegative SD and n >= 2")
        return sd**2 / (n * mean**2)

    rows = []
    for (study, response), block in effects.groupby(["study_id", "response"], sort=True):
        for _, control in block.groupby("control", sort=True):
            for column in ("control_estimate", "control_sd", "n_control_reactors"):
                if control[column].nunique(dropna=False) != 1:
                    raise ValueError("Shared control summaries disagree within a study/response")
        ordered = [r for _, r in block.sort_values("treatment").iterrows()]
        for a, b in combinations_with_replacement(ordered, 2):
            diagonal = a["treatment"] == b["treatment"]
            shared = a["control"] == b["control"]
            # Validate both arms even for an off-diagonal entry.
            va, vb = variance(a, "treatment"), variance(b, "treatment")
            ca, cb = variance(a, "control"), variance(b, "control")
            available = np.isfinite([va, vb, ca, cb]).all()
            covariance = va + ca if diagonal else ca if shared else 0.0
            rows.append(
                {
                    "study_id": study,
                    "response": response,
                    "treatment_a": a["treatment"],
                    "treatment_b": b["treatment"],
                    "shared_control": shared,
                    "is_diagonal": diagonal,
                    "covariance": float(covariance) if available else np.nan,
                    "correlation": float(covariance / np.sqrt((va + ca) * (vb + cb)))
                    if available and (va + ca) * (vb + cb) > 0
                    else np.nan,
                    "uncertainty_available": bool(available),
                    "method": "delta_method_conditional_on_fitted_reactor_parameters",
                }
            )
    return pd.DataFrame(rows)


def leave_one_reactor_out_effects(frame: pd.DataFrame) -> pd.DataFrame:
    """Delete one independent reactor estimate at a time within each contrast.

    Each trajectory is fitted once. All observations from a reactor disappear
    together through its fitted estimate. This is an influence diagnostic,
    not cross-validation, a confidence interval or a correction sensitivity.
    A one-reactor remainder is allowed only as a labelled descriptive value.
    """
    return _leave_one_estimate_out(_reactor_kinetic_estimates(frame))


def _leave_one_estimate_out(estimates: pd.DataFrame) -> pd.DataFrame:
    estimates = estimates.reset_index(drop=True)
    keys = ["study_id", "treatment", "replicate"]
    if estimates.duplicated(keys).any():
        raise ValueError("Repeated estimates cannot count as independent reactors")
    if estimates[keys].isna().any().any():
        raise ValueError("Reactor identities must be complete")
    values = estimates[list(RESPONSES)].to_numpy(float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("Reactor kinetic estimates must be finite and positive")
    rows = []
    for study, block in estimates.groupby("study_id", sort=True):
        control = block.loc[block["treatment"] == "food_waste"]
        if len(control) < 2:
            raise ValueError("Sensitivity needs at least two control reactors")
        for treatment, group in block.loc[block["treatment"] != "food_waste"].groupby(
            "treatment", sort=True
        ):
            if len(group) < 2:
                raise ValueError("Sensitivity needs at least two treatment reactors")
            for response in RESPONSES:
                original = float(np.log(group[response].mean() / control[response].mean()))
                for arm, units in (("treatment", group), ("control", control)):
                    for index, unit in units.iterrows():
                        t = group.drop(index) if arm == "treatment" else group
                        c = control.drop(index) if arm == "control" else control
                        omitted = float(np.log(t[response].mean() / c[response].mean()))
                        rows.append(
                            {
                                "study_id": study,
                                "treatment": treatment,
                                "response": response,
                                "omitted_arm": arm,
                                "omitted_replicate": unit["replicate"],
                                "original_log_response_ratio": original,
                                "omitted_log_response_ratio": omitted,
                                "original_percent_change": float(100 * np.expm1(original)),
                                "omitted_percent_change": float(100 * np.expm1(omitted)),
                                "sign_changed": bool(np.sign(original) != np.sign(omitted)),
                                "n_treatment_remaining": len(t),
                                "n_control_remaining": len(c),
                                "unreplicated_remainder": min(len(t), len(c)) < 2,
                            }
                        )
    return pd.DataFrame(rows)
