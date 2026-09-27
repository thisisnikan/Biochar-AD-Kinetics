"""Fail-closed behaviour of the pre-registered admission gate (synthetic fixtures)."""

import copy
import json
from pathlib import Path

import pandas as pd
import pytest

from biochar_ad_kinetics.validation_admission import (
    admit_cycles,
    classify_validation_role,
    clean_windows,
    leakage_audit,
    load_spec,
    validate_spec,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "data/validation/sanglier_2022_validation_spec.json"


def spec_for(windows, horizon=5.0, treatments=None):
    spec = copy.deepcopy(json.loads(SPEC_PATH.read_text()))
    spec["temporal_definition"]["expected_windows"] = windows
    spec["temporal_definition"]["expected_horizon_days"] = horizon
    spec["allowable_treatments"] = treatments or {"LAB": ["C", "B"]}
    return spec


def adjudication(rows):
    columns = [
        "lab",
        "batch_id",
        "bottle_id",
        "source_condition_inoculation",
        "adjudication_class",
        "rules",
    ]
    return pd.DataFrame(rows, columns=columns)


def durations(frame, days=5.2):
    out = frame[["lab", "batch_id", "bottle_id"]].copy()
    out["last_within_batch_days"] = days
    return out


def design(extra=()):
    rows = []
    for bottle, arm in (("c1", "C"), ("c2", "C"), ("b1", "B"), ("b2", "B")):
        for batch in (1, 2, 3):
            rows.append(["LAB", batch, bottle, arm, "source_consistent", ""])
    rows.extend(extra)
    return rows


def test_committed_spec_is_complete_and_frozen():
    spec = load_spec(SPEC_PATH)
    assert spec["dataset_roles"]["locked_external_validation"]["status"] == "blocked"
    assert spec["transfer_rules"]["parameters_allowed_to_transfer"] == []
    assert spec["unit_of_analysis"] == "bottle"


@pytest.mark.parametrize("field", ["failure_criteria", "leakage_prevention", "unit_of_analysis"])
def test_missing_required_field_fails_closed(field):
    spec = json.loads(SPEC_PATH.read_text())
    del spec[field]
    with pytest.raises(ValueError, match=field):
        validate_spec(spec)


def test_unfrozen_or_interpolating_spec_is_rejected():
    spec = json.loads(SPEC_PATH.read_text())
    spec["status"] = "DRAFT"
    with pytest.raises(ValueError, match="frozen"):
        validate_spec(spec)
    spec = json.loads(SPEC_PATH.read_text())
    spec["temporal_definition"]["interpolation"] = "linear"
    with pytest.raises(ValueError, match="interpolation"):
        validate_spec(spec)


def test_refitting_is_never_called_external_validation():
    calib = ["intercept", "scale"]
    assert classify_validation_role([], calib, False) == "locked_external_validation"
    assert classify_validation_role(["scale"], calib, False) == "calibration_transfer"
    assert classify_validation_role(["scale", "potential"], calib, False) == "model_updating"
    assert classify_validation_role([], calib, True) == "exploratory"


def test_admission_rejects_outcome_columns():
    frame = adjudication(design())
    d = durations(frame)
    d["methane_yield_nml_gvs"] = 1.0
    with pytest.raises(ValueError, match="outcome-blind"):
        admit_cycles(frame, spec_for({"LAB": [1, 3]}), d)


def test_conflicting_cycle_removes_whole_bottle_for_carryover():
    rows = design()
    rows[4][4:] = ["conflicting", "R1_control_label_positive_biochar_mass"]  # c2 batch 2
    frame = adjudication(rows)
    table, summary = admit_cycles(frame, spec_for({"LAB": [1, 3]}), durations(frame))
    c2 = table[table.bottle_id == "c2"]
    assert not c2.admitted_primary.any()
    assert "LAB c2" in summary["excluded_bottles"]
    assert summary["admitted_bottles_by_arm"]["LAB C"] == ["c1"]


def test_co_intervention_is_excluded_even_when_resolvable():
    rows = design()
    rows[7][4:] = ["resolvable_from_source", "R4_ammonium_bicarbonate_recorded"]  # b1 b2
    frame = adjudication(rows)
    table, _ = admit_cycles(frame, spec_for({"LAB": [1, 3]}), durations(frame))
    assert not table[table.bottle_id == "b1"].admitted_primary.any()


def test_window_ends_before_lab_scope_confounder_and_mismatch_fails():
    rows = design([["LAB", 4, "c1", "C", "ambiguous", "R8_unspecified_subset_event_overlap"]])
    frame = adjudication(rows)
    assert clean_windows(frame) == {"LAB": (1, 3)}
    with pytest.raises(ValueError, match="differ from frozen"):
        admit_cycles(frame, spec_for({"LAB": [1, 4]}), durations(frame))


def test_horizon_mismatch_fails_closed():
    frame = adjudication(design())
    with pytest.raises(ValueError, match="Horizon"):
        admit_cycles(frame, spec_for({"LAB": [1, 3]}, horizon=6.0), durations(frame))


def test_leakage_audit_detects_planted_identifier(tmp_path):
    spec = json.loads(SPEC_PATH.read_text())
    spec["leakage_prevention"]["development_paths"] = ["results/effects"]
    (tmp_path / "results/effects").mkdir(parents=True)
    (tmp_path / "results/effects/clean.csv").write_text("study_id\nkozlowski\n")
    assert leakage_audit(tmp_path, spec)["passed"]
    (tmp_path / "results/effects/leak.csv").write_text("study_id\nSanglier_2022\n")
    audit = leakage_audit(tmp_path, spec)
    assert not audit["passed"]
    assert audit["hits"] == [{"path": "results/effects/leak.csv", "identifier": "sanglier"}]


def test_repository_development_paths_contain_no_sanglier_identifier():
    audit = leakage_audit(ROOT, load_spec(SPEC_PATH))
    assert audit["passed"], audit["hits"]
    assert audit["files_scanned"] > 0
