"""Batch trajectory benchmarking: per-reactor kinetic curve fitting.

This module complements the global dose-response model with per-reactor fits.
It is deliberately descriptive: fitting a trajectory does not establish a
mechanism. Matched-control effect extraction (the control-normalized
comparison between treated and control reactor fits) lives in
``batch_effects.py`` so there is exactly one definition of "effect" used
across the codebase; this module only produces the per-reactor fits that
``batch_effects.extract_matched_control_effects`` consumes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import curve_fit

ModelName = Literal["modified_gompertz", "first_order", "logistic"]


@dataclass(frozen=True)
class TrajectoryFit:
    reactor_id: str
    model: ModelName
    potential: float
    max_rate: float
    lag_days: float
    t50_days: float
    t90_days: float
    rmse: float
    aicc: float
    n_observations: int
    converged: bool = True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def modified_gompertz(
    time_days: ArrayLike, potential: float, max_rate: float, lag_days: float
) -> NDArray[np.float64]:
    time = np.asarray(time_days, dtype=float)
    exponent = (np.e * max_rate / potential) * (lag_days - time) + 1.0
    return potential * np.exp(-np.exp(np.clip(exponent, -50.0, 50.0)))


def first_order(
    time_days: ArrayLike,
    potential: float,
    rate_constant: float,
) -> NDArray[np.float64]:
    time = np.asarray(time_days, dtype=float)
    return potential * (1.0 - np.exp(-rate_constant * np.clip(time, 0.0, None)))


def logistic(
    time_days: ArrayLike,
    potential: float,
    rate_constant: float,
    midpoint_days: float,
) -> NDArray[np.float64]:
    time = np.asarray(time_days, dtype=float)
    return potential / (
        1.0
        + np.exp(
            np.clip(-rate_constant * (time - midpoint_days), -50, 50)
        )
    )


def _aicc(observed: np.ndarray, predicted: np.ndarray, n_parameters: int) -> float:
    n = observed.size
    rss = float(np.sum((observed - predicted) ** 2))
    rss = max(rss, np.finfo(float).tiny)
    aic = n * np.log(rss / n) + 2 * n_parameters
    if n <= n_parameters + 1:
        return float("inf")
    return float(aic + (2 * n_parameters * (n_parameters + 1)) / (n - n_parameters - 1))


def _crossing_time(
    fn: Callable[..., NDArray[np.float64]],
    params: tuple[float, ...],
    fraction: float,
    max_time: float,
) -> float:
    potential = params[0]
    target = fraction * potential
    grid = np.linspace(0.0, max(max_time * 3.0, 30.0), 4000)
    values = fn(grid, *params)
    reached = np.flatnonzero(values >= target)
    return float(grid[reached[0]]) if reached.size else float("nan")


def _fit_one_model(
    time: np.ndarray,
    methane: np.ndarray,
    model: ModelName,
) -> tuple[tuple[float, ...], np.ndarray]:
    max_y = max(float(np.nanmax(methane)), 1.0)
    max_t = max(float(np.nanmax(time)), 1.0)

    if model == "modified_gompertz":
        fn = modified_gompertz
        p0 = (
            max_y * 1.05,
            max(max_y / max_t, 0.1),
            max(float(np.nanmin(time)), 0.0),
        )
        bounds = (
            (1e-6, 1e-6, 0.0),
            (max_y * 10.0 + 1.0, max_y * 10.0 + 1.0, max_t * 2.0 + 10.0),
        )
    elif model == "first_order":
        fn = first_order
        p0 = (max_y * 1.05, 0.15)
        bounds = ((1e-6, 1e-8), (max_y * 10.0 + 1.0, 10.0))
    elif model == "logistic":
        fn = logistic
        p0 = (max_y * 1.05, 0.3, max_t / 2.0)
        bounds = (
            (1e-6, 1e-8, 0.0),
            (max_y * 10.0 + 1.0, 10.0, max_t * 3.0 + 10.0),
        )
    else:
        raise ValueError(f"Unknown trajectory model: {model}")

    params, _ = curve_fit(fn, time, methane, p0=p0, bounds=bounds, maxfev=20000)
    return tuple(float(value) for value in params), fn(time, *params)


def fit_reactor_trajectory(
    time_days: ArrayLike,
    methane: ArrayLike,
    reactor_id: str = "reactor",
    models: tuple[ModelName, ...] = (
        "modified_gompertz",
        "first_order",
        "logistic",
    ),
) -> list[TrajectoryFit]:
    """Fit multiple candidate kinetic curves to one reactor trajectory."""
    time = np.asarray(time_days, dtype=float)
    response = np.asarray(methane, dtype=float)
    valid = np.isfinite(time) & np.isfinite(response)
    time = time[valid]
    response = response[valid]
    order = np.argsort(time)
    time = time[order]
    response = response[order]

    if time.size < 4:
        raise ValueError("At least four finite time points are required for trajectory fitting")
    if np.any(time < 0) or np.any(response < 0):
        raise ValueError("Time and cumulative methane must be non-negative")
    if np.unique(time).size != time.size:
        raise ValueError("Time points must be unique within one reactor trajectory")

    fits: list[TrajectoryFit] = []
    for model in models:
        try:
            params, predicted = _fit_one_model(time, response, model)
        except (RuntimeError, ValueError, FloatingPointError):
            continue

        potential = params[0]
        if model == "modified_gompertz":
            max_rate = params[1]
            lag = params[2]
            fn: Callable[..., NDArray[np.float64]] = modified_gompertz
        elif model == "first_order":
            max_rate = potential * params[1]
            lag = 0.0
            fn = first_order
        else:
            max_rate = potential * params[1] / 4.0
            lag = max(params[2] - 2.0 / params[1], 0.0)
            fn = logistic

        rmse = float(np.sqrt(np.mean((response - predicted) ** 2)))
        t50 = _crossing_time(fn, params, 0.5, float(time.max()))
        t90 = _crossing_time(fn, params, 0.9, float(time.max()))
        fits.append(
            TrajectoryFit(
                reactor_id=str(reactor_id),
                model=model,
                potential=float(potential),
                max_rate=float(max_rate),
                lag_days=float(lag),
                t50_days=t50,
                t90_days=t90,
                rmse=rmse,
                aicc=_aicc(response, predicted, len(params)),
                n_observations=int(time.size),
            )
        )

    if not fits:
        raise RuntimeError("No candidate trajectory model converged")
    return sorted(fits, key=lambda fit: (fit.aicc, fit.rmse))


def fit_batch_frame(
    frame: pd.DataFrame,
    time_col: str = "time_days",
    response_col: str = "methane_ml_g_vs",
    reactor_col: str = "reactor_id",
) -> pd.DataFrame:
    """Fit and rank trajectory models independently for every reactor."""
    required = {reactor_col, time_col, response_col}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")

    rows: list[dict[str, object]] = []
    for reactor_id, group in frame.groupby(reactor_col, sort=True):
        fits = fit_reactor_trajectory(
            group[time_col],
            group[response_col],
            str(reactor_id),
        )
        for rank, fit in enumerate(fits, start=1):
            row = fit.to_dict()
            row["model_rank"] = rank
            row["selected"] = rank == 1
            rows.append(row)
    return pd.DataFrame(rows)
