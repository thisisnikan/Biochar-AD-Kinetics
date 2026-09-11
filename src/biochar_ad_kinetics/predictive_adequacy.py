"""Falsification test: does a physically consistent kinetic curve predict a
held-out reactor's later trajectory better than the existing modified
Gompertz model?

Scientific question (exact interpretation used throughout this module and
every output it writes): for a reactor held out completely, if models are
trained using sibling reactors from the same treatment only through day 10,
which model best predicts the held-out reactor from days 11-21? This tests
later-trajectory prediction for an unseen *reactor* under a *known*
treatment. It does NOT test unseen-study transfer, unseen-material
prediction, dose-response generalization, causal biochar effects,
biological mechanisms, or full-scale reactor forecasting.

Leakage rule enforced everywhere in this module: a held-out reactor's own
observations - at any time, including its own day <= 10 window - are never
used to fit, initialize, normalize, or select a model that is then scored
against that same reactor. Every model and baseline in the day-10 forecast
task is built strictly from sibling reactors of the same treatment (or, for
the treatment-agnostic ablation, sibling reactors pooled across all
treatments), restricted to the training window. The complete-trajectory
repeatability analysis is a separate, explicitly labeled design where
siblings' full trajectories are legitimate training data because the
question there is reactor reproducibility under a known treatment, not
forecasting - see ``complete_trajectory_repeatability``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from .baselines import BASELINES

# ---------------------------------------------------------------------------
# Data population
# ---------------------------------------------------------------------------

TREATMENTS = (
    "food_waste",
    "food_waste_hydrochar_240c",
    "food_waste_pyrolysis_600c",
    "food_waste_torrefaction_240c",
)

PRIMARY_CUTOFF_DAYS = 10.0
FORECAST_HORIZON_END_DAYS = 21.0
SENSITIVITY_CUTOFFS_DAYS = (7.0, 14.0)


@dataclass(frozen=True)
class ReactorPopulation:
    """Reactor-level and blank-level observations on a chosen time grid.

    ``substrate`` and ``blanks`` both carry ``raw_cumulative_methane_ml`` so
    that blank correction can be recomputed inside a bootstrap resample
    rather than trusting a value computed outside it.
    """

    substrate: pd.DataFrame
    blanks: pd.DataFrame
    substrate_vs_g: float
    excluded_reactor_ids: tuple[str, ...]


def _daily_mask(time_hours: pd.Series) -> pd.Series:
    return (time_hours % 24) == 0


def load_population(
    path: str,
    *,
    grid: str = "daily",
    include_flagged_reactors: bool = False,
) -> ReactorPopulation:
    """Load the Kozlowski reactor-observation export at a chosen time grid.

    ``grid`` is one of ``"daily"`` (primary, ``time_hours % 24 == 0``),
    ``"hourly"`` (every source row) or ``"48h"`` (``time_hours % 48 == 0``).
    ``include_flagged_reactors`` widens the population to the two reactors
    the publisher's own workbook marks inconsistent
    (``qc_include == False``) as a stress-test ablation; the primary
    analysis population always excludes them.
    """
    if grid not in {"daily", "hourly", "48h"}:
        raise ValueError(f"Unknown time grid: {grid}")

    frame = pd.read_csv(path)
    required = {
        "reactor_id",
        "treatment_id",
        "replicate_id",
        "time_days",
        "time_hours",
        "is_inoculum_blank",
        "qc_include",
        "raw_cumulative_methane_ml",
        "substrate_vs_g",
        "source_record_id",
        "qc_flags",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing reactor-observation columns: {', '.join(sorted(missing))}")

    if grid == "hourly":
        keep = pd.Series(True, index=frame.index)
    elif grid == "48h":
        keep = (frame["time_hours"] % 48) == 0
    else:
        keep = _daily_mask(frame["time_hours"])
    frame = frame.loc[keep].copy()

    blanks = frame.loc[frame["is_inoculum_blank"].astype(bool)].copy()
    substrate_all = frame.loc[~frame["is_inoculum_blank"].astype(bool)].copy()

    substrate_all["qc_include"] = substrate_all["qc_include"].astype(bool)
    excluded = tuple(
        sorted(substrate_all.loc[~substrate_all["qc_include"], "reactor_id"].unique())
    )
    substrate = (
        substrate_all if include_flagged_reactors else substrate_all.loc[substrate_all["qc_include"]]
    ).copy()

    vs_values = substrate_all["substrate_vs_g"].to_numpy(float)
    vs_mean = float(vs_values.mean())
    if not np.allclose(vs_values, vs_mean, rtol=1e-6):
        raise ValueError("substrate_vs_g must be a single shared constant across reactors")

    return ReactorPopulation(
        substrate=substrate.reset_index(drop=True),
        blanks=blanks.reset_index(drop=True),
        substrate_vs_g=vs_mean,
        excluded_reactor_ids=excluded,
    )


def blank_correct(
    raw_substrate_ml: np.ndarray,
    blank_mean_ml: np.ndarray,
    substrate_vs_g: float,
) -> np.ndarray:
    """Blank-correct and VS-normalize raw cumulative methane.

    Matches ``build_kozlowski_2025_dataset.py``'s published formula
    ``(raw - blank_mean) / substrate_vs_g`` exactly (verified against the
    committed ``blank_corrected_methane_ml_g_vs`` column to < 1e-8 ml/g VS).
    Negative results are not clipped: an early-trajectory blank ahead of the
    substrate reactor is a real, reported feature of this dataset.
    """
    return (np.asarray(raw_substrate_ml, dtype=float) - np.asarray(blank_mean_ml, dtype=float)) / (
        substrate_vs_g
    )


def blank_mean_by_time(blanks: pd.DataFrame, blank_reactor_ids: tuple[str, ...] | None = None) -> pd.Series:
    """Mean raw cumulative methane across the given (or all) blank reactors, by time_days."""
    subset = blanks if blank_reactor_ids is None else blanks.loc[blanks["reactor_id"].isin(blank_reactor_ids)]
    if subset.empty:
        raise ValueError("No blank reactors available to build a blank-mean trajectory")
    return subset.groupby("time_days")["raw_cumulative_methane_ml"].mean()


def build_response(
    substrate: pd.DataFrame,
    blanks: pd.DataFrame,
    substrate_vs_g: float,
    *,
    blank_reactor_ids: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Attach a recomputed ``methane_ml_g_vs`` response column to ``substrate``.

    Recomputes from raw values every time (never trusts a precomputed
    column) so the same function can build the response either for the
    point estimate or inside a bootstrap resample with substituted reactor
    and blank trajectories.
    """
    means = blank_mean_by_time(blanks, blank_reactor_ids)
    out = substrate.copy()
    missing_time = out.loc[~out["time_days"].isin(means.index), "time_days"].unique()
    if len(missing_time):
        raise ValueError(f"No blank trajectory covers time_days {sorted(missing_time)[:5]}...")
    blank_at_time = out["time_days"].map(means).to_numpy(dtype=float)
    out["methane_ml_g_vs"] = blank_correct(
        out["raw_cumulative_methane_ml"].to_numpy(float), blank_at_time, substrate_vs_g
    )
    return out


# ---------------------------------------------------------------------------
# Model definitions
# ---------------------------------------------------------------------------


def zero_anchored_gompertz_shape(
    time_days: np.ndarray, k: float, lag_days: float
) -> np.ndarray:
    exponent = 1.0 + k * (lag_days - time_days)
    return np.exp(-np.exp(np.clip(exponent, -50.0, 50.0)))


def zero_anchored_gompertz(
    time_days: np.ndarray, potential: float, k: float, lag_days: float
) -> np.ndarray:
    """Zero-anchored Gompertz: M(0) == 0 exactly, by construction.

    F(t) = exp(-exp(1 + k(lag - t))); M(t) = P * (F(t) - F(0)) / (1 - F(0)).
    ``k`` is a rate *constant* (1/day), not a methane production rate; use
    ``zero_anchored_gompertz_max_rate`` for the physically comparable
    maximum-rate quantity. Under the enforced bounds k > 0, lag >= 0, the
    exponent at t=0 is always >= 1, so F(0) <= exp(-e) ~= 0.066 and the
    denominator 1 - F(0) is bounded well away from zero; the explicit guard
    below still protects against the degenerate case if bounds are ever
    relaxed by a caller.
    """
    time = np.asarray(time_days, dtype=float)
    f0 = zero_anchored_gompertz_shape(np.zeros(1), k, lag_days)[0]
    denominator = 1.0 - f0
    if denominator < 1e-9:
        return np.full_like(time, np.nan)
    shape = zero_anchored_gompertz_shape(time, k, lag_days)
    return potential * (shape - f0) / denominator


def zero_anchored_gompertz_max_rate(potential: float, k: float, lag_days: float) -> float:
    """Maximum dM/dt for the zero-anchored Gompertz, derived from its own parameterization.

    F(t) = exp(-exp(u)), u = 1 + k(lag - t). dF/dt = k*exp(u - exp(u)), maximized
    at u = 0 (t = lag + 1/k) with value k/e. M = P*(F - F(0))/(1 - F(0)), so
    max(dM/dt) = P*k / (e * (1 - F(0))).
    """
    f0 = zero_anchored_gompertz_shape(np.zeros(1), k, lag_days)[0]
    denominator = 1.0 - f0
    if denominator < 1e-9:
        return float("nan")
    return float(potential * k / (np.e * denominator))


def delayed_first_order(time_days: np.ndarray, potential: float, k: float, lag_days: float) -> np.ndarray:
    """Diagnostic model: a simple onset delay applied to first-order kinetics.

    Tests whether a lag alone (no true sigmoid curvature) explains the
    apparent sigmoid shape. Not a candidate for the primary hypothesis.
    """
    time = np.asarray(time_days, dtype=float)
    elapsed = np.clip(time - lag_days, 0.0, None)
    return potential * (1.0 - np.exp(-k * elapsed))


@dataclass(frozen=True)
class ModelSpec:
    name: str
    function: object
    param_names: tuple[str, ...]
    lower: tuple[float, ...]
    upper: tuple[float, ...]
    starts: tuple[tuple[float, ...], ...]
    is_primary_challenger: bool = False
    is_diagnostic: bool = False


def _existing(name: str) -> object:
    return BASELINES[name].function


MODEL_SPECS: dict[str, ModelSpec] = {
    "first_order": ModelSpec(
        "first_order",
        _existing("first_order"),
        ("potential", "rate"),
        (1.0, 1e-4),
        (1000.0, 10.0),
        ((400.0, 0.2), (100.0, 0.05), (800.0, 0.5)),
    ),
    "modified_gompertz": ModelSpec(
        "modified_gompertz",
        _existing("modified_gompertz"),
        ("potential", "rate", "lag"),
        (1.0, 1e-3, 0.0),
        (1000.0, 1000.0, 21.0),
        ((400.0, 40.0, 0.2), (100.0, 10.0, 1.0), (800.0, 80.0, 3.0)),
    ),
    "logistic": ModelSpec(
        "logistic",
        _existing("logistic"),
        ("potential", "rate", "lag"),
        (1.0, 1e-3, 0.0),
        (1000.0, 1000.0, 21.0),
        ((400.0, 40.0, 0.2), (100.0, 10.0, 1.0), (800.0, 80.0, 3.0)),
    ),
    "zero_anchored_gompertz": ModelSpec(
        "zero_anchored_gompertz",
        zero_anchored_gompertz,
        ("potential", "k", "lag"),
        (1.0, 1e-4, 0.0),
        (1000.0, 5.0, 21.0),
        ((400.0, 0.2, 0.2), (100.0, 0.05, 1.0), (800.0, 0.8, 3.0)),
        is_primary_challenger=True,
    ),
    "delayed_first_order": ModelSpec(
        "delayed_first_order",
        delayed_first_order,
        ("potential", "k", "lag"),
        (1.0, 1e-4, 0.0),
        (1000.0, 5.0, 21.0),
        ((400.0, 0.2, 0.2), (100.0, 0.05, 1.0), (800.0, 0.8, 3.0)),
        is_diagnostic=True,
    ),
}

PRIMARY_MODELS = ("first_order", "modified_gompertz", "logistic", "zero_anchored_gompertz")
ALL_MODELS = tuple(MODEL_SPECS)


# ---------------------------------------------------------------------------
# Multi-start deterministic fitting with recorded diagnostics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FitDiagnostics:
    model: str
    converged: bool
    objective: float
    parameters: tuple[float, ...]
    parameter_names: tuple[str, ...]
    n_observations: int
    n_starts_attempted: int
    chosen_start_index: int
    chosen_start: tuple[float, ...]
    lower_bound_hits: tuple[str, ...]
    upper_bound_hits: tuple[str, ...]
    singular_values: tuple[float, ...]
    condition_number: float
    max_parameter_correlation: float
    loss: str

    def to_row(self) -> dict[str, object]:
        return {
            "model": self.model,
            "converged": self.converged,
            "objective": self.objective,
            **{f"param_{name}": value for name, value in zip(self.parameter_names, self.parameters, strict=True)},
            "n_observations": self.n_observations,
            "n_starts_attempted": self.n_starts_attempted,
            "chosen_start_index": self.chosen_start_index,
            "lower_bound_hits": ";".join(self.lower_bound_hits),
            "upper_bound_hits": ";".join(self.upper_bound_hits),
            "condition_number": self.condition_number,
            "max_parameter_correlation": self.max_parameter_correlation,
            "loss": self.loss,
            **{
                f"singular_value_{i}": value
                for i, value in enumerate(self.singular_values)
            },
        }


_BOUND_RELATIVE_TOLERANCE = 1e-6


def _bound_hits(x: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    span = np.maximum(upper - lower, 1e-12)
    at_lower = np.abs(x - lower) <= _BOUND_RELATIVE_TOLERANCE * span
    at_upper = np.abs(x - upper) <= _BOUND_RELATIVE_TOLERANCE * span
    return at_lower, at_upper


#: Residual scale (ml/g VS) for the robust-loss sensitivity, applied identically
#: to every eligible nonlinear model. Chosen as a round number close to the
#: typical OLS held-out RMSE observed in the primary day-10 forecast (see
#: results README); it is a fixed, stated constant, not tuned per model or fold.
ROBUST_LOSS_F_SCALE = 20.0


def fit_model(
    spec: ModelSpec,
    time_days: np.ndarray,
    observed: np.ndarray,
    *,
    loss: str = "linear",
    f_scale: float = 1.0,
) -> FitDiagnostics:
    """Fit one model with deterministic multi-start OLS (or a stated robust loss).

    Every attempted start is a fixed, hand-chosen point (never randomly
    sampled), so results are exactly reproducible. The converged solution
    with the lowest objective is chosen; if none converge, the lowest-cost
    attempt is still returned with ``converged=False`` rather than silently
    discarded, so callers can see and count failures. ``f_scale`` only
    matters when ``loss`` is not ``"linear"``; use ``ROBUST_LOSS_F_SCALE`` for
    the robust-loss sensitivity so every model shares the same residual scale.
    """
    time = np.asarray(time_days, dtype=float)
    y = np.asarray(observed, dtype=float)
    lower = np.asarray(spec.lower, dtype=float)
    upper = np.asarray(spec.upper, dtype=float)

    def residual(values: np.ndarray) -> np.ndarray:
        return spec.function(time, *values) - y

    attempts = []
    for start in spec.starts:
        x0 = np.clip(np.asarray(start, dtype=float), lower, upper)
        solution = least_squares(residual, x0, bounds=(lower, upper), loss=loss, f_scale=f_scale)
        attempts.append(solution)

    converged = [(i, s) for i, s in enumerate(attempts) if s.success]
    pool = converged if converged else list(enumerate(attempts))
    chosen_index, chosen = min(pool, key=lambda item: item[1].cost)

    at_lower, at_upper = _bound_hits(chosen.x, lower, upper)
    lower_hits = tuple(name for name, hit in zip(spec.param_names, at_lower, strict=True) if hit)
    upper_hits = tuple(name for name, hit in zip(spec.param_names, at_upper, strict=True) if hit)

    try:
        singular_values = tuple(float(value) for value in np.linalg.svd(chosen.jac, compute_uv=False))
        gram = chosen.jac.T @ chosen.jac
        condition_number = float(np.linalg.cond(gram)) if np.all(np.isfinite(gram)) else float("inf")
        degrees_of_freedom = max(len(y) - len(spec.param_names), 1)
        residual_variance = float(np.sum(chosen.fun**2)) / degrees_of_freedom
        covariance = residual_variance * np.linalg.pinv(gram)
        se = np.sqrt(np.clip(np.diag(covariance), 0, None))
        outer = np.outer(se, se)
        with np.errstate(invalid="ignore", divide="ignore"):
            correlation = np.where(outer > 0, covariance / outer, np.nan)
        off_diag = correlation[~np.eye(len(spec.param_names), dtype=bool)]
        off_diag = off_diag[np.isfinite(off_diag)]
        max_correlation = float(np.max(np.abs(off_diag))) if off_diag.size else float("nan")
    except np.linalg.LinAlgError:
        singular_values = ()
        condition_number = float("nan")
        max_correlation = float("nan")

    return FitDiagnostics(
        model=spec.name,
        converged=bool(chosen.success),
        objective=float(chosen.cost),
        parameters=tuple(float(value) for value in chosen.x),
        parameter_names=spec.param_names,
        n_observations=len(y),
        n_starts_attempted=len(spec.starts),
        chosen_start_index=chosen_index,
        chosen_start=tuple(float(value) for value in spec.starts[chosen_index]),
        lower_bound_hits=lower_hits,
        upper_bound_hits=upper_hits,
        singular_values=singular_values,
        condition_number=condition_number,
        max_parameter_correlation=max_correlation,
        loss=loss,
    )


def predict(spec: ModelSpec, diagnostics: FitDiagnostics, time_days: np.ndarray) -> np.ndarray:
    return np.asarray(spec.function(np.asarray(time_days, dtype=float), *diagnostics.parameters), dtype=float)


# ---------------------------------------------------------------------------
# Baselines that share the same fold structure but need no nonlinear fit
# ---------------------------------------------------------------------------


def persistence_baseline(train: pd.DataFrame, cutoff_days: float, test_times: np.ndarray) -> np.ndarray:
    """Hold the sibling-mean value observed at the cutoff constant forward."""
    at_cutoff = train.loc[np.isclose(train["time_days"], cutoff_days), "methane_ml_g_vs"]
    if at_cutoff.empty:
        raise ValueError(f"No sibling observation at cutoff day {cutoff_days}")
    level = float(at_cutoff.mean())
    return np.full(len(test_times), level, dtype=float)


def recent_rate_baseline(
    train: pd.DataFrame,
    cutoff_days: float,
    test_times: np.ndarray,
    *,
    window_days: float = 2.0,
) -> np.ndarray:
    """Linearly extrapolate the sibling mean's recent slope, floored at zero.

    The rate is estimated from the sibling-mean trajectory's own two most
    recent training points (``cutoff - window_days`` and ``cutoff``), using
    only information available in the training window.
    """
    sibling_mean = train.groupby("time_days")["methane_ml_g_vs"].mean()
    if cutoff_days not in sibling_mean.index:
        raise ValueError(f"No sibling observation at cutoff day {cutoff_days}")
    earlier_candidates = sibling_mean.index[sibling_mean.index <= cutoff_days - window_days]
    if len(earlier_candidates) == 0:
        earlier_time = sibling_mean.index.min()
    else:
        earlier_time = earlier_candidates.max()
    level = float(sibling_mean.loc[cutoff_days])
    earlier_level = float(sibling_mean.loc[earlier_time])
    elapsed = cutoff_days - earlier_time
    rate = (level - earlier_level) / elapsed if elapsed > 0 else 0.0
    prediction = level + rate * (np.asarray(test_times, dtype=float) - cutoff_days)
    return np.clip(prediction, 0.0, None)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def _rmse(observed: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.sqrt(np.mean((observed - predicted) ** 2)))


def _mae(observed: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs(observed - predicted)))


def _period_bias(times: np.ndarray, observed: np.ndarray, predicted: np.ndarray, lo: float, hi: float) -> float:
    mask = (times >= lo) & (times <= hi)
    if not mask.any():
        return float("nan")
    return float(np.mean(predicted[mask] - observed[mask]))


def _monotonicity_violations(predicted: np.ndarray) -> int:
    return int(np.sum(np.diff(predicted) < -1e-9))


def _negative_predictions(predicted: np.ndarray) -> int:
    return int(np.sum(predicted < -1e-9))


def treatment_balanced_mean(fold_metrics: pd.DataFrame, value_column: str, model_column: str = "model") -> pd.DataFrame:
    """Average reactor-level values within treatment, then average treatments equally."""
    per_treatment = fold_metrics.groupby([model_column, "treatment"], as_index=False)[value_column].mean()
    balanced = per_treatment.groupby(model_column, as_index=False)[value_column].mean()
    balanced = balanced.rename(columns={value_column: f"treatment_balanced_mean_{value_column}"})
    return balanced


# ---------------------------------------------------------------------------
# Primary day-10 forecasting validation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FoldSpec:
    treatment: str
    held_out_reactor: str
    training_reactor_ids: tuple[str, ...]
    fitting_scope: str  # "treatment_specific" or "treatment_agnostic"


def _build_folds(substrate: pd.DataFrame) -> list[FoldSpec]:
    """Build one fold per (treatment, held-out reactor).

    Sibling eligibility is decided by ``original_reactor_id`` (falling back
    to ``reactor_id`` when the column is absent, which is always true for
    the primary non-bootstrap population). This matters for
    ``bootstrap_pipeline``: when whole-reactor resampling draws the same
    original reactor twice, both copies carry distinct working
    ``reactor_id`` values but the same ``original_reactor_id``, and *every*
    copy of the held-out reactor's original must be excluded from its own
    training siblings - otherwise a duplicate of the held-out reactor could
    train the very model scored against it.
    """
    original_id = (
        substrate["original_reactor_id"] if "original_reactor_id" in substrate.columns else substrate["reactor_id"]
    )
    id_to_original = dict(zip(substrate["reactor_id"], original_id, strict=False))

    folds: list[FoldSpec] = []
    for treatment, group in substrate.groupby("treatment_id", sort=True):
        reactor_ids = sorted(group["reactor_id"].unique())
        for held_out in reactor_ids:
            held_out_original = id_to_original[held_out]
            siblings = tuple(
                rid for rid in reactor_ids if id_to_original[rid] != held_out_original
            )
            folds.append(FoldSpec(treatment, held_out, siblings, "treatment_specific"))
            agnostic_siblings = tuple(
                rid
                for rid in substrate["reactor_id"].unique()
                if id_to_original[rid] != held_out_original
            )
            folds.append(FoldSpec(treatment, held_out, agnostic_siblings, "treatment_agnostic"))
    return folds


def day10_forecast_validation(
    substrate: pd.DataFrame,
    *,
    cutoff_days: float = PRIMARY_CUTOFF_DAYS,
    horizon_end_days: float = FORECAST_HORIZON_END_DAYS,
    models: tuple[str, ...] = ALL_MODELS,
    loss: str = "linear",
    f_scale: float = 1.0,
    include_agnostic: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Nested, leakage-safe whole-reactor day-10-forecast validation.

    Returns ``(reactor_fold_metrics, parameter_diagnostics)``. Every row is
    one (model, held-out reactor, fitting scope) combination; no timestamp
    is ever treated as an independent sample for statistical purposes
    upstream of this function - this table stays at reactor granularity.
    """
    folds = _build_folds(substrate)
    if not include_agnostic:
        folds = [f for f in folds if f.fitting_scope == "treatment_specific"]

    metric_rows: list[dict[str, object]] = []
    diagnostic_rows: list[dict[str, object]] = []

    for fold in folds:
        train = substrate.loc[
            substrate["reactor_id"].isin(fold.training_reactor_ids) & (substrate["time_days"] <= cutoff_days)
        ]
        test = substrate.loc[
            (substrate["reactor_id"] == fold.held_out_reactor)
            & (substrate["time_days"] > cutoff_days)
            & (substrate["time_days"] <= horizon_end_days)
        ].sort_values("time_days")
        if test.empty:
            continue
        test_times = test["time_days"].to_numpy(float)
        test_observed = test["methane_ml_g_vs"].to_numpy(float)

        for model_name in models:
            spec = MODEL_SPECS[model_name]
            if spec.is_diagnostic and fold.fitting_scope == "treatment_agnostic":
                continue  # diagnostic model is scoped to the primary, treatment-specific design only
            train_times = train["time_days"].to_numpy(float)
            train_observed = train["methane_ml_g_vs"].to_numpy(float)
            diagnostics = fit_model(spec, train_times, train_observed, loss=loss, f_scale=f_scale)
            predicted = predict(spec, diagnostics, test_times)

            row = _score_fold(fold, model_name, cutoff_days, test_times, test_observed, predicted)
            metric_rows.append(row)
            diagnostic_rows.append({"treatment": fold.treatment, "held_out_reactor": fold.held_out_reactor,
                                     "fitting_scope": fold.fitting_scope, "cutoff_days": cutoff_days,
                                     **diagnostics.to_row()})

        for baseline_name, baseline_fn in (
            ("persistence", persistence_baseline),
            ("recent_rate", recent_rate_baseline),
        ):
            if fold.fitting_scope == "treatment_agnostic":
                continue  # baselines are defined relative to the treatment the reactor belongs to
            predicted = (
                persistence_baseline(train, cutoff_days, test_times)
                if baseline_name == "persistence"
                else recent_rate_baseline(train, cutoff_days, test_times)
            )
            row = _score_fold(fold, baseline_name, cutoff_days, test_times, test_observed, predicted)
            metric_rows.append(row)

    return pd.DataFrame(metric_rows), pd.DataFrame(diagnostic_rows)


def _score_fold(
    fold: FoldSpec,
    model_name: str,
    cutoff_days: float,
    test_times: np.ndarray,
    test_observed: np.ndarray,
    predicted: np.ndarray,
) -> dict[str, object]:
    errors = predicted - test_observed
    day21_mask = np.isclose(test_times, FORECAST_HORIZON_END_DAYS)
    third = max(len(test_times) // 3, 1)
    early_hi = test_times[min(third - 1, len(test_times) - 1)]
    late_lo = test_times[max(len(test_times) - third, 0)]
    return {
        "treatment": fold.treatment,
        "held_out_reactor": fold.held_out_reactor,
        "fitting_scope": fold.fitting_scope,
        "n_training_reactors": len(fold.training_reactor_ids),
        "cutoff_days": cutoff_days,
        "model": model_name,
        "n_test_points": len(test_times),
        "rmse": _rmse(test_observed, predicted),
        "mae": _mae(test_observed, predicted),
        "bias": float(np.mean(errors)),
        "day21_abs_error": float(np.abs(errors[day21_mask][0])) if day21_mask.any() else float("nan"),
        "day21_observed": float(test_observed[day21_mask][0]) if day21_mask.any() else float("nan"),
        "early_bias": _period_bias(test_times, test_observed, predicted, test_times.min(), early_hi),
        "late_bias": _period_bias(test_times, test_observed, predicted, late_lo, test_times.max()),
        "mean_daily_increment_error": float(
            np.mean(np.diff(predicted) - np.diff(test_observed))
        ) if len(test_times) > 1 else float("nan"),
        "monotonicity_violations": _monotonicity_violations(predicted),
        "negative_predictions": _negative_predictions(predicted),
        "initial_condition_ok": True,  # forecast task predicts t>cutoff only; no t=0 point to violate
    }


# ---------------------------------------------------------------------------
# Complete-trajectory repeatability (NOT forecasting - see module docstring)
# ---------------------------------------------------------------------------


def complete_trajectory_repeatability(
    substrate: pd.DataFrame, *, models: tuple[str, ...] = PRIMARY_MODELS, loss: str = "linear"
) -> pd.DataFrame:
    """Known-treatment complete-trajectory repeatability (leave-one-reactor-out).

    Siblings' *full* trajectories train each model; the held-out reactor's
    full trajectory (all time points) is then predicted and scored. This is
    legitimate because every training observation still comes from a
    reactor other than the one being scored - it is a reproducibility
    check, not a forecast, and must never be described as one.
    """
    rows: list[dict[str, object]] = []
    for treatment, group in substrate.groupby("treatment_id", sort=True):
        reactor_ids = sorted(group["reactor_id"].unique())
        if len(reactor_ids) < 2:
            continue
        for held_out in reactor_ids:
            siblings = [rid for rid in reactor_ids if rid != held_out]
            train = group.loc[group["reactor_id"].isin(siblings)]
            test = group.loc[group["reactor_id"] == held_out].sort_values("time_days")
            test_times = test["time_days"].to_numpy(float)
            test_observed = test["methane_ml_g_vs"].to_numpy(float)

            sibling_mean = train.groupby("time_days")["methane_ml_g_vs"].mean()
            sibling_mean_prediction = sibling_mean.reindex(test_times).to_numpy(float)
            rows.append(
                {
                    "treatment": treatment,
                    "held_out_reactor": held_out,
                    "model": "sibling_mean_trajectory",
                    "n_training_reactors": len(siblings),
                    "n_test_points": len(test_times),
                    "rmse": _rmse(test_observed, sibling_mean_prediction),
                    "mae": _mae(test_observed, sibling_mean_prediction),
                    "bias": float(np.mean(sibling_mean_prediction - test_observed)),
                }
            )
            for model_name in models:
                spec = MODEL_SPECS[model_name]
                diagnostics = fit_model(spec, train["time_days"].to_numpy(float), train["methane_ml_g_vs"].to_numpy(float), loss=loss)
                predicted = predict(spec, diagnostics, test_times)
                rows.append(
                    {
                        "treatment": treatment,
                        "held_out_reactor": held_out,
                        "model": model_name,
                        "n_training_reactors": len(siblings),
                        "n_test_points": len(test_times),
                        "rmse": _rmse(test_observed, predicted),
                        "mae": _mae(test_observed, predicted),
                        "bias": float(np.mean(predicted - test_observed)),
                    }
                )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Paired reactor-level statistics
# ---------------------------------------------------------------------------


def paired_reactor_differences(
    fold_metrics: pd.DataFrame,
    model_a: str,
    model_b: str,
    *,
    value_column: str = "rmse",
    fitting_scope: str = "treatment_specific",
) -> pd.DataFrame:
    """Reactor-level paired ``value_column`` difference (model_a - model_b).

    Positive means model_a is worse. Every model is evaluated on the same
    held-out-reactor folds, so this is a paired comparison, never an
    independent-sample test across timestamps.
    """
    scoped = fold_metrics.loc[fold_metrics["fitting_scope"] == fitting_scope]
    a = scoped.loc[scoped["model"] == model_a].set_index(["treatment", "held_out_reactor"])[value_column]
    b = scoped.loc[scoped["model"] == model_b].set_index(["treatment", "held_out_reactor"])[value_column]
    common = a.index.intersection(b.index)
    if len(common) == 0:
        raise ValueError(f"No shared folds between {model_a} and {model_b}")
    diff = (a.loc[common] - b.loc[common]).rename("paired_difference").reset_index()
    diff["model_a"] = model_a
    diff["model_b"] = model_b
    diff["value_column"] = value_column
    return diff


def treatment_balanced_paired_difference(paired: pd.DataFrame) -> float:
    per_treatment = paired.groupby("treatment")["paired_difference"].mean()
    return float(per_treatment.mean())


def bootstrap_paired_difference_interval(
    paired: pd.DataFrame,
    *,
    iterations: int = 2000,
    seed: int = 27,
    confidence: float = 0.90,
) -> dict[str, float]:
    """Nonparametric CI on the treatment-balanced paired difference.

    Resamples reactors *within treatment*, with replacement, and
    recomputes the treatment-balanced mean paired difference each time.
    This is a fixed-seed resampling of already-computed fold-level paired
    differences (for statistical inference on a tiny, n=10 sample), and is
    distinct from ``bootstrap_pipeline`` below, which resamples raw
    trajectories and refits the entire modelling pipeline. Because there
    are only 2-3 reactors per treatment, this interval is necessarily
    coarse; it is reported as descriptive, not as a precise confidence
    statement.
    """
    rng = np.random.default_rng(seed)
    by_treatment = {
        treatment: group["paired_difference"].to_numpy(float)
        for treatment, group in paired.groupby("treatment")
    }
    samples = []
    for _ in range(iterations):
        treatment_means = []
        for values in by_treatment.values():
            resample = rng.choice(values, size=len(values), replace=True)
            treatment_means.append(float(np.mean(resample)))
        samples.append(float(np.mean(treatment_means)))
    samples_arr = np.asarray(samples, dtype=float)
    alpha = 1.0 - confidence
    return {
        "point_estimate": treatment_balanced_paired_difference(paired),
        "ci_low": float(np.quantile(samples_arr, alpha / 2)),
        "ci_high": float(np.quantile(samples_arr, 1 - alpha / 2)),
        "confidence": confidence,
        "iterations": iterations,
        "n_treatments": len(by_treatment),
        "n_reactors": int(paired["held_out_reactor"].nunique()),
    }


# ---------------------------------------------------------------------------
# Decision rule
# ---------------------------------------------------------------------------

#: Prespecified practical margin (not derived from measurement error) for the
#: primary hypothesis test, exactly as given in the task brief.
DECISION_RULE_MARGIN = 0.10
CHALLENGER_MODEL = "zero_anchored_gompertz"
REFERENCE_MODEL = "modified_gompertz"
#: Fraction of folds hitting the same parameter bound above which "not
#: consistently on bounds" (decision-rule criterion 5) is considered to fail.
BOUND_HIT_FAILURE_FRACTION = 0.5


def evaluate_decision_rule(
    *,
    primary_balanced: pd.DataFrame,
    primary_folds: pd.DataFrame,
    primary_diagnostics: pd.DataFrame,
    sensitivity_balanced: dict[str, pd.DataFrame],
    paired_interval: dict[str, float],
) -> pd.DataFrame:
    """Evaluate every criterion of the prespecified decision rule and return one row each.

    ``primary_balanced`` is the treatment-specific, cutoff=10 output of
    ``treatment_balanced_mean`` for ``value_column="rmse"``.
    ``sensitivity_balanced`` maps a sensitivity label (e.g.
    ``"blank_leave_K1_out"``, ``"grid_hourly"``) to the same kind of table
    computed under that sensitivity, so criterion 6 can check the sign of
    the improvement survives.
    """
    rows: list[dict[str, object]] = []

    def add(criterion: str, value: object, threshold: object, passed: bool, detail: str) -> None:
        rows.append(
            {"criterion": criterion, "value": value, "threshold": threshold, "passed": bool(passed), "detail": detail}
        )

    ref = float(primary_balanced.set_index("model").loc[REFERENCE_MODEL, "treatment_balanced_mean_rmse"])
    chal = float(primary_balanced.set_index("model").loc[CHALLENGER_MODEL, "treatment_balanced_mean_rmse"])
    relative_change = (chal - ref) / ref
    criterion_1 = relative_change <= -DECISION_RULE_MARGIN
    add(
        "1_treatment_balanced_rmse_at_least_10pct_lower",
        relative_change,
        -DECISION_RULE_MARGIN,
        criterion_1,
        f"{CHALLENGER_MODEL} RMSE {chal:.3f} vs {REFERENCE_MODEL} {ref:.3f} ml/g VS "
        f"({relative_change * 100:+.1f}% change; negative is an improvement)",
    )

    per_treatment = (
        primary_folds.loc[
            primary_folds["fitting_scope"].eq("treatment_specific")
            & primary_folds["model"].isin([REFERENCE_MODEL, CHALLENGER_MODEL])
        ]
        .groupby(["treatment", "model"])["rmse"]
        .mean()
        .unstack("model")
    )
    per_treatment["relative_change"] = (
        per_treatment[CHALLENGER_MODEL] - per_treatment[REFERENCE_MODEL]
    ) / per_treatment[REFERENCE_MODEL]
    worst_worsening = float(per_treatment["relative_change"].max())
    criterion_2 = worst_worsening <= DECISION_RULE_MARGIN
    add(
        "2_no_treatment_worsened_by_more_than_10pct",
        worst_worsening,
        DECISION_RULE_MARGIN,
        criterion_2,
        per_treatment["relative_change"].round(4).to_dict(),
    )

    challenger_folds = primary_folds.loc[primary_folds["model"].eq(CHALLENGER_MODEL)]
    criterion_3 = True  # zero-anchoring is a structural property of the model; see test_predictive_adequacy.py
    add("3_zero_initial_condition", "structural (see tests)", "M(0) == 0.0 exactly", criterion_3, "verified by unit test, not refit per fold")

    criterion_4 = bool(
        (challenger_folds["monotonicity_violations"].eq(0)).all()
        and (challenger_folds["negative_predictions"].eq(0)).all()
    )
    add(
        "4_predictions_nonnegative_and_monotonic",
        {
            "monotonicity_violations": int(challenger_folds["monotonicity_violations"].sum()),
            "negative_predictions": int(challenger_folds["negative_predictions"].sum()),
        },
        0,
        criterion_4,
        "summed across all challenger folds",
    )

    challenger_diag = primary_diagnostics.loc[primary_diagnostics["model"].eq(CHALLENGER_MODEL)]
    n_folds = len(challenger_diag)
    bound_fractions = {}
    for column in ("lower_bound_hits", "upper_bound_hits"):
        hit_counts: dict[str, int] = {}
        for value in challenger_diag[column]:
            for name in str(value).split(";"):
                if name:
                    hit_counts[name] = hit_counts.get(name, 0) + 1
        for name, count in hit_counts.items():
            bound_fractions[f"{column}:{name}"] = count / n_folds if n_folds else float("nan")
    worst_bound_fraction = max(bound_fractions.values()) if bound_fractions else 0.0
    criterion_5 = worst_bound_fraction < BOUND_HIT_FAILURE_FRACTION
    add(
        "5_parameters_not_consistently_on_bounds",
        {k: round(v, 3) for k, v in bound_fractions.items()},
        BOUND_HIT_FAILURE_FRACTION,
        criterion_5,
        f"worst bound-hit fraction across {n_folds} challenger folds",
    )

    sensitivity_checks = {}
    for label, table in sensitivity_balanced.items():
        indexed = table.set_index("model")["treatment_balanced_mean_rmse"]
        if REFERENCE_MODEL not in indexed.index or CHALLENGER_MODEL not in indexed.index:
            continue
        sensitivity_checks[label] = bool(indexed[CHALLENGER_MODEL] < indexed[REFERENCE_MODEL])
    criterion_6 = bool(sensitivity_checks) and all(sensitivity_checks.values())
    add(
        "6_improvement_survives_blank_and_grid_sensitivities",
        sensitivity_checks,
        "challenger RMSE < reference RMSE in every listed sensitivity",
        criterion_6,
        f"checked against {len(sensitivity_checks)} sensitivity analyses",
    )

    criterion_7 = bool(paired_interval["ci_high"] < 0)
    add(
        "7_paired_improvement_interval_excludes_no_improvement",
        {"ci_low": paired_interval["ci_low"], "ci_high": paired_interval["ci_high"]},
        "interval entirely below 0 (paired_difference = challenger - reference RMSE)",
        criterion_7,
        f"{paired_interval['confidence']:.0%} interval from {paired_interval['iterations']} resamples",
    )

    overall_supported = all(row["passed"] for row in rows)
    for row in rows:
        row["overall_hypothesis_provisionally_supported"] = overall_supported
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Whole-pipeline bootstrap (Uncertainty section)
# ---------------------------------------------------------------------------


def bootstrap_pipeline(
    substrate: pd.DataFrame,
    blanks: pd.DataFrame,
    substrate_vs_g: float,
    *,
    models: tuple[str, ...] = (REFERENCE_MODEL, CHALLENGER_MODEL),
    iterations: int = 60,
    seed: int = 27,
    cutoff_days: float = PRIMARY_CUTOFF_DAYS,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Whole-reactor and whole-blank resampling with a full pipeline refit.

    Each resample: (1) resample substrate reactors with replacement,
    independently within each treatment; (2) resample the 3 raw blank
    trajectories with replacement to build one common blank estimate;
    (3) recompute blank-corrected, VS-normalized methane inside the
    resample from raw values; (4) refit every model on the resampled
    day-10 forecast task and record the treatment-balanced RMSE.
    A reactor's *every* bootstrap copy keeps the same original identity, so
    if a reactor is drawn twice it is duplicated as training data or as a
    held-out fold consistently - never split so one copy trains while
    another copy of the same original reactor is held out.

    Because only 2-3 reactors are retained per treatment, these intervals
    are conditional on this particular dataset and are described as
    unstable, not as a precise sampling distribution.
    """
    rng = np.random.default_rng(seed)
    treatments = {
        treatment: sorted(group["reactor_id"].unique())
        for treatment, group in substrate.groupby("treatment_id")
    }
    blank_ids = sorted(blanks["reactor_id"].unique())

    rows: list[dict[str, object]] = []
    failures = 0
    for iteration in range(iterations):
        resampled_blank_ids = tuple(rng.choice(blank_ids, size=len(blank_ids), replace=True))
        # Resample reactors within treatment, tagging each drawn copy with a
        # unique working id so duplicate draws of one original reactor are
        # never silently merged into (or split across) train and test roles.
        resampled_frames = []
        fold_reactor_map: dict[str, list[str]] = {}
        for treatment, reactor_ids in treatments.items():
            draws = rng.choice(reactor_ids, size=len(reactor_ids), replace=True)
            working_ids = []
            for copy_index, original_id in enumerate(draws):
                working_id = f"{original_id}__boot{copy_index}"
                working_ids.append(working_id)
                piece = substrate.loc[substrate["reactor_id"] == original_id].copy()
                piece["original_reactor_id"] = original_id
                piece["reactor_id"] = working_id
                piece["treatment_id"] = treatment
                resampled_frames.append(piece)
            fold_reactor_map[treatment] = working_ids
        resampled_substrate = pd.concat(resampled_frames, ignore_index=True)

        try:
            response = build_response(
                resampled_substrate, blanks, substrate_vs_g, blank_reactor_ids=resampled_blank_ids
            )
            metrics, _ = day10_forecast_validation(
                response, cutoff_days=cutoff_days, models=models, include_agnostic=False
            )
            balanced = treatment_balanced_mean(
                metrics.loc[metrics["fitting_scope"].eq("treatment_specific")], "rmse"
            )
        except (ValueError, RuntimeError):
            failures += 1
            continue

        for _, row in balanced.iterrows():
            rows.append(
                {
                    "iteration": iteration,
                    "model": row["model"],
                    "treatment_balanced_mean_rmse": row["treatment_balanced_mean_rmse"],
                    "resampled_blank_ids": ";".join(resampled_blank_ids),
                }
            )

    result = pd.DataFrame(rows)
    metadata = {
        "iterations_requested": iterations,
        "iterations_failed": failures,
        "iterations_succeeded": iterations - failures,
        "seed": seed,
        "note": (
            "Conditional, unstable interval: only 2-3 reactors retained per "
            "treatment, so whole-reactor bootstrap resampling has very few "
            "distinct values to draw from within some treatments."
        ),
    }
    return result, metadata


def summarize_bootstrap(bootstrap_rows: pd.DataFrame, confidence: float = 0.90) -> pd.DataFrame:
    if bootstrap_rows.empty:
        return pd.DataFrame(columns=["model", "median", "ci_low", "ci_high", "n_iterations"])
    alpha = 1.0 - confidence
    summary = bootstrap_rows.groupby("model")["treatment_balanced_mean_rmse"].agg(
        median="median",
        ci_low=lambda s: float(np.quantile(s, alpha / 2)),
        ci_high=lambda s: float(np.quantile(s, 1 - alpha / 2)),
        n_iterations="size",
    )
    return summary.reset_index()
