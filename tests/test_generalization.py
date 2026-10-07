from io import StringIO

import numpy as np
import pandas as pd
import pytest

from biochar_ad_kinetics.generalization import (
    audit_generalization_readiness,
    pairwise_study_support,
)


def _effect_rows(*, pooling: bool = True, complete_uncertainty: bool = True) -> pd.DataFrame:
    rows = []
    for study_id, material, temperature, doses in [
        ("study_a", "wood", 37.0, [1.0, 5.0]),
        ("study_b", "wood", 37.0, [2.0, 6.0]),
        ("study_c", "straw", 55.0, [3.0, 7.0]),
    ]:
        for dose in doses:
            rows.append(
                {
                    "study_id": study_id,
                    "response": "potential_ml_g_vs",
                    "dose_g_l": dose,
                    "material": material,
                    "temperature_c": temperature,
                    "log_response_ratio": 0.05 * dose,
                    "log_response_ratio_se": 0.02 if complete_uncertainty else np.nan,
                    "replicate_level_available": True,
                    "supports_cross_study_pooling": pooling,
                }
            )
    return pd.DataFrame(rows)


def test_pairwise_support_exposes_domain_shift() -> None:
    support = pairwise_study_support(_effect_rows())

    ac = support.loc[(support["study_a"] == "study_a") & (support["study_b"] == "study_c")].iloc[0]
    assert ac["dose_range_overlap_fraction"] > 0
    assert not ac["shared_material"]
    assert not ac["shared_temperature"]


def test_readiness_requires_explicit_pooling_admission() -> None:
    audit = audit_generalization_readiness(_effect_rows(pooling=False)).iloc[0]

    assert not audit["ready_for_loso"]
    assert "cross_study_pooling_not_admitted" in audit["blocking_reasons"]


def test_readiness_rejects_missing_uncertainty() -> None:
    audit = audit_generalization_readiness(_effect_rows(complete_uncertainty=False)).iloc[0]

    assert not audit["ready_for_loso"]
    assert "incomplete_effect_uncertainty" in audit["blocking_reasons"]


def test_readiness_can_pass_minimum_evidence_gate() -> None:
    audit = audit_generalization_readiness(_effect_rows()).iloc[0]

    assert audit["n_independent_studies"] == 3
    assert audit["ready_for_loso"]
    assert audit["blocking_reasons"] == ""


def test_missing_pooling_admission_is_rejected_not_silently_passed() -> None:
    # A blank/undetermined cell (as pd.read_csv produces for an empty field,
    # yielding an object-dtype column) must never be coerced to True by
    # astype(bool) and let a row through as if explicitly admitted for pooling.
    frame = _effect_rows()
    frame["supports_cross_study_pooling"] = frame["supports_cross_study_pooling"].astype(object)
    frame.loc[0, "supports_cross_study_pooling"] = np.nan

    with pytest.raises(ValueError, match="supports_cross_study_pooling"):
        audit_generalization_readiness(frame)


def test_missing_replicate_level_flag_is_rejected_not_silently_passed() -> None:
    frame = _effect_rows()
    frame["replicate_level_available"] = frame["replicate_level_available"].astype(object)
    frame.loc[0, "replicate_level_available"] = np.nan

    with pytest.raises(ValueError, match="replicate_level_available"):
        audit_generalization_readiness(frame)


@pytest.mark.parametrize("column", ["supports_cross_study_pooling", "replicate_level_available"])
def test_csv_blank_flags_fail_closed(column: str) -> None:
    frame = _effect_rows()
    frame[column] = frame[column].astype(object)
    frame.loc[0, column] = None
    loaded = pd.read_csv(StringIO(frame.to_csv(index=False)))
    with pytest.raises(ValueError, match=column):
        audit_generalization_readiness(loaded)


@pytest.mark.parametrize("column", ["supports_cross_study_pooling", "replicate_level_available"])
def test_false_strings_are_not_truthy_evidence(column: str) -> None:
    frame = _effect_rows()
    frame[column] = "True"
    frame.loc[0, column] = "False"
    before = frame.copy(deep=True)
    assert not audit_generalization_readiness(frame).iloc[0]["ready_for_loso"]
    pd.testing.assert_frame_equal(frame, before)


@pytest.mark.parametrize("bad_flag", [1, 0, "yes", "0", "undetermined", ""])
def test_ambiguous_admission_is_rejected(bad_flag: object) -> None:
    frame = _effect_rows()
    frame["supports_cross_study_pooling"] = frame["supports_cross_study_pooling"].astype(object)
    frame.loc[0, "supports_cross_study_pooling"] = bad_flag
    with pytest.raises(ValueError, match="explicit True/False"):
        audit_generalization_readiness(frame)


def test_single_study_reports_blocker_without_key_error() -> None:
    frame = _effect_rows().query("study_id == 'study_a'")
    assert pairwise_study_support(frame).empty
    audit = audit_generalization_readiness(frame).iloc[0]
    assert not audit["ready_for_loso"]
    assert "fewer_than_three_independent_studies" in audit["blocking_reasons"]
    assert np.isnan(audit["minimum_pairwise_dose_overlap_fraction"])


@pytest.mark.parametrize("se", [0, -0.1, np.inf, np.nan, "unknown"])
def test_invalid_uncertainty_blocks_generalization(se: object) -> None:
    frame = _effect_rows()
    frame["log_response_ratio_se"] = frame["log_response_ratio_se"].astype(object)
    frame.loc[0, "log_response_ratio_se"] = se
    audit = audit_generalization_readiness(frame).iloc[0]
    assert not audit["ready_for_loso"]
    assert "incomplete_effect_uncertainty" in audit["blocking_reasons"]


@pytest.mark.parametrize("value", [np.inf, -np.inf, np.nan])
def test_non_finite_effects_cannot_pass(value: float) -> None:
    frame = _effect_rows()
    frame.loc[0, "log_response_ratio"] = value
    assert (
        "non_finite_effect_estimate"
        in audit_generalization_readiness(frame).iloc[0]["blocking_reasons"]
    )


def test_infinite_dose_is_rejected() -> None:
    frame = _effect_rows()
    frame.loc[0, "dose_g_l"] = np.inf
    with pytest.raises(ValueError, match="dose_g_l"):
        audit_generalization_readiness(frame)
