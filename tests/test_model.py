import numpy as np
import pytest

from biochar_ad_kinetics.model import BatchCondition, KineticParameters, cumulative_methane


def test_curve_is_bounded_and_monotonic() -> None:
    time = np.linspace(0, 100, 200)
    parameters = KineticParameters()
    curve = cumulative_methane(time, BatchCondition(5, 37), parameters)
    assert np.all(np.diff(curve) >= 0)
    assert curve.min() >= 0
    assert curve.max() <= 500


def test_negative_dose_is_rejected() -> None:
    with pytest.raises(ValueError, match="dose"):
        cumulative_methane([0, 1], BatchCondition(-1, 37), KineticParameters())


def test_temperature_accelerates_rate() -> None:
    parameters = KineticParameters()
    mesophilic = cumulative_methane([8], BatchCondition(2, 37), parameters)[0]
    thermophilic = cumulative_methane([8], BatchCondition(2, 55), parameters)[0]
    assert thermophilic > mesophilic

