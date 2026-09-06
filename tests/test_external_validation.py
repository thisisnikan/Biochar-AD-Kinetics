import numpy as np
import pandas as pd

from biochar_ad_kinetics.external_validation import (
    MODEL_DEGREES,
    TARGETS,
    compare_external_dose_responses,
)

DATASET = "data/experimental/valentin_bialowiec_2024_parameters.csv"


def test_external_parameter_table_matches_published_table_3() -> None:
    frame = pd.read_csv(DATASET)
    assert frame["dose_g_l"].tolist() == [0, 2, 4, 6, 8]
    assert frame["source_doi"].eq("10.1038/s41598-024-59313-y").all()
    assert frame["data_origin"].eq("published_table_3").all()
    assert frame["n_reactors"].eq(3).all()
    assert np.isclose(frame.loc[frame["dose_g_l"] == 0, "potential_ml_g_vs"], 128.82)
    assert np.isclose(frame.loc[frame["dose_g_l"] == 8, "max_rate_ml_g_vs_day"], 90.97)
    assert np.isclose(frame.loc[frame["dose_g_l"] == 8, "lag_days"], 0.10)


def test_external_validation_uses_strict_dose_holdouts() -> None:
    frame = pd.read_csv(DATASET)
    result = compare_external_dose_responses(frame)
    assert len(result) == len(TARGETS) * len(MODEL_DEGREES)
    assert set(result["model"]) == set(MODEL_DEGREES)
    assert result["n_doses"].eq(5).all()
    assert np.isfinite(result["leave_one_dose_out_rmse"]).all()
    assert result.groupby("response")["rank_by_held_out_rmse"].min().eq(1).all()


def test_log_linear_is_stronger_than_quadratic_on_this_external_table() -> None:
    frame = pd.read_csv(DATASET)
    result = compare_external_dose_responses(frame)
    pivot = result.pivot(index="response", columns="model", values="leave_one_dose_out_rmse")
    assert (pivot["log_linear_dose"] < pivot["log_quadratic_dose"]).all()
