"""Material/context-aware modelling of batch kinetic fingerprints.

The module deliberately separates *capability* from *evidence*. It can fit a
small ridge model to dimensionless kinetic effects, but grouped external-study
validation is only enabled once at least three independent studies are present.
This prevents a two-study comparison from being presented as transferable ML.
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

NUMERIC_FEATURES = (
    "dose_g_l",
    "material_process_temperature_c",
)


@dataclass(frozen=True)
class StageCReadiness:
    n_rows: int
    n_studies: int
    n_materials: int
    eligible_for_grouped_validation: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "n_rows": self.n_rows,
            "n_studies": self.n_studies,
            "n_materials": self.n_materials,
            "eligible_for_grouped_validation": self.eligible_for_grouped_validation,
            "reason": self.reason,
        }


def assess_readiness(frame: pd.DataFrame, min_studies: int = 3) -> StageCReadiness:
    """Assess whether whole-study validation is scientifically interpretable."""
    required = {"study_id", "material", *NUMERIC_FEATURES, *TARGET_COLUMNS}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError("Missing Stage C columns: " + ", ".join(sorted(missing)))

    usable = frame.dropna(subset=["study_id", "material", *TARGET_COLUMNS]).copy()
    n_studies = int(usable["study_id"].nunique())
    n_materials = int(usable["material"].nunique())
    eligible = n_studies >= min_studies
    reason = (
        "enough independent studies for leave-one-study-out benchmarking"
        if eligible
        else f"requires at least {min_studies} independent studies; found {n_studies}"
    )
    return StageCReadiness(
        n_rows=len(usable),
        n_studies=n_studies,
        n_materials=n_materials,
        eligible_for_grouped_validation=eligible,
        reason=reason,
    )


def _design_matrix(
    frame: pd.DataFrame,
    categories: dict[str, list[str]] | None = None,
) -> tuple[np.ndarray, dict[str, list[str]]]:
    numeric = frame.loc[:, NUMERIC_FEATURES].astype(float).fillna(0.0)
    numeric_values = numeric.to_numpy(float)

    cat_columns = ("material",)
    fitted_categories: dict[str, list[str]] = {} if categories is None else categories
    pieces = [np.ones((len(frame), 1), dtype=float), numeric_values]

    for column in cat_columns:
        if categories is None:
            values = sorted(frame[column].fillna("unknown").astype(str).unique().tolist())
            fitted_categories[column] = values
        else:
            values = fitted_categories[column]
        observed = frame[column].fillna("unknown").astype(str)
        encoded = np.column_stack([(observed == value).to_numpy(float) for value in values])
        pieces.append(encoded)

    return np.column_stack(pieces), fitted_categories


def _ridge_fit(x: np.ndarray, y: np.ndarray, alpha: float) -> np.ndarray:
    penalty = np.eye(x.shape[1], dtype=float) * alpha
    penalty[0, 0] = 0.0
    return np.linalg.solve(x.T @ x + penalty, x.T @ y)


def leave_one_study_out(
    frame: pd.DataFrame,
    *,
    alpha: float = 1.0,
    min_studies: int = 3,
) -> pd.DataFrame:
    """Evaluate a small material-aware ridge model with whole studies held out."""
    readiness = assess_readiness(frame, min_studies=min_studies)
    if not readiness.eligible_for_grouped_validation:
        return pd.DataFrame(
            [
                {
                    "status": "blocked_insufficient_independent_studies",
                    "n_studies": readiness.n_studies,
                    "reason": readiness.reason,
                }
            ]
        )

    usable = frame.dropna(subset=["study_id", "material", *TARGET_COLUMNS]).copy()
    rows: list[dict[str, object]] = []
    for held_out in sorted(usable["study_id"].unique()):
        train = usable.loc[usable["study_id"] != held_out].copy()
        test = usable.loc[usable["study_id"] == held_out].copy()
        x_train, categories = _design_matrix(train)
        x_test, _ = _design_matrix(test, categories=categories)

        for target in TARGET_COLUMNS:
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
                }
            )
    return pd.DataFrame(rows)
