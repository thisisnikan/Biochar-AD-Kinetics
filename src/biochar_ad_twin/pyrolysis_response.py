"""Descriptive checks for the CDU 2026 pyrolysis-temperature summary table.

Six biochars (400-900 C) and one activated-carbon comparator are reported by
a single PhD thesis at the summary level only: mean final methane yield per
treatment, no reactor-level trajectories or blank-correction detail.
Pyrolysis temperature, BET surface area, electrical conductivity and pH all
increase together across the six biochars, so no fitted trend here can
separate which descriptor, if any, drives the response -- this module
reports that confounding explicitly rather than picking a "best" predictor.
This is a descriptive summary-data check, not evidence for a
conductivity/DIET mechanism (see docs/MECHANISM_EVIDENCE.md).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MODEL_DEGREES = {
    "temperature_invariant": 0,
    "linear_temperature": 1,
    "quadratic_temperature": 2,
}
YIELD_COLUMN = "final_methane_yield_nml"
DESCRIPTOR_COLUMNS = (
    "pyrolysis_temperature_c",
    "bet_surface_area_m2_g",
    "electrical_conductivity_us_cm",
    "ph",
)

# Above this absolute pairwise correlation, two descriptors are considered
# confounded in this table: the data cannot tell which one, if either,
# drives the response.
DESCRIPTOR_COLLINEARITY_THRESHOLD = 0.95


def _validate_pyrolysis_table(frame: pd.DataFrame) -> pd.DataFrame:
    required = {*DESCRIPTOR_COLUMNS, YIELD_COLUMN, "material_id", "source_doi"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing pyrolysis-temperature columns: {', '.join(sorted(missing))}")
    with_yield = frame.dropna(subset=[YIELD_COLUMN])
    if len(with_yield) < 5 or with_yield["pyrolysis_temperature_c"].nunique() != len(with_yield):
        raise ValueError(
            "Pyrolysis-temperature comparison needs at least five biochars with a "
            "reported methane yield at distinct pyrolysis temperatures"
        )
    return with_yield


def compare_pyrolysis_temperature_responses(frame: pd.DataFrame) -> pd.DataFrame:
    """Compare temperature-response forms by leave-one-biochar-out prediction.

    This is a summary-data, descriptive check only: with six biochars sharing
    one temperature series and no reactor-level replicates, held-out error
    says whether a trend is smooth, not whether it is causal or mechanistic.
    """
    with_yield = (
        _validate_pyrolysis_table(frame)
        .sort_values("pyrolysis_temperature_c")
        .reset_index(drop=True)
    )
    temperature = with_yield["pyrolysis_temperature_c"].to_numpy(float)
    observed = with_yield[YIELD_COLUMN].to_numpy(float)

    rows: list[dict[str, float | int | str]] = []
    for model, degree in MODEL_DEGREES.items():
        held_out_predictions = np.empty_like(observed)
        for held_out in range(len(with_yield)):
            train_mask = np.arange(len(with_yield)) != held_out
            coefficients = np.polyfit(temperature[train_mask], observed[train_mask], degree)
            held_out_predictions[held_out] = np.polyval(coefficients, temperature[held_out])
        residual = observed - held_out_predictions
        rows.append(
            {
                "model": model,
                "parameters": degree + 1,
                "n_biochars": len(with_yield),
                "leave_one_biochar_out_rmse": float(np.sqrt(np.mean(residual**2))),
                "leave_one_biochar_out_mae": float(np.mean(np.abs(residual))),
            }
        )
    result = pd.DataFrame(rows)
    result["rank_by_held_out_rmse"] = result["leave_one_biochar_out_rmse"].rank(method="min")
    return result.sort_values("rank_by_held_out_rmse").reset_index(drop=True)


def descriptor_collinearity(frame: pd.DataFrame) -> pd.DataFrame:
    """Pairwise correlation among pyrolysis descriptors across all rows with data.

    Reported as a diagnostic, not filtered out: this table's own design (one
    pyrolysis-temperature series) makes every descriptor pair highly
    correlated by construction, which is exactly why no fitted trend above
    can attribute the response to one specific material property.
    """
    available = frame[list(DESCRIPTOR_COLUMNS)].apply(pd.to_numeric, errors="coerce")
    return available.corr(min_periods=3)


def max_descriptor_collinearity(correlation: pd.DataFrame) -> float:
    """Largest absolute off-diagonal correlation in a descriptor matrix."""
    values = correlation.to_numpy()
    n = values.shape[0]
    off_diagonal = values[~np.eye(n, dtype=bool)]
    off_diagonal = off_diagonal[np.isfinite(off_diagonal)]
    return float(np.max(np.abs(off_diagonal))) if off_diagonal.size else float("nan")
