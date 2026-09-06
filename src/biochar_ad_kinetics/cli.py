"""Command-line interface."""

import argparse
import json
import math
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from .analysis import compare_models, leave_one_batch_out, summarize_holdouts
from .baselines import compare_experimental_baselines
from .data import generate_demo_dataset
from .effects import build_within_study_effect_table
from .external_validation import compare_external_dose_responses
from .fit import IDENTIFIABILITY_CORRELATION_THRESHOLD, bootstrap_parameters, fit_global
from .intake import validate_reactor_observations
from .pyrolysis_response import (
    DESCRIPTOR_COLLINEARITY_THRESHOLD,
    compare_pyrolysis_temperature_responses,
    descriptor_collinearity,
    max_descriptor_collinearity,
)
from .report import save_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo", help="Generate synthetic data and run the full workflow")
    demo.add_argument("--output", type=Path, default=Path("outputs"))
    demo.add_argument("--bootstrap", type=int, default=30)
    fit = commands.add_parser("fit", help="Fit a CSV dataset")
    fit.add_argument("csv", type=Path)
    fit.add_argument("--output", type=Path, default=Path("outputs"))
    fit.add_argument(
        "--bootstrap",
        type=int,
        default=0,
        help="Residual-bootstrap iterations for parameter uncertainty (0 disables; slow "
        "on large datasets, so it is opt-in here unlike the demo command)",
    )
    benchmark = commands.add_parser(
        "benchmark-experimental",
        help="Compare transparent kinetic baselines on replicate-level experimental BMP data",
    )
    benchmark.add_argument(
        "csv",
        type=Path,
        nargs="?",
        default=Path("data/experimental/kozlowski_2025_bmp.csv"),
    )
    benchmark.add_argument("--output", type=Path, default=Path("outputs/experimental"))
    external = commands.add_parser(
        "benchmark-external-dose",
        help="Challenge dose-response forms with independent published kinetic parameters",
    )
    external.add_argument(
        "csv",
        type=Path,
        nargs="?",
        default=Path("data/experimental/valentin_bialowiec_2024_parameters.csv"),
    )
    external.add_argument("--output", type=Path, default=Path("outputs/external-dose"))
    effects = commands.add_parser(
        "summarize-effects",
        help="Normalize public treatment estimates to controls within each study",
    )
    effects.add_argument(
        "--reactor-csv",
        type=Path,
        default=Path("data/experimental/kozlowski_2025_bmp.csv"),
    )
    effects.add_argument(
        "--parameter-csv",
        type=Path,
        default=Path("data/experimental/valentin_bialowiec_2024_parameters.csv"),
    )
    effects.add_argument("--output", type=Path, default=Path("outputs/effects"))
    intake = commands.add_parser(
        "validate-intake",
        help="Validate a reactor-level contribution before modelling or publication",
    )
    intake.add_argument("csv", type=Path)
    pyrolysis = commands.add_parser(
        "benchmark-pyrolysis-temperature",
        help="Descriptive temperature-response check on a published pyrolysis summary table",
    )
    pyrolysis.add_argument(
        "csv",
        type=Path,
        nargs="?",
        default=Path("data/experimental/cdu_wang_2026_pyrolysis_temperature.csv"),
    )
    pyrolysis.add_argument("--output", type=Path, default=Path("outputs/pyrolysis-temperature"))
    return parser


def _identifiability_warning(max_correlation: float) -> str | None:
    """Translate fit_global's max_parameter_correlation into a CLI-facing warning.

    A NaN correlation means the diagnostic itself failed (e.g. every
    off-diagonal entry was non-finite because a parameter sits at its fit
    bound), which must not be read as "no confounding found" — that would be
    the worst case reported as the best case.
    """
    if math.isnan(max_correlation):
        return (
            "The parameter-identifiability diagnostic could not be computed (the "
            "correlation matrix was entirely non-finite, e.g. a parameter sits at its "
            "fit bound). Treat this fit's parameters as unverified rather than assuming "
            "they are well separated."
        )
    if max_correlation >= IDENTIFIABILITY_CORRELATION_THRESHOLD:
        return (
            "At least two of the eight kinetic parameters are practically confounded "
            f"(|correlation| >= {IDENTIFIABILITY_CORRELATION_THRESHOLD}): the data cannot "
            "separate their individual values, only some combination of them. Point "
            "estimates for those parameters should not be interpreted individually."
        )
    return None


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "validate-intake":
        report = validate_reactor_observations(pd.read_csv(args.csv))
        print(json.dumps(report.to_dict(), indent=2))
        if not report.valid:
            raise SystemExit(2)
        return
    if args.command == "summarize-effects":
        effects = build_within_study_effect_table(
            pd.read_csv(args.reactor_csv), pd.read_csv(args.parameter_csv)
        )
        args.output.mkdir(parents=True, exist_ok=True)
        destination = args.output / "within_study_effects.csv"
        effects.to_csv(destination, index=False)

        # Studies differ in substrate, biochar and lab; the combined file above
        # is a convenience index, not a comparison table. Writing one file per
        # study makes any cross-study read require an explicit, deliberate
        # join instead of scanning rows that merely sit next to each other.
        per_study_outputs = {}
        for study_id, study_effects in effects.groupby("study_id"):
            study_destination = args.output / f"within_study_effects__{study_id}.csv"
            study_effects.to_csv(study_destination, index=False)
            per_study_outputs[study_id] = str(study_destination)

        print(
            json.dumps(
                {
                    "output": str(destination),
                    "per_study_output": per_study_outputs,
                    "studies": effects["study_id"].nunique(),
                    "effects": len(effects),
                    "low_replication_effects": int(effects["low_replication"].sum()),
                    "effects_without_uncertainty": int(
                        effects["log_response_ratio_se"].isna().sum()
                    ),
                    "cross_study_pooling_performed": False,
                },
                indent=2,
            )
        )
        return
    if args.command == "benchmark-external-dose":
        frame = pd.read_csv(args.csv)
        comparison = compare_external_dose_responses(frame)
        args.output.mkdir(parents=True, exist_ok=True)
        comparison.to_csv(args.output / "dose_response_comparison.csv", index=False)
        best = comparison.loc[comparison["rank_by_held_out_rmse"] == 1]
        print(
            json.dumps(
                {
                    "dataset": str(args.csv),
                    "selection_metric": "leave-one-dose-out RMSE",
                    "best_model_by_response": dict(zip(best["response"], best["model"])),
                },
                indent=2,
            )
        )
        return
    if args.command == "benchmark-pyrolysis-temperature":
        frame = pd.read_csv(args.csv)
        comparison = compare_pyrolysis_temperature_responses(frame)
        correlation = descriptor_collinearity(frame)
        args.output.mkdir(parents=True, exist_ok=True)
        comparison.to_csv(args.output / "temperature_response_comparison.csv", index=False)
        correlation.to_csv(args.output / "descriptor_collinearity.csv")
        max_collinearity = max_descriptor_collinearity(correlation)
        collinearity_warning = None
        if math.isnan(max_collinearity) or max_collinearity >= DESCRIPTOR_COLLINEARITY_THRESHOLD:
            collinearity_warning = (
                "Pyrolysis temperature, BET surface area, electrical conductivity and pH "
                "are practically confounded in this single-series table "
                f"(|correlation| >= {DESCRIPTOR_COLLINEARITY_THRESHOLD}): a good temperature "
                "trend cannot be attributed to any one material property, and this is a "
                "descriptive summary-data check, not evidence of a causal or DIET mechanism "
                "(see docs/MECHANISM_EVIDENCE.md)."
            )
        best = comparison.loc[comparison["rank_by_held_out_rmse"] == 1].iloc[0]
        print(
            json.dumps(
                {
                    "dataset": str(args.csv),
                    "selection_metric": "leave-one-biochar-out RMSE",
                    "best_model": best["model"],
                    "max_descriptor_collinearity": max_collinearity,
                    "collinearity_warning": collinearity_warning,
                },
                indent=2,
            )
        )
        return
    if args.command == "benchmark-experimental":
        frame = pd.read_csv(args.csv)
        comparison = compare_experimental_baselines(frame)
        args.output.mkdir(parents=True, exist_ok=True)
        comparison.to_csv(args.output / "kinetic_baseline_comparison.csv", index=False)
        best = comparison.loc[comparison["rank_by_holdout_rmse"] == 1]
        print(
            json.dumps(
                {
                    "dataset": str(args.csv),
                    "selection_metric": "replicate-held-out RMSE",
                    "best_model_by_treatment": dict(zip(best["treatment"], best["model"])),
                },
                indent=2,
            )
        )
        return
    if args.command == "demo":
        csv_path = args.output / "synthetic_bmp_data.csv"
        frame = generate_demo_dataset(csv_path)
    else:
        frame = pd.read_csv(args.csv)

    parameters, metrics = fit_global(frame)
    save_report(frame, parameters, metrics, args.output)
    comparison = compare_models(frame)
    comparison.to_csv(args.output / "model_comparison.csv", index=False)

    holdout_summary = None
    mean_held_out_rmse_interior = None
    mean_held_out_rmse_boundary = None
    if frame["batch_id"].nunique() >= 3:
        validation = leave_one_batch_out(frame)
        validation.to_csv(args.output / "leave_one_batch_out.csv", index=False)
        holdout_summary = summarize_holdouts(validation)
        holdout_summary.to_csv(args.output / "held_out_model_comparison.csv", index=False)

        # Interior/boundary error is reported for the full model only (the one
        # whose parameters/metrics/identifiability_warning appear alongside it
        # in this same JSON payload) rather than mixed across all candidates.
        full_model = validation.loc[validation["model"] == "global_dose_temperature"]
        interior = full_model.loc[~full_model["is_boundary_condition"], "rmse_ml_g_vs"]
        boundary = full_model.loc[full_model["is_boundary_condition"], "rmse_ml_g_vs"]
        mean_held_out_rmse_interior = float(interior.mean()) if len(interior) else None
        mean_held_out_rmse_boundary = float(boundary.mean()) if len(boundary) else None

    if args.bootstrap > 0:
        bootstrap = bootstrap_parameters(frame, iterations=args.bootstrap)
        bootstrap.describe(percentiles=[0.025, 0.5, 0.975]).to_csv(
            args.output / "bootstrap_summary.csv"
        )

    identifiability_warning = _identifiability_warning(metrics["max_parameter_correlation"])
    print(
        json.dumps(
            {
                "parameters": asdict(parameters),
                "metrics": metrics,
                "identifiability_warning": identifiability_warning,
                "best_model_by_aicc": comparison.iloc[0]["model"],
                "selection_metric": "mean whole-batch-held-out RMSE",
                "best_model_by_held_out_rmse": (
                    holdout_summary.iloc[0]["model"] if holdout_summary is not None else None
                ),
                "held_out_comparison": (
                    holdout_summary.to_dict(orient="records") if holdout_summary is not None else None
                ),
                "mean_held_out_rmse_interior_ml_g_vs": mean_held_out_rmse_interior,
                "mean_held_out_rmse_boundary_ml_g_vs": mean_held_out_rmse_boundary,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
