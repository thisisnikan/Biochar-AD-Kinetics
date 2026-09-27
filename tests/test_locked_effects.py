"""Unit-level effect statistics and committed locked-evaluation outputs."""

import filecmp
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from biochar_ad_kinetics.locked_effects import (
    balanced_variance_decomposition,
    exact_permutation_p,
    verdict,
    welch_log_ratio,
)

ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "results/validation"


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_welch_interval_matches_textbook_values():
    out = welch_log_ratio(np.array([1.0, 2.0, 3.0]), np.array([0.0, 1.0]))
    assert out["log_response_ratio"] == pytest.approx(1.5)
    assert out["se"] == pytest.approx(math.sqrt(1 / 3 + 0.5 / 2))
    assert out["welch_df"] == pytest.approx((1 / 3 + 0.25) ** 2 / ((1 / 3) ** 2 / 2 + 0.25**2))


def test_single_unit_arm_is_not_evaluable():
    out = welch_log_ratio(np.array([1.0]), np.array([0.0, 1.0]))
    assert math.isnan(out["ci_low"])
    assert verdict(out["ci_low"], out["ci_high"], 1, 2) == "not_evaluable"


def test_permutation_floor_reflects_design_size():
    perm = exact_permutation_p(np.array([3.0, 4.0, 5.0]), np.array([0.0, 1.0, 2.0]))
    assert perm["relabellings"] == 20
    assert perm["permutation_p_floor"] == pytest.approx(0.1)
    assert perm["permutation_p"] == pytest.approx(0.1)
    unequal = exact_permutation_p(np.array([3.0, 4.0, 5.0]), np.array([0.0, 1.0]))
    assert unequal["relabellings"] == 10
    assert unequal["permutation_p_floor"] == pytest.approx(0.1)
    assert unequal["permutation_p"] >= unequal["permutation_p_floor"]


def test_variance_components_sum_to_one_and_require_balance():
    rows = []
    for unit, arm, shift in (("a", "C", 0.0), ("b", "C", 0.1), ("c", "T", 1.0), ("d", "T", 0.9)):
        for batch, lot in ((1, 0.0), (2, 2.0), (3, -1.0)):
            rows.append({"u": unit, "arm": arm, "batch": batch, "y": shift + lot + 0.01 * batch})
    frame = pd.DataFrame(rows)
    out = balanced_variance_decomposition(frame, "y", "batch", "arm", "u")
    total = sum(
        out[k] for k in ("batch_share", "arm_share", "unit_within_arm_share", "residual_share")
    )
    assert total == pytest.approx(1.0)
    assert out["batch_share"] > out["arm_share"] > out["unit_within_arm_share"]
    with pytest.raises(ValueError, match="one value per unit"):
        balanced_variance_decomposition(frame.iloc[1:], "y", "batch", "arm", "u")


def test_locked_evaluation_rebuild_is_byte_identical(tmp_path):
    load("run_sanglier_2022_locked_evaluation").build(tmp_path)
    for name in (
        "sanglier_2022_locked_effects.csv",
        "sanglier_2022_bottle_summaries.csv",
        "sanglier_2022_variance_components.csv",
        "sanglier_2022_cycle_kinetics.csv",
        "sanglier_2022_truncation_extrapolation.csv",
        "sanglier_2022_generalization_failure_partition.csv",
        "sanglier_2022_locked_evaluation.json",
    ):
        assert filecmp.cmp(tmp_path / name, VALIDATION / name, shallow=False), name


def test_locked_evaluation_refuses_a_drifted_spec(tmp_path, monkeypatch):
    module = load("run_sanglier_2022_locked_evaluation")
    drifted = tmp_path / "spec.json"
    spec = json.loads(module.SPEC.read_text())
    spec["temporal_definition"]["expected_horizon_days"] = 5.0
    drifted.write_text(json.dumps(spec))
    monkeypatch.setattr(module, "SPEC", drifted)
    with pytest.raises(SystemExit, match="Spec changed"):
        module.build(tmp_path / "out")


def test_locked_results_are_reported_honestly():
    result = json.loads((VALIDATION / "sanglier_2022_locked_evaluation.json").read_text())
    assert result["not_external_validation"]
    assert result["primary_verdicts"]["BRL MBE[1]"] == "not_evaluable"
    assert all(d["locked"] is False for d in result["protocol_deviations"])
    assert result["independent_units"]["ml_defensible"] is False
    assert result["development_comparator"]["commensurate"] is False
    effects = pd.read_csv(VALIDATION / "sanglier_2022_locked_effects.csv")
    assert not effects.loc[effects.analysis.str.startswith("D1"), "locked"].any()
    assert effects.loc[~effects.analysis.str.startswith("D1"), "locked"].all()
    sa1 = set(effects.loc[effects.analysis == "SA1_include_plus_arms", "arm"])
    assert {"[1]+", "[2]+"} <= sa1
    # Bottles, not time rows, are the inferential units.
    evaluable = effects.dropna(subset=["ci_low"])
    assert evaluable[["n_treatment_units", "n_control_units"]].max().max() <= 3


def test_failure_partition_uses_allowed_status_vocabulary():
    partition = pd.read_csv(VALIDATION / "sanglier_2022_generalization_failure_partition.csv")
    assert len(partition) == 11
    assert set(partition.evidence_status) <= {
        "supported",
        "plausible_but_unproven",
        "contradicted",
        "unknown_due_to_missing_data",
    }


def test_heitkamp_envelope_is_plant_level_and_blocks_unresolved_comparisons(tmp_path):
    module = load("analyze_heitkamp_2021_envelope")
    report = module.build(tmp_path)
    for name in ("heitkamp_2021_plant_envelope.csv", "heitkamp_2021_envelope_report.json"):
        assert filecmp.cmp(tmp_path / name, VALIDATION / name, shallow=False), name
    assert report["unit_of_analysis"] == "plant"
    assert "methane_productivity_validation" in report["forbidden_uses"]
    assert {"TAN", "C2", "C3", "TS", "VS", "sCOD"} <= set(
        report["blocked_cross_source_comparisons"]
    )
    assert report["tvfa_internal_consistency"]["plant_days_tvfa_below_acetic"] > 0
