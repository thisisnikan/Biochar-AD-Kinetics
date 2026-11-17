import numpy as np
import pytest

from biochar_ad_kinetics.dose_design import (
    correct_form,
    dose_grid,
    held_out_scores,
    select_forms,
    share_selected,
    truth_curve,
)


def test_grids_include_zero_and_highest_dose():
    for spacing in ("log", "linear"):
        grid = dose_grid(6, 70, spacing)
        assert grid[0] == 0 and grid[-1] == pytest.approx(70) and len(grid) == 6
    assert np.allclose(np.diff(np.log1p(dose_grid(5, 30, "log"))), np.log1p(30) / 4)


def test_optimum_truth_peaks_at_stated_dose_with_stated_gain():
    f = truth_curve("optimum_20", 0.15)
    x = np.log1p(np.linspace(0, 100, 10001))
    assert np.expm1(x[np.argmax(f(x))]) == pytest.approx(20, abs=0.05)
    assert f(x).max() == pytest.approx(np.log1p(0.15))
    assert truth_curve("monotone", 0.15)(np.log1p(np.array([8.0])))[0] == pytest.approx(
        np.log1p(0.15)
    )
    assert correct_form("optimum_5") == "quadratic"


def test_held_out_fit_matches_direct_least_squares():
    rng = np.random.default_rng(3)
    x = np.log1p(np.array([0, 2, 5, 10, 30.0]))
    values = rng.normal(0, 0.05, (1, 5, 3)) + (0.1 * x - 0.02 * x**2)[None, :, None]
    scores = held_out_scores(values, x)
    expected = []
    for degree in range(3):
        errs = []
        for j in range(5):
            tr = [i for i in range(5) if i != j]
            xs = np.repeat(x[tr], 3)
            ys = values[0, tr, :].ravel()
            coef = np.polyfit(xs, ys, degree)
            errs.append(np.sqrt(np.mean((values[0, j] - np.polyval(coef, x[j])) ** 2)))
        expected.append(np.mean(errs))
    assert np.allclose(scores[0], expected)


def test_parsimony_rule_requires_more_than_ten_percent():
    scores = np.array([[1.0, 0.95, 0.5], [1.0, 0.85, 0.80], [1.0, 1.2, 0.89]])
    assert select_forms(scores).tolist() == [2, 1, 2]


def test_low_noise_truths_are_mostly_recovered():
    rng = np.random.default_rng(0)
    doses = dose_grid(6, 70, "log")
    for truth in ("constant", "monotone", "optimum_10"):
        share = share_selected(doses, 3, truth, 0.5, 0.01, 500, rng)
        assert share[correct_form(truth)] > 0.85
