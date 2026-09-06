import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT = Path("scripts/analyze_zhang_2022_summary.py")
if not SCRIPT.exists():
    SCRIPT = Path("verify/analyze_zhang_2022_summary.py")
SPEC = importlib.util.spec_from_file_location("analyze_zhang_2022_summary", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def _methane_frame() -> pd.DataFrame:
    time = np.array([0, 2, 4, 6, 8, 10, 12, 16, 20, 24, 28], dtype=float)
    rows = []
    for treatment, rate, lag in (("control", 20.0, 6.0), ("biochar_750c_60min", 24.3, 2.3)):
        values = MODULE.modified_gompertz(time, 280.0, rate, lag)
        rows.extend(
            {
                "experiment_axis": "pyrolysis_temperature",
                "treatment": treatment,
                "time_days": day,
                "cumulative_methane_ml": value,
            }
            for day, value in zip(time, values, strict=True)
        )
    return pd.DataFrame(rows)


def test_kinetic_metrics_recovers_faster_biochar_curve() -> None:
    metrics, comparison = MODULE.kinetic_metrics(_methane_frame())
    biochar = metrics.query("treatment == 'biochar_750c_60min'").iloc[0]
    assert biochar["gompertz_rate_vs_control_pct"] == pytest.approx(21.5, abs=0.1)
    assert biochar["t90_change_vs_control_d"] < 0
    assert len(comparison) == 6
    assert set(comparison["validation_scope"]) == {"descriptive_fit_to_consolidated_means"}


def test_process_metrics_sums_analytes_without_pseudo_replicates() -> None:
    rows = []
    conditions = (
        ("control", 100.0, 80.0, 6.9),
        ("biochar_750c_60min", 50.0, 20.0, 7.2),
    )
    for treatment, acetate, propionate, ph in conditions:
        for day in (6, 12, 18):
            rows.extend([
                {
                    "experiment_axis": "pyrolysis_temperature",
                    "treatment": treatment,
                    "time_days": day,
                    "measurement": "vfa",
                    "analyte": "acetate",
                    "value": acetate,
                },
                {
                    "experiment_axis": "pyrolysis_temperature",
                    "treatment": treatment,
                    "time_days": day,
                    "measurement": "vfa",
                    "analyte": "propionate",
                    "value": propionate,
                },
            ])
        rows.append(
            {
                "experiment_axis": "pyrolysis_temperature",
                "treatment": treatment,
                "time_days": 6,
                "measurement": "ph",
                "analyte": "",
                "value": ph,
            }
        )
    result = MODULE.process_metrics(pd.DataFrame(rows))
    biochar = result.query("treatment == 'biochar_750c_60min'").iloc[0]
    assert biochar["total_vfa_day6_mg_l"] == 70.0
    assert biochar["vfa_day6_vs_control_pct"] == pytest.approx(-61.1111, abs=1e-3)
    assert biochar["min_ph"] == 7.2


def test_day10_lookup_is_nan_instead_of_crashing_without_an_exact_sample() -> None:
    time = np.array([0, 2, 4, 6, 8, 9.5, 12, 16, 20, 24, 28], dtype=float)
    rows = []
    for treatment, rate, lag in (("control", 20.0, 6.0), ("biochar_750c_60min", 24.3, 2.3)):
        values = MODULE.modified_gompertz(time, 280.0, rate, lag)
        rows.extend(
            {
                "experiment_axis": "pyrolysis_temperature",
                "treatment": treatment,
                "time_days": day,
                "cumulative_methane_ml": value,
            }
            for day, value in zip(time, values, strict=True)
        )
    metrics, _ = MODULE.kinetic_metrics(pd.DataFrame(rows))
    assert metrics["day10_methane_ml"].isna().all()


def test_information_criteria_penalizes_extra_parameters() -> None:
    observed = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    predicted = observed.copy()
    two = MODULE._information_criteria(observed, predicted, 2)
    three = MODULE._information_criteria(observed, predicted, 3)
    assert three["aicc"] > two["aicc"]


import pytest
