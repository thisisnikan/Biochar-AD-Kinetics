import numpy as np
import pandas as pd
import pytest

from biochar_ad_kinetics.effect_diagnostics import (
    _leave_one_estimate_out,
    leave_one_reactor_out_effects,
    shared_control_covariance,
)


def _effects() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "study_id": "s",
                "response": "yield",
                "treatment": name,
                "control": "c",
                "treatment_estimate": mean,
                "control_estimate": 10.0,
                "treatment_sd": 2.0,
                "control_sd": 3.0,
                "n_treatment_reactors": 4,
                "n_control_reactors": 3,
            }
            for name, mean in [("a", 12.0), ("b", 15.0)]
        ]
    )


def test_shared_control_covariance_and_cancellation() -> None:
    result = shared_control_covariance(_effects())
    v_a, cov, v_b = result["covariance"]
    # Shared control variance: 3^2/(3*10^2) = .03.
    assert cov == pytest.approx(0.03)
    assert v_a == pytest.approx(4 / (4 * 12**2) + 0.03)
    assert v_b == pytest.approx(4 / (4 * 15**2) + 0.03)
    # Comparing two treatment effects cancels their common control.
    assert v_a + v_b - 2 * cov == pytest.approx(1 / 12**2 + 1 / 15**2)
    assert np.linalg.eigvalsh([[v_a, cov], [cov, v_b]]).min() > 0


def test_control_id_determines_dependence() -> None:
    frame = _effects()
    frame.loc[1, "control"] = "other_control"
    off_diagonal = shared_control_covariance(frame).query("not is_diagonal").iloc[0]
    assert off_diagonal["covariance"] == 0
    assert not off_diagonal["shared_control"]


def test_missing_summary_uncertainty_is_never_zero_imputed() -> None:
    frame = _effects()
    frame["control_sd"] = np.nan
    result = shared_control_covariance(frame)
    assert result["covariance"].isna().all()
    assert not result["uncertainty_available"].any()


def test_inconsistent_shared_control_is_rejected() -> None:
    frame = _effects()
    frame.loc[1, "control_estimate"] = 11
    with pytest.raises(ValueError, match="disagree"):
        shared_control_covariance(frame)


def test_duplicate_effects_are_rejected() -> None:
    frame = _effects()
    with pytest.raises(ValueError, match="One effect"):
        shared_control_covariance(pd.concat([frame, frame]))


def test_covariance_is_stratified_by_study() -> None:
    frame = _effects()
    other = frame.assign(study_id="other")
    result = shared_control_covariance(pd.concat([frame, other]))
    assert len(result) == 6
    assert result.groupby("study_id").size().eq(3).all()


def _estimates() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "study_id": "s",
                "treatment": arm,
                "replicate": i,
                "potential_ml_g_vs": value,
                "max_rate_ml_g_vs_day": value,
            }
            for arm, values in [("food_waste", [10.0, 10.0, 10.0]), ("amended", [9.0, 15.0])]
            for i, value in enumerate(values, start=1)
        ]
    )


def test_sensitivity_detects_single_reactor_direction_dependence() -> None:
    result = _leave_one_estimate_out(_estimates())
    omitted = result.query("omitted_arm == 'treatment' and omitted_replicate == 2")
    assert np.allclose(omitted["original_percent_change"], 20.0)
    assert np.allclose(omitted["omitted_percent_change"], -10.0)
    assert omitted["sign_changed"].all()
    assert omitted["unreplicated_remainder"].all()
    assert len(result) == 10  # five units, two responses; time points are not units


def test_sensitivity_rejects_duplicate_reactors() -> None:
    frame = _estimates()
    with pytest.raises(ValueError, match="independent reactors"):
        _leave_one_estimate_out(pd.concat([frame, frame]))


def test_sensitivity_uses_unit_identity_not_dataframe_index() -> None:
    frame = _estimates()
    expected = _leave_one_estimate_out(frame)
    frame.index = [0] * len(frame)
    pd.testing.assert_frame_equal(_leave_one_estimate_out(frame), expected)


def test_real_covariance_diagonal_matches_existing_standard_errors() -> None:
    frame = pd.read_csv("results/effects/within_study_effects.csv")
    result = shared_control_covariance(frame)
    diagonal = result.query("is_diagonal").rename(columns={"treatment_a": "treatment"})
    joined = diagonal.merge(frame, on=["study_id", "response", "treatment"])
    known = joined.loc[joined["uncertainty_available"]]
    assert np.allclose(known["covariance"], known["log_response_ratio_se"] ** 2)
    assert len(known) == 6
    assert result.query("study_id.str.startswith('valentin')")["covariance"].isna().all()


def test_real_sensitivity_keeps_reactor_count() -> None:
    result = leave_one_reactor_out_effects(pd.read_csv("data/experimental/kozlowski_2025_bmp.csv"))
    assert len(result) == 32  # (3+3 + 2+3 + 2+3) units * two responses
    assert set(result["omitted_arm"]) == {"control", "treatment"}
