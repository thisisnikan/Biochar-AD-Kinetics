"""Dataset validation and deterministic synthetic case-study generation."""

from pathlib import Path

import numpy as np
import pandas as pd

from .model import BatchCondition, KineticParameters, cumulative_methane

REQUIRED_COLUMNS = {
    "batch_id",
    "time_days",
    "dose_g_l",
    "temperature_c",
    "methane_ml_g_vs",
}


def validate_dataset(frame: pd.DataFrame) -> None:
    """Raise a clear error if a BMP dataset cannot be fitted safely."""

    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")
    if frame[list(REQUIRED_COLUMNS - {"batch_id"})].isna().any().any():
        raise ValueError("Numeric input columns cannot contain missing values")
    if frame["batch_id"].isna().any():
        raise ValueError("batch_id cannot contain missing values")
    if (frame["time_days"] < 0).any() or (frame["dose_g_l"] < 0).any():
        raise ValueError("Time and biochar dose must be non-negative")
    if frame["batch_id"].nunique() < 2:
        raise ValueError("At least two batch conditions are required for a global fit")


def generate_demo_dataset(path: str | Path, seed: int = 27) -> pd.DataFrame:
    """Create a labelled synthetic dataset for a reproducible demonstration."""

    rng = np.random.default_rng(seed)
    truth = KineticParameters()
    time = np.linspace(0, 30, 31)
    rows: list[dict[str, float | str]] = []
    for temperature in (37.0, 55.0):
        for dose in (0.0, 2.0, 5.0, 10.0):
            condition = BatchCondition(dose, temperature)
            clean = cumulative_methane(time, condition, truth)
            observed = np.maximum.accumulate(
                np.clip(clean + rng.normal(0, 4.0, time.size), 0, None)
            )
            batch_id = f"T{temperature:.0f}_D{dose:.0f}"
            rows.extend(
                {
                    "batch_id": batch_id,
                    "time_days": float(day),
                    "dose_g_l": dose,
                    "temperature_c": temperature,
                    "methane_ml_g_vs": float(value),
                    "data_origin": "synthetic_demo",
                }
                for day, value in zip(time, observed, strict=True)
            )
    frame = pd.DataFrame(rows)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(destination, index=False)
    return frame
