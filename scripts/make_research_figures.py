"""Draw the early-stopping and dose-design figures from committed result tables."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "figures"
INK, MUTED, GRID = "#1f1f1e", "#5f5e58", "#dddcd6"
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
RULES = {
    "adaptive": ("Calibrated adaptive", BLUE),
    "holliger_1pct": ("1% for 3 days", ORANGE),
    "fixed_day": ("Fixed day, calibrated", AQUA),
}


def _base(ax) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.set_axisbelow(True)


def early_stopping(output: Path) -> Path:
    stops = pd.read_csv(ROOT / "results/early-stopping/stops.csv")
    summary = pd.read_csv(ROOT / "results/early-stopping/summary.csv")
    lobo = stops[(stops.scheme == "leave_one_bottle_out") & (stops.population == "all_long_cycles")]
    fig, (left, right) = plt.subplots(1, 2, figsize=(7.2, 3.1), width_ratios=(1.1, 1))
    a = lobo[lobo.rule == "adaptive"]
    rng = np.random.default_rng(1)
    jitter = rng.uniform(-0.25, 0.25, len(a))
    hit, miss = a[a.covered.astype(bool)], a[~a.covered.astype(bool)]
    left.plot([5, 35], [5, 35], color=MUTED, linewidth=0.8)
    left.text(29.5, 31.5, "no saving", fontsize=7, color=MUTED, rotation=38)
    left.scatter(
        hit.end_day + jitter[a.covered.astype(bool).to_numpy()],
        hit.stop_day,
        s=14,
        color=BLUE,
        label="interval holds end yield",
        edgecolor="white",
        linewidth=0.4,
    )
    left.scatter(
        miss.end_day,
        miss.stop_day,
        s=22,
        color=ORANGE,
        marker="D",
        label="interval misses",
        edgecolor="white",
        linewidth=0.4,
    )
    left.set_xlabel("Planned end of cycle (day)", fontsize=8, color=INK)
    left.set_ylabel("Day the calibrated rule stops", fontsize=8, color=INK)
    left.set_title("(a) Calibrated adaptive rule, 100 cycles", fontsize=9, loc="left", color=INK)
    left.legend(frameon=False, fontsize=7, loc="upper left")
    left.grid(True, color=GRID, linewidth=0.6)
    left.set_xlim(12, 36)
    left.set_ylim(3, 36)
    _base(left)

    s = summary[
        (summary.scheme == "leave_one_bottle_out") & (summary.population == "all_long_cycles")
    ].set_index("rule")
    labels = list(RULES)
    y = np.arange(len(labels))
    saved = [s.loc[r, "mean_days_saved"] for r in labels]
    right.barh(y, saved, height=0.55, color=[RULES[r][1] for r in labels])
    for yi, r in zip(y, labels, strict=True):
        right.text(
            s.loc[r, "mean_days_saved"] + 0.15,
            yi,
            f"{s.loc[r, 'mean_days_saved']:.1f} d saved, "
            f"{100 * s.loc[r, 'within_10pct_at_stop']:.0f}% within 10%",
            va="center",
            fontsize=7,
            color=INK,
        )
    right.set_yticks(y, [RULES[r][0] for r in labels], color=INK, fontsize=8)
    right.invert_yaxis()
    right.set_xlim(0, 14)
    right.set_xlabel("Mean days saved per cycle (bottle-weighted)", fontsize=8, color=INK)
    right.set_title("(b) Days saved and accuracy at stop", fontsize=9, loc="left", color=INK)
    right.xaxis.grid(True, color=GRID, linewidth=0.6)
    _base(right)
    fig.tight_layout()
    path = output / "early_stopping.png"
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def dose_design(output: Path) -> Path:
    designs = pd.read_csv(ROOT / "results/dose-design/designs.csv")
    base = designs[(designs.budget == 36) & (designs.gain == 0.15)]
    fig, (left, right) = plt.subplots(1, 2, figsize=(7.2, 3.0))
    part = base[base.reactor_log_sd == 0.05]
    for spacing, color, label in (
        ("log", BLUE, "log-spaced doses"),
        ("linear", ORANGE, "evenly spaced doses"),
    ):
        best = part[part.spacing == spacing].groupby("highest_dose_g_l").worst_case_correct.max()
        left.plot(best.index, best.values, color=color, marker="o", markersize=4, linewidth=1.6)
        left.text(best.index[-1] + 2, best.values[-1], label, fontsize=7, va="center", color=INK)
    left.set_xlim(0, 135)
    left.set_ylim(0, 1)
    left.set_xlabel("Highest dose tested (g/L)", fontsize=8, color=INK)
    left.set_ylabel("Worst-case share correct", fontsize=8, color=INK)
    left.set_title("(a) Dose range, 36 reactors", fontsize=9, loc="left", color=INK)
    left.yaxis.grid(True, color=GRID, linewidth=0.6)
    _base(left)
    for sd, color in ((0.03, BLUE), (0.05, AQUA), (0.07, ORANGE)):
        row = base[
            (base.reactor_log_sd == sd) & (base.spacing == "log") & (base.highest_dose_g_l == 100)
        ].sort_values("doses")
        right.plot(
            row.doses, row.worst_case_correct, color=color, marker="o", markersize=4, linewidth=1.6
        )
        right.text(
            12.3,
            row.worst_case_correct.iloc[-1],
            f"replicate CV {100 * sd:.0f}%",
            fontsize=7,
            va="center",
            color=INK,
        )
    right.axhline(0.8, color=MUTED, linewidth=0.8, linestyle="--")
    right.set_xlim(3.5, 15.5)
    right.set_ylim(0, 1)
    right.set_xticks(range(4, 13, 2))
    right.set_xlabel("Doses (36 reactors shared among them)", fontsize=8, color=INK)
    right.set_title("(b) Doses against replicates", fontsize=9, loc="left", color=INK)
    right.yaxis.grid(True, color=GRID, linewidth=0.6)
    _base(right)
    fig.tight_layout()
    path = output / "dose_design.png"
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "serif"})
    for path in (early_stopping(output), dose_design(output)):
        print(path)


if __name__ == "__main__":
    main()
