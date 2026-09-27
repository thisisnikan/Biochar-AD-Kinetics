"""Minimum-information requirements for cross-study biochar-AD prediction.

Two uses:

1. ``build_scorecard`` grades datasets already in the repository against a fixed
   item list, using curated evidence that is cross-checked against committed data
   wherever the data allow an automatic check. A curated status that contradicts
   the data raises.
2. ``check_evidence_package`` grades a new contribution (reactor observations,
   material descriptors and an intervention log) before it is accepted, so a
   collaborating lab can see exactly which measurements are still missing.

Items that software cannot verify from files (gas normalization, license,
chemistry units) are reported as ``unknown`` until a source declaration exists.
``partial`` and ``unknown`` fail closed for cross-study use.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .intake import validate_reactor_observations
from .kinetic_structure import days_to_daily_increment_below

STATUSES = ("yes", "partial", "no", "unknown", "not_applicable")

MATERIAL_COLUMNS = (
    "material_id",
    "feedstock",
    "pyrolysis_temperature_c",
    "residence_time_min",
    "bet_surface_area_m2_g",
    "electrical_conductivity_us_cm",
    "ph",
    "ash_pct",
    "c_pct",
    "h_pct",
    "n_pct",
    "o_pct",
    "particle_size_um",
    "measurement_source",
)
CORE_DESCRIPTORS = (
    "feedstock",
    "pyrolysis_temperature_c",
    "bet_surface_area_m2_g",
    "electrical_conductivity_us_cm",
    "ph",
    "c_pct",
)
NOT_MEASURED = "not_measured"

INTERVENTION_COLUMNS = (
    "study_id",
    "experiment_id",
    "reactor_id",
    "time_days",
    "intervention",
    "amount",
    "amount_unit",
    "scope",
    "source_record_id",
)
INTERVENTION_SCOPES = ("reactor", "lab_unspecified")

PLATEAU_FRACTION = 0.01

# Items software cannot verify from the files; a contributor must declare them
# with evidence (for example a method section, instrument manual or license URL).
DECLARATION_ITEMS = (
    "methane_unit_verified",
    "substrate_inoculum_characterized",
    "stability_chemistry_with_units",
    "redistributable_source",
)


def load_items(path: str | Path) -> dict:
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    if tuple(spec["status_vocabulary"]) != STATUSES:
        raise ValueError("Item file status vocabulary differs from the module vocabulary")
    return spec


def validate_evidence(evidence: pd.DataFrame, items: dict) -> None:
    """Every dataset must state every item with an allowed status and evidence."""

    item_ids = [item["id"] for item in items["items"]]
    if evidence.duplicated(["dataset", "item_id"]).any():
        raise ValueError("Duplicate dataset/item evidence rows")
    unknown_items = set(evidence["item_id"]) - set(item_ids)
    if unknown_items:
        raise ValueError(f"Evidence for undefined items: {sorted(unknown_items)}")
    for dataset, group in evidence.groupby("dataset"):
        missing = set(item_ids) - set(group["item_id"])
        if missing:
            raise ValueError(f"{dataset} is missing items: {sorted(missing)}")
    bad = ~evidence["status"].isin(STATUSES)
    if bad.any():
        raise ValueError(f"Invalid statuses: {sorted(set(evidence.loc[bad, 'status']))}")
    if evidence["evidence"].fillna("").str.strip().eq("").any():
        raise ValueError("Every status needs an evidence statement")


def _share_status(share: float) -> str:
    if share >= 0.8:
        return "yes"
    if share >= 0.5:
        return "partial"
    return "no"


def _replicate_status(minimum: int) -> str:
    if minimum >= 3:
        return "yes"
    if minimum >= 2:
        return "partial"
    return "no"


def _count_status(count: int, required: int) -> str:
    return "yes" if count >= required else "no"


def reactor_plateau_share(frame: pd.DataFrame, reactor_keys: list[str]) -> float:
    reached = []
    for _, reactor in frame.groupby(reactor_keys, sort=True):
        r = reactor.sort_values("time_days")
        reached.append(
            np.isfinite(
                days_to_daily_increment_below(
                    r["time_days"].to_numpy(float),
                    r["raw_cumulative_methane_ml"].to_numpy(float),
                    PLATEAU_FRACTION,
                )
            )
        )
    return float(np.mean(reached)) if reached else float("nan")


def observation_checks(frame: pd.DataFrame) -> dict[str, str]:
    """Automatic item statuses from a reactor-observation table (data contract format)."""

    data = frame.copy()
    for column in ("is_control", "is_inoculum_blank", "qc_include"):
        data[column] = data[column].astype(str).str.lower().isin({"true", "1", "yes"})
    included = data[data["qc_include"]]
    reactors = ["study_id", "experiment_id", "reactor_id"]
    amended = included[~included["is_inoculum_blank"]]
    per_arm = amended.groupby(["experiment_id", "treatment_id"])["reactor_id"].nunique()
    positive = included[pd.to_numeric(included["dose_value"], errors="coerce") > 0]
    doses_per_material = positive.groupby(["experiment_id", "material_id"])["dose_value"].nunique()
    temps_per_material = positive.groupby("material_id")["temperature_c"].nunique()
    dose_units = set(positive["dose_unit"].astype(str))
    if dose_units and dose_units <= {"g_l", "g_g_vs"}:
        dose_basis = "yes"
    elif dose_units & {"pct_ts", "mg_reactor"}:
        dose_basis = "partial"
    else:
        dose_basis = "no"
    zero_control = included[
        included["is_control"]
        & ~included["is_inoculum_blank"]
        & (pd.to_numeric(included["dose_value"], errors="coerce") == 0)
    ]
    return {
        "reactor_level_trajectories": "yes" if included["reactor_id"].nunique() else "no",
        "intact_replicates_ge3": _replicate_status(int(per_arm.min()) if len(per_arm) else 0),
        "inoculum_blanks": "yes" if included["is_inoculum_blank"].any() else "no",
        "zero_dose_substrate_control": "yes" if len(zero_control) else "no",
        "run_to_plateau": _share_status(reactor_plateau_share(included, reactors)),
        "dose_physical_basis": dose_basis,
        "dose_levels_ge3": _count_status(
            int(doses_per_material.max()) if len(doses_per_material) else 0, 3
        ),
        "materials_ge2": _count_status(int(positive["material_id"].nunique()), 2),
        "digestion_temperature": "yes"
        if pd.to_numeric(included["temperature_c"], errors="coerce").notna().all()
        else "no",
        "temperature_levels_ge2": _count_status(
            int(temps_per_material.max()) if len(temps_per_material) else 0, 2
        ),
    }


def validate_material_descriptors(frame: pd.DataFrame) -> tuple[list[str], str]:
    """Return (errors, material_descriptors_core status).

    Blank cells are errors: a descriptor that was not measured must say
    ``not_measured`` so missingness is explicit rather than silent.
    """

    errors: list[str] = []
    missing = set(MATERIAL_COLUMNS) - set(frame.columns)
    if missing:
        return [f"missing columns: {sorted(missing)}"], "no"
    if frame["material_id"].duplicated().any():
        errors.append("duplicate material_id")
    text = frame[list(MATERIAL_COLUMNS)].astype(str).apply(lambda s: s.str.strip())
    blanks = text.eq("") | text.isin({"nan", "NaN", "None"})
    if blanks.to_numpy().any():
        errors.append("blank descriptor cells: use 'not_measured' for unmeasured values")
    numeric = [
        c for c in MATERIAL_COLUMNS if c not in {"material_id", "feedstock", "measurement_source"}
    ]
    for column in numeric:
        values = text[column]
        bad = ~values.eq(NOT_MEASURED) & pd.to_numeric(values, errors="coerce").isna()
        if bad.any():
            errors.append(f"{column} must be numeric or '{NOT_MEASURED}'")
    core = text[list(CORE_DESCRIPTORS)]
    measured = ~core.eq(NOT_MEASURED) & ~blanks[list(CORE_DESCRIPTORS)]
    if measured.to_numpy().all():
        status = "yes"
    elif measured.to_numpy().any():
        status = "partial"
    else:
        status = "no"
    return errors, status


def validate_intervention_log(
    frame: pd.DataFrame, reactor_ids: set[tuple[str, str, str]]
) -> tuple[list[str], str]:
    """Return (errors, co_interventions_per_reactor status).

    Exposure must be recorded per reactor. A laboratory-wide event with no named
    reactors is allowed as ``lab_unspecified`` but downgrades the item to partial,
    because it cannot be assigned to bottles.
    """

    errors: list[str] = []
    missing = set(INTERVENTION_COLUMNS) - set(frame.columns)
    if missing:
        return [f"missing columns: {sorted(missing)}"], "no"
    scope = frame["scope"].astype(str)
    if not scope.isin(INTERVENTION_SCOPES).all():
        errors.append(f"scope must be one of {INTERVENTION_SCOPES}")
    reactor_rows = frame[scope == "reactor"]
    keys = set(
        zip(
            reactor_rows["study_id"].astype(str),
            reactor_rows["experiment_id"].astype(str),
            reactor_rows["reactor_id"].astype(str),
            strict=True,
        )
    )
    unknown = keys - reactor_ids
    if unknown:
        errors.append(f"interventions for reactors not in observations: {sorted(unknown)[:5]}")
    amount = pd.to_numeric(frame["amount"], errors="coerce")
    no_unit = amount.notna() & frame["amount_unit"].fillna("").astype(str).str.strip().eq("")
    if no_unit.any():
        errors.append("every amount needs an amount_unit")
    if pd.to_numeric(frame["time_days"], errors="coerce").isna().any():
        errors.append("time_days must be numeric")
    if frame["source_record_id"].fillna("").astype(str).str.strip().eq("").any():
        errors.append("every intervention needs a source_record_id")
    if errors:
        return errors, "no"
    return errors, "partial" if (scope == "lab_unspecified").any() else "yes"


def check_evidence_package(
    observations: pd.DataFrame,
    materials: pd.DataFrame | None,
    interventions: pd.DataFrame | None,
    items: dict,
    declarations: dict | None = None,
) -> dict:
    """Grade a new contribution against every minimum-information item.

    ``declarations`` maps declaration-only items to ``{"status", "evidence"}``.
    Declarations for automatically checked items are rejected, so a declaration
    can never override what the data show.
    """

    intake = validate_reactor_observations(observations)
    statuses = {item["id"]: "unknown" for item in items["items"]}
    errors: dict[str, list[str]] = {}
    if intake.valid:
        statuses.update(observation_checks(observations))
    else:
        statuses["reactor_level_trajectories"] = "no"
        errors["observations"] = [i.message for i in intake.issues if i.severity == "error"]
    if materials is not None:
        material_errors, statuses["material_descriptors_core"] = validate_material_descriptors(
            materials
        )
        if material_errors:
            errors["materials"] = material_errors
        observed = set(
            observations.loc[
                pd.to_numeric(observations["dose_value"], errors="coerce") > 0, "material_id"
            ].astype(str)
        )
        undescribed = observed - set(materials.get("material_id", pd.Series(dtype=str)).astype(str))
        if undescribed:
            errors.setdefault("materials", []).append(
                f"materials without descriptors: {sorted(undescribed)}"
            )
            statuses["material_descriptors_core"] = "no"
    if interventions is not None:
        ids = set(
            zip(
                observations["study_id"].astype(str),
                observations["experiment_id"].astype(str),
                observations["reactor_id"].astype(str),
                strict=True,
            )
        )
        log_errors, statuses["co_interventions_per_reactor"] = validate_intervention_log(
            interventions, ids
        )
        if log_errors:
            errors["interventions"] = log_errors
    declared_evidence = {}
    for item_id, declaration in (declarations or {}).items():
        if item_id not in DECLARATION_ITEMS:
            errors.setdefault("declarations", []).append(
                f"{item_id} is checked from data and cannot be declared"
            )
            continue
        status = declaration.get("status")
        text = str(declaration.get("evidence", "")).strip()
        if status not in STATUSES or not text:
            errors.setdefault("declarations", []).append(
                f"{item_id} needs a valid status and non-empty evidence"
            )
            continue
        statuses[item_id] = status
        declared_evidence[item_id] = text
    critical = [item["id"] for item in items["items"] if item["critical_for_cross_study"]]
    blocking = [i for i in critical if statuses[i] != "yes"]
    return {
        "intake_valid": intake.valid,
        "item_status": statuses,
        "errors": errors,
        "blocking_critical_items": blocking,
        "ready_for_cross_study_use": not blocking and not errors,
        "declaration_required": [i for i in DECLARATION_ITEMS if i not in declared_evidence],
        "declared_evidence": declared_evidence,
    }


def build_scorecard(evidence: pd.DataFrame, items: dict) -> pd.DataFrame:
    critical = {item["id"] for item in items["items"] if item["critical_for_cross_study"]}
    rows = []
    for dataset, group in evidence.groupby("dataset", sort=True):
        status = dict(zip(group["item_id"], group["status"], strict=True))
        blocking = sorted(i for i in critical if status[i] != "yes")
        rows.append(
            {
                "dataset": dataset,
                "items_yes": sum(s == "yes" for s in status.values()),
                "items_total": len(status),
                "critical_yes": sum(status[i] == "yes" for i in critical),
                "critical_total": len(critical),
                "ready_for_cross_study_use": not blocking,
                "blocking_critical_items": ";".join(blocking),
            }
        )
    return pd.DataFrame(rows)
