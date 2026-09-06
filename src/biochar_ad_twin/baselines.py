"""Transparent kinetic baselines for replicate-level experimental BMP data."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from scipy.optimize import least_squares

from .analysis import information_criteria


@dataclass(frozen=True)
class BaselineSpec:
    """Definition and parameter bounds for one cumulative-methane model."""

    name: str
    function: Callable[..., NDArray[np.float64]]
    initial: tuple[float, ...]
    lower: tuple[float, ...]
    upper: tuple[float, ...]


def _first_order(time: NDArray[np.float64], potential: float, rate: float) -> NDArray[np.float64]:
    return potential * (1 - np.exp(-rate * time))


def _modified_gompertz(
    time: NDArray[np.float64], potential: float, rate: float, lag: float
) -> NDArray[np.float64]:
    exponent = (np.e * rate / potential) * (lag - time) + 1.0
    return potential * np.exp(-np.exp(np.clip(exponent, -50.0, 50.0)))


def _logistic(
    time: NDArray[np.float64], potential: float, rate: float, lag: float
) -> NDArray[np.float64]:
    exponent = (4 * rate / potential) * (lag - time) + 2.0
    return potential / (1 + np.exp(np.clip(exponent, -50.0, 50.0)))


BASELINES = {
    spec.name: spec
    for spec in (
        BaselineSpec("first_order", _first_order, (400.0, 0.2), (1.0, 1e-4), (1000.0, 10.0)),
        BaselineSpec(
            "modified_gompertz",
            _modified_gompertz,
            (400.0, 40.0, 0.2),
            (1.0, 1e-3, 0.0),
            (1000.0, 1000.0, 21.0),
        ),
        BaselineSpec(
            "logistic",
            _logistic,
            (400.0, 40.0, 0.2),
            (1.0, 1e-3, 0.0),
            (1000.0, 1000.0, 21.0),
        ),
    )
}


def include_mask(frame: pd.DataFrame, column: str = "included_in_benchmark") -> pd.Series:
    """Coerce a benchmark-inclusion column to boolean, tolerating string encodings."""
    inclusion = frame[column]
    if inclusion.dtype == bool:
        return inclusion
    return inclusion.astype(str).str.lower().isin({"true", "1", "yes"})


def fit_baseline(frame: pd.DataFrame, spec: BaselineSpec) -> tuple[np.ndarray, np.ndarray]:
    """Fit one baseline specification and return parameters and predictions."""
    time = frame["time_days"].to_numpy(float)
    observed = frame["methane_ml_g_vs"].to_numpy(float)
    solution = least_squares(
        lambda values: spec.function(time, *values) - observed,
        np.asarray(spec.initial, dtype=float),
        bounds=(spec.lower, spec.upper),
        loss="linear",
    )
    return solution.x, spec.function(time, *solution.x)


def compare_experimental_baselines(frame: pd.DataFrame) -> pd.DataFrame:
    """Compare curve families using AICc and leave-one-reactor-out prediction.

    A separate shared curve is fitted within each treatment. Replicate-held-out
    error is the primary result; information criteria are descriptive because
    observations within a cumulative reactor trajectory are autocorrelated.
    """

    required = {
        "treatment",
        "replicate",
        "time_days",
        "methane_ml_g_vs",
        "included_in_benchmark",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing experimental columns: {', '.join(sorted(missing))}")
    valid = frame.loc[include_mask(frame)].copy()
    if valid.empty:
        raise ValueError("No reactor trajectories are marked for benchmark inclusion")

    rows: list[dict[str, float | int | str]] = []
    for treatment, treatment_frame in valid.groupby("treatment", sort=True):
        replicas = sorted(treatment_frame["replicate"].unique())
        if len(replicas) < 2:
            raise ValueError(f"Treatment {treatment} needs at least two valid reactors")
        observed = treatment_frame["methane_ml_g_vs"].to_numpy(float)
        for spec in BASELINES.values():
            _, fitted = fit_baseline(treatment_frame, spec)
            residual = observed - fitted
            holdout_rmse = []
            holdout_mae = []
            for held_out in replicas:
                train = treatment_frame.loc[treatment_frame["replicate"] != held_out]
                test = treatment_frame.loc[treatment_frame["replicate"] == held_out]
                parameters, _ = fit_baseline(train, spec)
                predicted = spec.function(test["time_days"].to_numpy(float), *parameters)
                errors = test["methane_ml_g_vs"].to_numpy(float) - predicted
                holdout_rmse.append(float(np.sqrt(np.mean(errors**2))))
                holdout_mae.append(float(np.mean(np.abs(errors))))
            rows.append(
                {
                    "treatment": treatment,
                    "model": spec.name,
                    "parameters": len(spec.initial),
                    "n_reactors": len(replicas),
                    "n_observations": len(treatment_frame),
                    "train_rmse_ml_g_vs": float(np.sqrt(np.mean(residual**2))),
                    "mean_holdout_rmse_ml_g_vs": float(np.mean(holdout_rmse)),
                    "mean_holdout_mae_ml_g_vs": float(np.mean(holdout_mae)),
                    **information_criteria(observed, fitted, len(spec.initial)),
                }
            )
    result = pd.DataFrame(rows)
    result["rank_by_holdout_rmse"] = result.groupby("treatment")[
        "mean_holdout_rmse_ml_g_vs"
    ].rank(method="min")
    return result.sort_values(["treatment", "rank_by_holdout_rmse", "aicc"]).reset_index(drop=True)
