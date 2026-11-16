"""Fail-closed context audit before cross-study biochar-AD comparisons.

One row represents a documented experimental arm and response, NOT an
independent reactor observation. This module checks source-supported loading
regimes and biochar dose denominators before proposing any cross-study pairing.

It does not convert doses, fit models, verify experimental effects or grant
permission to pool studies. In particular, a numeric 10 can mean different
physical exposures depending on the original denominator.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = (
    "study_id",
    "experiment_id",
    "regime_id",
    "arm_id",
    "response",
    "digestion_mode",
    "is_control",
    "dose_value",
    "dose_unit",
    "dose_denominator",
    "isr_vs",
    "olr_g_vs_l_d",
    "hrt_days",
    "stress_status",
    "stress_evidence",
    "substrate_id",
    "inoculum_id",
    "material_id",
    "source_record_id",
)

# A physical denominator is required even when a dose unit looks familiar.
# No unit conversion is attempted (even for algebraically equivalent units).
UNIT_DENOMINATORS = {
    "g_l": "working_volume_l",
    "g_g_vs": "substrate_vs_g",
    "pct_substrate_vs": "substrate_vs_g",
    "pct_ts": "substrate_ts_g",
    "mg_reactor": "per_reactor",
    "none": "none",
}
STRESS_STATUSES = ("normal", "overloaded", "acid_stressed", "unknown")
MODES = ("batch", "continuous")
KEYS = ("study_id", "experiment_id", "regime_id", "response")


def _boolean(value: object) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    raise ValueError("is_control must contain explicit True/False values")


def _numeric(column: pd.Series) -> pd.Series:
    """Parse finite optional numbers; blanks are missing, not zero."""
    values = pd.to_numeric(column, errors="coerce")
    text = column.astype(str).str.strip().str.lower()
    missing = column.isna() | text.isin({"", "nan", "none"})
    bad = (~missing) & (~np.isfinite(values))
    if bad.any():
        raise ValueError(f"{column.name} must contain finite numbers or blanks")
    return values.astype(float)


def _nonblank(series: pd.Series) -> bool:
    return bool(series.notna().all() and series.astype(str).str.strip().ne("").all())


def _one_value(values: pd.Series) -> object | None:
    unique = values.dropna().unique()
    return unique[0] if len(unique) == 1 else None


def _is_same_number(a: object, b: object) -> bool:
    return bool(
        pd.notna(a)
        and pd.notna(b)
        and np.isclose(float(a), float(b), rtol=1e-6, atol=1e-9)
    )


def _range_overlap(a: tuple[float, float], b: tuple[float, float]) -> float:
    left = max(a[0], b[0])
    right = min(a[1], b[1])
    union = max(a[1], b[1]) - min(a[0], b[0])
    if union == 0:
        return 1.0 if a == b else 0.0
    return float(max(0.0, right - left) / union)


def audit_regime_dose_context(frame: pd.DataFrame) -> dict:
    """Return per-regime blockers and conditional across-study support.

    A pair with candidate_for_contextual_comparison=True only passes THIS
    preflight. The independent replicate/uncertainty/source-license and
    generalization evidence gates remain mandatory. No model is fitted.
    """
    missing = set(REQUIRED_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing context columns: {sorted(missing)}")
    if frame.empty:
        raise ValueError("The context audit requires at least one arm")
    data = frame.loc[:, REQUIRED_COLUMNS].copy()
    identity = ("study_id", "experiment_id", "regime_id", "arm_id", "response")
    for column in (
        "study_id", "experiment_id", "regime_id", "arm_id", "response",
        "substrate_id", "inoculum_id", "source_record_id",
    ):
        if not _nonblank(data[column]):
            raise ValueError(f"{column} must contain a nonblank documented value")
    if data.duplicated(list(identity)).any():
        raise ValueError("Duplicate arm/response identities")
    if not data["digestion_mode"].isin(MODES).all():
        raise ValueError("digestion_mode must be batch or continuous")
    if not data["stress_status"].isin(STRESS_STATUSES).all():
        raise ValueError(f"stress_status must be one of {STRESS_STATUSES}")
    if not data["dose_unit"].isin(UNIT_DENOMINATORS).all():
        raise ValueError(f"dose_unit must be one of {tuple(UNIT_DENOMINATORS)}")
    data["is_control"] = data["is_control"].map(_boolean)
    for column in ("dose_value", "isr_vs", "olr_g_vs_l_d", "hrt_days"):
        data[column] = _numeric(data[column])
    if data["dose_value"].isna().any() or (data["dose_value"] < 0).any():
        raise ValueError("dose_value must be finite and non-negative")
    if ((data["is_control"]) & (data["dose_value"] != 0)).any():
        raise ValueError("A control must have dose_value=0")
    if ((~data["is_control"]) & (data["dose_value"] <= 0)).any():
        raise ValueError("An amended arm must have a positive dose")
    for column in ("isr_vs", "olr_g_vs_l_d", "hrt_days"):
        if (data[column].dropna() <= 0).any():
            raise ValueError(f"{column} must be positive when reported")

    regimes: list[dict] = []
    for keys, group in data.groupby(list(KEYS), sort=True, dropna=False):
        study, experiment, regime_id, response = keys
        blockers: list[str] = []
        positive = group.loc[~group["is_control"]]
        modes = set(group["digestion_mode"])
        statuses = set(group["stress_status"])
        if len(modes) != 1:
            blockers.append("mixed_digestion_modes")
        if len(statuses) != 1:
            blockers.append("mixed_stress_status")
        if "unknown" in statuses:
            blockers.append("stress_status_undocumented")
        if not _nonblank(group["stress_evidence"]):
            blockers.append("stress_evidence_missing")
        if group["substrate_id"].nunique() != 1:
            blockers.append("unmatched_substrate_context")
        if group["inoculum_id"].nunique() != 1:
            blockers.append("unmatched_inoculum_context")
        if not group["is_control"].any():
            blockers.append("missing_zero_dose_control")
        if positive.empty:
            blockers.append("missing_amended_arm")

        invalid_denominator = any(
            UNIT_DENOMINATORS[unit] != denom
            for unit, denom in zip(
                group["dose_unit"], group["dose_denominator"], strict=True
            )
        )
        if invalid_denominator:
            blockers.append("dose_denominator_not_verified")
        if any(unit == "none" for unit in positive["dose_unit"]):
            blockers.append("positive_dose_unit_missing")
        if len(positive[["dose_unit", "dose_denominator"]].drop_duplicates()) > 1:
            blockers.append("mixed_amended_dose_bases")

        mode = _one_value(group["digestion_mode"])
        isr = _one_value(group["isr_vs"])
        olr = _one_value(group["olr_g_vs_l_d"])
        hrt = _one_value(group["hrt_days"])
        if mode == "batch":
            if group["isr_vs"].isna().any() or isr is None:
                blockers.append("batch_isr_vs_missing_or_inconsistent")
        elif mode == "continuous":
            if group["olr_g_vs_l_d"].isna().any() or olr is None:
                blockers.append("continuous_olr_missing_or_inconsistent")
            if group["hrt_days"].isna().any() or hrt is None:
                blockers.append("continuous_hrt_missing_or_inconsistent")
            if group["isr_vs"].notna().any():
                blockers.append("batch_isr_misapplied_to_continuous_mode")

        if positive["material_id"].fillna("").astype(str).str.strip().isin(
            {"", "none", "not_measured"}
        ).any():
            blockers.append("amended_material_identity_missing")
        if positive.empty:
            dose_range = None
            unit = None
            denominator = None
        else:
            dose_range = (
                float(positive["dose_value"].min()),
                float(positive["dose_value"].max()),
            )
            unit = _one_value(positive["dose_unit"])
            denominator = _one_value(positive["dose_denominator"])

        regimes.append(
            {
                "study_id": str(study),
                "experiment_id": str(experiment),
                "regime_id": str(regime_id),
                "response": str(response),
                "digestion_mode": mode,
                "stress_status": _one_value(group["stress_status"]),
                "isr_vs": float(isr) if pd.notna(isr) else None,
                "olr_g_vs_l_d": float(olr) if pd.notna(olr) else None,
                "hrt_days": float(hrt) if pd.notna(hrt) else None,
                "dose_unit": unit,
                "dose_denominator": denominator,
                "amended_dose_range": list(dose_range) if dose_range else None,
                "n_arms": int(len(group)),
                "n_amended_doses": int(positive["dose_value"].nunique()),
                "material_ids": sorted(
                    set(positive["material_id"].dropna().astype(str))
                    - {"", "none", "not_measured"}
                ),
                "source_record_ids": sorted(set(group["source_record_id"].astype(str))),
                "context_blockers": blockers,
                "context_documented": not blockers,
            }
        )

    pairs: list[dict] = []
    for a, b in combinations(regimes, 2):
        if a["study_id"] == b["study_id"] or a["response"] != b["response"]:
            continue
        reasons: list[str] = []
        if not a["context_documented"] or not b["context_documented"]:
            reasons.append("unresolved_regime_context")
        if a["digestion_mode"] != b["digestion_mode"]:
            reasons.append("digestion_mode_mismatch")
        if a["stress_status"] != b["stress_status"]:
            reasons.append("stress_status_mismatch")
        if a["digestion_mode"] == b["digestion_mode"] == "batch":
            if not _is_same_number(a["isr_vs"], b["isr_vs"]):
                reasons.append("isr_vs_mismatch")
        elif a["digestion_mode"] == b["digestion_mode"] == "continuous":
            if not _is_same_number(a["olr_g_vs_l_d"], b["olr_g_vs_l_d"]):
                reasons.append("olr_mismatch")
            if not _is_same_number(a["hrt_days"], b["hrt_days"]):
                reasons.append("hrt_mismatch")

        same_basis = bool(
            a["dose_unit"]
            and b["dose_unit"]
            and a["dose_unit"] == b["dose_unit"]
            and a["dose_denominator"] == b["dose_denominator"]
        )
        overlap = None
        if not same_basis:
            reasons.append("dose_basis_mismatch_no_conversion")
        elif a["amended_dose_range"] and b["amended_dose_range"]:
            overlap = _range_overlap(
                tuple(a["amended_dose_range"]), tuple(b["amended_dose_range"])
            )
            if overlap <= 0:
                reasons.append("no_amended_dose_range_overlap")

        pairs.append(
            {
                "study_a": a["study_id"],
                "regime_a": a["regime_id"],
                "study_b": b["study_id"],
                "regime_b": b["regime_id"],
                "response": a["response"],
                "same_dose_basis": same_basis,
                "dose_overlap_fraction": overlap,
                "same_material_label": bool(
                    set(a["material_ids"]) & set(b["material_ids"])
                ),
                "candidate_for_contextual_comparison": not reasons,
                "blocking_reasons": reasons,
            }
        )

    return {
        "regimes": regimes,
        "cross_study_pairs": pairs,
        "n_context_documented": sum(r["context_documented"] for r in regimes),
        "n_pairs_not_blocked_by_context": sum(
            p["candidate_for_contextual_comparison"] for p in pairs
        ),
        "cross_study_pooling_performed": False,
        "loso_validated": False,
        "interpretation": (
            "Conditional context screening only; matching labels and dose ranges "
            "are not proof of exchangeability. Apply the independent evidence, "
            "effect-uncertainty and held-out-validation gates separately."
        ),
    }
