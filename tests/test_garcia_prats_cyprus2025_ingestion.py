import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path("scripts/build_garcia_prats_cyprus2025_dataset.py")
SPEC = importlib.util.spec_from_file_location("build_garcia_prats_cyprus2025_dataset", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def _characteristics_sheet(biochar_ids: tuple[str, ...] = MODULE.EXPECTED_BIOCHAR_IDS) -> list[list[object]]:
    header = [
        "biochar_id", "ph", "ec_us_cm", "carbon_pct", "nitrogen_pct",
        "oxygen_pct", "hydrogen_pct", "h_c_ratio", "o_c_ratio",
    ]
    return [header] + [
        [biochar_id, 8.1, 950.0, 62.0, 1.4, 18.0, 2.1, 0.41, 0.22]
        for biochar_id in biochar_ids
    ]


def test_characteristics_requires_all_nine_expected_biochars() -> None:
    rows = MODULE.transform_characteristics(_characteristics_sheet())
    assert len(rows) == 9
    assert {row["biochar_id"] for row in rows} == set(MODULE.EXPECTED_BIOCHAR_IDS)
    q500 = next(row for row in rows if row["biochar_id"] == "Q500")
    assert q500["feedstock"] == "Q"
    assert q500["pyrolysis_temperature_c"] == 500
    assert q500["data_origin"] == "author_shared_unpublished_abstract"


def test_characteristics_rejects_a_missing_biochar() -> None:
    incomplete = MODULE.EXPECTED_BIOCHAR_IDS[:-1]
    with pytest.raises(ValueError, match="missing"):
        MODULE.transform_characteristics(_characteristics_sheet(incomplete))


def test_characteristics_rejects_an_unexpected_biochar() -> None:
    sheet = _characteristics_sheet(MODULE.EXPECTED_BIOCHAR_IDS[:-1] + ("Q999",))
    with pytest.raises(ValueError, match="unexpected"):
        MODULE.transform_characteristics(sheet)


def test_kinetics_keeps_control_and_both_doses() -> None:
    sheet = [
        ["biochar_id", "dose_pct", "lambda_days", "r_max_ml_g_vs_d", "y_max_ml_g_vs"],
        ["control", 5, 1.2, 30.0, 420.0],
        ["Q500", 5, 0.8, 35.0, 490.0],
        ["Q500", 10, 0.6, 40.0, 514.0],
    ]
    rows = MODULE.transform_kinetics(sheet)
    assert len(rows) == 3
    q500_10 = next(row for row in rows if row["biochar_id"] == "Q500" and row["dose_pct"] == 10)
    assert q500_10["y_max_ml_g_vs"] == 514.0


def test_correlations_derives_relevance_flag_rather_than_transcribing_it() -> None:
    sheet = [
        ["property", "outcome", "dose_pct", "pearson_r", "p_value"],
        ["oxygen_pct", "cmy", 5, 0.85, 0.01],
        ["ph", "cmy", 5, 0.2, 0.4],
    ]
    rows = MODULE.transform_correlations(sheet)
    relevant = {row["property"]: row["is_relevant"] for row in rows}
    assert relevant["oxygen_pct"] is True
    assert relevant["ph"] is False


def test_ad_performance_never_invents_a_chart_only_value() -> None:
    sheet = [
        [
            "biochar_id", "dose_pct", "metric", "value", "reported_standard_deviation",
            "percent_change_vs_control", "not_machine_extractable",
        ],
        ["control", 5, "cmy_ml_g_vs", 423.0, 20.0, None, "FALSE"],
        ["Q500", 5, "cmy_ml_g_vs", None, None, None, "TRUE"],
    ]
    rows = MODULE.transform_ad_performance(sheet)
    assert len(rows) == 2
    stated = next(row for row in rows if row["biochar_id"] == "control")
    chart_only = next(row for row in rows if row["biochar_id"] == "Q500")
    assert stated["value"] == 423.0
    assert stated["not_machine_extractable"] is False
    assert chart_only["value"] is None
    assert chart_only["not_machine_extractable"] is True


def test_ad_performance_drops_rows_with_neither_a_value_nor_a_flag() -> None:
    sheet = [
        ["biochar_id", "dose_pct", "metric", "value", "reported_standard_deviation",
         "percent_change_vs_control", "not_machine_extractable"],
        ["control", 5, "cmy_ml_g_vs", None, None, None, "FALSE"],
    ]
    rows = MODULE.transform_ad_performance(sheet)
    assert rows == []
