"""Draw the README key-findings figure from committed reference results.

The figure only re-plots numbers already stored under ``results/``; it fits no
model and reads no private data. Blue marks the lowest held-out error in each
comparison, grey marks every other candidate.

Usage::

    python scripts/make_summary_figure.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "figures" / "key_findings.png"

BEST = "#2a78d6"
OTHER = "#898781"
INK = "#0b0b0b"
SECONDARY = "#52514e"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SURFACE = "#fcfcfb"

TREATMENT_LABELS = {
    "food_waste": "Food waste (control)",
    "food_waste_torrefaction_240c": "+ torrefied carbon, 240 °C",
    "food_waste_pyrolysis_600c": "+ pyrolysis biochar, 600 °C",
    "food_waste_hydrochar_240c": "+ hydrochar, 240 °C",
}
KINETIC_LABELS = {
    "modified_gompertz": "Modified Gompertz",
    "logistic": "Logistic",
    "first_order": "First order",
}
KINETIC_MARKERS = {"modified_gompertz": "o", "logistic": "s", "first_order": "^"}
DOSE_LABELS = {
    "dose_invariant": "No dose effect",
    "log_linear_dose": "Log-linear",
    "log_quadratic_dose": "Log-quadratic (project hypothesis)",
}
FORECAST_LABELS = {
    "recent_rate": "Recent-rate baseline",
    "two_pool_first_order": "Two-pool first order",
    "first_order": "First order",
    "gompertz_plus_linear": "Gompertz + linear",
    "modified_gompertz": "Modified Gompertz",
    "persistence": "Persistence baseline",
    "logistic": "Logistic",
}
FORECAST_CUT_DAYS = 12.5


def load_results(root: Path = ROOT) -> dict[str, pd.DataFrame]:
    """Read the three committed result tables the figure is built from."""
    kinetic = pd.read_csv(root / "results" / "experimental" / "kinetic_baseline_comparison.csv")
    dose = pd.read_csv(root / "results" / "external-dose" / "dose_response_comparison.csv")
    forecast = pd.read_csv(root / "results" / "forecasting" / "summary.csv")
    forecast = forecast[
        (forecast["reference"] == "persistence")
        & (forecast["population"] == "all_long_cycles")
        & (forecast["cut_days"] == FORECAST_CUT_DAYS)
    ].copy()
    forecast["error_percent"] = 100.0 * forecast["equal_bottle_mean_abs_relative_error"]
    return {"kinetic": kinetic, "dose": dose, "forecast": forecast}


def _style(ax: plt.Axes, title: str, source: str, xlabel: str) -> None:
    ax.set_facecolor(SURFACE)
    for text, offset, size, color, weight in (
        (title, 24, 10.5, INK, "bold"),
        (source, 9, 9, SECONDARY, "normal"),
    ):
        ax.annotate(
            text,
            xy=(0, 1),
            xycoords=("figure fraction", "axes fraction"),
            xytext=(10, offset),
            textcoords="offset points",
            fontsize=size,
            color=color,
            fontweight=weight,
            ha="left",
            va="bottom",
        )
    ax.set_xlabel(xlabel, fontsize=9, color=SECONDARY)
    ax.tick_params(axis="both", colors=SECONDARY, labelsize=9, length=0)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.set_xlim(left=0)


def _bars(ax: plt.Axes, labels: list[str], values: list[float], unit: str) -> None:
    best = min(values)
    colors = [BEST if value == best else OTHER for value in values]
    positions = list(range(len(values)))[::-1]
    ax.barh(positions, values, height=0.56, color=colors)
    ax.set_yticks(positions, labels)
    ax.set_xlim(0, max(values) * 1.2)
    for position, value in zip(positions, values):
        ax.text(
            value + max(values) * 0.015,
            position,
            f"{value:.1f}{unit}",
            va="center",
            ha="left",
            fontsize=9,
            color=INK,
        )


def build_figure(results: dict[str, pd.DataFrame]) -> plt.Figure:
    """Return the three-panel key-findings figure."""
    fig, axes = plt.subplots(3, 1, figsize=(8.0, 10.2), facecolor=SURFACE)

    kinetic = results["kinetic"]
    ax = axes[0]
    rows = list(TREATMENT_LABELS)
    for model, label in KINETIC_LABELS.items():
        subset = kinetic[kinetic["model"] == model].set_index("treatment")
        ax.scatter(
            [subset.loc[treatment, "mean_holdout_rmse_ml_g_vs"] for treatment in rows],
            list(range(len(rows)))[::-1],
            s=70,
            marker=KINETIC_MARKERS[model],
            color=BEST if model == "modified_gompertz" else OTHER,
            edgecolor=SURFACE,
            linewidth=1.5,
            label=label,
            zorder=3,
        )
    ax.set_yticks(list(range(len(rows)))[::-1], [TREATMENT_LABELS[row] for row in rows])
    ax.set_ylim(-0.6, len(rows) - 0.4)
    _style(
        ax,
        "1. Modified Gompertz predicts unseen reactors best in every treatment",
        "Kozłowski et al. (2025): 10 of 12 food-waste reactors, 21 d, 37 °C",
        "Leave-one-reactor-out RMSE (mL CH4 per g VS)",
    )
    ax.set_xlim(0, 18)
    ax.legend(
        loc="lower right", frameon=False, fontsize=9, labelcolor=SECONDARY, handletextpad=0.3
    )

    dose = results["dose"]
    ax = axes[1]
    potential = dose[dose["response"] == "potential_ml_g_vs"].set_index("model")
    order = list(DOSE_LABELS)
    _bars(
        ax,
        [DOSE_LABELS[model] for model in order],
        [potential.loc[model, "mean_absolute_percentage_error"] for model in order],
        "%",
    )
    _style(
        ax,
        "2. A simpler dose response beats the project's own hypothesis on independent data",
        "Valentin & Białowiec (2024): published parameters at five biochar doses, 0 to 8 g/L",
        "Leave-one-dose-out error in methane potential (%)",
    )

    forecast = results["forecast"].sort_values("error_percent")
    ax = axes[2]
    _bars(
        ax,
        [FORECAST_LABELS[method] for method in forecast["method"]],
        forecast["error_percent"].tolist(),
        "%",
    )
    _style(
        ax,
        "3. A simple baseline forecasts final methane better than kinetic models",
        "Sanglier et al. (2022): 100 long cycles from 27 bottles, first 12.5 d observed",
        "Mean absolute relative error of the end-of-cycle forecast (%)",
    )

    fig.text(
        0.012,
        0.008,
        "Blue marks the lowest held-out error in each comparison. Retrospective results "
        "on small datasets.",
        fontsize=8.5,
        color=SECONDARY,
        ha="left",
        va="bottom",
    )
    fig.tight_layout(rect=(0, 0.025, 1, 0.97), h_pad=5.0)
    return fig


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure = build_figure(load_results())
    figure.savefig(args.output, dpi=160, facecolor=SURFACE)
    plt.close(figure)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
