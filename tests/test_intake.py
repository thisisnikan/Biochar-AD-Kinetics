from pathlib import Path

import pandas as pd
import pytest

from biochar_ad_kinetics.intake import NUMERIC_COLUMNS, validate_reactor_observations

TEMPLATE = Path("data/templates/reactor_observations.csv")


def test_reactor_observation_template_passes() -> None:
    report = validate_reactor_observations(pd.read_csv(TEMPLATE))

    assert report.valid
    assert report.row_count == 12
    assert report.reactor_count == 6
    assert report.experiment_count == 1
    assert not report.issues


def test_duplicate_reactor_time_is_rejected() -> None:
    frame = pd.read_csv(TEMPLATE)
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)

    report = validate_reactor_observations(frame)

    assert not report.valid
    assert "duplicate_observation_key" in {issue.code for issue in report.issues}


def test_changed_reactor_metadata_is_rejected() -> None:
    frame = pd.read_csv(TEMPLATE)
    frame.loc[frame["reactor_id"].eq("biochar_r1") & frame["time_days"].eq(1), "dose_value"] = 8

    report = validate_reactor_observations(frame)

    assert not report.valid
    assert "inconsistent_reactor_metadata" in {issue.code for issue in report.issues}


def test_missing_blank_is_reported_without_inventing_one() -> None:
    frame = pd.read_csv(TEMPLATE)
    frame = frame.loc[~frame["is_inoculum_blank"]]

    report = validate_reactor_observations(frame)

    assert report.valid
    assert "missing_inoculum_blank" in {issue.code for issue in report.issues}


def test_missing_dose_unit_is_rejected() -> None:
    frame = pd.read_csv(TEMPLATE)
    frame.loc[frame["reactor_id"].eq("biochar_r1"), "dose_unit"] = pd.NA

    report = validate_reactor_observations(frame)

    assert not report.valid
    assert "invalid_dose_unit" in {issue.code for issue in report.issues}


def test_reactor_identifiers_are_scoped_to_their_experiment() -> None:
    frame = pd.read_csv(TEMPLATE)
    second = frame.copy()
    second["experiment_id"] = "run_02"
    second["temperature_c"] = 55

    report = validate_reactor_observations(pd.concat([frame, second], ignore_index=True))

    assert report.valid
    assert report.experiment_count == 2
    assert report.reactor_count == 12


def test_empty_dataset_is_rejected() -> None:
    report = validate_reactor_observations(pd.read_csv(TEMPLATE).iloc[:0])

    assert not report.valid
    assert "empty_dataset" in {issue.code for issue in report.issues}


@pytest.mark.parametrize("column", NUMERIC_COLUMNS)
@pytest.mark.parametrize("value", [float("inf"), float("-inf"), "inf"])
def test_nonfinite_measurements_are_rejected(column: str, value: object) -> None:
    frame = pd.read_csv(TEMPLATE).astype({column: object})
    frame.loc[0, column] = value

    report = validate_reactor_observations(frame)

    assert not report.valid
    assert "invalid_numeric" in {issue.code for issue in report.issues}


@pytest.mark.parametrize("unit", [None, "", " ", "g/kg"])
def test_missing_or_unknown_dose_unit_is_rejected(unit: object) -> None:
    frame = pd.read_csv(TEMPLATE)
    frame.loc[frame["reactor_id"].eq("biochar_r1"), "dose_unit"] = unit

    report = validate_reactor_observations(frame)

    assert not report.valid
    assert "invalid_dose_unit" in {issue.code for issue in report.issues}


def test_positive_dose_requires_a_physical_unit() -> None:
    frame = pd.read_csv(TEMPLATE)
    frame.loc[frame["reactor_id"].eq("biochar_r1"), "dose_unit"] = "none"

    report = validate_reactor_observations(frame)

    assert not report.valid
    assert "missing_dose_basis" in {issue.code for issue in report.issues}


def test_equivalent_numeric_times_are_duplicate_keys() -> None:
    frame = pd.read_csv(TEMPLATE).astype({"time_days": object})
    duplicate = frame.iloc[[1]].copy()
    duplicate["time_days"] = "1.0"
    frame = pd.concat([frame, duplicate], ignore_index=True)

    report = validate_reactor_observations(frame)

    assert not report.valid
    assert "duplicate_observation_key" in {issue.code for issue in report.issues}


def test_numeric_text_is_sorted_by_time_without_mutating_source() -> None:
    frame = pd.read_csv(TEMPLATE).astype({"time_days": str, "temperature_c": object})
    frame["time_days"] = frame["time_days"].map({"0": "2", "1": "10"})
    frame.loc[0, "temperature_c"] = "37.0"
    frame["is_control"] = frame["is_control"].astype(object)
    frame.loc[0, "is_control"] = "yes"
    original = frame.copy(deep=True)

    report = validate_reactor_observations(frame)

    assert report.valid
    assert not report.issues
    pd.testing.assert_frame_equal(frame, original)


def test_inoculum_blanks_do_not_replace_substrate_controls() -> None:
    frame = pd.read_csv(TEMPLATE)
    frame = frame.loc[~frame["treatment_id"].eq("substrate_control")]

    report = validate_reactor_observations(frame)
    codes = {issue.code for issue in report.issues}

    assert report.valid
    assert "missing_control" in codes
    assert "missing_inoculum_blank" not in codes


@pytest.mark.parametrize(
    ("treatment", "expected"),
    [("substrate_control", "missing_control"), ("inoculum_blank", "missing_inoculum_blank")],
)
def test_excluded_controls_do_not_satisfy_design_checks(treatment: str, expected: str) -> None:
    frame = pd.read_csv(TEMPLATE)
    frame.loc[frame["treatment_id"].eq(treatment), "qc_include"] = False

    report = validate_reactor_observations(frame)
    codes = {issue.code for issue in report.issues}

    assert report.valid
    assert expected in codes
    assert "unreplicated_treatment" in codes
    assert report.row_count == 12
    assert report.reactor_count == 6


def test_excluded_reactor_does_not_satisfy_replication_check() -> None:
    frame = pd.read_csv(TEMPLATE)
    frame.loc[frame["reactor_id"].eq("biochar_r2"), "qc_include"] = False

    report = validate_reactor_observations(frame)

    assert report.valid
    assert "unreplicated_treatment" in {issue.code for issue in report.issues}


def test_partially_excluded_reactor_still_counts_once() -> None:
    frame = pd.read_csv(TEMPLATE)
    frame.loc[frame["time_days"].eq(0), "qc_include"] = False

    report = validate_reactor_observations(frame)

    assert report.valid
    assert not report.issues


def test_fully_excluded_experiment_is_preserved_with_warning() -> None:
    frame = pd.read_csv(TEMPLATE)
    frame["qc_include"] = False

    report = validate_reactor_observations(frame)

    assert report.valid
    assert report.row_count == 12
    assert "no_included_observations" in {issue.code for issue in report.issues}
