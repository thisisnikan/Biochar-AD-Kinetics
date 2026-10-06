"""Prefix-only baselines and paired, equal-bottle forecast comparisons.

Intervals resample bottles within labs, retaining every cycle of a bottle.
They are conditional descriptive intervals: shared batch shocks and source-unit
uncertainty are not modelled. No method selection or external validation occurs.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def prefix_baselines(time, observed, cut_days: float, target_day: float) -> dict[str, float]:
    """Predict from the observed prefix only; target day is a supplied horizon.

    Persistence keeps the last value. Recent-rate extrapolation uses OLS on the
    final three prefix readings, clips a negative rate to zero, and extends from
    the last observed reading. Future values never set slopes or clipping bounds.
    """
    t = np.asarray(time, dtype=float)
    y = np.asarray(observed, dtype=float)
    if t.ndim != 1 or y.shape != t.shape:
        raise ValueError("time and observed must be aligned one-dimensional arrays")
    if not np.isfinite(cut_days) or not np.isfinite(target_day) or target_day <= cut_days:
        raise ValueError("target_day must be finite and later than finite cut_days")
    # Restrict first: held-out outcomes, including missing ones, are never inspected.
    prefix = t <= cut_days + 1e-9
    pt, py = t[prefix], y[prefix]
    if len(pt) < 3 or not np.isfinite(pt).all() or not np.isfinite(py).all():
        raise ValueError("at least three finite prefix readings are required")
    if not np.isfinite(t).all() or np.any(np.diff(t) <= 0) or pt[0] < 0:
        raise ValueError("time must be finite, nonnegative and strictly increasing")
    recent_t, recent_y = pt[-3:], py[-3:]
    centered = recent_t - recent_t.mean()
    slope = max(float(centered @ (recent_y - recent_y.mean()) / (centered @ centered)), 0.0)
    return {
        "persistence": float(py[-1]),
        "recent_rate": float(py[-1] + slope * (target_day - pt[-1])),
    }


def paired_bottle_comparison(
    scores: pd.DataFrame, reference: str = "persistence", *, draws: int = 5000, seed: int = 20261006
) -> pd.DataFrame:
    """Equal-bottle mean absolute relative error and paired bootstrap differences.

    Input is one finite signed relative error per lab/bottle/batch/method/cut.
    Missing paired methods and duplicate identities fail instead of silently
    comparing different populations. Negative differences favour the method.
    """
    keys = ["lab", "bottle_id", "batch_id", "cut_days"]
    required = keys + ["method", "relative_error"]
    if any(c not in scores for c in required) or scores.empty:
        raise ValueError("nonempty scores with all identity and error columns required")
    if scores[required].isna().any().any() or not np.isfinite(scores["relative_error"]).all():
        raise ValueError("identities and errors must be present and errors finite")
    if scores.duplicated(keys + ["method"]).any():
        raise ValueError("duplicate cycle/method scores")
    if draws < 100:
        raise ValueError("at least 100 bootstrap draws required")
    rng = np.random.default_rng(seed)
    rows = []
    for cut, part in scores.groupby("cut_days", sort=True):
        wide = part.pivot(index=keys, columns="method", values="relative_error").abs()
        if reference not in wide or wide.isna().any().any():
            raise ValueError("all methods must have the same paired cycles including reference")
        bottles = wide.groupby(level=["lab", "bottle_id"], sort=True).mean()
        labs = bottles.index.get_level_values("lab")
        positions = [np.flatnonzero(labs == lab) for lab in sorted(set(labs))]
        if any(len(p) < 2 for p in positions):
            raise ValueError("at least two bottles per lab required for uncertainty")
        # Every method uses the identical resampled bottles for paired differences.
        resamples = np.concatenate(
            [rng.choice(p, size=(draws, len(p)), replace=True) for p in positions], axis=1
        )
        reference_values = bottles[reference].to_numpy()
        for method in bottles.columns:
            values = bottles[method].to_numpy()
            delta = values - reference_values
            interval = np.quantile(delta[resamples].mean(axis=1), [0.025, 0.975])
            rows.append(
                {
                    "cut_days": float(cut),
                    "method": method,
                    "reference": reference,
                    "cycles": len(wide),
                    "bottles": len(bottles),
                    "equal_bottle_mean_abs_relative_error": float(values.mean()),
                    "paired_difference": float(delta.mean()),
                    "difference_ci_low": float(interval[0]),
                    "difference_ci_high": float(interval[1]),
                    "bottle_win_fraction": float((delta < 0).mean()),
                }
            )
    return pd.DataFrame(rows)
