"""Leakage and repeated-bottle safeguards for retrospective forecasting."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from biochar_ad_kinetics.forecast_benchmark import paired_bottle_comparison, prefix_baselines


def test_baselines_ignore_future_outcomes():
    t = np.arange(6.0)
    y = 2 * t
    expected = prefix_baselines(t, y, 2.5, 5)
    y[3:] = [np.nan, -999, 1e12]
    assert prefix_baselines(t, y, 2.5, 5) == expected
    assert expected == {"persistence": 4.0, "recent_rate": 10.0}


def test_negative_recent_rate_is_clipped_without_changing_prefix():
    assert prefix_baselines([0, 1, 2, 3], [3, 2, 1, 10], 2, 3) == {
        "persistence": 1.0,
        "recent_rate": 1.0,
    }


@pytest.mark.parametrize(
    "time,values,cut,target",
    [
        ([0, 1, 1, 3], [0, 1, 2, 3], 2, 3),
        ([0, 1, 2], [0, np.nan, 2], 2, 3),
        ([0, 1, 2], [0, 1, 2], 1, 3),
        ([0, 1, 2], [0, 1, 2], 2, 2),
        ([0, 1, 2], [0, 1], 2, 3),
    ],
)
def test_invalid_prefix_rejected(time, values, cut, target):
    with pytest.raises(ValueError):
        prefix_baselines(time, values, cut, target)


def scores():
    rows = []
    # One bottle has many cycles; its weight must still equal the other bottle's.
    for bottle, batches, err in [("A", range(10), 0.1), ("B", range(1), 0.9)]:
        for batch in batches:
            for method, error in [("persistence", err), ("model", err / 2)]:
                rows.append(
                    {
                        "lab": "L",
                        "bottle_id": bottle,
                        "batch_id": batch,
                        "cut_days": 6.5,
                        "method": method,
                        "relative_error": error,
                    }
                )
    return pd.DataFrame(rows)


def test_equal_bottle_weight_and_paired_interval():
    result = paired_bottle_comparison(scores(), draws=1000).set_index("method")
    assert result.loc["persistence", "equal_bottle_mean_abs_relative_error"] == pytest.approx(0.5)
    assert result.loc["model", "paired_difference"] == pytest.approx(-0.25)
    assert result.loc["model", "difference_ci_high"] < 0
    assert result.loc["persistence", "difference_ci_low"] == 0
    assert result.loc["model", "bottles"] == 2
    pd.testing.assert_frame_equal(
        paired_bottle_comparison(scores(), draws=1000),
        paired_bottle_comparison(scores().sample(frac=1, random_state=4), draws=1000),
    )


@pytest.mark.parametrize("defect", ["missing", "duplicate", "nonfinite", "identity", "single"])
def test_unpaired_or_invalid_scores_fail(defect):
    frame = scores()
    if defect == "missing":
        frame = frame.iloc[1:]
    elif defect == "duplicate":
        frame = pd.concat([frame, frame.iloc[:1]])
    elif defect == "nonfinite":
        frame.loc[0, "relative_error"] = np.inf
    elif defect == "identity":
        frame.loc[0, "bottle_id"] = None
    else:
        frame = frame[frame["bottle_id"] == "A"]
    with pytest.raises(ValueError):
        paired_bottle_comparison(frame)


def test_committed_forecast_outputs_reproduce(tmp_path):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "benchmark", root / "scripts/benchmark_sanglier_forecasts.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.build(tmp_path)
    assert report["status"].startswith("EXPLORATORY_WITHIN_STUDY")
    for name in ("scores.csv", "summary.csv"):
        pd.testing.assert_frame_equal(
            pd.read_csv(tmp_path / name),
            pd.read_csv(root / "results/forecasting" / name),
            check_exact=False,
            rtol=1e-8,
            atol=1e-10,
        )
