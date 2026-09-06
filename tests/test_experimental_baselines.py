import numpy as np
import pandas as pd

from biochar_ad_kinetics.baselines import BASELINES, compare_experimental_baselines

DATASET = "data/experimental/kozlowski_2025_bmp.csv"


def test_experimental_dataset_has_traceable_reactor_curves() -> None:
    frame = pd.read_csv(DATASET)
    assert len(frame) == 6060
    assert frame["data_origin"].eq("experimental_publisher_supplement").all()
    assert frame["source_doi"].eq("10.1038/s41598-025-02564-0").all()
    assert frame["time_days"].max() == 21
    assert frame["source_reported_time_days"].max() == 5.25
    assert frame["treatment"].nunique() == 4
    excluded = frame.loc[~frame["included_in_benchmark"], ["treatment", "replicate"]]
    assert len(excluded.drop_duplicates()) == 2
    final = frame.loc[(frame["included_in_benchmark"]) & (frame["time_days"] == 21)]
    treatment_means = final.groupby("treatment")["methane_ml_g_vs"].mean()
    assert np.isclose(treatment_means["food_waste"], 355.59834616)
    assert np.isclose(treatment_means["food_waste_torrefaction_240c"], 403.44881412)
    assert np.isclose(treatment_means["food_waste_pyrolysis_600c"], 370.79781796)
    assert np.isclose(treatment_means["food_waste_hydrochar_240c"], 390.04194603)


def test_real_data_baselines_use_replicate_holdouts() -> None:
    frame = pd.read_csv(DATASET)
    comparison = compare_experimental_baselines(frame)
    assert len(comparison) == frame["treatment"].nunique() * len(BASELINES)
    assert set(comparison["model"]) == set(BASELINES)
    assert comparison.groupby("treatment")["rank_by_holdout_rmse"].min().eq(1).all()
    assert np.isfinite(comparison["mean_holdout_rmse_ml_g_vs"]).all()
