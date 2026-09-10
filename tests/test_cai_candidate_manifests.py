import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "data" / "candidate_manifests" / "cai_jiao_bmp_records_583_594.csv"
AGGREGATE = ROOT / "data" / "candidate_manifests" / "cai_2016_aggregate_evidence.csv"
SOURCE_MANIFEST = ROOT / "data" / "external_source_manifest.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_cai_candidate_rows_remain_blocked_and_unrecovered_values_blank():
    rows = read_csv(CANDIDATE)

    assert [int(row["query_no"]) for row in rows] == list(range(583, 595))
    assert all(row["qc_status"] == "BLOCKED_OFFICIAL_EXPORT" for row in rows)
    assert all(row["import_eligible"] == "No" for row in rows)

    unrecovered_fields = (
        "isr_i_s_vs",
        "biochar_dose_g_g_waste",
        "pmax_ml_ch4_g_vs",
        "rmax_ml_ch4_g_vs_d",
        "lag_days",
    )
    assert all(row[field] == "" for row in rows for field in unrecovered_fields)


def test_cai_aggregate_evidence_remains_reference_only():
    rows = read_csv(AGGREGATE)

    assert len(rows) == 3
    assert all(row["model_use"] == "reference_only" for row in rows)
    assert all(
        row["evidence_level"] == "abstract_reported_aggregate" for row in rows
    )
    assert rows[0]["lag_shortening_direction_verified"] == "No"
    assert all(
        row["lag_shortening_direction_verified"] == "Yes" for row in rows[1:]
    )


def test_cai_manifest_identifiers_and_paths_are_consistent():
    manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    source = next(
        item
        for item in manifest["sources"]
        if item["study_id"] == "cai_jiao_tongji_thesis_bmp"
    )

    assert source["bmp_query_numbers"] == list(range(583, 595))
    assert source["expected_file"] == CANDIDATE.name
    assert ROOT.joinpath(source["candidate_manifest"]).is_file()
    assert ROOT.joinpath(source["aggregate_context_file"]).is_file()
