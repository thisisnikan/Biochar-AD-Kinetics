"""Build Stage A->B batch kinetic fingerprints from real repository datasets.

Public reactor trajectories are fitted per reactor. Published condition-level
parameters are converted to the same dimensionless effect convention. Private or
unpublished inputs are recorded in the status manifest but never pulled into CI.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from biochar_ad_kinetics.batch_effects import (
    extract_matched_control_effects,
    relative_gain,
    relative_reduction,
)
from biochar_ad_kinetics.batch_trajectory import fit_batch_frame


def gompertz_crossing_time(
    potential: float,
    max_rate: float,
    lag_days: float,
    fraction: float,
) -> float:
    """Analytic time at which a modified-Gompertz curve reaches fraction*P."""
    if potential <= 0 or max_rate <= 0 or not 0 < fraction < 1:
        return float("nan")
    return float(
        lag_days
        + (potential / (np.e * max_rate)) * (1.0 - np.log(-np.log(fraction)))
    )


def _as_true(series: pd.Series) -> pd.Series:
    """Coerce common CSV boolean encodings without treating 'false' as truthy."""
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes"})


def prepare_kozlowski(path: Path) -> tuple[pd.DataFrame, dict[str, int]]:
    raw = pd.read_csv(path)
    included = raw.loc[_as_true(raw["included_in_benchmark"])].copy()
    included["reactor_id"] = (
        included["treatment"].astype(str)
        + "::rep"
        + included["replicate"].astype(str)
    )
    included["treatment_id"] = included["treatment"].astype(str)
    included["experiment_id"] = "kozlowski_2025_37c_food_waste"
    included["is_control"] = included["treatment"].eq("food_waste")
    included["substrate_id"] = "food_waste"
    included["inoculum_id"] = "kozlowski_shared_inoculum"

    negative = included["methane_ml_g_vs"].lt(0)
    n_negative = int(negative.sum())
    included["fit_methane_ml_g_vs"] = included["methane_ml_g_vs"].clip(lower=0.0)

    audit = {
        "rows_included": len(included),
        "reactors_included": int(included["reactor_id"].nunique()),
        "negative_blank_corrected_observations_floored_for_fit": n_negative,
    }
    return included, audit


def kozlowski_fingerprints(
    path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    frame, audit = prepare_kozlowski(path)
    fits = fit_batch_frame(
        frame,
        time_col="time_days",
        response_col="fit_methane_ml_g_vs",
        reactor_col="reactor_id",
    )
    effects = extract_matched_control_effects(frame, fits)
    material = frame[
        ["reactor_id", "carbon_material", "process_temperature_c", "source_doi"]
    ].drop_duplicates("reactor_id")
    effects = effects.merge(
        material,
        on="reactor_id",
        how="left",
        validate="many_to_one",
    )
    effects = effects.rename(
        columns={
            "carbon_material": "material",
            "process_temperature_c": "material_process_temperature_c",
        }
    )
    effects["evidence_level"] = "reactor_level_public_trajectory"
    effects["replicate_level_available"] = True
    effects["source_scope"] = "public_publisher_supplement"
    return fits, effects, audit


def valentin_fingerprints(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path).sort_values("dose_g_l").reset_index(drop=True)
    control = data.loc[data["dose_g_l"].eq(0)].iloc[0]
    control_t50 = gompertz_crossing_time(
        float(control["potential_ml_g_vs"]),
        float(control["max_rate_ml_g_vs_day"]),
        float(control["lag_days"]),
        0.5,
    )
    control_t90 = gompertz_crossing_time(
        float(control["potential_ml_g_vs"]),
        float(control["max_rate_ml_g_vs_day"]),
        float(control["lag_days"]),
        0.9,
    )

    rows: list[dict[str, object]] = []
    for _, row in data.loc[data["dose_g_l"].gt(0)].iterrows():
        t50 = gompertz_crossing_time(
            float(row["potential_ml_g_vs"]),
            float(row["max_rate_ml_g_vs_day"]),
            float(row["lag_days"]),
            0.5,
        )
        t90 = gompertz_crossing_time(
            float(row["potential_ml_g_vs"]),
            float(row["max_rate_ml_g_vs_day"]),
            float(row["lag_days"]),
            0.9,
        )
        rows.append(
            {
                "study_id": "valentin_bialowiec_2024_scientific_reports",
                "experiment_id": "valentin_2024_glucose_37c",
                "treatment_id": f"dose_{float(row['dose_g_l']):g}_g_l",
                "reactor_id": "published_condition_parameter",
                "control_group_id": "valentin_2024::dose_0_g_l",
                "dose_g_l": float(row["dose_g_l"]),
                "delta_potential": relative_gain(
                    float(row["potential_ml_g_vs"]),
                    float(control["potential_ml_g_vs"]),
                ),
                "delta_max_rate": relative_gain(
                    float(row["max_rate_ml_g_vs_day"]),
                    float(control["max_rate_ml_g_vs_day"]),
                ),
                "delta_lag": relative_reduction(
                    float(row["lag_days"]),
                    float(control["lag_days"]),
                ),
                "delta_t50": relative_reduction(t50, control_t50),
                "delta_t90": relative_reduction(t90, control_t90),
                "treated_model": "published_modified_gompertz",
                "control_model": "published_modified_gompertz",
                "material": "biochar",
                "material_process_temperature_c": float(row["biochar_pyrolysis_c"]),
                "source_doi": str(row["source_doi"]),
                "evidence_level": "published_condition_parameter",
                "replicate_level_available": False,
                "source_scope": "published_table_3",
            }
        )
    return pd.DataFrame(rows)


def summarize(fingerprints: pd.DataFrame) -> dict[str, object]:
    public_biochar = fingerprints.loc[fingerprints["material"].eq("biochar")].copy()
    by_study = []
    for study_id, group in public_biochar.groupby("study_id", sort=True):
        by_study.append(
            {
                "study_id": study_id,
                "n_effect_rows": len(group),
                "dose_min_g_l": float(group["dose_g_l"].min()),
                "dose_max_g_l": float(group["dose_g_l"].max()),
                "mean_delta_potential": float(group["delta_potential"].mean()),
                "mean_delta_max_rate": float(group["delta_max_rate"].mean()),
                "mean_delta_lag": float(group["delta_lag"].mean()),
                "mean_delta_t50": float(group["delta_t50"].mean()),
                "mean_delta_t90": float(group["delta_t90"].mean()),
            }
        )
    return {
        "interpretation": (
            "Stage A->B descriptive kinetic fingerprints; no pooled causal or "
            "cross-study treatment-effect estimate is claimed."
        ),
        "n_fingerprint_rows": len(fingerprints),
        "n_biochar_rows": len(public_biochar),
        "studies_with_public_effect_information": sorted(
            fingerprints["study_id"].unique().tolist()
        ),
        "biochar_by_study": by_study,
    }


def run(output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    koz_path = Path("data/experimental/kozlowski_2025_bmp.csv")
    val_path = Path("data/experimental/valentin_bialowiec_2024_parameters.csv")

    koz_fits, koz_effects, koz_audit = kozlowski_fingerprints(koz_path)
    val_effects = valentin_fingerprints(val_path)
    fingerprints = pd.concat([koz_effects, val_effects], ignore_index=True, sort=False)
    fingerprints = fingerprints.sort_values(
        ["study_id", "dose_g_l", "material", "reactor_id"]
    ).reset_index(drop=True)

    koz_fits.to_csv(output / "kozlowski_model_fits.csv", index=False)
    koz_fits.loc[koz_fits["selected"].astype(bool)].to_csv(
        output / "kozlowski_selected_fits.csv",
        index=False,
    )
    fingerprints.to_csv(output / "kinetic_fingerprints.csv", index=False)

    status = {
        "kozlowski_2025": {
            "status": "run_public_reactor_level",
            "input": str(koz_path),
            "audit": koz_audit,
        },
        "valentin_bialowiec_2024": {
            "status": "run_public_published_parameters",
            "input": str(val_path),
            "limitation": (
                "No raw reactor trajectories or parameter uncertainty in repository."
            ),
        },
        "zhang_2022": {
            "status": "private_input_required_not_run_in_public_ci",
            "reason": (
                "Author-shared workbook is not redistributed and original triplicate "
                "reactor trajectories are unavailable."
            ),
        },
        "garcia_prats_cyprus2025": {
            "status": "private_input_required_not_run_in_public_ci",
            "reason": (
                "Author-shared unpublished data are intentionally excluded from public CI."
            ),
        },
    }
    (output / "dataset_status.json").write_text(
        json.dumps(status, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = summarize(fingerprints)
    summary["kozlowski_fit_audit"] = koz_audit
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/batch-stage-ab"),
    )
    args = parser.parse_args()
    print(json.dumps(run(args.output), indent=2))


if __name__ == "__main__":
    main()
