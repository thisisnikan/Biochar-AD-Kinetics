"""Run the day-10 forecast falsification experiment end to end.

Scientific question (see src/biochar_ad_kinetics/predictive_adequacy.py for
the full statement): for a reactor held out completely, if models are
trained using sibling reactors from the same treatment only through day 10,
which model best predicts the held-out reactor from days 11-21? This is a
falsification test of the zero-anchored Gompertz challenger against the
existing modified Gompertz model. A negative result is reported as such.

Usage:
    python scripts/run_predictive_adequacy_analysis.py --output results/predictive_adequacy
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import scipy

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from biochar_ad_kinetics.predictive_adequacy import (
    ALL_MODELS,
    CHALLENGER_MODEL,
    DECISION_RULE_MARGIN,
    FORECAST_HORIZON_END_DAYS,
    MODEL_SPECS,
    PRIMARY_CUTOFF_DAYS,
    PRIMARY_MODELS,
    REFERENCE_MODEL,
    ROBUST_LOSS_F_SCALE,
    SENSITIVITY_CUTOFFS_DAYS,
    _build_folds,
    bootstrap_paired_difference_interval,
    bootstrap_pipeline,
    build_response,
    complete_trajectory_repeatability,
    day10_forecast_validation,
    evaluate_decision_rule,
    fit_model,
    load_population,
    paired_reactor_differences,
    predict,
    summarize_bootstrap,
    treatment_balanced_mean,
)

DEFAULT_SOURCE = "data/experimental/kozlowski_2025_reactor_observations.csv.gz"
RANDOM_SEED = 27


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _balanced(metrics: pd.DataFrame) -> pd.DataFrame:
    scoped = metrics.loc[metrics["fitting_scope"].eq("treatment_specific")]
    return treatment_balanced_mean(scoped, "rmse")


def _run_sensitivity_grid(source: str, grid: str, cutoff: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    pop = load_population(source, grid=grid)
    response = build_response(pop.substrate, pop.blanks, pop.substrate_vs_g)
    metrics, _ = day10_forecast_validation(
        response, cutoff_days=cutoff, models=PRIMARY_MODELS, include_agnostic=False
    )
    return metrics, _balanced(metrics)


def _make_figures(
    *,
    output: Path,
    substrate: pd.DataFrame,
    primary_metrics: pd.DataFrame,
    primary_diagnostics: pd.DataFrame,
    paired: pd.DataFrame,
    sensitivity_summary: pd.DataFrame,
) -> None:
    figures_dir = output / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    plot_models = (REFERENCE_MODEL, CHALLENGER_MODEL)
    colors = {REFERENCE_MODEL: "#1B3FC4", CHALLENGER_MODEL: "#B06A22"}

    # 1. Observed vs predicted trajectory per held-out reactor -----------------
    reactor_ids = sorted(substrate["reactor_id"].unique())
    n = len(reactor_ids)
    fig, axes = plt.subplots(int(np.ceil(n / 2)), 2, figsize=(11, 2.6 * np.ceil(n / 2)), squeeze=False)
    for ax, reactor_id in zip(axes.ravel(), reactor_ids, strict=False):
        treatment = substrate.loc[substrate["reactor_id"] == reactor_id, "treatment_id"].iloc[0]
        fold = next(
            f
            for f in _build_folds(substrate)
            if f.held_out_reactor == reactor_id and f.fitting_scope == "treatment_specific"
        )
        observed_curve = substrate.loc[substrate["reactor_id"] == reactor_id].sort_values("time_days")
        ax.plot(observed_curve["time_days"], observed_curve["methane_ml_g_vs"], "k.", markersize=3, label="observed")
        ax.axvline(PRIMARY_CUTOFF_DAYS, color="grey", linestyle=":", linewidth=1)
        train = substrate.loc[
            substrate["reactor_id"].isin(fold.training_reactor_ids) & (substrate["time_days"] <= PRIMARY_CUTOFF_DAYS)
        ]
        for model_name in plot_models:
            spec = MODEL_SPECS[model_name]
            diagnostics = fit_model(spec, train["time_days"].to_numpy(float), train["methane_ml_g_vs"].to_numpy(float))
            time_grid = np.linspace(0, FORECAST_HORIZON_END_DAYS, 200)
            ax.plot(time_grid, predict(spec, diagnostics, time_grid), color=colors[model_name], label=model_name, linewidth=1.3)
        ax.set_title(f"{reactor_id} ({treatment})", fontsize=8)
        ax.tick_params(labelsize=7)
    for ax in axes.ravel()[n:]:
        ax.axis("off")
    axes.ravel()[0].legend(fontsize=6, loc="upper left")
    fig.suptitle("Observed vs predicted trajectories (dotted line = day-10 cutoff)")
    fig.tight_layout()
    fig.savefig(figures_dir / "01_observed_vs_predicted_trajectories.png", dpi=150)
    plt.close(fig)

    # 2. Reactor-level paired RMSE differences ---------------------------------
    fig, ax = plt.subplots(figsize=(7, 4))
    ordered = paired.sort_values("paired_difference")
    bar_colors = ["#B06A22" if v > 0 else "#2F7563" for v in ordered["paired_difference"]]
    ax.barh(ordered["held_out_reactor"], ordered["paired_difference"], color=bar_colors)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel(f"RMSE({CHALLENGER_MODEL}) - RMSE({REFERENCE_MODEL}) [ml/g VS]\n(positive = challenger worse)")
    ax.set_title("Reactor-level paired RMSE difference")
    fig.tight_layout()
    fig.savefig(figures_dir / "02_paired_rmse_differences.png", dpi=150)
    plt.close(fig)

    # 3 & 4. Residual and daily-increment-error trajectories --------------------
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for model_name in plot_models:
        for fold in _build_folds(substrate):
            if fold.fitting_scope != "treatment_specific":
                continue
            train = substrate.loc[
                substrate["reactor_id"].isin(fold.training_reactor_ids)
                & (substrate["time_days"] <= PRIMARY_CUTOFF_DAYS)
            ]
            test = substrate.loc[
                (substrate["reactor_id"] == fold.held_out_reactor)
                & (substrate["time_days"] > PRIMARY_CUTOFF_DAYS)
            ].sort_values("time_days")
            spec = MODEL_SPECS[model_name]
            diagnostics = fit_model(spec, train["time_days"].to_numpy(float), train["methane_ml_g_vs"].to_numpy(float))
            predicted = predict(spec, diagnostics, test["time_days"].to_numpy(float))
            residual = predicted - test["methane_ml_g_vs"].to_numpy(float)
            axes[0].plot(test["time_days"], residual, color=colors[model_name], alpha=0.4, linewidth=1)
            if len(test) > 1:
                increment_error = np.diff(predicted) - np.diff(test["methane_ml_g_vs"].to_numpy(float))
                axes[1].plot(test["time_days"].to_numpy()[1:], increment_error, color=colors[model_name], alpha=0.4, linewidth=1)
    for ax, title, ylabel in (
        (axes[0], "Residual trajectories (predicted - observed)", "residual [ml/g VS]"),
        (axes[1], "Daily-increment errors", "increment error [ml/g VS]"),
    ):
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("time (days)")
        ax.set_ylabel(ylabel)
    handles = [plt.Line2D([0], [0], color=colors[m], label=m) for m in plot_models]
    axes[0].legend(handles=handles, fontsize=7)
    fig.tight_layout()
    fig.savefig(figures_dir / "03_residuals_and_increment_errors.png", dpi=150)
    plt.close(fig)

    # 5. Identifiability diagnostics --------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    scoped = primary_diagnostics.loc[primary_diagnostics["fitting_scope"].eq("treatment_specific")]
    for model_name in plot_models:
        subset = scoped.loc[scoped["model"].eq(model_name)]
        axes[0].scatter(
            range(len(subset)), subset["max_parameter_correlation"], color=colors[model_name], label=model_name
        )
        axes[1].scatter(range(len(subset)), subset["condition_number"], color=colors[model_name], label=model_name)
    axes[0].axhline(0.95, color="grey", linestyle="--", linewidth=1, label="0.95 threshold")
    axes[0].set_title("Max parameter correlation per fold")
    axes[1].set_yscale("log")
    axes[1].set_title("Jacobian Gram condition number per fold (log scale)")
    for ax in axes:
        ax.set_xlabel("fold index")
        ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(figures_dir / "04_identifiability_diagnostics.png", dpi=150)
    plt.close(fig)

    # 6. Sensitivity comparison ---------------------------------------------------
    if len(sensitivity_summary):
        pivot = sensitivity_summary.loc[sensitivity_summary["model"].isin(plot_models)].pivot(
            index="sensitivity", columns="model", values="treatment_balanced_mean_rmse"
        )
        fig, ax = plt.subplots(figsize=(8, 5))
        y = np.arange(len(pivot))
        ax.barh(y - 0.2, pivot[REFERENCE_MODEL], height=0.4, color=colors[REFERENCE_MODEL], label=REFERENCE_MODEL)
        ax.barh(y + 0.2, pivot[CHALLENGER_MODEL], height=0.4, color=colors[CHALLENGER_MODEL], label=CHALLENGER_MODEL)
        ax.set_yticks(y)
        ax.set_yticklabels(pivot.index, fontsize=7)
        ax.set_xlabel("treatment-balanced mean RMSE [ml/g VS]")
        ax.set_title("Blank, QC and sampling-grid sensitivities")
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(figures_dir / "05_sensitivity_comparison.png", dpi=150)
        plt.close(fig)

    # 7. Measured day-21 methane vs fitted P --------------------------------------
    fig, ax = plt.subplots(figsize=(6, 6))
    for model_name in plot_models:
        subset = primary_metrics.loc[
            primary_metrics["model"].eq(model_name) & primary_metrics["fitting_scope"].eq("treatment_specific")
        ][["treatment", "held_out_reactor", "day21_observed"]]
        diag_subset = scoped.loc[scoped["model"].eq(model_name)][
            ["treatment", "held_out_reactor", "param_potential"]
        ]
        merged = subset.merge(diag_subset, on=["treatment", "held_out_reactor"])
        ax.scatter(merged["day21_observed"], merged["param_potential"], color=colors[model_name], label=model_name)
    lims = [0, max(primary_metrics["day21_observed"].max(), primary_diagnostics["param_potential"].max()) * 1.05]
    ax.plot(lims, lims, color="black", linewidth=0.8, linestyle="--", label="1:1")
    ax.set_xlabel("measured day-21 methane [ml/g VS]")
    ax.set_ylabel("fitted potential P [ml/g VS] (fit on siblings only)")
    ax.set_title("Measured day-21 methane vs fitted asymptotic P (kept conceptually separate)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(figures_dir / "06_day21_observed_vs_fitted_potential.png", dpi=150)
    plt.close(fig)


def run(output: Path, source: str = DEFAULT_SOURCE, bootstrap_iterations: int = 60) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    exclusion_reasons: dict[str, str] = {}

    # --- Primary population and response -----------------------------------
    pop = load_population(source, grid="daily")
    for reactor_id in pop.excluded_reactor_ids:
        exclusion_reasons[reactor_id] = "qc_include=False (publisher-flagged inconsistent raw signal)"
    substrate = build_response(pop.substrate, pop.blanks, pop.substrate_vs_g)

    # --- Primary day-10 forecast validation (all models) --------------------
    primary_metrics, primary_diagnostics = day10_forecast_validation(
        substrate, cutoff_days=PRIMARY_CUTOFF_DAYS, models=ALL_MODELS, include_agnostic=True
    )
    primary_balanced = _balanced(primary_metrics)
    agnostic_metrics = primary_metrics.loc[primary_metrics["fitting_scope"].eq("treatment_agnostic")]
    agnostic_balanced = treatment_balanced_mean(agnostic_metrics, "rmse") if len(agnostic_metrics) else pd.DataFrame()

    # --- Complete-trajectory repeatability (separate, not a forecast) -------
    repeatability = complete_trajectory_repeatability(substrate, models=PRIMARY_MODELS)
    repeatability_balanced = treatment_balanced_mean(repeatability, "rmse")

    # --- Paired statistics + bootstrap CI for the decision rule -------------
    paired = paired_reactor_differences(primary_metrics, CHALLENGER_MODEL, REFERENCE_MODEL)
    paired_interval = bootstrap_paired_difference_interval(paired, iterations=2000, seed=RANDOM_SEED)

    # --- Sensitivities --------------------------------------------------------
    sensitivity_rows: list[dict[str, object]] = []
    sensitivity_balanced: dict[str, pd.DataFrame] = {}

    for cutoff in SENSITIVITY_CUTOFFS_DAYS:
        metrics, _ = day10_forecast_validation(
            substrate, cutoff_days=cutoff, models=PRIMARY_MODELS, include_agnostic=False
        )
        balanced = _balanced(metrics)
        label = f"cutoff_day_{int(cutoff)}"
        sensitivity_balanced[label] = balanced
        for _, row in balanced.iterrows():
            sensitivity_rows.append({"sensitivity": label, **row.to_dict()})

    for grid in ("hourly", "48h"):
        _, balanced = _run_sensitivity_grid(source, grid, PRIMARY_CUTOFF_DAYS)
        label = f"grid_{grid}"
        sensitivity_balanced[label] = balanced
        for _, row in balanced.iterrows():
            sensitivity_rows.append({"sensitivity": label, **row.to_dict()})

    blank_ids = sorted(pop.blanks["reactor_id"].unique())
    for blank_id in blank_ids:
        remaining = tuple(bid for bid in blank_ids if bid != blank_id)
        response = build_response(pop.substrate, pop.blanks, pop.substrate_vs_g, blank_reactor_ids=remaining)
        metrics, _ = day10_forecast_validation(
            response, cutoff_days=PRIMARY_CUTOFF_DAYS, models=PRIMARY_MODELS, include_agnostic=False
        )
        balanced = _balanced(metrics)
        label = f"blank_leave_{blank_id}_out"
        sensitivity_balanced[label] = balanced
        for _, row in balanced.iterrows():
            sensitivity_rows.append({"sensitivity": label, **row.to_dict()})

    flagged_pop = load_population(source, grid="daily", include_flagged_reactors=True)
    flagged_response = build_response(flagged_pop.substrate, flagged_pop.blanks, flagged_pop.substrate_vs_g)
    flagged_metrics, _ = day10_forecast_validation(
        flagged_response, cutoff_days=PRIMARY_CUTOFF_DAYS, models=PRIMARY_MODELS, include_agnostic=False
    )
    flagged_balanced = _balanced(flagged_metrics)
    sensitivity_balanced["flagged_reactor_stress_test"] = flagged_balanced
    for _, row in flagged_balanced.iterrows():
        sensitivity_rows.append({"sensitivity": "flagged_reactor_stress_test", **row.to_dict()})

    robust_metrics, _ = day10_forecast_validation(
        substrate,
        cutoff_days=PRIMARY_CUTOFF_DAYS,
        models=PRIMARY_MODELS,
        loss="soft_l1",
        f_scale=ROBUST_LOSS_F_SCALE,
        include_agnostic=False,
    )
    robust_balanced = _balanced(robust_metrics)
    sensitivity_balanced["robust_loss"] = robust_balanced
    for _, row in robust_balanced.iterrows():
        sensitivity_rows.append({"sensitivity": "robust_loss", **row.to_dict()})

    sensitivity_summary = pd.DataFrame(sensitivity_rows)

    # --- Decision rule ---------------------------------------------------------
    decision = evaluate_decision_rule(
        primary_balanced=primary_balanced,
        primary_folds=primary_metrics,
        primary_diagnostics=primary_diagnostics,
        sensitivity_balanced={
            k: v for k, v in sensitivity_balanced.items() if not k.startswith("cutoff_day")
        },
        paired_interval=paired_interval,
    )
    overall_supported = bool(decision["overall_hypothesis_provisionally_supported"].iloc[0])

    # --- Whole-pipeline bootstrap (Uncertainty section) -------------------------
    bootstrap_rows, bootstrap_metadata = bootstrap_pipeline(
        pop.substrate, pop.blanks, pop.substrate_vs_g,
        models=(REFERENCE_MODEL, CHALLENGER_MODEL),
        iterations=bootstrap_iterations,
        seed=RANDOM_SEED,
    )
    bootstrap_summary = summarize_bootstrap(bootstrap_rows)

    # --- Write outputs -----------------------------------------------------
    reactor_fold_metrics = primary_metrics.copy()
    reactor_fold_metrics.to_csv(output / "reactor_fold_metrics.csv", index=False)

    model_summary_parts = [primary_balanced.assign(scope="treatment_specific_day10_forecast")]
    if len(agnostic_balanced):
        model_summary_parts.append(agnostic_balanced.assign(scope="treatment_agnostic_day10_forecast"))
    model_summary_parts.append(repeatability_balanced.assign(scope="complete_trajectory_repeatability"))
    model_summary = pd.concat(model_summary_parts, ignore_index=True)
    model_summary.to_csv(output / "model_summary.csv", index=False)

    primary_diagnostics.to_csv(output / "parameter_diagnostics.csv", index=False)

    bootstrap_rows.to_csv(output / "bootstrap_raw_iterations.csv", index=False)
    bootstrap_summary.to_csv(output / "bootstrap_summary.csv", index=False)

    sensitivity_summary.to_csv(output / "sensitivity_summary.csv", index=False)
    decision.to_csv(output / "claim_decisions.csv", index=False)

    paired.to_csv(output / "paired_reactor_differences.csv", index=False)
    repeatability.to_csv(output / "complete_trajectory_repeatability.csv", index=False)

    _make_figures(
        output=output,
        substrate=substrate,
        primary_metrics=primary_metrics,
        primary_diagnostics=primary_diagnostics,
        paired=paired,
        sensitivity_summary=sensitivity_summary,
    )

    metadata = {
        "source_commit": _git_commit(),
        "dataset": source,
        "dataset_role": "Kozlowski et al. (2025) public reactor-observation export",
        "analysis_population": "10 qc_include=True substrate reactors across 4 treatments, 3 inoculum blanks",
        "excluded_reactors": exclusion_reasons,
        "validation_task": (
            "Nested whole-reactor holdout: train on sibling reactors of the "
            "same treatment restricted to time_days <= cutoff, predict the "
            "held-out reactor for time_days in (cutoff, 21]. Not "
            "unseen-study, unseen-material, or dose-response transfer."
        ),
        "primary_cutoff_days": PRIMARY_CUTOFF_DAYS,
        "sensitivity_cutoffs_days": list(SENSITIVITY_CUTOFFS_DAYS),
        "forecast_horizon_end_days": FORECAST_HORIZON_END_DAYS,
        "reference_model": REFERENCE_MODEL,
        "challenger_model": CHALLENGER_MODEL,
        "decision_rule_margin": DECISION_RULE_MARGIN,
        "decision_rule_margin_note": (
            "Prespecified practical threshold given in the task brief, not a "
            "value derived from known measurement error."
        ),
        "random_seed": RANDOM_SEED,
        "bootstrap_iterations_requested": bootstrap_iterations,
        "bootstrap_iterations_succeeded": bootstrap_metadata["iterations_succeeded"],
        "bootstrap_note": bootstrap_metadata["note"],
        "robust_loss_f_scale_ml_g_vs": ROBUST_LOSS_F_SCALE,
        "primary_hypothesis_provisionally_supported": overall_supported,
        "effective_reactor_counts_by_treatment": {
            treatment: int(group["reactor_id"].nunique())
            for treatment, group in pop.substrate.groupby("treatment_id")
        },
        "software_versions": {
            "python": sys.version,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "pandas": pd.__version__,
            "platform": platform.platform(),
        },
    }
    (output / "analysis_metadata.json").write_text(json.dumps(metadata, indent=2, default=str) + "\n")

    return {
        "primary_balanced": primary_balanced,
        "decision": decision,
        "overall_supported": overall_supported,
        "paired_interval": paired_interval,
        "metadata": metadata,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=Path("results/predictive_adequacy"))
    parser.add_argument("--bootstrap-iterations", type=int, default=60)
    args = parser.parse_args()
    result = run(args.output, source=args.source, bootstrap_iterations=args.bootstrap_iterations)
    print(result["primary_balanced"].sort_values("treatment_balanced_mean_rmse").to_string(index=False))
    print()
    print(f"Primary hypothesis provisionally supported: {result['overall_supported']}")


if __name__ == "__main__":
    main()
