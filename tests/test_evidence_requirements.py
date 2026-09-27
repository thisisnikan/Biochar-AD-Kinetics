"""Tests for kinetic-structure, design-requirement and minimum-information tooling."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from biochar_ad_kinetics.design_requirements import (
    contrast_se,
    mean_square_components,
    minimum_bottles,
    permutation_floor,
    power_two_sample,
)
from biochar_ad_kinetics.evidence_requirements import (
    check_evidence_package,
    load_items,
    validate_evidence,
)
from biochar_ad_kinetics.kinetic_structure import (
    days_to_daily_increment_below,
    evaluate_cycle,
    modified_gompertz,
    two_pool_first_order,
)

ROOT = Path(__file__).resolve().parents[1]
REQ = ROOT / "results/requirements"
ITEMS = load_items(ROOT / "data/requirements/minimum_information_items.json")


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------- kinetics


def test_plateau_day_matches_analytic_first_order_curve():
    t = np.arange(0, 40.01, 0.5)
    y = 400 * (1 - np.exp(-0.3 * t))
    day = days_to_daily_increment_below(t, y, 0.01)
    # Solve (y(t) - y(t-1)) / y(t) < 0.01 analytically on the same grid.
    ratio = (y[2:] - y[:-2]) / y[2:]
    expected = t[2:][np.argmax(ratio < 0.01)]
    assert day == pytest.approx(expected)
    assert np.isnan(days_to_daily_increment_below(t[:10], y[:10], 0.01))


def test_structure_and_identifiability_are_separated():
    t = np.arange(0, 20.01, 0.5)
    y = two_pool_first_order(t, 250.0, 0.9, 350.0, 0.08)
    rows = {r["family"]: r for r in evaluate_cycle(t, y, 6.5)}
    assert rows["two_pool_first_order"]["full_rmse_relative_to_final"] < 1e-3
    # A single-pool sigmoid fits the whole curve worse than the true structure ...
    assert rows["modified_gompertz"]["full_rmse"] > rows["two_pool_first_order"]["full_rmse"]
    # ... and mispredicts the end from the first 6.5 days.
    assert abs(rows["modified_gompertz"]["final_relative_error"]) > 0.1
    with pytest.raises(ValueError, match="at least 6 points"):
        evaluate_cycle(t[:5], y[:5], 1.0)


def test_gompertz_data_are_recovered_from_a_long_prefix():
    t = np.arange(0, 20.01, 0.5)
    y = modified_gompertz(t, 500.0, 60.0, 1.0)
    rows = {r["family"]: r for r in evaluate_cycle(t, y, 12.5)}
    assert abs(rows["modified_gompertz"]["final_relative_error"]) < 1e-3


def test_committed_structure_summary_matches_by_cycle_table():
    by_cycle = pd.read_csv(REQ / "sanglier_2022_structure_by_cycle.csv")
    summary = pd.read_csv(REQ / "sanglier_2022_structure_summary.csv")
    report = json.loads((REQ / "sanglier_2022_structure_report.json").read_text())
    assert (
        by_cycle[["lab", "batch_id", "bottle_id"]].drop_duplicates().shape[0]
        == report["cycles_used"]
    )
    row = summary[
        (summary.population == "all_long_cycles")
        & (summary.family == "modified_gompertz")
        & (summary.cut_days == 6.5)
    ].iloc[0]
    subset = by_cycle[(by_cycle.family == "modified_gompertz") & (by_cycle.cut_days == 6.5)]
    assert row.median_abs_final_error == pytest.approx(
        subset.final_relative_error.abs().median(), rel=1e-4
    )
    # No technical-fault cycle (IV.5 / IV.8 batch 1) is used.
    faults = by_cycle[(by_cycle.bottle_id.isin(["IV.5", "IV.8"])) & (by_cycle.batch_id == 1)]
    assert faults.empty


def test_structure_build_is_reproducible_on_a_small_subset(tmp_path, monkeypatch):
    module = load("analyze_sanglier_2022_kinetic_structure")
    original = module.long_cycles
    monkeypatch.setattr(module, "long_cycles", lambda m, a: original(m, a).head(2))
    first = module.build(tmp_path / "a")
    second = module.build(tmp_path / "b")
    assert first == second
    a = pd.read_csv(tmp_path / "a/sanglier_2022_structure_by_cycle.csv")
    committed = pd.read_csv(REQ / "sanglier_2022_structure_by_cycle.csv")
    merged = a.merge(committed, on=["lab", "batch_id", "bottle_id", "family", "cut_days"])
    assert len(merged) == len(a)
    np.testing.assert_allclose(
        merged.final_relative_error_x, merged.final_relative_error_y, rtol=1e-3, atol=1e-5
    )


# ---------------------------------------------------------------- design


def test_design_formulas():
    assert contrast_se(0.01, 0.04, 4, 4) == pytest.approx(np.sqrt(2 * (0.01 + 0.01) / 4))
    assert permutation_floor(3) == pytest.approx(0.1)
    assert permutation_floor(4) == pytest.approx(2 / 70)
    low = power_two_sample(np.log(1.1), 0.05, 10)
    high = power_two_sample(np.log(1.1), 0.02, 10)
    assert 0 < low < high <= 1
    assert power_two_sample(np.log(1.2), 1e-4, 6) == pytest.approx(1.0)
    n = minimum_bottles(0.0, 0.004, 0.10, 10)
    assert n is not None and n >= 4 and permutation_floor(n) < 0.05


def test_mean_square_components_recover_simulated_variances():
    rng = np.random.default_rng(1)
    rows = []
    for arm in ("C", "T"):
        for b in range(40):
            bottle_effect = rng.normal(0, 0.1)
            for batch in range(12):
                rows.append(
                    {
                        "arm": arm,
                        "unit": f"{arm}{b}",
                        "batch": batch,
                        "y": 0.3 * (arm == "T") + 0.05 * batch + bottle_effect + rng.normal(0, 0.2),
                    }
                )
    comp = mean_square_components(pd.DataFrame(rows), "y", "batch", "arm", "unit")
    assert comp["sigma2_unit"] == pytest.approx(0.01, rel=0.5)
    assert comp["sigma2_residual"] == pytest.approx(0.04, rel=0.1)


def test_design_outputs_are_reproducible(tmp_path):
    report = load("analyze_design_requirements").build(tmp_path)
    committed = json.loads((REQ / "design_requirements.json").read_text())
    assert report["scenarios"] == committed["scenarios"]
    pd.testing.assert_frame_equal(
        pd.read_csv(tmp_path / "design_power_table.csv"),
        pd.read_csv(REQ / "design_power_table.csv"),
        rtol=1e-6,
    )


# ---------------------------------------------------------------- scorecard


def test_evidence_grid_is_complete_and_no_dataset_is_ready():
    evidence = pd.read_csv(ROOT / "data/requirements/dataset_evidence.csv")
    validate_evidence(evidence, ITEMS)
    scorecard = pd.read_csv(REQ / "dataset_scorecard.csv")
    assert len(scorecard) == evidence.dataset.nunique() == 8
    assert not scorecard.ready_for_cross_study_use.any()


def test_evidence_validation_fails_closed():
    evidence = pd.read_csv(ROOT / "data/requirements/dataset_evidence.csv")
    with pytest.raises(ValueError, match="missing items"):
        validate_evidence(evidence.iloc[1:], ITEMS)
    bad = evidence.copy()
    bad.loc[0, "status"] = "probably"
    with pytest.raises(ValueError, match="Invalid statuses"):
        validate_evidence(bad, ITEMS)
    bad = evidence.copy()
    bad.loc[0, "evidence"] = " "
    with pytest.raises(ValueError, match="evidence statement"):
        validate_evidence(bad, ITEMS)


def test_optimistic_curation_contradicting_data_stops_the_scorecard(tmp_path, monkeypatch):
    module = load("score_dataset_requirements")
    evidence = pd.read_csv(module.EVIDENCE)
    mask = (evidence.dataset == "kozlowski_2025") & (evidence.item_id == "dose_levels_ge3")
    evidence.loc[mask, "status"] = "yes"
    patched = tmp_path / "evidence.csv"
    evidence.to_csv(patched, index=False)
    monkeypatch.setattr(module, "EVIDENCE", patched)
    with pytest.raises(SystemExit, match="contradicts committed data"):
        module.build(tmp_path / "out")


def test_scorecard_rebuild_is_identical(tmp_path):
    load("score_dataset_requirements").build(tmp_path)
    for name in ("dataset_scorecard.csv", "dataset_item_matrix.csv", "scorecard_report.json"):
        assert (tmp_path / name).read_bytes() == (REQ / name).read_bytes(), name


# ---------------------------------------------------------------- contributor package


def synthetic_package():
    rows = []
    t = np.arange(0, 25.01, 1.0)
    design = [("blank", "none", 0.0, True, True), ("control", "none", 0.0, True, False)]
    design += [(f"{m}_{d}", m, d, False, False) for m in ("bc1", "bc2") for d in (1.0, 2.0, 4.0)]
    for treatment, material, dose, control, blank in design:
        for rep in (1, 2, 3):
            reactor = f"{treatment}_r{rep}"
            curve = (60 if blank else 400 + 10 * dose) * (1 - np.exp(-0.35 * t))
            for ti, yi in zip(t, curve, strict=True):
                rows.append(
                    {
                        "study_id": "s",
                        "experiment_id": "e",
                        "reactor_id": reactor,
                        "treatment_id": treatment,
                        "replicate_id": rep,
                        "time_days": ti,
                        "temperature_c": 37,
                        "is_control": control,
                        "is_inoculum_blank": blank,
                        "substrate_id": "none" if blank else "fw",
                        "inoculum_id": "inoc",
                        "material_id": material,
                        "dose_value": dose,
                        "dose_unit": "none" if material == "none" and dose == 0 else "g_l",
                        "raw_cumulative_methane_ml": yi,
                        "blank_corrected_methane_ml_g_vs": None if blank else yi / 2,
                        "qc_include": True,
                        "qc_flags": "",
                        "data_origin": "synthetic",
                        "source_record_id": f"{reactor}:{ti}",
                    }
                )
    observations = pd.DataFrame(rows)
    materials = pd.DataFrame(
        [
            {
                "material_id": m,
                "feedstock": "wood",
                "pyrolysis_temperature_c": "550",
                "residence_time_min": "60",
                "bet_surface_area_m2_g": "120",
                "electrical_conductivity_us_cm": "400",
                "ph": "9",
                "ash_pct": "5",
                "c_pct": "75",
                "h_pct": "2",
                "n_pct": "0.5",
                "o_pct": "10",
                "particle_size_um": "500",
                "measurement_source": "synthetic",
            }
            for m in ("bc1", "bc2")
        ]
    )
    reactors = observations.drop_duplicates("reactor_id")
    interventions = pd.DataFrame(
        {
            "study_id": "s",
            "experiment_id": "e",
            "reactor_id": reactors.reactor_id,
            "time_days": 0,
            "intervention": "start",
            "amount": np.nan,
            "amount_unit": "",
            "scope": "reactor",
            "source_record_id": "log:" + reactors.reactor_id,
        }
    )
    declarations = {
        item: {"status": "yes", "evidence": "synthetic method statement"}
        for item in (
            "methane_unit_verified",
            "substrate_inoculum_characterized",
            "stability_chemistry_with_units",
            "redistributable_source",
        )
    }
    return observations, materials, interventions, declarations


def test_complete_synthetic_package_is_ready():
    obs, mat, log, dec = synthetic_package()
    report = check_evidence_package(obs, mat, log, ITEMS, dec)
    assert report["errors"] == {}
    assert report["blocking_critical_items"] == []
    assert report["ready_for_cross_study_use"]


def test_package_fails_closed_on_missing_or_overriding_information():
    obs, mat, log, dec = synthetic_package()
    blank = mat.copy()
    blank.loc[0, "bet_surface_area_m2_g"] = ""
    assert "materials" in check_evidence_package(obs, blank, log, ITEMS, dec)["errors"]
    stray = log.copy()
    stray.loc[0, "reactor_id"] = "ghost"
    assert "interventions" in check_evidence_package(obs, mat, stray, ITEMS, dec)["errors"]
    generic = log.copy()
    generic.loc[0, "scope"] = "lab_unspecified"
    report = check_evidence_package(obs, mat, generic, ITEMS, dec)
    assert report["item_status"]["co_interventions_per_reactor"] == "partial"
    assert not report["ready_for_cross_study_use"]
    override = {**dec, "run_to_plateau": {"status": "yes", "evidence": "trust me"}}
    assert "declarations" in check_evidence_package(obs, mat, log, ITEMS, override)["errors"]
    short = obs[obs.time_days <= 6]
    assert (
        check_evidence_package(short, mat, log, ITEMS, dec)["item_status"]["run_to_plateau"] == "no"
    )


def test_cli_check_evidence_on_templates(monkeypatch, capsys):
    from biochar_ad_kinetics import cli

    monkeypatch.chdir(ROOT)
    monkeypatch.setattr(
        "sys.argv",
        [
            "biochar-ad",
            "check-evidence",
            "data/templates/reactor_observations.csv",
            "--materials",
            "data/templates/biochar_materials.csv",
            "--interventions",
            "data/templates/intervention_log.csv",
        ],
    )
    cli.main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["intake_valid"] and not payload["ready_for_cross_study_use"]
    assert "run_to_plateau" in payload["blocking_critical_items"]
