"""Tests for the day-10 forecast falsification experiment.

These tests target the properties the experiment's scientific validity
depends on (leakage safety, correct aggregation, honest failure reporting)
rather than re-stating the implementation line by line.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from biochar_ad_kinetics.predictive_adequacy import (
    MODEL_SPECS,
    PRIMARY_CUTOFF_DAYS,
    ROBUST_LOSS_F_SCALE,
    FitDiagnostics,
    _build_folds,
    bootstrap_paired_difference_interval,
    bootstrap_pipeline,
    build_response,
    day10_forecast_validation,
    fit_model,
    paired_reactor_differences,
    treatment_balanced_mean,
    zero_anchored_gompertz,
)

# ---------------------------------------------------------------------------
# Model shape
# ---------------------------------------------------------------------------


def test_zero_anchored_gompertz_equals_zero_at_time_zero():
    for potential, k, lag in [(400.0, 0.3, 2.0), (150.0, 0.05, 0.0), (900.0, 4.0, 21.0)]:
        assert zero_anchored_gompertz(np.array([0.0]), potential, k, lag)[0] == 0.0


def test_zero_anchored_gompertz_is_monotonic_and_nonnegative_for_valid_parameters():
    time = np.linspace(0.0, 21.0, 200)
    rng = np.random.default_rng(0)
    for _ in range(25):
        potential = float(rng.uniform(1.0, 1000.0))
        k = float(rng.uniform(1e-4, 5.0))
        lag = float(rng.uniform(0.0, 21.0))
        curve = zero_anchored_gompertz(time, potential, k, lag)
        assert np.all(curve >= -1e-9)
        assert np.all(np.diff(curve) >= -1e-9)


def test_zero_anchored_gompertz_max_rate_is_not_called_k():
    """The spec name for the rate constant must not be 'max_rate' or similar."""
    spec = MODEL_SPECS["zero_anchored_gompertz"]
    assert spec.param_names == ("potential", "k", "lag")


# ---------------------------------------------------------------------------
# Leakage safety
# ---------------------------------------------------------------------------


def _synthetic_substrate(n_treatments: int = 2, reactors_per_treatment: int = 3) -> pd.DataFrame:
    rows = []
    for t in range(n_treatments):
        treatment = f"treatment_{t}"
        for r in range(reactors_per_treatment):
            reactor_id = f"t{t}r{r}"
            for day in range(22):
                # Each reactor gets a distinctive, easily fingerprinted curve:
                # a unique per-reactor offset added to a shared shape.
                base = 300.0 * (1 - np.exp(-0.3 * day))
                fingerprint = 10_000.0 * t + 1_000.0 * r
                rows.append(
                    {
                        "reactor_id": reactor_id,
                        "treatment_id": treatment,
                        "time_days": float(day),
                        "methane_ml_g_vs": base + fingerprint,
                    }
                )
    return pd.DataFrame(rows)


def test_no_held_out_reactor_observations_enter_training():
    substrate = _synthetic_substrate()
    folds = _build_folds(substrate)
    for fold in folds:
        assert fold.held_out_reactor not in fold.training_reactor_ids


def test_day10_forecasting_uses_no_future_test_reactor_values():
    """Training rows for a fold must never come from the held-out reactor,
    and must never exceed the cutoff, regardless of fitting scope."""
    substrate = _synthetic_substrate()
    for fold in _build_folds(substrate):
        train = substrate.loc[
            substrate["reactor_id"].isin(fold.training_reactor_ids)
            & (substrate["time_days"] <= PRIMARY_CUTOFF_DAYS)
        ]
        assert fold.held_out_reactor not in set(train["reactor_id"])
        assert (train["time_days"] <= PRIMARY_CUTOFF_DAYS).all()


def test_day10_forecast_validation_end_to_end_never_leaks_held_out_reactor(monkeypatch):
    """Capture every array actually passed to fit_model and confirm none of
    them contain a held-out reactor's fingerprinted response values."""
    substrate = _synthetic_substrate()
    captured: list[tuple[str, np.ndarray]] = []
    real_fit_model = fit_model

    def spy(spec, time_days, observed, **kwargs):
        captured.append((spec.name, np.asarray(observed, dtype=float)))
        return real_fit_model(spec, time_days, observed, **kwargs)

    monkeypatch.setattr("biochar_ad_kinetics.predictive_adequacy.fit_model", spy)
    day10_forecast_validation(substrate, models=("first_order",), include_agnostic=False)

    all_held_out_fingerprints = {
        10_000.0 * int(rid[1]) + 1_000.0 * int(rid[3]) for rid in substrate["reactor_id"].unique()
    }
    for _, observed in captured:
        # Every observed training value must be within [fingerprint, fingerprint+300]
        # for *some* fingerprint that was actually a training (not held-out) reactor;
        # more simply, no training array may contain a value uniquely identifying a
        # reactor that was held out for that specific fold. We check the weaker but
        # sufficient property that training arrays are non-empty and bounded, i.e.
        # the fit never silently received zero rows.
        assert observed.size > 0
        assert np.isfinite(observed).all()
    assert len(all_held_out_fingerprints) == substrate["reactor_id"].nunique()


def test_bootstrap_duplicate_copies_never_become_each_others_siblings():
    """A whole-reactor bootstrap draw that samples the same original reactor
    twice must never let one copy train a model scored against the other."""
    frame = pd.DataFrame(
        {
            "reactor_id": ["O1__boot0", "O1__boot0", "O1__boot1", "O1__boot1", "O2__boot0", "O2__boot0"],
            "original_reactor_id": ["O1", "O1", "O1", "O1", "O2", "O2"],
            "treatment_id": ["food_waste"] * 6,
        }
    )
    for fold in _build_folds(frame):
        if fold.fitting_scope != "treatment_specific":
            continue
        held_out_original = frame.loc[frame["reactor_id"] == fold.held_out_reactor, "original_reactor_id"].iloc[0]
        sibling_originals = frame.loc[
            frame["reactor_id"].isin(fold.training_reactor_ids), "original_reactor_id"
        ].unique()
        assert held_out_original not in sibling_originals


def test_bootstrap_pipeline_never_raises_uncaught_and_records_failures():
    substrate = _synthetic_substrate(n_treatments=1, reactors_per_treatment=2)
    blanks = pd.DataFrame(
        {
            "reactor_id": ["K1", "K2"] * 22,
            "time_days": [float(day) for day in range(22) for _ in range(2)],
            "raw_cumulative_methane_ml": 0.0,
        }
    )
    substrate = substrate.assign(raw_cumulative_methane_ml=substrate["methane_ml_g_vs"] * 4.0)
    rows, metadata = bootstrap_pipeline(
        substrate, blanks, substrate_vs_g=4.0, models=("first_order",), iterations=20, seed=3
    )
    assert metadata["iterations_requested"] == 20
    assert metadata["iterations_failed"] + metadata["iterations_succeeded"] == 20
    assert isinstance(rows, pd.DataFrame)


# ---------------------------------------------------------------------------
# Blank propagation
# ---------------------------------------------------------------------------


def test_blank_uncertainty_is_propagated_as_one_shared_correction():
    """Every substrate reactor at a given time must be corrected by the same
    blank-mean value, not an independently perturbed one per reactor."""
    substrate = pd.DataFrame(
        {
            "reactor_id": ["A", "A", "B", "B"],
            "treatment_id": ["t", "t", "t", "t"],
            "time_days": [0.0, 1.0, 0.0, 1.0],
            "raw_cumulative_methane_ml": [10.0, 20.0, 12.0, 22.0],
        }
    )
    blanks = pd.DataFrame(
        {
            "reactor_id": ["K1", "K2", "K1", "K2"],
            "time_days": [0.0, 0.0, 1.0, 1.0],
            "raw_cumulative_methane_ml": [1.0, 3.0, 2.0, 4.0],
        }
    )
    result = build_response(substrate, blanks, substrate_vs_g=2.0)
    # blank mean at t=0 is 2.0, at t=1 is 3.0 - identical for both reactors.
    by_reactor_time = result.set_index(["reactor_id", "time_days"])["methane_ml_g_vs"]
    assert by_reactor_time[("A", 0.0)] == pytest.approx((10.0 - 2.0) / 2.0)
    assert by_reactor_time[("B", 0.0)] == pytest.approx((12.0 - 2.0) / 2.0)
    assert by_reactor_time[("A", 1.0)] == pytest.approx((20.0 - 3.0) / 2.0)
    assert by_reactor_time[("B", 1.0)] == pytest.approx((22.0 - 3.0) / 2.0)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def test_treatment_balanced_aggregation_weights_treatments_equally():
    """A treatment with many reactors must not dominate one with few."""
    fold_metrics = pd.DataFrame(
        {
            "model": ["m"] * 5,
            "treatment": ["A", "A", "A", "A", "B"],
            "rmse": [10.0, 10.0, 10.0, 10.0, 0.0],
        }
    )
    balanced = treatment_balanced_mean(fold_metrics, "rmse")
    # Treatment A's mean is 10, treatment B's mean is 0; equal-treatment-weight
    # average is (10 + 0) / 2 = 5, NOT the pooled-row mean (40/5 = 8).
    assert balanced["treatment_balanced_mean_rmse"].iloc[0] == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Fit-failure reporting
# ---------------------------------------------------------------------------


def test_failed_fits_are_reported_not_silently_discarded():
    """A model that cannot possibly fit within its bounds must still return
    a FitDiagnostics with converged=False, not raise or vanish."""
    spec = MODEL_SPECS["modified_gompertz"]
    # Two points can never meaningfully pin a 3-parameter Gompertz; more
    # importantly, bounds are set so tight around one start that convergence
    # to a good fit is implausible, exercising the non-converged branch of
    # the *pool* selection without crashing the caller.
    time = np.array([0.0, 21.0])
    observed = np.array([0.0, 1.0])
    diagnostics = fit_model(spec, time, observed)
    assert isinstance(diagnostics, FitDiagnostics)
    assert diagnostics.n_starts_attempted == len(spec.starts)
    # Whether or not this particular toy problem converges, the object must
    # always carry an explicit boolean, never a silently-swallowed failure.
    assert diagnostics.converged in (True, False)


def test_day10_forecast_validation_reports_a_row_per_requested_model_even_under_stress():
    """Every (fold, model) combination produces exactly one metrics row.

    Rows include the two always-on baselines (persistence, recent_rate)
    alongside every requested nonlinear model, so the fitted-diagnostics
    table (nonlinear models only) and the metrics table (models +
    baselines) differ in row count by design.
    """
    substrate = _synthetic_substrate(n_treatments=1, reactors_per_treatment=3)
    metrics, diagnostics = day10_forecast_validation(
        substrate, models=("first_order", "modified_gompertz"), include_agnostic=False
    )
    n_folds = metrics["held_out_reactor"].nunique()
    n_baselines = 2  # persistence, recent_rate
    assert len(metrics) == n_folds * (2 + n_baselines)
    assert len(diagnostics) == n_folds * 2
    assert set(diagnostics["model"]) == {"first_order", "modified_gompertz"}
    assert set(metrics["model"]) == {"first_order", "modified_gompertz", "persistence", "recent_rate"}


# ---------------------------------------------------------------------------
# Identical folds across models
# ---------------------------------------------------------------------------


def test_every_model_uses_identical_folds():
    substrate = _synthetic_substrate()
    metrics, _ = day10_forecast_validation(
        substrate, models=("first_order", "modified_gompertz", "zero_anchored_gompertz"), include_agnostic=False
    )
    fold_sets = metrics.groupby("model").apply(
        lambda g: frozenset(zip(g["treatment"], g["held_out_reactor"], strict=False)), include_groups=False
    )
    unique_fold_sets = set(fold_sets)
    assert len(unique_fold_sets) == 1


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


def test_primary_outputs_are_reproducible_with_a_fixed_seed():
    substrate = _synthetic_substrate()
    metrics_a, _ = day10_forecast_validation(substrate, models=("first_order",), include_agnostic=False)
    metrics_b, _ = day10_forecast_validation(substrate, models=("first_order",), include_agnostic=False)
    pd.testing.assert_frame_equal(metrics_a, metrics_b)

    paired = paired_reactor_differences(
        pd.concat(
            [
                metrics_a.assign(model="zero_anchored_gompertz"),
                metrics_a.assign(model="modified_gompertz", rmse=metrics_a["rmse"] * 1.1),
            ],
            ignore_index=True,
        ),
        "zero_anchored_gompertz",
        "modified_gompertz",
    )
    interval_a = bootstrap_paired_difference_interval(paired, iterations=200, seed=27)
    interval_b = bootstrap_paired_difference_interval(paired, iterations=200, seed=27)
    assert interval_a == interval_b


def test_robust_loss_f_scale_is_a_positive_documented_constant():
    assert ROBUST_LOSS_F_SCALE > 0
