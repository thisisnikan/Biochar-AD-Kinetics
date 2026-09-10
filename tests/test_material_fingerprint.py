import numpy as np
import pandas as pd

from biochar_ad_kinetics.material_fingerprint import (
    assess_readiness,
    leave_one_study_out,
)


def _frame(n_studies: int, missing_lag_for_last: bool = False) -> pd.DataFrame:
    rows = []
    for study in range(n_studies):
        for dose in (2.0, 5.0, 8.0):
            lag = np.nan if missing_lag_for_last and study == n_studies - 1 else 0.01 * dose
            rows.append(
                {
                    "study_id": f"study-{study}",
                    "material": "biochar" if study % 2 == 0 else "hydrochar",
                    "dose_g_l": dose,
                    "material_process_temperature_c": 500.0 + 100.0 * study,
                    "delta_potential": 0.02 * dose + 0.01 * study,
                    "delta_max_rate": 0.03 * dose - 0.01 * study,
                    "delta_lag": lag,
                    "delta_t50": 0.015 * dose,
                    "delta_t90": 0.012 * dose,
                }
            )
    return pd.DataFrame(rows)


def test_stage_c_blocks_two_study_claims():
    readiness = assess_readiness(_frame(2))
    result = leave_one_study_out(_frame(2))

    assert all(not item.eligible for item in readiness.values())
    assert set(result["status"]) == {"blocked_insufficient_independent_studies"}


def test_stage_c_runs_grouped_validation_with_three_studies():
    result = leave_one_study_out(_frame(3))
    evaluated = result.loc[result["status"] == "evaluated"]

    assert evaluated["held_out_study"].nunique() == 3
    assert evaluated["target"].nunique() == 5


def test_stage_c_can_evaluate_some_targets_when_lag_is_missing():
    readiness = assess_readiness(_frame(3, missing_lag_for_last=True))
    result = leave_one_study_out(_frame(3, missing_lag_for_last=True))

    assert readiness["delta_potential"].eligible
    assert not readiness["delta_lag"].eligible
    assert set(result.loc[result["target"] == "delta_lag", "status"]) == {
        "blocked_insufficient_independent_studies"
    }
    assert set(result.loc[result["target"] == "delta_potential", "status"]) == {"evaluated"}


def _evaluated_sorted(result: pd.DataFrame) -> pd.DataFrame:
    evaluated = result.loc[result["status"] == "evaluated"].copy()
    return evaluated.sort_values(["target", "held_out_study"]).reset_index(drop=True)


def test_stage_c_ridge_is_scale_invariant_to_numeric_feature_units():
    """An affine change of units for a numeric predictor must not change RMSE.

    Ridge's L2 penalty is only scale-invariant if numeric predictors are
    standardized before fitting; on raw, unstandardized features the same
    alpha penalizes differently-scaled coefficients unevenly.
    """
    frame = _frame(4)
    rescaled = frame.copy()
    rescaled["dose_g_l"] = rescaled["dose_g_l"] * 1000.0 + 50.0
    rescaled["material_process_temperature_c"] = (
        rescaled["material_process_temperature_c"] / 37.0 - 12.0
    )

    baseline = _evaluated_sorted(leave_one_study_out(frame))
    rescaled_result = _evaluated_sorted(leave_one_study_out(rescaled))

    assert len(baseline) > 0
    assert list(baseline["target"]) == list(rescaled_result["target"])
    assert list(baseline["held_out_study"]) == list(rescaled_result["held_out_study"])
    np.testing.assert_allclose(
        baseline["rmse"].to_numpy(float),
        rescaled_result["rmse"].to_numpy(float),
        rtol=1e-6,
        atol=1e-9,
    )


def test_numeric_standardizer_uses_train_fold_statistics_only():
    """The scaler applied to a held-out fold must come from the train fold alone.

    A leaky implementation (e.g. fitting mean/scale on the full frame) would
    make the transform applied to a test row depend on that row's own value
    or on other held-out rows. Here the transform must exactly equal
    ``(raw - train_mean) / train_scale`` no matter what the held-out row
    contains, including an extreme outlier far outside the training range.
    """
    from biochar_ad_kinetics.material_fingerprint import _design_matrix, _numeric_scaler

    numeric_features = ("dose_g_l", "material_process_temperature_c")
    train = pd.DataFrame(
        {
            "material": ["biochar", "biochar", "hydrochar"],
            "dose_g_l": [2.0, 4.0, 6.0],
            "material_process_temperature_c": [500.0, 550.0, 600.0],
        }
    )
    train_numeric = train.loc[:, numeric_features].to_numpy(float)
    mean, scale = _numeric_scaler(train_numeric)

    np.testing.assert_allclose(mean, train_numeric.mean(axis=0))
    np.testing.assert_allclose(scale, train_numeric.std(axis=0))

    outlier_test = pd.DataFrame(
        {
            "material": ["biochar"],
            "dose_g_l": [1.0e6],
            "material_process_temperature_c": [-1.0e6],
        }
    )
    x_test, _ = _design_matrix(
        outlier_test,
        numeric_features,
        categories=["biochar", "hydrochar"],
        numeric_mean=mean,
        numeric_scale=scale,
    )
    expected = (outlier_test.loc[:, numeric_features].to_numpy(float) - mean) / scale
    np.testing.assert_allclose(x_test[:, 1:3], expected)
