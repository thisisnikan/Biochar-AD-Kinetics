"""Design requirements implied by observed variance, for planning new experiments.

Inputs are variance components of ln(methane yield) estimated inside one study.
They describe that study's bottles and batches, not biochar-AD in general, so
every requirement is reported per scenario with a chi-square interval for the
bottle-level component instead of a single number.
"""

from __future__ import annotations

from math import comb

import numpy as np
import pandas as pd
from scipy import integrate, stats


def mean_square_components(
    frame: pd.DataFrame, value: str, batch: str, arm: str, unit: str
) -> dict[str, float]:
    """Method-of-moments components for a balanced unit-by-batch design.

    ``sigma2_unit`` is persistent between-bottle variance within an arm;
    ``sigma2_residual`` is bottle-by-batch variance. Batch variance is reported but
    cancels from within-batch arm contrasts when every arm runs in every batch.
    """

    units = frame[unit].nunique()
    arms = frame[arm].nunique()
    batches = frame[batch].nunique()
    if (frame.groupby(unit)[batch].nunique() != batches).any():
        raise ValueError("Balanced design required: every unit in every batch")
    y = frame[value].to_numpy(float)
    grand = y.mean()
    unit_mean = frame.groupby(unit)[value].transform("mean")
    batch_mean = frame.groupby(batch)[value].transform("mean")
    arm_mean = frame.groupby(arm)[value].transform("mean")
    ss_unit = float(((unit_mean - arm_mean) ** 2).sum())
    ss_resid = float(((y - unit_mean - batch_mean + grand) ** 2).sum())
    ss_batch = float(((batch_mean - grand) ** 2).sum())
    df_unit = units - arms
    df_resid = (units - 1) * (batches - 1)
    ms_unit = ss_unit / df_unit
    ms_resid = ss_resid / df_resid
    sigma2_resid = ms_resid
    sigma2_unit = max((ms_unit - ms_resid) / batches, 0.0)
    ms_batch = ss_batch / (batches - 1)
    sigma2_batch = max((ms_batch - ms_resid) / units, 0.0)
    return {
        "units": int(units),
        "arms": int(arms),
        "batches": int(batches),
        "df_unit": int(df_unit),
        "df_residual": int(df_resid),
        "ms_unit": ms_unit,
        "sigma2_unit": sigma2_unit,
        "sigma2_residual": sigma2_resid,
        "sigma2_batch": sigma2_batch,
        # Upper 95% bound for the variance of a bottle mean over the observed batches.
        "ms_unit_upper95": df_unit * ms_unit / float(stats.chi2.ppf(0.025, df_unit)),
    }


def contrast_se(sigma2_unit: float, sigma2_resid: float, bottles: int, batches: int) -> float:
    """SE of a difference of arm means of bottle-level means (equal arms)."""

    return float(np.sqrt(2 * (sigma2_unit + sigma2_resid / batches) / bottles))


# Below this noncentrality scipy's noncentral t is fast and agrees with direct
# integration to about 1e-13; above it the integral is used instead.
NCT_RELIABLE_UP_TO = 8.0


def power_two_sample(effect: float, se: float, df: int, alpha: float = 0.05) -> float:
    """Two-sided t-test power for a log-ratio ``effect`` with standard error ``se``.

    Integrates the normal tail probability over the chi-square distribution of
    the variance estimate. This equals the noncentral-t power but stays accurate
    far in the tail, where scipy's noncentral t can return NaN or differ between
    releases. With few degrees of freedom power stays below 1 even for very large
    effects, because the variance estimate can be arbitrarily large.
    """

    if df < 1 or se <= 0:
        return float("nan")
    q = float(stats.t.ppf(1 - alpha / 2, df))
    nc = abs(effect) / se
    if nc <= NCT_RELIABLE_UP_TO:
        return float(stats.nct.sf(q, df, nc) + stats.nct.cdf(-q, df, nc))

    def integrand(v: float) -> float:
        scale = q * np.sqrt(v / df)
        tail = stats.norm.sf(scale - nc) + stats.norm.cdf(-scale - nc)
        return float(stats.chi2.pdf(v, df) * tail)

    upper = float(stats.chi2.ppf(1 - 1e-14, df))
    power, _ = integrate.quad(integrand, 0.0, upper, limit=200, epsabs=1e-12, epsrel=1e-10)
    return float(min(max(power, 0.0), 1.0))


def permutation_floor(bottles_per_arm: int) -> float:
    """Smallest exact two-sided permutation p with two equal arms."""

    return 2 / comb(2 * bottles_per_arm, bottles_per_arm)


def design_table(
    sigma2_unit: float,
    sigma2_resid: float,
    effects: tuple[float, ...],
    bottles: tuple[int, ...] = (2, 3, 4, 5, 6, 8, 10),
    batches: tuple[int, ...] = (1, 3, 5, 10),
) -> pd.DataFrame:
    rows = []
    for n in bottles:
        for m in batches:
            se = contrast_se(sigma2_unit, sigma2_resid, n, m)
            row = {
                "bottles_per_arm": n,
                "batches_per_bottle": m,
                "contrast_se_log": se,
                "ci95_half_width_percent": 100
                * float(np.expm1(stats.t.ppf(0.975, 2 * n - 2) * se)),
                "permutation_p_floor": permutation_floor(n),
            }
            for effect in effects:
                row[f"power_{round(100 * effect)}pct"] = power_two_sample(
                    float(np.log1p(effect)), se, 2 * n - 2
                )
            rows.append(row)
    return pd.DataFrame(rows)


def minimum_bottles(
    sigma2_unit: float,
    sigma2_resid: float,
    effect: float,
    batches: int,
    target_power: float = 0.8,
    max_bottles: int = 200,
) -> int | None:
    """Smallest equal-arm bottle count reaching ``target_power`` and an exact
    permutation floor below 0.05; None if not reached by ``max_bottles``."""

    for n in range(2, max_bottles + 1):
        se = contrast_se(sigma2_unit, sigma2_resid, n, batches)
        if (
            power_two_sample(float(np.log1p(effect)), se, 2 * n - 2) >= target_power
            and permutation_floor(n) < 0.05
        ):
            return n
    return None
