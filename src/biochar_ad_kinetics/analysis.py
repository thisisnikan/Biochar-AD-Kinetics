"""Model comparison and validation utilities for BMP research workflows."""

from __future__ import annotations

import numpy as np
import pandas as pd

from biochar_ad_kinetics.fit import fit_global, predict_frame

CANDIDATES = {
    "constant_gompertz": "constant",
    "log_linear_dose_temperature": "log_linear",
    "global_dose_temperature": "log_quadratic",
}


def information_criteria(observed: np.ndarray, predicted: np.ndarray, k: int) -> dict[str, float]:
    """Return Gaussian AIC, small-sample AICc and BIC from unweighted residuals."""
    observed = np.asarray(observed, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    n = observed.size
    if n != predicted.size or n <= k + 1:
        raise ValueError("AICc requires equal vectors and n > k + 1")
    rss = float(np.sum((observed - predicted) ** 2))
    rss = max(rss, np.finfo(float).tiny)
    aic = n * np.log(rss / n) + 2 * k
    return {
        "aic": float(aic),
        "aicc": float(aic + (2 * k * (k + 1)) / (n - k - 1)),
        "bic": float(n * np.log(rss / n) + k * np.log(n)),
    }


def compare_models(frame: pd.DataFrame) -> pd.DataFrame:
    """Compare the proposed global model with a parsimonious Gompertz baseline."""
    frame = frame.reset_index(drop=True)
    observed = frame["methane_ml_g_vs"].to_numpy(float)
    rows = []
    for name, response in CANDIDATES.items():
        parameters, metrics = fit_global(frame, response=response)
        predicted = predict_frame(frame, parameters)
        k = int(metrics["n_parameters"])
        residual = observed - predicted
        rows.append(
            {
                "model": name,
                "parameters": k,
                "rmse_ml_g_vs": float(np.sqrt(np.mean(residual**2))),
                **information_criteria(observed, predicted, k),
            }
        )
    result = pd.DataFrame(rows).sort_values("aicc").reset_index(drop=True)
    result["delta_aicc"] = result["aicc"] - result["aicc"].min()
    return result


def leave_one_batch_out(frame: pd.DataFrame) -> pd.DataFrame:
    """Compare all candidates on identical, whole-batch holdouts.

    Fit parameters, bounds and robust loss are shared across nested candidates.
    A single training temperature cannot support extrapolation to a new one.
    This is within-dataset validation, not held-out-study validation.

    Most held-out batches also sit inside the observed dose/temperature
    range, so their error mainly measures interpolation, not extrapolation.
    Each row is tagged ``is_boundary_condition`` when the held-out batch is
    at the min or max of the observed dose or temperature range; only those
    rows say anything about extrapolation to untested conditions, and the
    two groups should be reported separately rather than pooled into one
    mean.
    """
    if frame["batch_id"].nunique() < 3:
        raise ValueError(
            "At least three batch conditions are required for leave-one-batch-out "
            "validation (two must remain after holding one out)"
        )
    batch_conditions = frame.drop_duplicates("batch_id").set_index("batch_id")
    dose_bounds = (batch_conditions["dose_g_l"].min(), batch_conditions["dose_g_l"].max())
    temperature_bounds = (
        batch_conditions["temperature_c"].min(),
        batch_conditions["temperature_c"].max(),
    )
    rows = []
    for batch_id in frame["batch_id"].drop_duplicates():
        train = frame.loc[frame["batch_id"] != batch_id].reset_index(drop=True)
        test = frame.loc[frame["batch_id"] == batch_id].reset_index(drop=True)
        if train["temperature_c"].nunique() == 1 and not test["temperature_c"].isin(
            train["temperature_c"].unique()
        ).all():
            raise ValueError("Cannot estimate temperature extrapolation from one training temperature")
        condition = batch_conditions.loc[batch_id]
        is_boundary_condition = bool(
            condition["dose_g_l"] in dose_bounds or condition["temperature_c"] in temperature_bounds
        )
        for name, response in CANDIDATES.items():
            parameters, metrics = fit_global(train, response=response)
            residual = test["methane_ml_g_vs"].to_numpy(float) - predict_frame(test, parameters)
            rows.append(
                {
                    "model": name,
                    "held_out_batch": batch_id,
                    "n_train": len(train),
                    "n_test": len(test),
                    "parameters": int(metrics["n_parameters"]),
                    "is_boundary_condition": is_boundary_condition,
                    "rmse_ml_g_vs": float(np.sqrt(np.mean(residual**2))),
                    "mae_ml_g_vs": float(np.mean(np.abs(residual))),
                }
            )
    return pd.DataFrame(rows)


def summarize_holdouts(validation: pd.DataFrame) -> pd.DataFrame:
    """Weight each held-out batch equally; keep training criteria secondary."""
    summary = validation.groupby("model", as_index=False).agg(
        mean_held_out_rmse_ml_g_vs=("rmse_ml_g_vs", "mean"),
        mean_held_out_mae_ml_g_vs=("mae_ml_g_vs", "mean"),
        n_folds=("held_out_batch", "nunique"),
    )
    return summary.sort_values("mean_held_out_rmse_ml_g_vs").reset_index(drop=True)
