import numpy as np
import pandas as pd

from biochar_ad_kinetics.material_fingerprint import assess_readiness, leave_one_study_out


def _frame(n_studies: int, missing_lag_for_last: bool = False) -> pd.DataFrame:
    rows = []
    for study in range(n_studies):
        for dose in (2.0, 5.0, 8.0):
            lag = np.nan if missing_lag_for_last and study == n_studies - 1 else 0.01 * dose
            rows.append(
                {
                    "study_id": f"study-{study}",
                    "material": "biochar" if study % 2 == 0 else "hydrochar",
                    "dose_g_l": dose,
                    "material_process_temperature_c": 500.0 + 100.0 * study,
                    "delta_potential": 0.02 * dose + 0.01 * study,
                    "delta_max_rate": 0.03 * dose - 0.01 * study,
                    "delta_lag": lag,
                    "delta_t50": 0.015 * dose,
                    "delta_t90": 0.012 * dose,
                }
            )
    return pd.DataFrame(rows)


def test_stage_c_blocks_two_study_claims():
    readiness = assess_readiness(_frame(2))
    result = leave_one_study_out(_frame(2))

    assert all(not item.eligible for item in readiness.values())
    assert set(result["status"]) == {"blocked_insufficient_independent_studies"}


def test_stage_c_runs_grouped_validation_with_three_studies():
    result = leave_one_study_out(_frame(3))
    evaluated = result.loc[result["status"] == "evaluated"]

    assert evaluated["held_out_study"].nunique() == 3
    assert evaluated["target"].nunique() == 5


def test_stage_c_can_evaluate_some_targets_when_lag_is_missing():
    readiness = assess_readiness(_frame(3, missing_lag_for_last=True))
    result = leave_one_study_out(_frame(3, missing_lag_for_last=True))

    assert readiness["delta_potential"].eligible
    assert not readiness["delta_lag"].eligible
    assert set(result.loc[result["target"] == "delta_lag", "status"]) == {
        "blocked_insufficient_independent_studies"
    }
    assert set(result.loc[result["target"] == "delta_potential", "status"]) == {"evaluated"}
