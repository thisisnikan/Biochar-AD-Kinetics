"""Calibrated early stopping of batch methane tests.

Implements the frozen protocol ``data/validation/early_stopping_v1.json``.
From the observed prefix of a cumulative methane curve a point forecast of the
end-of-cycle yield is made, and a conformal interval is placed around it.
Repeated cycles of one bottle are not exchangeable, so calibration treats the
bottle as the unit: each calibration bottle carries total weight one, shared
equally by its (cycle, cutoff) pairs (CDF pooling; Dunn, Wasserman and Ramdas,
2023). Scores are log ratios, so a shared unit of the yield cancels.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .forecast_benchmark import prefix_baselines

TOLERANCE = math.log(1.10)
GAIN_FLOOR = 0.01
KEYS = ["lab", "batch_id", "bottle_id"]


def pooled_conformal_quantile(scores, groups, alpha: float) -> float:
    """Conformal quantile with each group weighted equally (CDF pooling).

    Returns the smallest score ``s`` whose pooled empirical CDF reaches
    ``ceil((1 - alpha)(n + 1)) / n``, where ``n`` is the number of groups.
    Returns ``inf`` when that level exceeds one (too few groups for ``alpha``).
    """
    s = np.asarray(scores, dtype=float)
    g = np.asarray(groups)
    if s.ndim != 1 or s.shape != g.shape or s.size == 0:
        raise ValueError("scores and groups must be aligned, non-empty, one-dimensional")
    if not np.isfinite(s).all() or (s < 0).any():
        raise ValueError("scores must be finite and non-negative")
    if not 0 < alpha < 1:
        raise ValueError("alpha must lie in (0, 1)")
    labels, inverse, counts = np.unique(g, return_inverse=True, return_counts=True)
    n = len(labels)
    level = math.ceil((1 - alpha) * (n + 1)) / n
    if level > 1:
        return math.inf
    weights = 1.0 / counts[inverse]
    order = np.argsort(s, kind="stable")
    cumulative = np.cumsum(weights[order]) / n
    index = int(np.searchsorted(cumulative, level - 1e-12, side="left"))
    return float(s[order][min(index, len(s) - 1)])


def holliger_stop_day(time, cumulative, end_day: float) -> tuple[float, float] | None:
    """First whole day ``d`` at which the last three one-day increments are each
    below 1% of the cumulative yield on their day, with the yield on that day;
    ``None`` if the criterion is not met before ``end_day``.

    Only readings at whole days are used. Gross yield is used as supplied.
    """
    t = np.asarray(time, dtype=float)
    y = np.asarray(cumulative, dtype=float)
    whole = np.isclose(t, np.round(t), atol=1e-6)
    daily = dict(zip(np.round(t[whole]).astype(int), y[whole], strict=True))
    for d in range(3, math.floor(end_day + 1e-9)):
        if d >= end_day - 1e-9:
            break
        days = (d - 2, d - 1, d)
        if not all(k in daily and k - 1 in daily for k in days):
            continue
        if all(daily[k] > 0 and daily[k] - daily[k - 1] < 0.01 * daily[k] for k in days):
            return float(d), float(daily[d])
    return None


def forecast_pairs(trajectories: dict, first_cut: int = 5) -> pd.DataFrame:
    """One row per (cycle, whole-day cutoff) with forecasts and both scores."""
    rows = []
    for key, (t, y) in sorted(trajectories.items()):
        end_day, end_yield = float(t[-1]), float(y[-1])
        if not end_yield > 0:
            raise ValueError(f"non-positive end-of-cycle yield: {key}")
        cut = first_cut
        while cut <= end_day - 1 + 1e-9:
            forecasts = prefix_baselines(t, y, float(cut), end_day)
            last = forecasts["persistence"]
            if not last > 0:
                raise ValueError(f"non-positive prefix yield at day {cut}: {key}")
            yhat = forecasts["recent_rate"]
            gain = math.log(yhat / last)
            error = abs(math.log(yhat / end_yield))
            rows.append(
                dict(zip(KEYS, key, strict=True))
                | {
                    "cut_days": float(cut),
                    "end_day": end_day,
                    "end_yield": end_yield,
                    "recent_rate": yhat,
                    "persistence": last,
                    "predicted_gain": gain,
                    "score_fixed": error,
                    "score_normalised": error / max(gain, GAIN_FLOOR),
                    "score_persistence": abs(math.log(last / end_yield)),
                }
            )
            cut += 1
    return pd.DataFrame(rows)


def _bottle(frame: pd.DataFrame) -> pd.Series:
    return frame["lab"].astype(str) + "/" + frame["bottle_id"].astype(str)


def calibrate(calibration: pd.DataFrame, alpha: float) -> dict:
    """Quantiles learned from calibration bottles only."""
    bottle = _bottle(calibration)
    fixed = {
        cut: pooled_conformal_quantile(part["score_fixed"], bottle[part.index], alpha)
        for cut, part in calibration.groupby("cut_days")
    }
    persistence = {
        cut: pooled_conformal_quantile(part["score_persistence"], bottle[part.index], alpha)
        for cut, part in calibration.groupby("cut_days")
    }
    normalised = pooled_conformal_quantile(calibration["score_normalised"], bottle, alpha)
    first_fixed = min((c for c, q in fixed.items() if q <= TOLERANCE), default=None)
    first_persistence = min((c for c, q in persistence.items() if q <= TOLERANCE), default=None)
    return {
        "fixed": fixed,
        "persistence": persistence,
        "normalised": normalised,
        "fixed_stop_day": first_fixed,
        "persistence_stop_day": first_persistence,
    }


def _record(base: dict, rule: str, row, estimate_column: str, covered) -> dict:
    if row is None:
        return base | {
            "rule": rule,
            "stop_day": base["end_day"],
            "fired": False,
            "abs_log_error": 0.0,
            "covered": True,
            "within_10pct": True,
        }
    ratio = row[estimate_column] / row["end_yield"]
    return base | {
        "rule": rule,
        "stop_day": float(row["cut_days"]),
        "fired": True,
        "abs_log_error": abs(math.log(ratio)),
        "covered": bool(covered(row)),
        "within_10pct": bool(abs(ratio - 1) <= 0.10),
    }


def evaluate(test: pd.DataFrame, model: dict, holliger: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Coverage of every test pair and the outcome of each stopping rule per cycle.

    The 1%-rule has no interval; its ``covered`` is whether it is within 10%.
    A rule that does not fire runs to the end of the cycle with zero error.
    """
    pairs = test.copy()
    q_fixed = pairs["cut_days"].map(model["fixed"]).fillna(math.inf)
    pairs["covered_fixed"] = pairs["score_fixed"] <= q_fixed
    half = model["normalised"] * np.maximum(pairs["predicted_gain"], GAIN_FLOOR)
    pairs["covered_normalised"] = pairs["score_normalised"] <= model["normalised"]
    pairs["adaptive_half_width"] = half
    stops = []
    for key, cycle in pairs.groupby(KEYS, sort=True):
        cycle = cycle.sort_values("cut_days")
        end_day = float(cycle["end_day"].iloc[0])
        base = dict(zip(KEYS, key, strict=True)) | {"end_day": end_day}

        adaptive = cycle[cycle["adaptive_half_width"] <= TOLERANCE]
        row = adaptive.iloc[0] if len(adaptive) else None
        stops.append(
            _record(base, "adaptive", row, "recent_rate", lambda r: r["covered_normalised"])
        )
        for rule, day_key, column, q_key in (
            ("fixed_day", "fixed_stop_day", "recent_rate", "fixed"),
            ("fixed_day_persistence", "persistence_stop_day", "persistence", "persistence"),
        ):
            day = model[day_key]
            hit = cycle[cycle["cut_days"] == day] if day is not None else cycle.iloc[0:0]
            row = hit.iloc[0] if len(hit) else None
            score = "score_fixed" if column == "recent_rate" else "score_persistence"
            stops.append(
                _record(
                    base,
                    rule,
                    row,
                    column,
                    lambda r, s=score, k=q_key: r[s] <= model[k][r["cut_days"]],
                )
            )
        fired = holliger.get(key)
        if fired is None:
            stops.append(_record(base, "holliger_1pct", None, "", None))
        else:
            day, estimate = fired
            end_yield = float(cycle["end_yield"].iloc[0])
            ratio = estimate / end_yield
            stops.append(
                base
                | {
                    "rule": "holliger_1pct",
                    "stop_day": day,
                    "fired": True,
                    "abs_log_error": abs(math.log(ratio)),
                    "covered": abs(ratio - 1) <= 0.10,
                    "within_10pct": abs(ratio - 1) <= 0.10,
                }
            )
    return pairs, pd.DataFrame(stops)


def bottle_mean(frame: pd.DataFrame, column: str) -> float:
    """Average within bottle, then across bottles."""
    values = frame.assign(_b=_bottle(frame)).groupby("_b")[column].mean()
    return float(values.mean())
