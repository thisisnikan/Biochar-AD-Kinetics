"""Committed Sanglier semantics and admission outputs are reproducible and honest."""

import filecmp
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "results/validation"


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SEMANTICS = load("audit_sanglier_2022_semantics")
ADMISSION = load("run_sanglier_2022_admission")

SEMANTIC_FILES = (
    "sanglier_2022_variable_dictionary.csv",
    "sanglier_2022_event_scope.csv",
    "sanglier_2022_treatment_adjudication.csv",
    "sanglier_2022_semantics_qc.json",
)


def test_semantics_rebuild_is_byte_identical(tmp_path):
    SEMANTICS.build(tmp_path)
    for name in SEMANTIC_FILES:
        assert filecmp.cmp(tmp_path / name, VALIDATION / name, shallow=False), name


def test_admission_rebuild_is_byte_identical(tmp_path):
    ADMISSION.build(tmp_path)
    for name in ("sanglier_2022_admission.csv", "sanglier_2022_admission_report.json"):
        assert filecmp.cmp(tmp_path / name, VALIDATION / name, shallow=False), name


def test_units_are_never_guessed():
    d = pd.read_csv(VALIDATION / "sanglier_2022_variable_dictionary.csv")
    resolved = d[d.unit_status.str.startswith("resolved")]
    assert resolved.variable.tolist() == ["pH"]
    chem = d[d.source_sheet == "Analyses"].set_index("variable")
    assert (chem.drop(index="pH").unit_status == "unresolved").all()
    assert chem.loc["FAN", "admission_use"] == "prohibited_as_independent_feature"
    methane = d[d.source_sheet == "AMPTShort"]
    assert not methane.unit_status.str.startswith("resolved").any()


def test_adjudication_preserves_source_values():
    adj = pd.read_csv(VALIDATION / "sanglier_2022_treatment_adjudication.csv")
    methane = pd.read_csv(ROOT / "results/intake/sanglier_2022_candidate.csv.gz")
    cycles = methane.drop_duplicates(["lab", "batch_id", "bottle_id"])
    merged = adj.merge(cycles, on=["lab", "batch_id", "bottle_id"], suffixes=("", "_src"))
    assert len(merged) == len(adj) == len(cycles)
    for column in (
        "source_condition_ampts",
        "source_condition_inoculation",
        "biochar_label_ampts",
        "inoculation_biochar_g",
        "inoculation_ammonium_bicarbonate_g",
    ):
        left, right = merged[column], merged[f"{column}_src"]
        assert ((left == right) | (left.isna() & right.isna())).all(), column


def test_known_conflicts_are_classified_not_corrected():
    adj = pd.read_csv(VALIDATION / "sanglier_2022_treatment_adjudication.csv")
    ii4 = adj[(adj.bottle_id == "II.4") & adj.batch_id.between(2, 5)]
    assert (ii4.adjudication_class == "conflicting").all()
    assert (ii4.source_condition_inoculation == "MBE[0]").all()
    assert (ii4.inoculation_biochar_g > 0).all()
    later = adj[(adj.bottle_id == "II.4") & (adj.batch_id > 5)]
    assert (later.adjudication_class == "excluded").all()
    brl11 = adj[(adj.lab == "BRL") & (adj.batch_id == 11)]
    assert brl11.inoculation_ammonium_bicarbonate_g.sub(3.11).abs().max() < 1e-9
    others = brl11[
        ~brl11.source_condition_inoculation.str.replace(" ", "").str.startswith("MBE[2]+")
    ]
    assert set(others.adjudication_class) == {"conflicting", "excluded"}
    # II.4 is already excluded by carry-over; every other non-N bottle conflicts.
    assert (others[others.bottle_id != "II.4"].adjudication_class == "conflicting").all()


def test_every_event_scope_is_classified_and_generic_events_assign_no_bottle():
    events = pd.read_csv(VALIDATION / "sanglier_2022_event_scope.csv")
    assert len(events) == 8
    generic = events[events.scope_supported_by_text == "unspecified_subset"]
    assert not generic.bottle_exposure_assignable.any()


def test_changed_event_text_fails_closed():
    events = pd.read_csv(ROOT / "results/intake/sanglier_2022_events.csv")
    events.loc[events.source_event_row == "Events!3", "Event"] = "NH3 added to all bottles"
    with pytest.raises(ValueError, match="re-adjudicate"):
        SEMANTICS.event_scope(events)


def test_admission_report_records_spec_hash_and_decision():
    report = json.loads((VALIDATION / "sanglier_2022_admission_report.json").read_text())
    from biochar_ad_kinetics.validation_admission import file_sha256

    assert report["spec_sha256"] == file_sha256(ROOT / report["spec_path"])
    assert report["dataset_role_decision"]["overall"] == "partially_admissible"
    assert report["dataset_role_decision"]["locked_external_validation"] == "blocked"
    assert report["leakage_audit"]["passed"]
    assert report["horizon_days"] == 5.5
    assert report["windows"] == {"BRL": [1, 10], "LBE": [1, 8]}
    admitted = pd.read_csv(VALIDATION / "sanglier_2022_admission.csv")
    assert set(admitted.columns).isdisjoint(
        {"volume_raw_nml", "volume_corrected_nml", "flow_nml_h", "methane_yield_nml_gvs"}
    )
    assert int(admitted.admitted_primary.sum()) == report["admitted_cycles"] == 166
