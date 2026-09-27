"""Small-sample effect estimates for pre-registered, unit-level contrasts.

The experimental unit (for example a bottle) is the only thing counted as a
replicate. Repeated batches and time points must be summarised to one value per
unit before these functions are called.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats


def welch_log_ratio(treatment: np.ndarray, control: np.ndarray, level: float = 0.95) -> dict:
    """Difference of means of per-unit log values with a Welch t interval.

    With per-unit summaries on the log scale the difference is a log response
    ratio of geometric means. Returns NaN interval fields if either arm has
    fewer than two units; that case is ``not_evaluable`` under the decision rule.
    """

    t = np.asarray(treatment, dtype=float)
    c = np.asarray(control, dtype=float)
    estimate = float(t.mean() - c.mean()) if t.size and c.size else float("nan")
    out = {
        "n_treatment_units": int(t.size),
        "n_control_units": int(c.size),
        "log_response_ratio": estimate,
        "welch_df": float("nan"),
        "se": float("nan"),
        "ci_low": float("nan"),
        "ci_high": float("nan"),
    }
    if t.size < 2 or c.size < 2:
        return out
    vt, vc = t.var(ddof=1) / t.size, c.var(ddof=1) / c.size
    se = float(np.sqrt(vt + vc))
    if se == 0:
        return {**out, "se": 0.0, "ci_low": estimate, "ci_high": estimate, "welch_df": np.inf}
    df = float((vt + vc) ** 2 / (vt**2 / (t.size - 1) + vc**2 / (c.size - 1)))
    q = float(stats.t.ppf(0.5 + level / 2, df))
    return {
        **out,
        "welch_df": df,
        "se": se,
        "ci_low": estimate - q * se,
        "ci_high": estimate + q * se,
    }


def exact_permutation_p(treatment: np.ndarray, control: np.ndarray) -> dict:
    """Two-sided exact permutation p-value for a difference in means.

    Enumerates every relabelling of the pooled units. ``p_floor`` is the smallest
    p-value the design can produce, which bounds what any result could show.
    """

    t = np.asarray(treatment, dtype=float)
    c = np.asarray(control, dtype=float)
    pooled = np.concatenate([t, c])
    n = pooled.size
    observed = abs(t.mean() - c.mean())
    count = 0
    total = 0
    for idx in combinations(range(n), t.size):
        mask = np.zeros(n, dtype=bool)
        mask[list(idx)] = True
        diff = abs(pooled[mask].mean() - pooled[~mask].mean())
        total += 1
        if diff >= observed - 1e-12:
            count += 1
    # With equal arm sizes every relabelling has a mirror image with the same
    # absolute difference, so at least two relabellings reach the observed value.
    floor = (2 if t.size == c.size else 1) / total
    return {"permutation_p": count / total, "permutation_p_floor": floor, "relabellings": total}


def verdict(ci_low: float, ci_high: float, n_treatment: int, n_control: int) -> str:
    if n_treatment < 2 or n_control < 2 or not np.isfinite(ci_low):
        return "not_evaluable"
    if ci_low > 0:
        return "increase"
    if ci_high < 0:
        return "decrease"
    return "inconclusive"


def balanced_variance_decomposition(
    frame: pd.DataFrame, value: str, batch: str, arm: str, unit: str
) -> dict:
    """Orthogonal sum-of-squares split for a balanced unit x batch design.

    Components: batch (shared across all units, e.g. substrate lot), arm,
    unit-within-arm (persistent bottle differences) and residual
    (unit-by-batch). Raises if the design is not balanced, because the split is
    only orthogonal when every unit is observed in every batch.
    """

    counts = frame.groupby([unit, batch]).size()
    batches = frame[batch].nunique()
    if (counts != 1).any() or (frame.groupby(unit)[batch].nunique() != batches).any():
        raise ValueError("Variance decomposition requires one value per unit and batch")
    y = frame[value].to_numpy(float)
    grand = y.mean()
    total = float(((y - grand) ** 2).sum())
    batch_means = frame.groupby(batch)[value].transform("mean")
    unit_means = frame.groupby(unit)[value].transform("mean")
    arm_means = frame.groupby(arm)[value].transform("mean")
    ss_batch = float(((batch_means - grand) ** 2).sum())
    ss_arm = float(((arm_means - grand) ** 2).sum())
    ss_unit = float(((unit_means - arm_means) ** 2).sum())
    ss_resid = float(((y - unit_means - batch_means + grand) ** 2).sum())
    return {
        "total_ss": total,
        "batch_share": ss_batch / total,
        "arm_share": ss_arm / total,
        "unit_within_arm_share": ss_unit / total,
        "residual_share": ss_resid / total,
        "units": int(frame[unit].nunique()),
        "batches": int(batches),
    }
