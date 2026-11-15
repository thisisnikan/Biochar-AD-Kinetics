import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from biochar_ad_kinetics.blank_sensitivity import (
    REFERENCE_SCENARIO,
    SCENARIOS,
    run_blank_sensitivity,
    scenario_frame,
    summarize,
)

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "data" / "experimental" / "kozlowski_2025_bmp.csv"
INTAKE = ROOT / "data" / "experimental" / "kozlowski_2025_reactor_observations.csv.gz"
RESULTS = ROOT / "results" / "blank-sensitivity"


@pytest.fixture(scope="module")
def inputs():
    return pd.read_csv(BENCHMARK), pd.read_csv(INTAKE)


@pytest.fixture(scope="module")
def results(inputs):
    return run_blank_sensitivity(*inputs)


def test_reference_scenario_reproduces_committed_yields(inputs):
    benchmark, intake = inputs
    frame = scenario_frame(benchmark, intake, SCENARIOS[0])
    assert SCENARIOS[0].name == REFERENCE_SCENARIO
    np.testing.assert_allclose(
        frame["methane_ml_g_vs"], benchmark["methane_ml_g_vs"], rtol=0, atol=1e-7
    )


def test_running_maximum_only_changes_readings_after_the_k1_decrease(inputs):
    benchmark, intake = inputs
    reference = scenario_frame(benchmark, intake, SCENARIOS[0])
    repaired = scenario_frame(benchmark, intake, SCENARIOS[1])
    changed = reference.loc[
        ~np.isclose(reference["methane_ml_g_vs"], repaired["methane_ml_g_vs"]), "time_hours"
    ]
    assert not changed.empty
    assert changed.min() >= 469


def test_conclusions_are_stable_across_blank_scenarios(results):
    summary = summarize(results)
    assert all(summary["full_ranking_identical_to_published"].values())
    assert all(
        models == ["modified_gompertz"] for models in summary["best_model_by_scenario"].values()
    )
    assert summary["effect_sign_changes"] == []
    assert summary["max_abs_final_yield_change_percent"] < 2.0
    assert summary["max_abs_effect_shift_percentage_points"] < 2.0


def test_committed_outputs_match_a_fresh_run(results):
    report = json.loads((RESULTS / "report.json").read_text())
    summary = summarize(results)
    assert report["max_abs_final_yield_change_percent"] == pytest.approx(
        summary["max_abs_final_yield_change_percent"], abs=1e-3
    )
    assert report["effect_sign_changes"] == summary["effect_sign_changes"]
    committed = pd.read_csv(RESULTS / "final_yields.csv")
    fresh = results["final_yields"]
    assert committed["scenario"].tolist() == fresh["scenario"].tolist()
    np.testing.assert_allclose(
        committed["final_yield_ml_g_vs"], fresh["final_yield_ml_g_vs"], rtol=1e-4
    )


def test_incomplete_blank_set_is_rejected(inputs):
    benchmark, intake = inputs
    without_k3 = intake.loc[intake["reactor_id"] != "K3"]
    with pytest.raises(ValueError, match="Three complete"):
        scenario_frame(benchmark, without_k3, SCENARIOS[0])
