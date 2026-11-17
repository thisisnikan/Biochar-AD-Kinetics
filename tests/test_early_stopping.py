import math

import numpy as np
import pytest

from biochar_ad_kinetics.early_stopping import (
    TOLERANCE,
    calibrate,
    evaluate,
    forecast_pairs,
    holliger_stop_day,
    pooled_conformal_quantile,
)


def test_quantile_matches_split_conformal_with_one_point_per_group():
    scores = np.arange(1, 20, dtype=float)
    groups = np.arange(19)
    # n = 19, level = ceil(0.9 * 20) / 19 = 18 / 19 -> 18th smallest score
    assert pooled_conformal_quantile(scores, groups, 0.1) == 18.0


def test_quantile_gives_each_group_equal_weight():
    # Group "a" has many small scores, group "b" one large score.
    scores = np.array([0.1] * 50 + [5.0])
    groups = np.array(["a"] * 50 + ["b"])
    # n = 2, level = ceil(0.5 * 3) / 2 = 1 -> needs the largest score
    assert pooled_conformal_quantile(scores, groups, 0.5) == 5.0


def test_quantile_is_infinite_when_too_few_groups():
    assert pooled_conformal_quantile([1.0, 2.0], ["a", "b"], 0.1) == math.inf


@pytest.mark.parametrize("bad", [[-1.0], [math.nan]])
def test_quantile_rejects_invalid_scores(bad):
    with pytest.raises(ValueError):
        pooled_conformal_quantile(bad, ["a"], 0.1)


def test_holliger_fires_after_three_slow_days():
    t = np.arange(0, 20, 0.5)
    y = 100 * (1 - np.exp(-0.5 * t))
    day, value = holliger_stop_day(t, y, 19.5)
    increments = [y[t == k][0] - y[t == k - 1][0] for k in (day - 2, day - 1, day)]
    assert all(inc < 0.01 * y[t == k][0] for inc, k in zip(increments, (day - 2, day - 1, day)))
    earlier = day - 1
    slow = [
        y[t == k][0] - y[t == k - 1][0] < 0.01 * y[t == k][0]
        for k in (earlier - 2, earlier - 1, earlier)
    ]
    assert not all(slow)
    assert value == pytest.approx(y[t == day][0])


def test_holliger_does_not_fire_on_linear_growth():
    t = np.arange(0, 15, 0.5)
    assert holliger_stop_day(t, 10 + 5 * t, 14.5) is None


def _toy_trajectories(n_bottles=12, rate=0.25):
    rng = np.random.default_rng(0)
    trajectories = {}
    for b in range(n_bottles):
        for batch in (1, 2):
            t = np.arange(0, 20.5, 0.5)
            potential = 300 * rng.uniform(0.9, 1.1)
            y = potential * (1 - np.exp(-rate * t)) + 1.0
            trajectories[("L", batch, f"B{b}")] = (t, y)
    return trajectories


def test_forecast_pairs_uses_prefix_only():
    traj = _toy_trajectories(2)
    pairs = forecast_pairs(traj)
    key = ("L", 1, "B0")
    t, y = traj[key]
    altered = dict(traj)
    y2 = y.copy()
    y2[t > 10] *= 1.5  # change only the future after day 10
    altered[key] = (t, y2)
    p1 = pairs[(pairs.bottle_id == "B0") & (pairs.batch_id == 1) & (pairs.cut_days == 10)]
    p2 = forecast_pairs(altered)
    p2 = p2[(p2.bottle_id == "B0") & (p2.batch_id == 1) & (p2.cut_days == 10)]
    assert p1["recent_rate"].iloc[0] == p2["recent_rate"].iloc[0]
    assert pairs["cut_days"].max() == 19.0


def test_held_out_bottle_never_enters_calibration_and_rules_run():
    pairs = forecast_pairs(_toy_trajectories())
    held = pairs["bottle_id"] == "B0"
    model = calibrate(pairs[~held], 0.1)
    scored, stops = evaluate(pairs[held], model, {})
    assert set(stops["rule"]) == {"adaptive", "fixed_day", "fixed_day_persistence", "holliger_1pct"}
    assert len(stops) == 4 * 2
    adaptive = stops[stops.rule == "adaptive"]
    assert (adaptive["stop_day"] <= adaptive["end_day"]).all()
    assert model["normalised"] > 0 and TOLERANCE == pytest.approx(math.log(1.1))
    assert scored["covered_fixed"].dtype == bool
    # Unfired 1%-rule runs to the end with zero error.
    holliger = stops[stops.rule == "holliger_1pct"]
    assert (~holliger["fired"]).all() and (holliger["abs_log_error"] == 0).all()
