"""Sensitivity analysis for a Phase-III -> Phase-IV continuous-reactor transition.

The script deliberately uses only NumPy/Pandas so it does not expand the package
requirements. It expects a *processed* CSV with, at minimum, these columns:

    time, phase, OLR, methane_pct, CH4_L_d,
    methane_yield_Nml_gVS, biogas

The processed input must already have source-specific QC applied. In particular,
this script never assumes that numeric zero means missing.

Model for each response y:

    y = b0 + b1*time_centered + b2*post + b3*post_time + b4*OLR + error

where post = 1 at/after the declared transition day. The script compares this
segmented model with a simpler time + OLR model by AIC and repeats the fit over
several symmetric windows around the transition.

This is an association/sensitivity analysis, not causal identification.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

TARGETS = (
    "methane_pct",
    "CH4_L_d",
    "methane_yield_Nml_gVS",
    "biogas",
)


def _ols(y: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Return coefficients, RSS and Gaussian OLS AIC."""
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    residual = y - x @ beta
    rss = float(residual @ residual)
    n, k = x.shape
    if n <= k or rss <= 0:
        return beta, rss, np.nan
    aic = n * np.log(rss / n) + 2 * k
    return beta, rss, float(aic)


def fit_one(
    frame: pd.DataFrame,
    response: str,
    boundary: float,
    window: float | None,
) -> dict[str, float | int | str]:
    cols = ["time", "OLR", response]
    data = frame.loc[:, cols].copy()
    if window is not None:
        data = data.loc[
            (data["time"] >= boundary - window)
            & (data["time"] <= boundary + window)
        ]
    data = data.dropna()

    t = data["time"].to_numpy(float) - boundary
    olr = data["OLR"].to_numpy(float)
    post = (data["time"].to_numpy(float) >= boundary).astype(float)
    post_time = t * post
    y = data[response].to_numpy(float)

    x_simple = np.column_stack([np.ones(len(data)), t, olr])
    x_segmented = np.column_stack(
        [np.ones(len(data)), t, post, post_time, olr]
    )

    _, _, aic_simple = _ols(y, x_simple)
    beta, _, aic_segmented = _ols(y, x_segmented)

    return {
        "response": response,
        "boundary_day": boundary,
        "window_days": "full" if window is None else window,
        "n": len(data),
        "intercept": beta[0],
        "pre_slope_per_day": beta[1],
        "level_change": beta[2],
        "post_slope_change_per_day": beta[3],
        "OLR_coefficient": beta[4],
        "aic_simple_time_olr": aic_simple,
        "aic_segmented": aic_segmented,
        "delta_aic_simple_minus_segmented": aic_simple - aic_segmented,
    }


def run(input_csv: Path, output_csv: Path, boundary: float) -> None:
    frame = pd.read_csv(input_csv)
    required = {"time", "phase", "OLR", *TARGETS}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Restrict this first challenge to the immediate pre/post phases.
    frame = frame.loc[frame["phase"].isin(["phase III", "phase IV"])].copy()

    rows: list[dict[str, float | int | str]] = []
    for response in TARGETS:
        for window in (30.0, 40.0, 50.0, 60.0, 80.0, None):
            rows.append(fit_one(frame, response, boundary, window))

    result = pd.DataFrame(rows)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_csv, index=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--output", type=Path, default=Path("outputs/continuous_transition_sensitivity.csv"))
    parser.add_argument("--boundary-day", type=float, default=309.0)
    args = parser.parse_args()
    run(args.input_csv, args.output, args.boundary_day)


if __name__ == "__main__":
    main()
