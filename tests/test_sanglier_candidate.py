"""Scientific safeguards for the quarantined Sanglier source intake."""

import gzip
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "results/intake/sanglier_2022_candidate.csv.gz"
QC = ROOT / "results/intake/sanglier_2022_qc.json"


def test_public_candidate_preserves_identity_and_source_conflicts():
    rows = pd.read_csv(CANDIDATE, keep_default_na=False)
    report = json.loads(QC.read_text())
    assert len(rows) == report["joined_rows"] == 8403
    assert report["status"] == "CANDIDATE_QC_ONLY_NOT_ADMITTED_FOR_FITTING_OR_VALIDATION"
    assert not rows.duplicated(["lab", "batch_id", "bottle_id", "absolute_days_lab"]).any()
    assert rows["source_amptshort_row"].nunique() == len(rows)
    assert (rows["within_batch_days"] >= 0).all()

    # The original control label and the conflicting inoculation mass must
    # remain visible together; resolving either by overwriting would erase QC.
    conflict = rows.loc[rows.qc_flags.str.contains("control_label_positive_inoculation_biochar")]
    assert len(conflict) == 64
    assert set(conflict.batch_id) == {2, 3, 4, 5}
    assert set(conflict.bottle_id) == {"II.4"}
    assert set(conflict.biochar_label_ampts) == {0}
    assert (conflict.inoculation_biochar_g > 0).all()
    assert report["qc_flag_row_counts"]["condition_label_disagreement"] == 318

    # Source zeros and empty cells are separate. Neither is imputed.
    assert (rows.volume_corrected_nml == "").sum() == 348
    assert (rows.volume_corrected_nml == "0").sum() == 348


def test_candidate_has_stable_gzip_metadata():
    with CANDIDATE.open("rb") as handle:
        header = handle.read(10)
    assert header[:2] == b"\x1f\x8b"
    assert header[4:8] == b"\0\0\0\0"
    with gzip.open(CANDIDATE, "rt") as handle:
        assert "source_inoculation_row" in handle.readline()
