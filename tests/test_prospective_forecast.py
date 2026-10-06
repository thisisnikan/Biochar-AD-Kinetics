"""Synthetic contract tests; no future experimental result is manufactured."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from biochar_ad_kinetics.prospective_forecast import (
    PROTOCOL,
    digest,
    evaluate,
    predict,
    write_new,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def cohort():
    return {
        "cohort_id": "SYNTHETIC_TEST_ONLY",
        "collection_start_date": "2026-10-07",
        "yield_unit": PROTOCOL["yield_unit"],
        "source_reference": "synthetic unit-test equations",
        "unit_audit_reference": "synthetic unit-test convention",
        "new_batch_declared": True,
        "outcomes_unseen_declared": True,
    }


@pytest.fixture
def inputs(tmp_path):
    prefix, endpoints = [], []
    for bottle in range(4):
        p = 200 + 20 * bottle
        identity = {"lab": "synthetic", "batch_id": "test", "bottle_id": str(bottle)}
        for t in [0, 2, 4, 6, 10, 12.5]:
            prefix.append(identity | {"time_days": t, "methane_yield": p * (1 - np.exp(-0.1 * t))})
        endpoints.append(identity | {"target_day": 21, "methane_yield": p * (1 - np.exp(-2.1))})
    prefix_path = tmp_path / "prefix.csv"
    endpoints_path = tmp_path / "endpoints.csv"
    pd.DataFrame(prefix).to_csv(prefix_path, index=False)
    pd.DataFrame(endpoints).to_csv(endpoints_path, index=False)
    return prefix_path, endpoints_path


def test_fixed_protocol_matches_committed_registration():
    assert (
        json.loads((ROOT / "data/validation/future_batch_forecast_v1.json").read_text()) == PROTOCOL
    )


def test_predict_then_evaluate_without_refitting(inputs, cohort, monkeypatch):
    prefix, endpoints = inputs
    record = predict(prefix, cohort, copy.deepcopy(PROTOCOL))
    assert len(record["predictions"]) == 4
    assert record["protocol_sha256"] == digest(PROTOCOL)
    monkeypatch.setattr(
        "biochar_ad_kinetics.prospective_forecast.fit_family",
        lambda *args: pytest.fail("evaluation must not refit"),
    )
    report = evaluate(record, prefix, endpoints)
    assert report["bottles"] == 4
    assert report["methods"]["first_order"]["mean_absolute_endpoint_error"] < 1e-6
    assert report["status"].endswith("PROSPECTIVE_STATUS_UNVERIFIED")


@pytest.mark.parametrize(
    "defect",
    [
        "future",
        "duplicate",
        "stale",
        "short",
        "missing",
        "extra_column",
        "few_bottles",
        "multiple_batch",
        "negative",
    ],
)
def test_prefix_failures(inputs, cohort, defect):
    prefix, _ = inputs
    frame = pd.read_csv(prefix)
    if defect == "future":
        frame.loc[0, "time_days"] = 13
    elif defect == "duplicate":
        frame = pd.concat([frame, frame.iloc[:1]])
    elif defect == "stale":
        frame["time_days"] *= 0.9
    elif defect == "short":
        frame = frame.iloc[1:]
    elif defect == "missing":
        frame.loc[0, "methane_yield"] = np.nan
    elif defect == "extra_column":
        frame["endpoint_yield"] = 99
    elif defect == "few_bottles":
        frame = frame[frame["bottle_id"] != 3]
    elif defect == "multiple_batch":
        frame.loc[0, "batch_id"] = "other"
    else:
        frame.loc[0, "methane_yield"] = -1
    frame.to_csv(prefix, index=False)
    with pytest.raises(ValueError):
        predict(prefix, cohort, PROTOCOL)


@pytest.mark.parametrize(
    "field,value",
    [
        ("collection_start_date", "2026-09-27"),
        ("yield_unit", "unknown"),
        ("source_reference", ""),
        ("new_batch_declared", "true"),
        ("outcomes_unseen_declared", False),
    ],
)
def test_unadmitted_cohort(inputs, cohort, field, value):
    cohort[field] = value
    with pytest.raises(ValueError):
        predict(inputs[0], cohort, PROTOCOL)


def test_protocol_drift_rejected(inputs, cohort):
    protocol = copy.deepcopy(PROTOCOL)
    protocol["target_day"] = 27
    with pytest.raises(ValueError, match="Protocol differs"):
        predict(inputs[0], cohort, protocol)


@pytest.mark.parametrize("defect", ["missing", "extra", "wrong_day", "duplicate", "nonfinite"])
def test_endpoint_population_and_horizon_fail_closed(inputs, cohort, defect):
    prefix, endpoints = inputs
    record = predict(prefix, cohort, PROTOCOL)
    frame = pd.read_csv(endpoints)
    if defect == "missing":
        frame = frame.iloc[1:]
    elif defect == "extra":
        frame.loc[0, "bottle_id"] = 99
    elif defect == "wrong_day":
        frame.loc[0, "target_day"] = 20
    elif defect == "duplicate":
        frame = pd.concat([frame, frame.iloc[:1]])
    else:
        frame.loc[0, "methane_yield"] = np.inf
    frame.to_csv(endpoints, index=False)
    with pytest.raises(ValueError):
        evaluate(record, prefix, endpoints)


def test_zero_endpoint_retained_and_relative_summary_blocked(inputs, cohort):
    prefix, endpoints = inputs
    record = predict(prefix, cohort, PROTOCOL)
    frame = pd.read_csv(endpoints)
    frame.loc[0, "methane_yield"] = 0
    frame.to_csv(endpoints, index=False)
    report = evaluate(record, prefix, endpoints)
    assert report["bottles"] == 4
    assert report["zero_endpoint_bottles"] == 1
    assert report["secondary_metric_evaluable"] is False
    assert all(
        v["mean_absolute_relative_endpoint_error"] is None for v in report["methods"].values()
    )


def test_record_and_prefix_tampering_rejected(inputs, cohort):
    prefix, endpoints = inputs
    record = predict(prefix, cohort, PROTOCOL)
    changed = copy.deepcopy(record)
    changed["predictions"][0]["predictions"]["recent_rate"] += 1
    with pytest.raises(ValueError, match="integrity"):
        evaluate(changed, prefix, endpoints)
    prefix.write_text(prefix.read_text() + "\n")
    with pytest.raises(ValueError, match="Prefix differs"):
        evaluate(record, prefix, endpoints)


def test_saved_artifact_never_overwritten(tmp_path):
    path = tmp_path / "saved.json"
    write_new(path, {"test": 1})
    with pytest.raises(FileExistsError):
        write_new(path, {"test": 2})
    assert json.loads(path.read_text()) == {"test": 1}


@pytest.mark.parametrize("defect", ["method_provenance", "code_hash", "duplicate_roster"])
def test_resealed_but_invalid_artifact_rejected(inputs, cohort, defect):
    prefix, endpoints = inputs
    record = predict(prefix, cohort, PROTOCOL)
    if defect == "method_provenance":
        record["method_sha256"] = {}
    elif defect == "code_hash":
        record["method_sha256"]["prospective_forecast.py"] = "0" * 64
    else:
        record["predictions"].append(record["predictions"][0])
    record["record_sha256"] = digest({k: v for k, v in record.items() if k != "record_sha256"})
    with pytest.raises(ValueError):
        evaluate(record, prefix, endpoints)


def test_nonconverged_fit_blocks_prediction_without_dropping_bottle(inputs, cohort, monkeypatch):
    monkeypatch.setattr(
        "biochar_ad_kinetics.prospective_forecast.fit_family", lambda *args: {"converged": False}
    )
    with pytest.raises(ValueError, match="solver failed"):
        predict(inputs[0], cohort, PROTOCOL)


def test_cli_two_stage_roundtrip(inputs, cohort, tmp_path):
    prefix, endpoints = inputs
    manifest = tmp_path / "cohort.json"
    manifest.write_text(json.dumps(cohort))
    predictions = tmp_path / "predictions.json"
    report = tmp_path / "report.json"
    command = [sys.executable, str(ROOT / "scripts/run_prospective_forecast.py")]
    subprocess.run(
        command
        + [
            "predict",
            "--prefix",
            str(prefix),
            "--cohort",
            str(manifest),
            "--output",
            str(predictions),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        command
        + [
            "evaluate",
            "--prefix",
            str(prefix),
            "--endpoints",
            str(endpoints),
            "--predictions",
            str(predictions),
            "--output",
            str(report),
        ],
        check=True,
        capture_output=True,
    )
    assert json.loads(report.read_text())["bottles"] == 4
