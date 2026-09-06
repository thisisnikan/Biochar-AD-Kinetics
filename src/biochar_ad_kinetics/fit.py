"""Global parameter estimation and batch-aware bootstrap uncertainty."""

from dataclasses import asdict

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from .data import validate_dataset
from .model import BatchCondition, KineticParameters, cumulative_methane

PARAMETER_NAMES = tuple(asdict(KineticParameters()).keys())
LOWER = np.array([50, 1, 0, -1, -1, -1, -1, 1.01], dtype=float)
UPPER = np.array([1000, 100, 15, 1, 0.5, 1, 0.5, 4], dtype=float)

# Above this absolute pairwise correlation, two parameters are considered
# practically confounded: the data cannot tell their individual values apart,
# only some combination of them (Bates & Watts 1988, ch. 3 on curvature and
# near-collinearity in nonlinear least squares).
IDENTIFIABILITY_CORRELATION_THRESHOLD = 0.95


def _unpack(values: np.ndarray) -> KineticParameters:
    return KineticParameters(**dict(zip(PARAMETER_NAMES, values, strict=True)))


def predict_frame(frame: pd.DataFrame, parameters: KineticParameters) -> np.ndarray:
    """Predict each observation while preserving input row order."""

    prediction = np.empty(len(frame), dtype=float)
    for (_, dose, temperature), indices in frame.groupby(
        ["batch_id", "dose_g_l", "temperature_c"], sort=False
    ).groups.items():
        positions = frame.index.get_indexer(indices)
        subset = frame.loc[indices]
        prediction[positions] = cumulative_methane(
            subset["time_days"].to_numpy(),
            BatchCondition(float(dose), float(temperature)),
            parameters,
        )
    return prediction


def _numerical_jacobian(
    residual_fn, x: np.ndarray, lower: np.ndarray, upper: np.ndarray, relative_step: float = 1e-6
) -> np.ndarray:
    """Central-difference Jacobian of the raw ``residual_fn`` at ``x``.

    ``least_squares(..., loss="soft_l1")`` returns ``solution.jac`` scaled by
    the robust loss's derivative, while ``solution.fun`` stays the raw,
    unweighted residual. Pairing that reweighted Jacobian with the raw
    residual variance (as an ordinary least-squares covariance formula
    expects) is inconsistent. Recomputing an unweighted Jacobian here keeps
    the identifiability diagnostic paired with the same raw residuals used
    for the residual-variance estimate.
    """
    x = np.asarray(x, dtype=float)
    baseline = residual_fn(x)
    jacobian = np.empty((baseline.size, x.size), dtype=float)
    for i in range(x.size):
        step = relative_step * max(abs(x[i]), 1.0)
        x_plus = x.copy()
        x_minus = x.copy()
        x_plus[i] = min(x[i] + step, upper[i])
        x_minus[i] = max(x[i] - step, lower[i])
        span = x_plus[i] - x_minus[i]
        if span <= 0:
            jacobian[:, i] = 0.0
            continue
        jacobian[:, i] = (residual_fn(x_plus) - residual_fn(x_minus)) / span
    return jacobian


def parameter_covariance(jacobian: np.ndarray, residuals: np.ndarray, n_observations: int) -> np.ndarray:
    """Approximate the parameter covariance matrix from a Jacobian and its residuals.

    Uses the standard nonlinear-least-squares approximation
    ``cov = residual_variance * pinv(J^T J)`` (Bates & Watts 1988). A
    pseudo-inverse is used because near-confounded parameters make ``J^T J``
    close to singular; that near-singularity is itself the identifiability
    signal callers should read from the resulting correlations, not an error
    to hide. ``jacobian`` and ``residuals`` must come from the same
    (unweighted) residual function.
    """

    n_params = jacobian.shape[1]
    degrees_of_freedom = max(n_observations - n_params, 1)
    residual_variance = float(np.sum(residuals**2)) / degrees_of_freedom
    return residual_variance * np.linalg.pinv(jacobian.T @ jacobian)


def parameter_correlation_matrix(
    covariance: np.ndarray, names: tuple[str, ...] = PARAMETER_NAMES
) -> pd.DataFrame:
    """Turn a parameter covariance matrix into a labelled correlation matrix.

    ``names`` defaults to all eight kinetic parameters, but a nested response
    form (``constant``/``log_linear``) only optimizes a subset of them —
    pass the active parameter names so the matrix labels match its shape.
    """

    standard_error = np.sqrt(np.clip(np.diag(covariance), 0, None))
    outer = np.outer(standard_error, standard_error)
    with np.errstate(invalid="ignore", divide="ignore"):
        correlation = np.where(outer > 0, covariance / outer, np.nan)
    return pd.DataFrame(correlation, index=list(names), columns=list(names))


def _identifiability_metrics(
    jacobian: np.ndarray,
    residuals: np.ndarray,
    n_observations: int,
    parameter_names: tuple[str, ...],
) -> dict[str, float]:
    covariance = parameter_covariance(jacobian, residuals, n_observations)
    correlation = parameter_correlation_matrix(covariance, names=parameter_names).to_numpy()
    n_params = correlation.shape[0]
    off_diagonal = correlation[~np.eye(n_params, dtype=bool)]
    off_diagonal = off_diagonal[np.isfinite(off_diagonal)]
    max_correlation = float(np.max(np.abs(off_diagonal))) if off_diagonal.size else float("nan")
    gram = jacobian.T @ jacobian
    condition_number = float(np.linalg.cond(gram)) if np.all(np.isfinite(gram)) else float("inf")
    return {
        "max_parameter_correlation": max_correlation,
        "parameter_gram_condition_number": condition_number,
    }


def fit_global(
    frame: pd.DataFrame, response: str = "log_quadratic"
) -> tuple[KineticParameters, dict[str, float]]:
    """Fit all batch conditions simultaneously and return diagnostic metrics.

    ``response`` selects how many of the eight kinetic parameters are free:
    ``"constant"`` (dose/temperature-invariant, 3 parameters), ``"log_linear"``
    (dose enters linearly in log space, no Q10 curvature term) or the full
    ``"log_quadratic"`` model. A single training temperature also deactivates
    Q10, since it cannot be identified separately from ``rate_0`` without a
    second temperature to anchor it.

    ``max_parameter_correlation`` and ``parameter_gram_condition_number`` in
    the returned metrics are practical-identifiability diagnostics computed
    over whichever parameters were actually free for this fit, not goodness
    of fit: a high correlation (beyond ``IDENTIFIABILITY_CORRELATION_THRESHOLD``)
    or condition number means the data cannot separate two or more of them,
    even when RMSE/R-squared look good.
    """

    frame = frame.reset_index(drop=True).copy()
    validate_dataset(frame)
    observed = frame["methane_ml_g_vs"].to_numpy(dtype=float)

    if response not in {"constant", "log_linear", "log_quadratic"}:
        raise ValueError(f"Unknown response model: {response}")
    initial = np.array(list(asdict(KineticParameters()).values()), dtype=float)
    active = np.ones(len(initial), dtype=bool)
    if response in {"constant", "log_linear"}:
        active[[4, 6]] = False
        initial[[4, 6]] = 0
    if response == "constant":
        active[[3, 5, 7]] = False
        initial[[3, 5]] = 0
        initial[7] = 1
    elif frame["temperature_c"].nunique() == 1:
        # At one temperature Q10 cannot be identified separately from rate_0.
        active[7] = False
        initial[7] = 1

    def unpack_active(values: np.ndarray) -> KineticParameters:
        full = initial.copy()
        full[active] = values
        return _unpack(full)

    def residual(values: np.ndarray) -> np.ndarray:
        return predict_frame(frame, unpack_active(values)) - observed

    solution = least_squares(
        residual, initial[active], bounds=(LOWER[active], UPPER[active]), loss="soft_l1"
    )
    if not solution.success:
        raise RuntimeError(f"Kinetic fit did not converge: {solution.message}")
    parameters = unpack_active(solution.x)
    fitted = predict_frame(frame, parameters)
    errors = observed - fitted
    ss_total = float(np.sum((observed - observed.mean()) ** 2))
    metrics = {
        "rmse_ml_g_vs": float(np.sqrt(np.mean(errors**2))),
        "mae_ml_g_vs": float(np.mean(np.abs(errors))),
        "r_squared": float(1 - np.sum(errors**2) / ss_total),
        "n_observations": float(len(frame)),
        "n_parameters": float(active.sum()),
    }
    active_names = tuple(name for name, flag in zip(PARAMETER_NAMES, active, strict=True) if flag)
    jacobian = _numerical_jacobian(residual, solution.x, LOWER[active], UPPER[active])
    metrics.update(_identifiability_metrics(jacobian, solution.fun, len(observed), active_names))
    return parameters, metrics


def bootstrap_parameters(
    frame: pd.DataFrame, iterations: int = 100, seed: int = 27
) -> pd.DataFrame:
    """Estimate uncertainty by resampling residuals independently within batches."""

    if iterations < 1:
        raise ValueError("Bootstrap iterations must be positive")
    frame = frame.reset_index(drop=True).copy()
    baseline, _ = fit_global(frame)
    fitted = predict_frame(frame, baseline)
    residuals = frame["methane_ml_g_vs"].to_numpy() - fitted
    rng = np.random.default_rng(seed)
    samples: list[dict[str, float]] = []
    groups = frame.groupby("batch_id").indices
    for _ in range(iterations):
        simulated = frame.copy()
        response = fitted.copy()
        for indices in groups.values():
            response[indices] += rng.choice(residuals[indices], size=len(indices), replace=True)
        simulated["methane_ml_g_vs"] = np.clip(response, 0, None)
        try:
            estimate, _ = fit_global(simulated)
            samples.append(asdict(estimate))
        except (ValueError, RuntimeError):
            continue
    return pd.DataFrame(samples)

