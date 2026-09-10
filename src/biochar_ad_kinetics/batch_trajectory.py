"""Batch trajectory benchmarking and matched-control kinetic effects.

This module complements the global dose-response model with per-reactor fits.
It is deliberately descriptive: fitting a trajectory does not establish a
mechanism. The resulting kinetic summaries can be compared between matched
biochar and control reactors before any cross-study ML is attempted.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable, Literal

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


@dataclass(frozen=True)
class KineticEffect:
    study_id: str
    experiment_id: str
    treatment_id: str
    reactor_id: str
    control_group_id: str
    dose_g_l: float
    delta_potential: float
    delta_max_rate: float
    delta_lag: float
    delta_t50: float
    delta_t90: float
    treated_model: str
    control_model: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def modified_gompertz(
    time_days: ArrayLike, potential: float, max_rate: float, lag_days: float
) -> NDArray[np.float64]:
    time = np.asarray(time_days, dtype=float)
    exponent = (np.e * max_rate / potential) * (lag_days - time) + 1.0
    return potential * np.exp(-np.exp(np.clip(exponent, -50.0, 50.0)))


def first_order(time_days: ArrayLike, potential: float, rate_constant: float) -> NDArray[np.float64]:
    time = np.asarray(time_days, dtype=float)
    return potential * (1.0 - np.exp(-rate_constant * np.clip(time, 0.0, None)))


def logistic(
    time_days: ArrayLike, potential: float, rate_constant: float, midpoint_days: float
) -> NDArray[np.float64]:
    time = np.asarray(time_days, dtype=float)
    return potential / (1.0 + np.exp(np.clip(-rate_constant * (time - midpoint_days), -50, 50)))


def _aicc(observed: np.ndarray, predicted: np.ndarray, n_parameters: int) -> float:
    n = observed.size
    rss = float(np.sum((observed - predicted) ** 2))
    rss = max(rss, np.finfo(float).tiny)
    aic = n * np.log(rss / n) + 2 * n_parameters
    if n <= n_parameters + 1:
        return float("inf")
    return float(aic + (2 * n_parameters * (n_parameters + 1)) / (n - n_parameters - 1))


def _crossing_time(
    fn: Callable[..., NDArray[np.float64]], params: tuple[float, ...], fraction: float, max_time: float
) -> float:
    potential = params[0]
    target = fraction * potential
    grid = np.linspace(0.0, max(max_time * 3.0, 30.0), 4000)
    values = fn(grid, *params)
    reached = np.flatnonzero(values >= target)
    return float(grid[reached[0]]) if reached.size else float("nan")


def _fit_one_model(time: np.ndarray, methane: np.ndarray, model: ModelName) -> tuple[tuple[float, ...], np.ndarray]:
    max_y = max(float(np.nanmax(methane)), 1.0)
    max_t = max(float(np.nanmax(time)), 1.0)

    if model == "modified_gompertz":
        fn = modified_gompertz
        p0 = (max_y * 1.05, max(max_y / max_t, 0.1), max(float(np.nanmin(time)), 0.0))
        bounds = ((1e-6, 1e-6, 0.0), (max_y * 10.0 + 1.0, max_y * 10.0 + 1.0, max_t * 2.0 + 10.0))
    elif model == "first_order":
        fn = first_order
        p0 = (max_y * 1.05, 0.15)
        bounds = ((1e-6, 1e-8), (max_y * 10.0 + 1.0, 10.0))
    elif model == "logistic":
        fn = logistic
        p0 = (max_y * 1.05, 0.3, max_t / 2.0)
        bounds = ((1e-6, 1e-8, 0.0), (max_y * 10.0 + 1.0, 10.0, max_t * 3.0 + 10.0))
    else:
        raise ValueError(f"Unknown trajectory model: {model}")

    params, _ = curve_fit(fn, time, methane, p0=p0, bounds=bounds, maxfev=20000)
    return tuple(float(value) for value in params), fn(time, *params)


def fit_reactor_trajectory(
    time_days: ArrayLike,
    methane: ArrayLike,
    reactor_id: str = "reactor",
    models: tuple[ModelName, ...] = ("modified_gompertz", "first_order", "logistic"),
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
        fits = fit_reactor_trajectory(group[time_col], group[response_col], str(reactor_id))
        for rank, fit in enumerate(fits, start=1):
            row = fit.to_dict()
            row["model_rank"] = rank
            row["selected"] = rank == 1
            rows.append(row)
    return pd.DataFrame(rows)


def _relative(treated: float, control: float) -> float:
    if not np.isfinite(control) or abs(control) < 1e-12:
        return float("nan")
    return float((treated - control) / control)


def matched_control_effects(
    frame: pd.DataFrame,
    fits: pd.DataFrame,
    *,
    control_group_columns: tuple[str, ...] = (
        "study_id",
        "experiment_id",
        "temperature_c",
        "substrate_id",
        "inoculum_id",
    ),
) -> pd.DataFrame:
    """Compute kinetic effects relative to the mean matched control trajectory.

    Only each reactor's selected best-fit trajectory is used. Controls are
    matched within study/experiment/temperature/substrate/inoculum. This avoids
    comparing a treatment with an unrelated BMP baseline from another study.
    """
    required = {
        "reactor_id",
        "treatment_id",
        "dose_g_l",
        "is_control",
        *control_group_columns,
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing columns for matched-control effects: {', '.join(sorted(missing))}")
    if "selected" not in fits or "reactor_id" not in fits:
        raise ValueError("fits must come from fit_batch_frame and include selected/reactor_id")

    meta = frame.drop_duplicates("reactor_id").copy()
    selected = fits.loc[fits["selected"].astype(bool)].copy()
    merged = selected.merge(meta, on="reactor_id", how="left", validate="one_to_one")

    rows: list[dict[str, object]] = []
    for key, group in merged.groupby(list(control_group_columns), dropna=False, sort=True):
        controls = group.loc[group["is_control"].astype(bool)]
        treated = group.loc[~group["is_control"].astype(bool)]
        if controls.empty or treated.empty:
            continue

        baseline = controls[["potential", "max_rate", "lag_days", "t50_days", "t90_days"]].mean()
        control_models = ",".join(sorted(set(controls["model"].astype(str))))
        control_group_id = "::".join(str(value) for value in (key if isinstance(key, tuple) else (key,)))

        for _, row in treated.iterrows():
            effect = KineticEffect(
                study_id=str(row["study_id"]),
                experiment_id=str(row["experiment_id"]),
                treatment_id=str(row["treatment_id"]),
                reactor_id=str(row["reactor_id"]),
                control_group_id=control_group_id,
                dose_g_l=float(row["dose_g_l"]),
                delta_potential=_relative(float(row["potential"]), float(baseline["potential"])),
                delta_max_rate=_relative(float(row["max_rate"]), float(baseline["max_rate"])),
                delta_lag=_relative(float(baseline["lag_days"]), float(row["lag_days"])) if float(row["lag_days"]) > 0 else float("nan"),
                delta_t50=_relative(float(baseline["t50_days"]), float(row["t50_days"])),
                delta_t90=_relative(float(baseline["t90_days"]), float(row["t90_days"])),
                treated_model=str(row["model"]),
                control_model=control_models,
            )
            rows.append(effect.to_dict())
    return pd.DataFrame(rows)
