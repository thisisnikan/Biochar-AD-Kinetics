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
    included["fit_methane_ml_g_vs"] = included["methane_ml_g_vs"].clip(lower=0.0)
    audit = {
        "rows_included": len(included),
        "reactors_included": int(included["reactor_id"].nunique()),
        "negative_blank_corrected_observations_floored_for_fit": int(negative.sum()),
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
    effects = effects.merge(material, on="reactor_id", how="left", validate="many_to_one")
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


def _published_gompertz_effects(
    data: pd.DataFrame,
    *,
    study_id: str,
    experiment_id: str,
    treatment_col: str,
    control_mask: pd.Series,
    potential_col: str,
    rate_col: str,
    lag_col: str,
    dose_col: str,
    temperature_col: str,
    source_scope: str,
) -> pd.DataFrame:
    control = data.loc[control_mask].iloc[0]
    control_t50 = gompertz_crossing_time(
        float(control[potential_col]), float(control[rate_col]), float(control[lag_col]), 0.5
    )
    control_t90 = gompertz_crossing_time(
        float(control[potential_col]), float(control[rate_col]), float(control[lag_col]), 0.9
    )
    rows: list[dict[str, object]] = []
    for _, row in data.loc[~control_mask].iterrows():
        lag = float(row[lag_col])
        control_lag = float(control[lag_col])
        t50 = gompertz_crossing_time(float(row[potential_col]), float(row[rate_col]), lag, 0.5)
        t90 = gompertz_crossing_time(float(row[potential_col]), float(row[rate_col]), lag, 0.9)
        rows.append(
            {
                "study_id": study_id,
                "experiment_id": experiment_id,
                "treatment_id": str(row[treatment_col]),
                "reactor_id": "published_condition_parameter",
                "control_group_id": f"{study_id}::control",
                "dose_g_l": float(row[dose_col]),
                "delta_potential": relative_gain(
                    float(row[potential_col]), float(control[potential_col])
                ),
                "delta_max_rate": relative_gain(float(row[rate_col]), float(control[rate_col])),
                "delta_lag": (
                    relative_reduction(lag, control_lag)
                    if control_lag > 0
                    else float("nan")
                ),
                "delta_t50": relative_reduction(t50, control_t50),
                "delta_t90": relative_reduction(t90, control_t90),
                "treated_model": "published_modified_gompertz",
                "control_model": "published_modified_gompertz",
                "material": "biochar",
                "material_process_temperature_c": float(row[temperature_col]),
                "source_doi": str(row["source_doi"]),
                "evidence_level": "published_condition_parameter",
                "replicate_level_available": False,
                "source_scope": source_scope,
            }
        )
    return pd.DataFrame(rows)


def valentin_fingerprints(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path).sort_values("dose_g_l").reset_index(drop=True)
    return _published_gompertz_effects(
        data,
        study_id="valentin_bialowiec_2024_scientific_reports",
        experiment_id="valentin_2024_glucose_37c",
        treatment_col="dose_g_l",
        control_mask=data["dose_g_l"].eq(0),
        potential_col="potential_ml_g_vs",
        rate_col="max_rate_ml_g_vs_day",
        lag_col="lag_days",
        dose_col="dose_g_l",
        temperature_col="biochar_pyrolysis_c",
        source_scope="published_table_3",
    )


def chiappero_fingerprints(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path)
    effects = _published_gompertz_effects(
        data,
        study_id="chiappero_2021_catalysts",
        experiment_id="chiappero_2021_bmp",
        treatment_col="treatment",
        control_mask=data["treatment"].eq("CTRL"),
        potential_col="potential_nm3_kg_vs",
        rate_col="max_rate_nm3_kg_vs_day",
        lag_col="lag_days",
        dose_col="dose_g_l",
        temperature_col="pyrolysis_temperature_c",
        source_scope="published_table_3",
    )
    descriptors = data.loc[~data["treatment"].eq("CTRL"), [
        "treatment", "feedstock", "activated", "activation_temperature_c",
        "surface_area_m2_g", "pore_volume_cm3_g",
    ]].copy()
    descriptors = descriptors.rename(columns={"treatment": "treatment_id"})
    return effects.merge(descriptors, on="treatment_id", how="left", validate="one_to_one")


def summarize(fingerprints: pd.DataFrame) -> dict[str, object]:
    by_study = []
    for study_id, group in fingerprints.groupby("study_id", sort=True):
        by_study.append(
            {
                "study_id": study_id,
                "n_effect_rows": len(group),
                "dose_min_g_l": float(group["dose_g_l"].min()),
                "dose_max_g_l": float(group["dose_g_l"].max()),
                "mean_delta_potential": float(group["delta_potential"].mean()),
                "mean_delta_max_rate": float(group["delta_max_rate"].mean()),
                "mean_delta_lag": float(group["delta_lag"].mean()) if group["delta_lag"].notna().any() else None,
                "mean_delta_t50": float(group["delta_t50"].mean()),
                "mean_delta_t90": float(group["delta_t90"].mean()),
            }
        )
    return {
        "interpretation": (
            "Descriptive kinetic fingerprints; published-parameter studies are not treated "
            "as replicate-level estimates and no pooled causal effect is claimed."
        ),
        "n_fingerprint_rows": len(fingerprints),
        "n_independent_studies": int(fingerprints["study_id"].nunique()),
        "studies_with_public_effect_information": sorted(fingerprints["study_id"].unique()),
        "by_study": by_study,
    }


def run(output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    koz_path = Path("data/experimental/kozlowski_2025_bmp.csv")
    val_path = Path("data/experimental/valentin_bialowiec_2024_parameters.csv")
    chi_path = Path("data/experimental/chiappero_2021_parameters.csv")

    koz_fits, koz_effects, koz_audit = kozlowski_fingerprints(koz_path)
    fingerprints = pd.concat(
        [koz_effects, valentin_fingerprints(val_path), chiappero_fingerprints(chi_path)],
        ignore_index=True,
        sort=False,
    ).sort_values(["study_id", "dose_g_l", "treatment_id"]).reset_index(drop=True)

    koz_fits.to_csv(output / "kozlowski_model_fits.csv", index=False)
    koz_fits.loc[koz_fits["selected"].astype(bool)].to_csv(
        output / "kozlowski_selected_fits.csv", index=False
    )
    fingerprints.to_csv(output / "kinetic_fingerprints.csv", index=False)

    status = {
        "kozlowski_2025": {"status": "run_public_reactor_level", "audit": koz_audit},
        "valentin_bialowiec_2024": {
            "status": "run_public_published_parameters",
            "limitation": "No reactor-level parameter uncertainty in repository.",
        },
        "chiappero_2021": {
            "status": "run_public_published_parameters",
            "limitation": "Published condition-level Gompertz parameters; lag is zero for all conditions.",
        },
        "ataa_2026": {
            "status": "registered_not_used_for_g_l_model",
            "reason": "Native dose is 5 g biochar per 20 g food waste; no unverified g/L conversion is made.",
        },
        "zhang_2022": {"status": "private_input_required_not_run_in_public_ci"},
        "garcia_prats_cyprus2025": {"status": "private_input_required_not_run_in_public_ci"},
    }
    (output / "dataset_status.json").write_text(json.dumps(status, indent=2) + "\n")
    summary = summarize(fingerprints)
    summary["kozlowski_fit_audit"] = koz_audit
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/batch-stage-ab"))
    args = parser.parse_args()
    print(json.dumps(run(args.output), indent=2))


if __name__ == "__main__":
    main()
