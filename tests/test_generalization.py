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

    ac = support.loc[
        (support["study_a"] == "study_a") & (support["study_b"] == "study_c")
    ].iloc[0]
    assert ac["dose_range_overlap_fraction"] > 0
    assert not ac["shared_material"]
    assert not ac["shared_temperature"]


def test_readiness_requires_explicit_pooling_admission() -> None:
    audit = audit_generalization_readiness(_effect_rows(pooling=False)).iloc[0]

    assert not audit["ready_for_loso"]
    assert "cross_study_pooling_not_admitted" in audit["blocking_reasons"]


def test_readiness_rejects_missing_uncertainty() -> None:
    audit = audit_generalization_readiness(
        _effect_rows(complete_uncertainty=False)
    ).iloc[0]

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
