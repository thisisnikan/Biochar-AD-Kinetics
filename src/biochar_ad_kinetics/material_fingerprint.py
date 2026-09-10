"""Material/context-aware modelling of batch kinetic fingerprints.

Validation is target-specific because independent studies do not always report
all kinetic descriptors. A target is only evaluated when at least three
independent studies contain that target plus the requested features.
Validation is always grouped by whole held-out study (leave-one-study-out),
never a random row split, so cross-study claims cannot leak sibling
observations between train and test. Numeric predictors are standardized
(mean/scale) using the training fold only, then the same transform is
applied to the held-out fold, so Ridge's L2 penalty is scale-invariant and
no test-fold statistic reaches the fitted coefficients.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TARGET_COLUMNS = (
    "delta_potential",
    "delta_max_rate",
    "delta_lag",
    "delta_t50",
    "delta_t90",
)

DEFAULT_NUMERIC_FEATURES = (
    "dose_g_l",
    "material_process_temperature_c",
)


@dataclass(frozen=True)
class TargetReadiness:
    target: str
    n_rows: int
    n_studies: int
    eligible: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "n_rows": self.n_rows,
            "n_studies": self.n_studies,
            "eligible": self.eligible,
            "reason": self.reason,
        }


def _usable(
    frame: pd.DataFrame,
    target: str,
    numeric_features: tuple[str, ...],
) -> pd.DataFrame:
    required = {"study_id", "material", target, *numeric_features}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError("Missing Stage C columns: " + ", ".join(sorted(missing)))
    return frame.dropna(subset=["study_id", "material", target, *numeric_features]).copy()


def assess_target_readiness(
    frame: pd.DataFrame,
    target: str,
    *,
    numeric_features: tuple[str, ...] = DEFAULT_NUMERIC_FEATURES,
    min_studies: int = 3,
) -> TargetReadiness:
    if target not in TARGET_COLUMNS:
        raise ValueError(f"Unknown Stage C target: {target}")
    usable = _usable(frame, target, numeric_features)
    n_studies = int(usable["study_id"].nunique())
    eligible = n_studies >= min_studies
    reason = (
        "enough independent studies for leave-one-study-out benchmarking"
        if eligible
        else f"requires at least {min_studies} independent studies; found {n_studies}"
    )
    return TargetReadiness(
        target=target,
        n_rows=len(usable),
        n_studies=n_studies,
        eligible=eligible,
        reason=reason,
    )


def assess_readiness(
    frame: pd.DataFrame,
    min_studies: int = 3,
) -> dict[str, TargetReadiness]:
    """Return readiness independently for every kinetic target."""
    return {
        target: assess_target_readiness(frame, target, min_studies=min_studies)
        for target in TARGET_COLUMNS
    }


def _numeric_scaler(x_train: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Fit a mean/scale standardizer on the training fold only."""
    mean = x_train.mean(axis=0)
    scale = x_train.std(axis=0)
    scale[scale == 0] = 1.0
    return mean, scale


def _design_matrix(
    frame: pd.DataFrame,
    numeric_features: tuple[str, ...],
    categories: list[str] | None = None,
    numeric_mean: np.ndarray | None = None,
    numeric_scale: np.ndarray | None = None,
) -> tuple[np.ndarray, list[str]]:
    numeric = frame.loc[:, numeric_features].astype(float).to_numpy(float)
    if numeric_mean is not None and numeric_scale is not None:
        numeric = (numeric - numeric_mean) / numeric_scale
    observed = frame["material"].fillna("unknown").astype(str)
    fitted_categories = sorted(observed.unique()) if categories is None else categories
    encoded = np.column_stack(
        [(observed == value).to_numpy(float) for value in fitted_categories]
    )
    return np.column_stack([np.ones((len(frame), 1)), numeric, encoded]), fitted_categories


def _ridge_fit(x: np.ndarray, y: np.ndarray, alpha: float) -> np.ndarray:
    penalty = np.eye(x.shape[1], dtype=float) * alpha
    penalty[0, 0] = 0.0
    return np.linalg.solve(x.T @ x + penalty, x.T @ y)


def leave_one_study_out(
    frame: pd.DataFrame,
    *,
    alpha: float = 1.0,
    min_studies: int = 3,
    numeric_features: tuple[str, ...] = DEFAULT_NUMERIC_FEATURES,
) -> pd.DataFrame:
    """Evaluate each kinetic target with whole studies held out."""
    rows: list[dict[str, object]] = []
    for target in TARGET_COLUMNS:
        readiness = assess_target_readiness(
            frame,
            target,
            numeric_features=numeric_features,
            min_studies=min_studies,
        )
        if not readiness.eligible:
            rows.append(
                {
                    "status": "blocked_insufficient_independent_studies",
                    "target": target,
                    "n_studies": readiness.n_studies,
                    "reason": readiness.reason,
                }
            )
            continue

        usable = _usable(frame, target, numeric_features)
        for held_out in sorted(usable["study_id"].unique()):
            train = usable.loc[usable["study_id"] != held_out].copy()
            test = usable.loc[usable["study_id"] == held_out].copy()
            raw_train_numeric = train.loc[:, numeric_features].astype(float).to_numpy(float)
            numeric_mean, numeric_scale = _numeric_scaler(raw_train_numeric)
            x_train, categories = _design_matrix(
                train, numeric_features, numeric_mean=numeric_mean, numeric_scale=numeric_scale
            )
            x_test, _ = _design_matrix(
                test,
                numeric_features,
                categories=categories,
                numeric_mean=numeric_mean,
                numeric_scale=numeric_scale,
            )
            y_train = train[target].to_numpy(float)
            y_test = test[target].to_numpy(float)
            beta = _ridge_fit(x_train, y_train, alpha)
            predicted = x_test @ beta
            baseline = np.full_like(y_test, y_train.mean(), dtype=float)
            rmse = float(np.sqrt(np.mean((y_test - predicted) ** 2)))
            baseline_rmse = float(np.sqrt(np.mean((y_test - baseline) ** 2)))
            rows.append(
                {
                    "status": "evaluated",
                    "held_out_study": str(held_out),
                    "target": target,
                    "n_train": len(train),
                    "n_test": len(test),
                    "rmse": rmse,
                    "study_mean_baseline_rmse": baseline_rmse,
                    "rmse_improvement_vs_baseline": baseline_rmse - rmse,
                    "alpha": alpha,
                    "numeric_features": ",".join(numeric_features),
                }
            )
    return pd.DataFrame(rows)
