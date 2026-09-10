import numpy as np
import pandas as pd

from biochar_ad_kinetics.batch_effects import extract_matched_control_effects
from biochar_ad_kinetics.batch_trajectory import fit_batch_frame, modified_gompertz


def _trajectory(reactor_id: str, treatment_id: str, dose: float, is_control: bool, potential: float, rate: float, lag: float) -> pd.DataFrame:
    time = np.linspace(0, 30, 13)
    methane = modified_gompertz(time, potential, rate, lag)
    return pd.DataFrame(
        {
            "study_id": "study-1",
            "experiment_id": "exp-1",
            "reactor_id": reactor_id,
            "treatment_id": treatment_id,
            "dose_g_l": dose,
            "is_control": is_control,
            "temperature_c": 37.0,
            "substrate_id": "substrate-a",
            "inoculum_id": "inoculum-a",
            "time_days": time,
            "methane_ml_g_vs": methane,
        }
    )


def test_batch_fit_selects_gompertz_for_gompertz_generated_data():
    frame = _trajectory("c1", "control", 0.0, True, 300.0, 20.0, 2.0)
    fits = fit_batch_frame(frame)
    selected = fits.loc[fits["selected"]].iloc[0]

    assert selected["model"] == "modified_gompertz"
    assert abs(float(selected["potential"]) - 300.0) < 2.0
    assert abs(float(selected["max_rate"]) - 20.0) < 1.0


def test_matched_control_effects_have_expected_direction():
    control = _trajectory("c1", "control", 0.0, True, 300.0, 20.0, 3.0)
    treated = _trajectory("t1", "biochar-10", 10.0, False, 330.0, 25.0, 1.5)
    frame = pd.concat([control, treated], ignore_index=True)
    fits = fit_batch_frame(frame)

    effects = extract_matched_control_effects(frame, fits)
    effect = effects.iloc[0]

    assert float(effect["delta_potential"]) > 0
    assert float(effect["delta_max_rate"]) > 0
    assert float(effect["delta_lag"]) > 0
    assert float(effect["delta_t50"]) > 0
    assert float(effect["delta_t90"]) > 0
