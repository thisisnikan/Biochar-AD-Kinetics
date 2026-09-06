"""Real-data regression checks: source identity, blanks, correction and exclusions."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from biochar_ad_kinetics.baselines import compare_experimental_baselines
from biochar_ad_kinetics.intake import validate_reactor_observations

INTAKE = Path("data/experimental/kozlowski_2025_reactor_observations.csv.gz")
LEGACY = Path("data/experimental/kozlowski_2025_bmp.csv")
REPORT = Path("results/intake/kozlowski_2025_validation.json")


def test_real_intake_preserves_source_reactors_and_expected_warnings() -> None:
    frame = pd.read_csv(INTAKE)
    report = validate_reactor_observations(frame)
    assert report.valid
    assert report.row_count == 7575
    assert report.reactor_count == 15
    assert {i.code for i in report.issues} == {"decreasing_cumulative_raw"}
    assert frame.groupby("reactor_id").size().eq(505).all()
    assert frame.source_record_id.is_unique
    saved_report = json.loads(REPORT.read_text())
    for key, value in report.to_dict().items():
        assert saved_report[key] == value


def test_individual_blank_values_and_denominators_are_preserved() -> None:
    frame = pd.read_csv(INTAKE)
    blanks = frame.loc[frame.is_inoculum_blank]
    assert len(blanks) == 1515
    assert blanks.substrate_vs_g.eq(0).all()
    assert blanks.blank_corrected_methane_ml_g_vs.isna().all()
    assert blanks.inoculum_to_substrate_vs_ratio.isna().all()
    final = blanks.loc[blanks.time_days.eq(21)].set_index("reactor_id")
    # Verified workbook Godzinowe!E522:G522, not reconstructed from a mean.
    assert final.raw_cumulative_methane_ml.to_dict() == {"K1": 461.3, "K2": 534.3, "K3": 542.8}
    assert final.source_record_id.to_dict() == {
        "K1": "Godzinowe!E522", "K2": "Godzinowe!F522", "K3": "Godzinowe!G522"
    }
    means = blanks.groupby("time_hours").raw_cumulative_methane_ml.mean()
    np.testing.assert_allclose(
        frame.blank_mean_cumulative_methane_ml, frame.time_hours.map(means), rtol=0, atol=5e-9
    )
    substrate = frame.loc[~frame.is_inoculum_blank]
    recomputed = (
        substrate.raw_cumulative_methane_ml - substrate.time_hours.map(means)
    ) / substrate.substrate_vs_g
    np.testing.assert_allclose(
        substrate.blank_corrected_methane_ml_g_vs, recomputed, rtol=0, atol=5e-9
    )


def test_legacy_measurements_and_exclusions_are_unchanged() -> None:
    frame = pd.read_csv(INTAKE)
    legacy = pd.read_csv(LEGACY)
    substrate = frame.loc[~frame.is_inoculum_blank].rename(
        columns={"treatment_id": "treatment", "replicate_id": "replicate"}
    )
    keys = ["treatment", "replicate", "time_hours"]
    merged = substrate.merge(legacy, on=keys, suffixes=("_intake", "_legacy"), validate="one_to_one")
    assert len(merged) == len(legacy) == 6060
    for field in (
        "raw_cumulative_methane_ml", "blank_mean_cumulative_methane_ml",
        "time_days", "temperature_c",
    ):
        np.testing.assert_array_equal(merged[field + "_intake"], merged[field + "_legacy"])
    # The legacy file rounded this audit-only source field to eight decimals.
    np.testing.assert_allclose(
        merged.source_reported_time_days_intake,
        merged.source_reported_time_days_legacy,
        rtol=0, atol=5e-9,
    )
    np.testing.assert_allclose(
        merged.blank_corrected_methane_ml_g_vs, merged.methane_ml_g_vs, rtol=0, atol=1e-8
    )
    np.testing.assert_array_equal(merged.qc_include, merged.included_in_benchmark)
    np.testing.assert_array_equal(merged.dose_value, merged.dose_g_l)
    assert set(frame.loc[~frame.qc_include, "reactor_id"]) == {"O+T2", "O+B3"}


def test_conflicting_control_metadata_remains_visible() -> None:
    frame = pd.read_csv(INTAKE)
    controls = frame.loc[frame.treatment_id.eq("food_waste")]
    assert controls.dose_value.eq(0).all()
    assert controls.source_dose_g_l.eq(5).all()
    assert controls.source_carbon_mass_g.eq(2).all()
    assert controls.qc_flags.str.contains("source_control_dose_conflict").all()
    assert frame.loc[frame.time_hours.gt(0), "qc_flags"].str.contains(
        "source_time_divisor_conflict"
    ).all()


def test_intake_projection_preserves_held_out_benchmark() -> None:
    frame = pd.read_csv(INTAKE)
    projected = frame.loc[~frame.is_inoculum_blank].rename(
        columns={
            "treatment_id": "treatment", "replicate_id": "replicate",
            "dose_value": "dose_g_l", "qc_include": "included_in_benchmark",
            "blank_corrected_methane_ml_g_vs": "methane_ml_g_vs",
        }
    )
    actual = compare_experimental_baselines(projected)
    legacy = compare_experimental_baselines(pd.read_csv(LEGACY))
    pd.testing.assert_frame_equal(actual, legacy, check_exact=True)


def test_wrong_source_hash_cannot_publish_intake(tmp_path) -> None:
    spec = importlib.util.spec_from_file_location(
        "kozlowski_builder", "scripts/build_kozlowski_2025_dataset.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "unverified.xlsx"
    source.write_bytes(b"unverified source")
    output, report = tmp_path / "intake.csv", tmp_path / "report.json"
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        module.build_intake_dataset(source, output, report)
    assert not output.exists()
    assert not report.exists()
