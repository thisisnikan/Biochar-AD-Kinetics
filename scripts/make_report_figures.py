"""Draw the technical-report figures from committed result tables.

No model is refitted. Every plotted value is read from a CSV under ``results/``:
``experimental/kinetic_baseline_comparison.csv``,
``external-dose/dose_response_comparison.csv`` and ``forecasting/summary.csv``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "report" / "figures"
INK, MUTED, GRID = "#1f1f1e", "#5f5e58", "#dddcd6"
BLUE, ORANGE, AQUA, YELLOW, MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"

TREATMENTS = {
    "food_waste": "Food waste (3 reactors)",
    "food_waste_hydrochar_240c": "+ hydrochar 240 °C (3)",
    "food_waste_pyrolysis_600c": "+ biochar 600 °C (2)",
    "food_waste_torrefaction_240c": "+ torrefied 240 °C (2)",
}
CURVES = {
    "modified_gompertz": ("Modified Gompertz", BLUE),
    "logistic": ("Logistic", ORANGE),
    "first_order": ("First order", AQUA),
}
DOSE_FORMS = {
    "log_linear_dose": ("Log-linear", BLUE),
    "log_quadratic_dose": ("Log-quadratic", ORANGE),
    "dose_invariant": ("Constant", AQUA),
}
RESPONSES = {
    "potential_ml_g_vs": "Potential P",
    "max_rate_ml_g_vs_day": "Max. rate R",
}
FORECASTS = {
    "recent_rate": ("Recent-rate baseline", BLUE),
    "two_pool_first_order": ("Two-pool first order", ORANGE),
    "first_order": ("First order", AQUA),
    "modified_gompertz": ("Modified Gompertz", YELLOW),
    "persistence": ("Persistence baseline", MAGENTA),
}


def _base(ax: plt.Axes) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.set_axisbelow(True)


def _legend(ax: plt.Axes) -> None:
    ax.legend(
        frameon=False, fontsize=7, ncol=3, loc="lower left", bbox_to_anchor=(0, 1.0),
        borderaxespad=0.2, handlelength=1.0, columnspacing=0.8, handletextpad=0.4,
    )


def _grouped(ax, table, groups, series, value, fmt) -> None:
    width = 0.26
    for j, (key, (label, color)) in enumerate(series.items()):
        values = [table.loc[(group, key), value] for group in groups]
        y = np.arange(len(groups)) + (j - 1) * width
        ax.barh(y, values, height=width - 0.03, color=color, label=label)
        for yi, v in zip(y, values, strict=True):
            ax.text(v, yi, " " + fmt.format(v), va="center", ha="left", fontsize=7, color=INK)
    ax.set_yticks(np.arange(len(groups)), list(groups.values()), color=INK)
    ax.invert_yaxis()
    ax.xaxis.grid(True, color=GRID, linewidth=0.6)
    _base(ax)


def figure_model_selection(output: Path) -> Path:
    curves = pd.read_csv(ROOT / "results/experimental/kinetic_baseline_comparison.csv")
    dose = pd.read_csv(ROOT / "results/external-dose/dose_response_comparison.csv")
    fig, (left, right) = plt.subplots(1, 2, figsize=(7.2, 3.0))
    _grouped(
        left,
        curves.set_index(["treatment", "model"]),
        TREATMENTS,
        CURVES,
        "mean_holdout_rmse_ml_g_vs",
        "{:.1f}",
    )
    left.set_xlabel("Leave-one-reactor-out RMSE (mL CH$_4$ g$^{-1}$ VS)", fontsize=8, color=INK)
    left.set_title("(a) Curve family", fontsize=9, loc="left", color=INK, pad=22)
    left.set_xlim(0, 19)
    _legend(left)
    _grouped(
        right,
        dose.set_index(["response", "model"]),
        RESPONSES,
        DOSE_FORMS,
        "mean_absolute_percentage_error",
        "{:.1f}%",
    )
    right.set_xlabel("Leave-one-dose-out absolute error (%)", fontsize=8, color=INK)
    right.set_title("(b) Dose-response form", fontsize=9, loc="left", color=INK, pad=22)
    right.set_xlim(0, 80)
    _legend(right)
    fig.tight_layout()
    path = output / "fig1_model_selection.pdf"
    fig.savefig(path)
    plt.close(fig)
    return path


def figure_forecasting(output: Path) -> Path:
    summary = pd.read_csv(ROOT / "results/forecasting/summary.csv")
    primary = summary[
        (summary["population"] == "all_long_cycles") & (summary["reference"] == "recent_rate")
    ]
    fig, (left, right) = plt.subplots(1, 2, figsize=(7.2, 3.0), width_ratios=(1.25, 1))
    ends = {}
    for method, (_, color) in FORECASTS.items():
        rows = primary[primary["method"] == method].sort_values("cut_days")
        error = 100 * rows["equal_bottle_mean_abs_relative_error"]
        left.plot(rows["cut_days"], error, color=color, linewidth=1.6, marker="o", markersize=4)
        ends[method] = float(error.iloc[-1])
    # Direct labels, spread vertically so near-equal endpoints stay legible.
    slot = 3.0
    for method in sorted(ends, key=ends.get):
        label, color = FORECASTS[method]
        slot = max(slot + 3.6, ends[method])
        left.plot([12.6, 13.1], [ends[method], slot], color=color, linewidth=0.7)
        left.text(
            13.2, slot, f"{label}  {ends[method]:.1f}%", fontsize=7, va="center", color=INK
        )
    left.set_xticks([6.5, 9.5, 12.5])
    left.set_xlim(6.0, 18.2)
    left.set_ylim(0, 55)
    left.set_xlabel("Observed prefix (days)", fontsize=8, color=INK, loc="left")
    left.set_ylabel("Mean absolute relative\nendpoint error (%)", fontsize=8, color=INK)
    left.set_title("(a) Forecast error, equal bottle weights", fontsize=9, loc="left", color=INK)
    left.yaxis.grid(True, color=GRID, linewidth=0.6)
    _base(left)

    pair = primary[primary["method"] == "two_pool_first_order"].sort_values("cut_days")
    x = np.arange(len(pair))
    diff = 100 * pair["paired_difference"].to_numpy()
    low = 100 * pair["difference_ci_low"].to_numpy()
    high = 100 * pair["difference_ci_high"].to_numpy()
    right.axhline(0, color=MUTED, linewidth=0.8)
    right.errorbar(
        x, diff, yerr=[diff - low, high - diff], fmt="o", color=INK, ecolor=INK,
        elinewidth=1.2, capsize=3, markersize=5,
    )
    for xi, d in zip(x, diff, strict=True):
        right.text(xi + 0.16, d + 1.5, f"{d:+.1f}", fontsize=7.5, va="center", color=INK)
    right.set_xticks(x, [f"{c:g} d" for c in pair["cut_days"]])
    right.set_xlim(-0.5, 2.6)
    right.set_xlabel("Observed prefix", fontsize=8, color=INK)
    right.set_ylabel("Two-pool minus recent-rate\n(percentage points)", fontsize=8, color=INK)
    right.set_title("(b) Paired difference, 95% interval", fontsize=9, loc="left", color=INK)
    right.text(2.55, 9, "baseline better", fontsize=7, ha="right", color=MUTED)
    right.text(2.55, -46, "kinetic model better", fontsize=7, ha="right", color=MUTED)
    right.set_ylim(-50, 12)
    right.yaxis.grid(True, color=GRID, linewidth=0.6)
    _base(right)
    fig.tight_layout()
    path = output / "fig2_forecasting.pdf"
    fig.savefig(path)
    plt.close(fig)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "serif", "pdf.fonttype": 42})
    for path in (figure_model_selection(output), figure_forecasting(output)):
        print(path)


if __name__ == "__main__":
    main()
