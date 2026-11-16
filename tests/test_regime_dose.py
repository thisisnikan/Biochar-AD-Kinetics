from copy import deepcopy
from io import StringIO

import pandas as pd
import pytest

from biochar_ad_kinetics.regime_dose import audit_regime_dose_context


def _arms(
    study: str,
    *,
    mode: str = "batch",
    dose_unit: str = "pct_substrate_vs",
    denominator: str = "substrate_vs_g",
    isr: float | None = 0.5,
    stress: str = "overloaded",
    response: str = "final_methane_yield",
) -> list[dict]:
    rows = []
    for label, dose in [("control", 0.0), ("biochar_10", 10.0), ("biochar_25", 25.0)]:
        rows.append(
            {
                "study_id": study,
                "experiment_id": "exp_01",
                "regime_id": "loading_1",
                "arm_id": label,
                "response": response,
                "digestion_mode": mode,
                "is_control": label == "control",
                "dose_value": dose,
                "dose_unit": "none" if label == "control" else dose_unit,
                "dose_denominator": "none" if label == "control" else denominator,
                "isr_vs": isr if mode == "batch" else None,
                "olr_g_vs_l_d": 2.0 if mode == "continuous" else None,
                "hrt_days": 20.0 if mode == "continuous" else None,
                "stress_status": stress,
                "stress_evidence": "source method and measured process context",
                "substrate_id": "food_waste",
                "inoculum_id": "inoculum_a",
                "material_id": "none" if label == "control" else "grass_750",
                "source_record_id": f"{study}/table-1/{label}",
            }
        )
    return rows


def test_compatible_batch_regimes_are_conditional_candidates_not_pooling() -> None:
    frame = pd.DataFrame(_arms("study_a") + _arms("study_b"))
    original = frame.copy(deep=True)
    audit = audit_regime_dose_context(frame)
    assert audit["n_context_documented"] == 2
    assert audit["n_pairs_not_blocked_by_context"] == 1
    assert audit["cross_study_pairs"][0]["candidate_for_contextual_comparison"]
    assert audit["cross_study_pooling_performed"] is False
    assert audit["loso_validated"] is False
    pd.testing.assert_frame_equal(frame, original)


def test_different_isr_blocks_pair_despite_matching_dose_range() -> None:
    rows = _arms("study_a") + _arms("study_b", isr=2)
    audit = audit_regime_dose_context(pd.DataFrame(rows))
    pair = audit["cross_study_pairs"][0]
    assert not pair["candidate_for_contextual_comparison"]
    assert "isr_vs_mismatch" in pair["blocking_reasons"]
    assert pair["same_dose_basis"]


def test_dose_denominator_is_not_implicitly_converted() -> None:
    rows = _arms("study_a") + _arms(
        "study_b", dose_unit="g_l", denominator="working_volume_l"
    )
    pair = audit_regime_dose_context(pd.DataFrame(rows))["cross_study_pairs"][0]
    assert not pair["candidate_for_contextual_comparison"]
    assert pair["dose_overlap_fraction"] is None
    assert "dose_basis_mismatch_no_conversion" in pair["blocking_reasons"]


def test_stress_status_is_not_inferred_from_isr() -> None:
    rows = _arms("study_a", stress="unknown") + _arms("study_b")
    audit = audit_regime_dose_context(pd.DataFrame(rows))
    assert "stress_status_undocumented" in audit["regimes"][0]["context_blockers"]
    assert "unresolved_regime_context" in audit["cross_study_pairs"][0]["blocking_reasons"]


def test_missing_isr_blocks_batch_context() -> None:
    audit = audit_regime_dose_context(pd.DataFrame(_arms("a", isr=None)))
    assert "batch_isr_vs_missing_or_inconsistent" in audit["regimes"][0]["context_blockers"]


def test_continuous_needs_olr_and_hrt_and_never_compares_to_batch() -> None:
    rows = _arms("study_a", mode="continuous") + _arms("study_b", mode="batch")
    pair = audit_regime_dose_context(pd.DataFrame(rows))["cross_study_pairs"][0]
    assert "digestion_mode_mismatch" in pair["blocking_reasons"]
    missing = pd.DataFrame(_arms("study_c", mode="continuous"))
    missing["hrt_days"] = None
    report = audit_regime_dose_context(missing)
    assert "continuous_hrt_missing_or_inconsistent" in report["regimes"][0]["context_blockers"]


def test_continuous_olr_difference_blocks() -> None:
    rows = _arms("a", mode="continuous") + _arms("b", mode="continuous")
    for row in rows:
        if row["study_id"] == "b":
            row["olr_g_vs_l_d"] = 4.0
    pair = audit_regime_dose_context(pd.DataFrame(rows))["cross_study_pairs"][0]
    assert "olr_mismatch" in pair["blocking_reasons"]


def test_no_matched_control_blocks_study() -> None:
    rows = [r for r in _arms("a") if not r["is_control"]]
    audit = audit_regime_dose_context(pd.DataFrame(rows))
    assert "missing_zero_dose_control" in audit["regimes"][0]["context_blockers"]


def test_unknown_or_wrong_denominator_blocks() -> None:
    rows = _arms("a")
    rows[1]["dose_denominator"] = "unknown"
    audit = audit_regime_dose_context(pd.DataFrame(rows))
    assert "dose_denominator_not_verified" in audit["regimes"][0]["context_blockers"]


def test_nonoverlapping_ranges_fail_even_in_same_units() -> None:
    rows = _arms("a") + _arms("b")
    for row in rows:
        if row["study_id"] == "b" and not row["is_control"]:
            row["dose_value"] += 100
    pair = audit_regime_dose_context(pd.DataFrame(rows))["cross_study_pairs"][0]
    assert "no_amended_dose_range_overlap" in pair["blocking_reasons"]


def test_distinct_responses_never_compared() -> None:
    rows = _arms("a", response="rate_constant") + _arms(
        "b", response="final_methane_yield"
    )
    audit = audit_regime_dose_context(pd.DataFrame(rows))
    assert audit["cross_study_pairs"] == []


def test_same_study_regimes_not_counted_as_independent_studies() -> None:
    rows = _arms("a")
    second = deepcopy(_arms("a"))
    for row in second:
        row["regime_id"] = "loading_2"
        row["isr_vs"] = 2.0
    audit = audit_regime_dose_context(pd.DataFrame(rows + second))
    assert len(audit["regimes"]) == 2
    assert audit["cross_study_pairs"] == []


@pytest.mark.parametrize("flag", ["yes", "", 1, None])
def test_ambiguous_control_flag_fails_closed(flag: object) -> None:
    frame = pd.DataFrame(_arms("a"))
    frame["is_control"] = frame["is_control"].astype(object)
    frame.loc[0, "is_control"] = flag
    with pytest.raises(ValueError, match="explicit True/False"):
        audit_regime_dose_context(frame)


def test_csv_boolean_strings_remain_valid() -> None:
    frame = pd.DataFrame(_arms("a") + _arms("b"))
    loaded = pd.read_csv(StringIO(frame.to_csv(index=False)))
    assert audit_regime_dose_context(loaded)["n_pairs_not_blocked_by_context"] == 1


def test_nonnumeric_dose_fails_closed() -> None:
    frame = pd.DataFrame(_arms("a"))
    frame["dose_value"] = frame["dose_value"].astype(object)
    frame.loc[1, "dose_value"] = "unverified"
    with pytest.raises(ValueError, match="dose_value"):
        audit_regime_dose_context(frame)


def test_missing_or_ambiguous_stress_evidence_fails_closed() -> None:
    frame = pd.DataFrame(_arms("a"))
    frame["stress_evidence"] = ""
    audit = audit_regime_dose_context(frame)
    assert "stress_evidence_missing" in audit["regimes"][0]["context_blockers"]


def test_missing_material_id_blocks_amended_arm() -> None:
    frame = pd.DataFrame(_arms("a"))
    frame.loc[1, "material_id"] = "not_measured"
    audit = audit_regime_dose_context(frame)
    assert "amended_material_identity_missing" in audit["regimes"][0]["context_blockers"]
