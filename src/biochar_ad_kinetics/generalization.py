"""Evidence gates for cross-study generalization.

The functions in this module do not fit a pooled model. They answer the prior
question a research group should ask first: does the available evidence support
an honest out-of-study generalization experiment?

A dataset can be computationally fit long before it is scientifically
comparable. The audit therefore keeps evidence sufficiency, uncertainty,
dose support, and experimental heterogeneity visible instead of silently
pooling unlike studies.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = {
    "study_id",
    "response",
    "dose_g_l",
    "material",
    "temperature_c",
    "log_response_ratio",
    "log_response_ratio_se",
    "replicate_level_available",
    "supports_cross_study_pooling",
}


def _validate_effect_table(frame: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(
            f"Missing generalization-audit columns: {', '.join(sorted(missing))}"
        )
    if frame.empty:
        raise ValueError("Generalization audit needs at least one effect row")
    if frame["study_id"].isna().any() or frame["response"].isna().any():
        raise ValueError("study_id and response must be complete")
    if frame["dose_g_l"].isna().any() or (frame["dose_g_l"] < 0).any():
        raise ValueError("dose_g_l must be complete and non-negative")


def _dose_overlap_fraction(a: pd.Series, b: pd.Series) -> float:
    """Return overlap of two observed dose ranges relative to their union.

    This is a support diagnostic, not a similarity score. A value of zero means
    that interpolation learned in one study cannot directly cover the dose
    range of the other study.
    """

    a_min, a_max = float(a.min()), float(a.max())
    b_min, b_max = float(b.min()), float(b.max())
    union_min, union_max = min(a_min, b_min), max(a_max, b_max)
    if union_max == union_min:
        return 1.0
    overlap = max(0.0, min(a_max, b_max) - max(a_min, b_min))
    return float(overlap / (union_max - union_min))


def pairwise_study_support(frame: pd.DataFrame) -> pd.DataFrame:
    """Describe pairwise dose support and major condition differences.

    Rows are stratified by response. No assertion of exchangeability is made;
    the output exists to reveal when a nominal validation split would actually
    be extrapolating across dose, material, or temperature domains.
    """

    _validate_effect_table(frame)
    rows: list[dict[str, object]] = []

    for response, response_frame in frame.groupby("response", sort=True):
        studies = {
            study_id: group.copy()
            for study_id, group in response_frame.groupby("study_id", sort=True)
        }
        for study_a, study_b in combinations(sorted(studies), 2):
            a = studies[study_a]
            b = studies[study_b]
            materials_a = set(a["material"].dropna().astype(str))
            materials_b = set(b["material"].dropna().astype(str))
            temperatures_a = set(a["temperature_c"].dropna().astype(float))
            temperatures_b = set(b["temperature_c"].dropna().astype(float))
            rows.append(
                {
                    "response": response,
                    "study_a": study_a,
                    "study_b": study_b,
                    "dose_range_overlap_fraction": _dose_overlap_fraction(
                        a["dose_g_l"], b["dose_g_l"]
                    ),
                    "shared_exact_doses": len(
                        set(a["dose_g_l"].astype(float)).intersection(
                            set(b["dose_g_l"].astype(float))
                        )
                    ),
                    "shared_material": bool(materials_a.intersection(materials_b)),
                    "shared_temperature": bool(
                        temperatures_a.intersection(temperatures_b)
                    ),
                }
            )

    return pd.DataFrame(rows)


def audit_generalization_readiness(frame: pd.DataFrame) -> pd.DataFrame:
    """Audit whether each response is ready for leave-one-study-out modelling.

    ``ready_for_loso`` is intentionally conservative and purely an evidence
    gate. It requires at least three independent studies, uncertainty on every
    effect row, replicate-level evidence on every effect row, and explicit
    admission of every row for cross-study pooling. Passing this gate does not
    prove exchangeability or causality; it only means a LOSO experiment is no
    longer blocked by these basic evidence defects.
    """

    _validate_effect_table(frame)
    pairwise = pairwise_study_support(frame)
    rows: list[dict[str, object]] = []

    for response, group in frame.groupby("response", sort=True):
        n_studies = int(group["study_id"].nunique())
        uncertainty_complete = bool(
            np.isfinite(group["log_response_ratio_se"].astype(float)).all()
        )
        replicate_level_complete = bool(group["replicate_level_available"].astype(bool).all())
        pooling_admitted = bool(group["supports_cross_study_pooling"].astype(bool).all())
        support = pairwise.loc[pairwise["response"] == response]
        minimum_dose_overlap = (
            float(support["dose_range_overlap_fraction"].min()) if not support.empty else np.nan
        )
        all_pairs_share_material = (
            bool(support["shared_material"].all()) if not support.empty else False
        )
        all_pairs_share_temperature = (
            bool(support["shared_temperature"].all()) if not support.empty else False
        )

        blockers: list[str] = []
        if n_studies < 3:
            blockers.append("fewer_than_three_independent_studies")
        if not uncertainty_complete:
            blockers.append("incomplete_effect_uncertainty")
        if not replicate_level_complete:
            blockers.append("non_replicate_level_evidence_present")
        if not pooling_admitted:
            blockers.append("cross_study_pooling_not_admitted")

        rows.append(
            {
                "response": response,
                "n_effect_rows": len(group),
                "n_independent_studies": n_studies,
                "n_materials": int(group["material"].dropna().nunique()),
                "n_temperatures": int(group["temperature_c"].dropna().nunique()),
                "uncertainty_complete": uncertainty_complete,
                "replicate_level_complete": replicate_level_complete,
                "pooling_admitted": pooling_admitted,
                "minimum_pairwise_dose_overlap_fraction": minimum_dose_overlap,
                "all_study_pairs_share_material": all_pairs_share_material,
                "all_study_pairs_share_temperature": all_pairs_share_temperature,
                "ready_for_loso": not blockers,
                "blocking_reasons": ";".join(blockers),
            }
        )

    return pd.DataFrame(rows).sort_values("response").reset_index(drop=True)
