import numpy as np
import pandas as pd
import pytest

from biochar_ad_kinetics.pyrolysis_response import (
    DESCRIPTOR_COLLINEARITY_THRESHOLD,
    MODEL_DEGREES,
    compare_pyrolysis_temperature_responses,
    descriptor_collinearity,
    max_descriptor_collinearity,
)

DATASET = "data/experimental/cdu_wang_2026_pyrolysis_temperature.csv"


def test_cdu_table_matches_the_published_thesis_values() -> None:
    frame = pd.read_csv(DATASET)
    assert frame["source_doi"].eq("10.25913/xgzk-zs88").all()
    biochars = frame.dropna(subset=["final_methane_yield_nml"])
    assert biochars["pyrolysis_temperature_c"].tolist() == [400, 500, 600, 700, 800, 900]
    assert np.isclose(
        biochars.loc[biochars["material_id"] == "p900", "final_methane_yield_nml"], 5515.74
    )
    assert biochars["n_replicates"].eq(3).all()
    # Activated carbon has descriptor values but no reported methane yield.
    activated_carbon = frame.loc[frame["material_id"] == "activated_carbon"].iloc[0]
    assert pd.isna(activated_carbon["final_methane_yield_nml"])
    assert activated_carbon["bet_surface_area_m2_g"] > 0


def test_temperature_response_comparison_uses_all_six_biochars() -> None:
    frame = pd.read_csv(DATASET)
    result = compare_pyrolysis_temperature_responses(frame)
    assert set(result["model"]) == set(MODEL_DEGREES)
    assert result["n_biochars"].eq(6).all()
    assert np.isfinite(result["leave_one_biochar_out_rmse"]).all()
    assert result["rank_by_held_out_rmse"].min() == 1


def test_temperature_response_rejects_too_few_biochars() -> None:
    frame = pd.read_csv(DATASET)
    truncated = frame.dropna(subset=["final_methane_yield_nml"]).iloc[:4]

    with pytest.raises(ValueError, match="at least five biochars"):
        compare_pyrolysis_temperature_responses(truncated)


def test_descriptors_are_confounded_by_the_single_temperature_series() -> None:
    frame = pd.read_csv(DATASET)
    correlation = descriptor_collinearity(frame)
    max_corr = max_descriptor_collinearity(correlation)

    # This is the whole point of the diagnostic: temperature, BET,
    # conductivity and pH move together in this table by construction.
    assert max_corr >= DESCRIPTOR_COLLINEARITY_THRESHOLD
