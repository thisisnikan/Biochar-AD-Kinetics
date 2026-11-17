"""Fast design search for biochar dose-response experiments (simulation only).

Implements the surrogate in ``data/validation/dose_design_v1.json``: each reactor's
methane potential is ``ln P = f(x) + e`` with ``x = ln(1 + dose)``. Constant, linear
and quadratic forms in ``x`` are compared by whole-dose-held-out RMSE of ``ln P``
and the simplest form is kept unless a more complex one is better by more than
the Stage A parsimony margin. No experimental data are used.
"""

from __future__ import annotations

import math

import numpy as np

FORMS = ("constant", "linear", "quadratic")
PARSIMONY_MARGIN = 0.10


def dose_grid(n_doses: int, highest: float, spacing: str) -> np.ndarray:
    """Doses including zero, evenly spaced in ``ln(1 + d)`` or in ``d``."""
    if n_doses < 4 or highest <= 0:
        raise ValueError("need at least four doses and a positive highest dose")
    if spacing == "log":
        return np.expm1(np.linspace(0.0, math.log1p(highest), n_doses))
    if spacing == "linear":
        return np.linspace(0.0, highest, n_doses)
    raise ValueError(f"unknown spacing: {spacing}")


def truth_curve(truth: str, gain: float):
    """Return ``f(x)`` (change in ln P from zero dose) for a named truth."""
    h = math.log1p(gain)
    if truth == "constant":
        return lambda x: np.zeros_like(x)
    if truth == "monotone":
        slope = h / math.log1p(8.0)
        return lambda x: slope * x
    if truth.startswith("optimum_"):
        x_star = math.log1p(float(truth.split("_", 1)[1]))
        return lambda x: h * (2 * x / x_star - (x / x_star) ** 2)
    raise ValueError(f"unknown truth: {truth}")


def correct_form(truth: str) -> str:
    return {"constant": "constant", "monotone": "linear"}.get(truth, "quadratic")


def _held_out_rows(x: np.ndarray) -> dict[str, np.ndarray]:
    """For each form, a (k, k) matrix whose row j maps dose means to the
    prediction at dose j from a fit that excludes dose j."""
    k = len(x)
    rows = {}
    for degree, form in enumerate(FORMS):
        weights = np.zeros((k, k))
        for j in range(k):
            train = np.delete(np.arange(k), j)
            design = np.vander(x[train], degree + 1, increasing=True)
            target = np.vander(x[[j]], degree + 1, increasing=True)
            weights[j, train] = (target @ np.linalg.pinv(design))[0]
        rows[form] = weights
    return rows


def held_out_scores(values: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Mean whole-dose-held-out RMSE per form.

    ``values`` has shape (simulations, doses, replicates). With equal replicates,
    least squares on all reactors equals least squares on dose means.
    """
    if values.ndim != 3 or values.shape[1] != len(x):
        raise ValueError("values must have shape (simulations, doses, replicates)")
    if len(x) - 1 < 3:
        raise ValueError("a quadratic held-out fit needs at least three training doses")
    means = values.mean(axis=2)
    out = np.empty((values.shape[0], len(FORMS)))
    for i, form in enumerate(FORMS):
        prediction = means @ _held_out_rows(x)[form].T
        rmse = np.sqrt(((values - prediction[:, :, None]) ** 2).mean(axis=2))
        out[:, i] = rmse.mean(axis=1)
    return out


def select_forms(scores: np.ndarray, margin: float = PARSIMONY_MARGIN) -> np.ndarray:
    """Index of the chosen form per simulation (simplest unless clearly better)."""
    chosen = np.zeros(scores.shape[0], dtype=int)
    for i in range(1, scores.shape[1]):
        better = scores[:, i] < (1 - margin) * scores[np.arange(len(chosen)), chosen]
        chosen = np.where(better, i, chosen)
    return chosen


def share_selected(
    doses, replicates: int, truth: str, gain: float, sd: float, n: int, rng
) -> dict[str, float]:
    """Simulate one scenario and return the share selecting each form."""
    x = np.log1p(np.asarray(doses, dtype=float))
    mean = truth_curve(truth, gain)(x)
    values = mean[None, :, None] + rng.normal(0.0, sd, (n, len(x), replicates))
    chosen = select_forms(held_out_scores(values, x))
    return {form: float((chosen == i).mean()) for i, form in enumerate(FORMS)}
