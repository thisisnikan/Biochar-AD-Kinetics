"""Synthetic fixtures only: never publish the author's private observations."""

import csv
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "marta_summary", ROOT / "scripts/build_garcia_prats_2024_summary.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    sheet = [[None] * 15 for _ in range(36)]
    sheet[9][2:] = module.DAYS
    sheet[24][2:] = module.DAYS
    for i, label in enumerate(module.LABELS):
        sheet[10 + i][1] = sheet[25 + i][1] = label
        for j, day in enumerate(module.DAYS, 2):
            missing = day > 22 and label in ("Cellulose", "B1-1", "B1-5", "B1-10")
            sheet[10 + i][j] = "-" if missing else (0 if day in (0, 23) else 10)
            sheet[25 + i][j] = "-" if missing else (0 if day in (0, 23) else 1)
    with (ROOT / "data/experimental/garcia_prats_2024_treatment_design.csv").open() as f:
        design = {r["condition_id"]: r for r in csv.DictReader(f)}
    return sheet, design


def test_two_feedings_and_source_zeros_preserved():
    rows, qc = module.transform(*fixture())
    assert qc["observed_rows"] == 119
    assert qc["missing_design_slots"] == 24
    assert qc["observations_by_feeding"] == {"1": 77, "2": 42}
    assert len(rows) == 143
    assert all(r["n_replicates_reported"] == 3 for r in rows)
    assert not any(r["replicate_level_available"] or r["model_admission"] for r in rows)
    reset = next(r for r in rows if r["source_label"] == "Control" and r["source_day"] == 23)
    assert reset["cumulative_methane_mean_ml_gvs"] == 0
    assert reset["days_since_recorded_phase_zero"] == 0
    assert not reset["phase_time_is_confirmed"]
    assert reset["source_mean_cell"] == "Hoja1!J12"
    assert reset["source_sd_cell"] == "Hoja1!J27"
    missing = next(r for r in rows if r["source_label"] == "B1-1" and r["source_day"] == 23)
    assert missing["source_mean_token"] == "-"
    assert missing["cumulative_methane_mean_ml_gvs"] is None
    assert missing["biochar_id"] == "BC1"
    assert missing["dose_pct_ts"] == "1"


@pytest.mark.parametrize(
    "fault", ["mismatched_time", "mismatched_label", "partial_missing", "negative_sd", "nan"]
)
def test_ambiguous_or_invalid_source_fails_closed(fault):
    sheet, design = fixture()
    if fault == "mismatched_time":
        sheet[24][3] = 3
    if fault == "mismatched_label":
        sheet[25][1] = "Control"
    if fault == "partial_missing":
        sheet[25][3] = "-"
    if fault == "negative_sd":
        sheet[25][3] = -1
    if fault == "nan":
        sheet[10][3] = float("nan")
    with pytest.raises(ValueError):
        module.transform(sheet, design)


def test_hash_mismatch_rejected(tmp_path):
    source = tmp_path / "source.xlsx"
    source.write_bytes(b"not the author workbook")
    with pytest.raises(ValueError, match="SHA-256"):
        module.build(source, tmp_path / "design.csv")
