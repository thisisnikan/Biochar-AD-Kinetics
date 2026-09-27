"""Structural checks for cumulative-methane curve families.

Two questions are kept separate:

1. Structure: can a curve family describe a complete long cycle at all?
   (full-cycle fit, in-sample RMSE and AICc)
2. Identifiability from short data: fitted only to the first ``t_cut`` days, does
   the family predict the rest of the cycle? (out-of-time extrapolation error)

A family can pass (1) and fail (2); that means the data are too short, not that
the equation is wrong. Failing (1) is evidence against the structure itself.
Multi-start least squares with fixed, data-scaled starting points keeps results
deterministic.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import least_squares

from .analysis import information_criteria

Array = NDArray[np.float64]


def first_order(t: Array, p: float, k: float) -> Array:
    return p * (1 - np.exp(-k * t))


def modified_gompertz(t: Array, p: float, rm: float, lag: float) -> Array:
    return p * np.exp(-np.exp(np.clip((np.e * rm / p) * (lag - t) + 1.0, -50.0, 50.0)))


def logistic(t: Array, p: float, rm: float, lag: float) -> Array:
    return p / (1 + np.exp(np.clip((4 * rm / p) * (lag - t) + 2.0, -50.0, 50.0)))


def two_pool_first_order(t: Array, pf: float, kf: float, ps: float, ratio: float) -> Array:
    """Fast plus slow first-order pools; ``ratio`` = k_slow / k_fast in (0, 1)."""

    return pf * (1 - np.exp(-kf * t)) + ps * (1 - np.exp(-kf * ratio * t))


def gompertz_plus_linear(t: Array, p: float, rm: float, lag: float, b: float) -> Array:
    """Gompertz pool plus constant background production (e.g. carried-over solids)."""

    return modified_gompertz(t, p, rm, lag) + b * t


@dataclass(frozen=True)
class CurveFamily:
    name: str
    function: Callable[..., Array]
    lower: tuple[float, ...]
    upper: tuple[float, ...]
    starts: Callable[[float], list[tuple[float, ...]]]
    description: str


FAMILIES: dict[str, CurveFamily] = {
    f.name: f
    for f in (
        CurveFamily(
            "first_order",
            first_order,
            (1.0, 1e-4),
            (3000.0, 20.0),
            lambda y: [(1.2 * y, 0.3), (2 * y, 0.05)],
            "single first-order pool",
        ),
        CurveFamily(
            "modified_gompertz",
            modified_gompertz,
            (1.0, 1e-3, 0.0),
            (3000.0, 3000.0, 21.0),
            lambda y: [(1.2 * y, y / 3, 0.2), (2 * y, y / 6, 0.0)],
            "sigmoidal single pool (repository baseline)",
        ),
        CurveFamily(
            "logistic",
            logistic,
            (1.0, 1e-3, 0.0),
            (3000.0, 3000.0, 21.0),
            lambda y: [(1.2 * y, y / 3, 0.2), (2 * y, y / 6, 0.0)],
            "symmetric sigmoidal single pool",
        ),
        CurveFamily(
            "two_pool_first_order",
            two_pool_first_order,
            (0.0, 1e-3, 0.0, 1e-4),
            (3000.0, 20.0, 3000.0, 0.999),
            lambda y: [(0.7 * y, 0.8, 0.8 * y, 0.1), (0.5 * y, 0.4, 1.5 * y, 0.05)],
            "fast and slow first-order pools",
        ),
        CurveFamily(
            "gompertz_plus_linear",
            gompertz_plus_linear,
            (1.0, 1e-3, 0.0, 0.0),
            (3000.0, 3000.0, 21.0, 200.0),
            lambda y: [(1.0 * y, y / 3, 0.2, y / 50), (0.8 * y, y / 4, 0.0, y / 20)],
            "sigmoidal pool plus constant background rate",
        ),
    )
}


def fit_family(family: CurveFamily, time: Array, observed: Array) -> dict:
    """Multi-start bounded least squares; returns the best solution found."""

    time = np.asarray(time, dtype=float)
    observed = np.asarray(observed, dtype=float)
    scale = max(float(np.nanmax(observed)), 1.0)
    lower = np.asarray(family.lower, dtype=float)
    upper = np.asarray(family.upper, dtype=float)
    best = None
    for start in family.starts(scale):
        x0 = np.clip(np.asarray(start, dtype=float), lower + 1e-9, upper - 1e-9)
        sol = least_squares(
            lambda v: family.function(time, *v) - observed,
            x0,
            bounds=(lower, upper),
            xtol=1e-12,
            ftol=1e-12,
            gtol=1e-12,
            max_nfev=20000,
        )
        if best is None or sol.cost < best.cost:
            best = sol
    predicted = family.function(time, *best.x)
    at_bound = bool(
        np.any(np.isclose(best.x, upper, rtol=1e-6) | np.isclose(best.x, lower, atol=1e-9))
    )
    return {
        "parameters": best.x,
        "predicted": predicted,
        "rmse": float(np.sqrt(np.mean((observed - predicted) ** 2))),
        "at_bound": at_bound,
        "converged": bool(best.success),
        "n_parameters": len(best.x),
    }


def evaluate_cycle(time: Array, observed: Array, t_cut: float) -> list[dict]:
    """Full-cycle fit and first-``t_cut``-days extrapolation for every family."""

    time = np.asarray(time, dtype=float)
    observed = np.asarray(observed, dtype=float)
    early = time <= t_cut + 1e-9
    late = ~early
    if early.sum() < 6 or late.sum() < 2:
        raise ValueError("Cycle needs at least 6 points before and 2 after the cut")
    rows = []
    for family in FAMILIES.values():
        full = fit_family(family, time, observed)
        ic = information_criteria(observed, full["predicted"], full["n_parameters"])
        short = fit_family(family, time[early], observed[early])
        extrap = family.function(time[late], *short["parameters"])
        final_obs = float(observed[late][-1])
        rows.append(
            {
                "family": family.name,
                "n_parameters": full["n_parameters"],
                "full_rmse": full["rmse"],
                "full_rmse_relative_to_final": full["rmse"] / final_obs
                if final_obs > 0
                else np.nan,
                "full_aicc": ic["aicc"],
                "full_at_bound": full["at_bound"],
                "cut_days": t_cut,
                "extrapolation_rmse": float(np.sqrt(np.mean((extrap - observed[late]) ** 2))),
                "final_relative_error": float((extrap[-1] - final_obs) / final_obs)
                if final_obs > 0
                else np.nan,
                "short_at_bound": short["at_bound"],
            }
        )
    return rows


def days_to_daily_increment_below(time: Array, observed: Array, fraction: float = 0.01) -> float:
    """First time at which the previous 24 h added less than ``fraction`` of the total so far.

    Returns NaN if the criterion is never met within the record.
    """

    time = np.asarray(time, dtype=float)
    observed = np.asarray(observed, dtype=float)
    for i, t in enumerate(time):
        if t < 1.0 or observed[i] <= 0:
            continue
        prior = np.nonzero(time <= t - 1.0 + 1e-9)[0]
        if prior.size == 0:
            continue
        increment = observed[i] - observed[prior[-1]]
        if increment / observed[i] < fraction:
            return float(t)
    return float("nan")
