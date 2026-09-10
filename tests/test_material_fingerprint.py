import pandas as pd

from biochar_ad_kinetics.material_fingerprint import (
    assess_readiness,
    leave_one_study_out,
)


def _frame(n_studies: int) -> pd.DataFrame:
    rows = []
    for study in range(n_studies):
        for dose in (2.0, 5.0, 8.0):
            rows.append(
                {
                    "study_id": f"study-{study}",
                    "material": "biochar" if study % 2 == 0 else "hydrochar",
                    "dose_g_l": dose,
                    "material_process_temperature_c": 500.0 + 100.0 * study,
                    "delta_potential": 0.02 * dose + 0.01 * study,
                    "delta_max_rate": 0.03 * dose - 0.01 * study,
                    "delta_lag": 0.01 * dose,
                    "delta_t50": 0.015 * dose,
                    "delta_t90": 0.012 * dose,
                }
            )
    return pd.DataFrame(rows)


def test_stage_c_blocks_two_study_claims():
    readiness = assess_readiness(_frame(2))
    result = leave_one_study_out(_frame(2))

    assert not readiness.eligible_for_grouped_validation
    assert result.iloc[0]["status"] == "blocked_insufficient_independent_studies"


def test_stage_c_runs_grouped_validation_with_three_studies():
    result = leave_one_study_out(_frame(3))

    assert set(result["status"]) == {"evaluated"}
    assert result["held_out_study"].nunique() == 3
    assert result["target"].nunique() == 5
