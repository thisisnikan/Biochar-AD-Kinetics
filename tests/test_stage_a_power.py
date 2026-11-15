import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from biochar_ad_kinetics.model import BatchCondition, effective_kinetics
from biochar_ad_kinetics.stage_a_power import (
    DESIGNS,
    MODEL_ORDER,
    REFERENCE_DOSE_G_L,
    STAGE_A_PARSIMONY_MARGIN,
    TRUTH_TO_MODEL,
    recovery_table,
    select_model,
    simulate_design,
    stage_a_decision,
    truth_parameters,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "stage-a-power"


def _potential(truth: str, dose: float) -> float:
    return effective_kinetics(BatchCondition(dose, 37.0), truth_parameters(truth, 0.15))[0]


def test_truths_share_the_effect_at_the_reference_dose():
    baseline = _potential("no_dose_effect", 0.0)
    assert _potential("no_dose_effect", 40.0) == pytest.approx(baseline)
    for truth in ("log_linear", "log_quadratic"):
        assert _potential(truth, 0.0) == pytest.approx(baseline)
        assert _potential(truth, REFERENCE_DOSE_G_L) == pytest.approx(1.15 * baseline)


def test_quadratic_truth_peaks_at_reference_and_linear_truth_keeps_rising():
    assert _potential("log_quadratic", 70.0) < _potential("log_quadratic", REFERENCE_DOSE_G_L)
    assert _potential("log_quadratic", 2.0) < _potential("log_quadratic", REFERENCE_DOSE_G_L)
    assert _potential("log_linear", 70.0) > _potential("log_linear", REFERENCE_DOSE_G_L)


def test_unknown_truth_is_rejected():
    with pytest.raises(ValueError, match="Unknown truth"):
        truth_parameters("sigmoid", 0.15)


def test_simulated_design_has_the_stage_a_structure():
    design = DESIGNS[0]
    frame = simulate_design(
        design, truth_parameters("log_linear", 0.15), 0.03, np.random.default_rng(1)
    )
    assert frame["batch_id"].nunique() == len(design.doses_g_l) * design.replicates
    assert frame.groupby("validation_dose_id")["dose_g_l"].nunique().eq(1).all()
    assert frame.groupby("batch_id")["validation_reactor_id"].nunique().eq(1).all()
    assert sorted(frame["dose_g_l"].unique()) == sorted(float(d) for d in design.doses_g_l)


def test_every_design_passes_the_minimum_stage_a_gate():
    for design in DESIGNS:
        assert 0 in design.doses_g_l
        assert sum(dose > 0 for dose in design.doses_g_l) >= 3
        assert design.replicates >= 3


def test_parsimony_rule_prefers_the_simpler_candidate_within_the_margin():
    scores = {
        f"all__{MODEL_ORDER[0]}": 10.0,
        f"all__{MODEL_ORDER[1]}": 9.5,
        f"all__{MODEL_ORDER[2]}": 6.0,
    }
    assert select_model(scores, "all", 0.0) == MODEL_ORDER[2]
    assert select_model(scores, "all", 0.10) == MODEL_ORDER[2]
    assert select_model(scores, "all", 0.50) == MODEL_ORDER[0]
    scores[f"all__{MODEL_ORDER[2]}"] = 9.4
    assert select_model(scores, "all", 0.0) == MODEL_ORDER[2]
    assert select_model(scores, "all", 0.10) == MODEL_ORDER[0]


def test_recovery_table_counts_selections():
    rows = []
    for index, winner in enumerate([MODEL_ORDER[1]] * 3 + [MODEL_ORDER[0]]):
        scores = {f"{folds}__{model}": 10.0 for folds in ("all", "interior") for model in MODEL_ORDER}
        scores[f"all__{winner}"] = 5.0
        rows.append(
            {"design": "d", "truth": "log_linear", "reactor_log_sd": 0.03, "simulation": index}
            | scores
        )
    table = recovery_table(pd.DataFrame(rows), {"lowest": ("all", 0.0)})
    assert table.loc[0, "share_correct"] == pytest.approx(0.75)
    assert table.loc[0, "simulations"] == 4


def test_committed_recovery_table_matches_committed_simulations():
    simulations = pd.read_csv(RESULTS / "simulations.csv")
    report = json.loads((RESULTS / "report.json").read_text())
    rules = {name: (rule["folds"], rule["margin"]) for name, rule in report["rules"].items()}
    fresh = recovery_table(simulations, rules)
    committed = pd.read_csv(RESULTS / "recovery.csv")
    assert len(fresh) == len(committed)
    np.testing.assert_allclose(fresh["share_correct"], committed["share_correct"], atol=1e-3)
    assert set(simulations["truth"]) == set(TRUTH_TO_MODEL)
    counts = simulations.groupby(["design", "truth", "reactor_log_sd"]).size()
    assert counts.eq(report["simulations_per_scenario"]).all()


def test_frozen_specification_matches_code_and_committed_evidence():
    import hashlib

    spec = json.loads((ROOT / "data" / "validation" / "stage_a_dose_v1.json").read_text())
    assert spec["status"] == "FROZEN_BEFORE_ANY_STAGE_A_DATA"
    assert spec["decision_rule"]["parsimony_margin"] == STAGE_A_PARSIMONY_MARGIN
    assert spec["candidates"] == list(MODEL_ORDER)
    for relative, expected in spec["evidence_sha256"].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected


def test_frozen_rule_limits_false_dose_effects_in_committed_simulations():
    recovery = pd.read_csv(RESULTS / "recovery.csv")
    frozen = recovery[
        (recovery["rule"] == "parsimony_10pct_all_doses") & (recovery["truth"] == "no_dose_effect")
    ]
    plain = recovery[
        (recovery["rule"] == "lowest_rmse_all_doses") & (recovery["truth"] == "no_dose_effect")
    ]
    assert frozen["share_correct"].min() >= 0.8
    assert frozen["share_correct"].min() > plain["share_correct"].min()


def test_stage_a_decision_applies_the_margin():
    decision = stage_a_decision(
        {MODEL_ORDER[0]: 10.0, MODEL_ORDER[1]: 9.5, MODEL_ORDER[2]: 9.4}
    )
    assert decision["selected_model"] == MODEL_ORDER[0]
    assert decision["lowest_rmse_model"] == MODEL_ORDER[2]
    with pytest.raises(ValueError, match="Missing Stage A candidates"):
        stage_a_decision({MODEL_ORDER[0]: 1.0})
