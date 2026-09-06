"""Kinetic model for exploratory biochar/BMP studies.

The response layer is a testable hypothesis, not a validated universal law.
It combines a modified Gompertz curve with smooth dose and temperature terms.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray


@dataclass(frozen=True)
class BatchCondition:
    """Operating conditions for one batch methane-potential experiment."""

    dose_g_l: float
    temperature_c: float


@dataclass(frozen=True)
class KineticParameters:
    """Global parameters shared by a collection of batch experiments."""

    potential_0: float = 300.0
    rate_0: float = 18.0
    lag_days: float = 2.0
    potential_linear: float = 0.20
    potential_quadratic: float = -0.035
    rate_linear: float = 0.25
    rate_quadratic: float = -0.045
    q10: float = 1.8


def effective_kinetics(
    condition: BatchCondition, parameters: KineticParameters
) -> tuple[float, float]:
    """Return methane potential and maximum production rate for a condition."""

    if condition.dose_g_l < 0:
        raise ValueError("Biochar dose cannot be negative")
    if parameters.potential_0 <= 0 or parameters.rate_0 <= 0 or parameters.q10 <= 0:
        raise ValueError("Baseline kinetics and Q10 must be positive")

    transformed_dose = np.log1p(condition.dose_g_l)
    potential_factor = np.exp(
        parameters.potential_linear * transformed_dose
        + parameters.potential_quadratic * transformed_dose**2
    )
    rate_factor = np.exp(
        parameters.rate_linear * transformed_dose
        + parameters.rate_quadratic * transformed_dose**2
    )
    temperature_factor = parameters.q10 ** ((condition.temperature_c - 37.0) / 10.0)
    return (
        float(parameters.potential_0 * potential_factor),
        float(parameters.rate_0 * rate_factor * temperature_factor),
    )


def cumulative_methane(
    time_days: ArrayLike,
    condition: BatchCondition,
    parameters: KineticParameters,
) -> NDArray[np.float64]:
    """Calculate cumulative methane using the modified Gompertz equation."""

    time = np.asarray(time_days, dtype=float)
    potential, rate = effective_kinetics(condition, parameters)
    exponent = (np.e * rate / potential) * (parameters.lag_days - time) + 1.0
    return potential * np.exp(-np.exp(np.clip(exponent, -50.0, 50.0)))

