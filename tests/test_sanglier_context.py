"""Protect source identities, co-interventions, and sparse sampling semantics."""

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location(
    "sanglier_context", ROOT / "scripts/build_sanglier_2022_context.py"
)
context = importlib.util.module_from_spec(spec)
spec.loader.exec_module(context)


def fixtures():
    inoc = dict(
        Lab="A",
        Batch=1,
        Bottle="b",
        Cond="control",
        Replicate=1,
        Experiment_ID="x",
        Biochar=2,
        **{"Ammonium bicarbonate": 0},
        source_row=3,
    )
    sample = dict(inoc, Days=1, Sampling="t0", source_row=2)
    sample.update({c: None for c in context.MEASUREMENTS})
    sample.update(Biochar=0, pH=7, C2=0)
    event = {"Lab": "A", "Days": 0, "Event": "Only bottle z treated", "source_row": 2}
    return [sample], [event], [inoc], []


def test_missing_methane_and_real_zeros_survive_without_imputation():
    chemistry, _events, cycles, report = context.build_context(*fixtures(), "md5", "sha256")
    assert chemistry[0]["C2"] == 0
    assert chemistry[0]["TAN"] is None
    assert "control_label_positive_inoculation_biochar" in chemistry[0]["qc_flags"]
    assert "no_methane_for_bottle_batch" in chemistry[0]["qc_flags"]
    assert not chemistry[0]["model_admission"]
    assert cycles[0]["methane_rows"] == 0
    assert report["chemistry_samples_without_methane"] == 1


def test_future_and_other_lab_events_never_leak_into_context():
    events = [
        {"Lab": "A", "Days": 1, "source_row": 2},
        {"Lab": "A", "Days": 3, "source_row": 3},
        {"Lab": "B", "Days": 0, "source_row": 4},
    ]
    assert context.contextual_events(events, "A", 1) == "Events!2"
    assert context.contextual_events(events, "A", 0) == ""


@pytest.mark.parametrize("fault", ["duplicate_inoculation", "duplicate_sample", "orphan_sample"])
def test_ambiguous_joins_fail_closed(fault):
    a, e, i, m = copy.deepcopy(fixtures())
    if fault == "duplicate_inoculation":
        i.append(i[0].copy())
    elif fault == "duplicate_sample":
        a.append(a[0].copy())
    else:
        a[0]["Bottle"] = "unknown"
    with pytest.raises(ValueError):
        context.build_context(a, e, i, m, "md5", "sha256")


def test_public_context_is_lossless_and_remains_quarantined():
    path = ROOT / "results/intake"
    chemistry = pd.read_csv(path / "sanglier_2022_chemistry.csv", keep_default_na=False)
    cycles = pd.read_csv(path / "sanglier_2022_bottle_batches.csv", keep_default_na=False)
    events = pd.read_csv(path / "sanglier_2022_events.csv", keep_default_na=False)
    qc = json.loads((path / "sanglier_2022_context_qc.json").read_text())
    assert len(chemistry) == qc["chemistry_rows"] == 923
    assert len(events) == 8
    assert len(cycles) == 363
    assert qc["chemistry_bottle_batches"] == 315
    assert cycles.methane_rows.sum() == 8403
    assert cycles.chemistry_rows.sum() == 923
    assert chemistry.source_analysis_row.nunique() == 923
    assert not chemistry.model_admission.any()
    assert not cycles.model_admission.any()
    assert (chemistry.TAN == "").sum() == 711
    assert (chemistry.C2 == "0").sum() == 13
    assert qc["chemistry_samples_without_methane"] == 15
    assert qc["qc_flag_counts"]["condition_label_disagreement"] == 6
    # This source event explains why later MBE[2]+ outcomes cannot be biochar-only effects.
    assert (
        "ammonium bicarbonate" in events.loc[events.source_event_row == "Events!3", "Event"].item()
    )
    assert qc["status"] == context.STATUS
