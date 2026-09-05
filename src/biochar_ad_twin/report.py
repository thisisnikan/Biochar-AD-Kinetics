"""Small reporting helpers for portfolio-ready outputs."""

import json
from dataclasses import asdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .fit import predict_frame
from .model import KineticParameters


def save_report(
    frame: pd.DataFrame,
    parameters: KineticParameters,
    metrics: dict[str, float],
    output_dir: str | Path,
) -> None:
    """Write machine-readable results and a fitted-curves figure."""

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    payload = {"parameters": asdict(parameters), "metrics": metrics}
    (destination / "fit_summary.json").write_text(json.dumps(payload, indent=2) + "\n")

    plotting = frame.reset_index(drop=True).copy()
    plotting["prediction"] = predict_frame(plotting, parameters)
    temperature_groups = list(plotting.groupby("temperature_c"))
    fig, axes = plt.subplots(
        1, len(temperature_groups), figsize=(6 * len(temperature_groups), 5), sharey=True
    )
    axes = np.atleast_1d(axes)
    for axis, (temperature, group) in zip(axes, temperature_groups, strict=True):
        for dose, batch in group.sort_values("dose_g_l").groupby("dose_g_l", sort=True):
            axis.scatter(batch["time_days"], batch["methane_ml_g_vs"], s=10, alpha=0.55)
            axis.plot(batch["time_days"], batch["prediction"], label=f"{dose:g} g/L")
        axis.set_title(f"{temperature:g} °C")
        axis.set_xlabel("Time (days)")
        axis.grid(alpha=0.2)
    axes[0].set_ylabel("Cumulative methane (mL gVS⁻¹)")
    axes[-1].legend(title="Biochar dose", frameon=False)
    fig.suptitle("Global fit across biochar dose and temperature")
    fig.tight_layout()
    fig.savefig(destination / "fitted_curves.png", dpi=180)
    plt.close(fig)
