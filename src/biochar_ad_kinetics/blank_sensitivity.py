"""Sensitivity of the Kozłowski benchmark to the inoculum-blank correction.

The published correction subtracts the mean of three inoculum-only blanks. Blank
K1 decreases at two late readings and ends well below K2 and K3. The validation
plan requires a labelled sensitivity analysis before any change to that
correction. Nothing here alters the reference dataset: each scenario recomputes
blank-corrected yields from the committed raw reactor trajectories and reruns
the same curve-family comparison and within-study effects.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .baselines import compare_experimental_baselines
from .effects import reactor_within_study_effects

REFERENCE_SCENARIO = "published_three_blank_mean"


def _all_blanks(blanks: pd.DataFrame) -> pd.Series:
    return blanks.mean(axis=1)


def _without(reactor: str) -> Callable[[pd.DataFrame], pd.Series]:
    def correction(blanks: pd.DataFrame) -> pd.Series:
        return blanks.drop(columns=reactor).mean(axis=1)

    return correction


def _monotone_k1(blanks: pd.DataFrame) -> pd.Series:
    repaired = blanks.copy()
    repaired["K1"] = repaired["K1"].cummax()
    return repaired.mean(axis=1)


@dataclass(frozen=True)
class BlankScenario:
    """One labelled alternative to the published blank correction."""

    name: str
    description: str
    correction: Callable[[pd.DataFrame], pd.Series]


SCENARIOS: tuple[BlankScenario, ...] = (
    BlankScenario(
        REFERENCE_SCENARIO,
        "Mean of K1, K2 and K3 at each reading, as published.",
        _all_blanks,
    ),
    BlankScenario(
        "k1_running_maximum",
        "K1 replaced by its running maximum so cumulative methane never decreases.",
        _monotone_k1,
    ),
    BlankScenario("exclude_k1", "Mean of K2 and K3 only.", _without("K1")),
    BlankScenario("exclude_k2", "Mean of K1 and K3 only.", _without("K2")),
    BlankScenario("exclude_k3", "Mean of K1 and K2 only.", _without("K3")),
)


def blank_trajectories(intake: pd.DataFrame) -> pd.DataFrame:
    """Return raw cumulative methane of each inoculum blank, indexed by hour."""
    blanks = intake.loc[intake["is_inoculum_blank"].astype(bool)]
    table = blanks.pivot(
        index="time_hours", columns="reactor_id", values="raw_cumulative_methane_ml"
    ).sort_index()
    if table.shape[1] < 3 or table.isna().any().any():
        raise ValueError("Three complete inoculum-blank trajectories are required")
    return table


def scenario_frame(
    benchmark: pd.DataFrame, intake: pd.DataFrame, scenario: BlankScenario
) -> pd.DataFrame:
    """Recompute blank-corrected yields of the benchmark under one scenario."""
    substrate_vs = intake.loc[~intake["is_inoculum_blank"].astype(bool), "substrate_vs_g"]
    if not np.allclose(substrate_vs, substrate_vs.iloc[0], rtol=1e-12, atol=0):
        raise ValueError("A single substrate VS mass is required for this benchmark")
    blank = scenario.correction(blank_trajectories(intake))
    frame = benchmark.copy()
    frame["blank_mean_cumulative_methane_ml"] = frame["time_hours"].map(blank)
    if frame["blank_mean_cumulative_methane_ml"].isna().any():
        raise ValueError("Benchmark readings lack a matching blank reading")
    frame["methane_ml_g_vs"] = (
        frame["raw_cumulative_methane_ml"] - frame["blank_mean_cumulative_methane_ml"]
    ) / float(substrate_vs.iloc[0])
    return frame


def run_blank_sensitivity(
    benchmark: pd.DataFrame, intake: pd.DataFrame
) -> dict[str, pd.DataFrame]:
    """Rerun curve-family ranking and within-study effects under every scenario."""
    rankings, effects, yields = [], [], []
    for scenario in SCENARIOS:
        frame = scenario_frame(benchmark, intake, scenario)
        ranking = compare_experimental_baselines(frame)
        ranking.insert(0, "scenario", scenario.name)
        rankings.append(ranking)
        effect = reactor_within_study_effects(frame)
        effect.insert(0, "scenario", scenario.name)
        effects.append(effect)
        included = frame.loc[frame["included_in_benchmark"].astype(bool)]
        final = included.loc[included["time_hours"] == included["time_hours"].max()]
        summary = (
            final.groupby("treatment")["methane_ml_g_vs"].mean().rename("final_yield_ml_g_vs")
        ).reset_index()
        summary.insert(0, "scenario", scenario.name)
        yields.append(summary)

    ranking_table = pd.concat(rankings, ignore_index=True)
    effect_table = pd.concat(effects, ignore_index=True)
    yield_table = pd.concat(yields, ignore_index=True)
    reference = yield_table.loc[yield_table["scenario"] == REFERENCE_SCENARIO].set_index(
        "treatment"
    )["final_yield_ml_g_vs"]
    yield_table["percent_change_from_published"] = 100 * (
        yield_table["final_yield_ml_g_vs"] / yield_table["treatment"].map(reference) - 1
    )
    return {"rankings": ranking_table, "effects": effect_table, "final_yields": yield_table}


def summarize(results: dict[str, pd.DataFrame]) -> dict[str, object]:
    """Reduce the scenario tables to the statements the analysis supports."""
    rankings = results["rankings"]
    best = rankings.loc[rankings["rank_by_holdout_rmse"] == 1.0]
    best_models = best.groupby("scenario")["model"].agg(lambda models: sorted(set(models)))
    order = {
        scenario: tuple(
            group.sort_values(["treatment", "rank_by_holdout_rmse"])["model"].tolist()
        )
        for scenario, group in rankings.groupby("scenario")
    }
    effects = results["effects"]
    key = ["treatment", "response"]
    wide = effects.pivot_table(index=key, columns="scenario", values="percent_change")
    reference = wide[REFERENCE_SCENARIO]
    others = wide.drop(columns=REFERENCE_SCENARIO)
    sign_changes = sorted(
        f"{treatment}/{response}/{scenario}"
        for (treatment, response), row in others.iterrows()
        for scenario, value in row.items()
        if np.sign(value) != np.sign(reference.loc[(treatment, response)])
    )
    yields = results["final_yields"]
    return {
        "scenarios": {scenario.name: scenario.description for scenario in SCENARIOS},
        "best_model_by_scenario": {key: value for key, value in best_models.items()},
        "full_ranking_identical_to_published": {
            scenario: ranking == order[REFERENCE_SCENARIO] for scenario, ranking in order.items()
        },
        "max_abs_final_yield_change_percent": float(
            yields["percent_change_from_published"].abs().max()
        ),
        "max_abs_effect_shift_percentage_points": float(
            others.sub(reference, axis=0).abs().max().max()
        ),
        "effect_sign_changes": sign_changes,
        "interpretation_boundary": (
            "Sensitivity analysis only. The published three-blank correction remains the "
            "reference; no source value is repaired and no blank is removed from the dataset."
        ),
    }
