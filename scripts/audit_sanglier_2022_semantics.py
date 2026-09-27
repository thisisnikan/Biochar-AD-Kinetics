"""Audit Sanglier 2022 variable semantics, intervention exposure and label conflicts.

Inputs are only the committed, source-traceable intake tables under
``results/intake/``. The original workbook is not needed and is not read.

Outputs (``results/validation/``):

- ``sanglier_2022_variable_dictionary.csv``: meaning and unit status per variable,
  with the evidence available in this repository. Units are never guessed: a unit
  is ``unresolved`` unless a committed source label or an exact internal identity
  supports it.
- ``sanglier_2022_event_scope.csv``: each source event classified by the scope
  its own text supports (named bottles, named condition, unspecified subset).
- ``sanglier_2022_treatment_adjudication.csv``: one row per bottle/batch with
  original source values, an evidence class and the rule that produced it.
  Original values are copied, never overwritten.
- ``sanglier_2022_semantics_qc.json``: numerical consistency checks and hashes.

Methane outcome values are used here only for the dimensional identity
``yield = corrected volume / substrate VS``; no treatment contrast is computed.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INTAKE = ROOT / "results" / "intake"
DEFAULT_OUTPUT = ROOT / "results" / "validation"

SOURCES = {
    "methane": INTAKE / "sanglier_2022_candidate.csv.gz",
    "chemistry": INTAKE / "sanglier_2022_chemistry.csv",
    "events": INTAKE / "sanglier_2022_events.csv",
    "bottle_batches": INTAKE / "sanglier_2022_bottle_batches.csv",
}

# Each event is classified from its own source text. The key phrase must still be
# present in the committed text; otherwise the audit fails closed.
EVENT_SCOPE = {
    "Events!2": (
        "Experiment start",
        "lab_time_origin",
        "",
        "none",
        "Defines BRL day 0; not an intervention.",
    ),
    "Events!3": (
        "for one condition in MBE (MBE[2]+)",
        "condition_named",
        "MBE[2]+",
        "ammonium_bicarbonate",
        (
            "Text names one condition. Inoculation also records 3.11 g ammonium bicarbonate "
            "for every BRL bottle at batch 11, which contradicts the single-condition scope."
        ),
    ),
    "Events!4": (
        "bottles IV.1 to IV.9 start getting the Celtics",
        "bottles_named",
        "IV.1-IV.9 Celtics TE; IV.10-IV.15 water",
        "trace_element_regime_change",
        "Named bottle ranges; agrees with Inoculation TE 2 volumes (2.0 or 0.35 mL vs 0.0).",
    ),
    "Events!5": (
        "some bottles only have the motors turned on",
        "unspecified_subset",
        "some LBE bottles",
        "mixing_reduction",
        "Bottle subset not named; days 106-128. No bottle can be assigned or cleared.",
    ),
    "Events!6": (
        "Bottle IV.3 (Control) stopped producing",
        "bottles_named",
        "IV.3",
        "outcome_event",
        "Reports a process outcome, not an intervention; not an exclusion instruction.",
    ),
    "Events!7": (
        "Bottle IV.2 (Control) stopped producing",
        "bottles_named",
        "IV.2",
        "outcome_event",
        "Reports a process outcome, not an intervention; not an exclusion instruction.",
    ),
    "Events!8": (
        "Technical problem on bottle IV.5",
        "bottles_named",
        "IV.5",
        "technical_fault_source_exclusion",
        "Source text says the bottle should be removed; duration beyond batch 1 unstated.",
    ),
    "Events!9": (
        "Technical problem on bottle IV.8",
        "bottles_named",
        "IV.8",
        "technical_fault_source_exclusion",
        "Source text says the bottle should be removed; duration beyond batch 1 unstated.",
    ),
}

CHEMISTRY_VARIABLES = {
    # variable: (conventional meaning, meaning status)
    "pH": ("pH", "resolved_dimensionless_scale"),
    "TAN": ("total ammonia nitrogen (conventional abbreviation)", "abbreviation_only"),
    "FAN": ("free ammonia nitrogen (conventional abbreviation)", "abbreviation_only"),
    "sCOD": ("soluble chemical oxygen demand (conventional abbreviation)", "abbreviation_only"),
    "TS": ("total solids (conventional abbreviation)", "abbreviation_only"),
    "VS": ("volatile solids (conventional abbreviation)", "abbreviation_only"),
    "C2": ("acetic acid (C2 chain-length convention)", "abbreviation_only"),
    "C3": ("propionic acid (C3 chain-length convention)", "abbreviation_only"),
    "C4": ("n-butyric acid (C4 chain-length convention)", "abbreviation_only"),
    "C5": ("n-valeric acid (C5 chain-length convention)", "abbreviation_only"),
    "C6": ("n-caproic acid (C6 chain-length convention)", "abbreviation_only"),
    "IC4": ("iso-butyric acid (branched C4 convention)", "abbreviation_only"),
    "IC5": ("iso-valeric acid (branched C5 convention)", "abbreviation_only"),
    "IC6": ("iso-caproic acid (branched C6 convention)", "abbreviation_only"),
}

# Anthonisen et al. (1976) free-ammonia form, used only as a consistency probe.
ANTHONISEN_EXPONENT = 6344.0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_sources() -> dict[str, pd.DataFrame]:
    return {
        "methane": pd.read_csv(SOURCES["methane"]),
        "chemistry": pd.read_csv(SOURCES["chemistry"]),
        "events": pd.read_csv(SOURCES["events"]),
        "bottle_batches": pd.read_csv(SOURCES["bottle_batches"]),
    }


def _stats(series: pd.Series) -> dict[str, object]:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return {"n_nonmissing": 0, "n_zero": 0, "min": None, "median": None, "max": None}
    return {
        "n_nonmissing": int(values.size),
        "n_zero": int((values == 0).sum()),
        "min": float(values.min()),
        "median": float(values.median()),
        "max": float(values.max()),
    }


def log10_scale_gap(series: pd.Series) -> float:
    """Largest gap between consecutive sorted log10 positive values.

    A gap above one decade inside a single column is treated as evidence of mixed
    scales or bases; it is reported, never corrected.
    """

    values = np.sort(np.log10(pd.to_numeric(series, errors="coerce").dropna().to_numpy()))
    values = values[np.isfinite(values)]
    if values.size < 2:
        return 0.0
    return float(np.max(np.diff(values)))


def chemistry_checks(chem: pd.DataFrame) -> dict[str, object]:
    checks: dict[str, object] = {}

    # FAN: is it a deterministic transform of TAN and pH?
    both = chem.dropna(subset=["TAN", "FAN", "pH"])
    simple_ratio = both["FAN"] / both["TAN"]
    temperatures = np.arange(20.0, 45.01, 0.01)
    best = None
    for temperature in temperatures:
        predicted = (
            both["TAN"]
            * 10 ** both["pH"]
            / (np.exp(ANTHONISEN_EXPONENT / (273.15 + temperature)) + 10 ** both["pH"])
        )
        ratio = both["FAN"] / predicted
        score = abs(float(ratio.mean()) - 1.0)
        if best is None or score < best[0]:
            best = (score, float(temperature), float(ratio.std(ddof=1) / ratio.mean()))
    checks["FAN_derivation_probe"] = {
        "rows_with_TAN_FAN_pH": len(both),
        "labs": sorted(both["Lab"].unique().tolist()),
        "cv_of_FAN_over_TAN": float(simple_ratio.std(ddof=1) / simple_ratio.mean()),
        "anthonisen_best_matching_temperature_c": round(best[1], 2),
        "cv_of_FAN_over_anthonisen_prediction": best[2],
        "interpretation": (
            "FAN varies with pH at fixed TAN exactly as an equilibrium transform "
            "would; after that transform the residual CV is about 1%. FAN is "
            "therefore treated as derived from TAN and pH, not as an independent "
            "measurement. The formula and temperature the source used are not "
            "documented in the repository; the matching temperature is a probe "
            "result, not a recovered operating temperature."
        ),
    }

    # TS / VS basis
    tv = chem.dropna(subset=["TS", "VS"])
    by_lab = {}
    for lab, group in tv.groupby("Lab"):
        by_lab[lab] = {
            "rows": len(group),
            "TS_range": [float(group["TS"].min()), float(group["TS"].max())],
            "VS_range": [float(group["VS"].min()), float(group["VS"].max())],
            "rows_VS_greater_than_TS": int((group["VS"] > group["TS"]).sum()),
        }
    checks["TS_VS_basis"] = {
        "by_lab": by_lab,
        "TS_log10_max_gap": log10_scale_gap(chem["TS"]),
        "VS_log10_max_gap": log10_scale_gap(chem["VS"]),
        "interpretation": (
            "BRL rows have VS greater than TS in every row, which is impossible "
            "if both columns share one basis; LBE rows have VS below TS and values "
            "two orders of magnitude smaller. TS and VS therefore use different "
            "bases between labs (and possibly between TS and VS within BRL). No "
            "conversion is applied; cross-lab TS/VS comparison is blocked."
        ),
    }

    # sCOD scale discontinuity
    scod = chem.dropna(subset=["sCOD"])
    high = scod[scod["sCOD"] > 10 * scod["sCOD"].median()]
    checks["sCOD_scale"] = {
        "rows": len(scod),
        "log10_max_gap": log10_scale_gap(chem["sCOD"]),
        "rows_above_10x_median": len(high),
        "rows_above_10x_median_source": sorted(high["source_analysis_row"].tolist()),
        "labs_batches_above_10x_median": sorted(
            {f"{r.Lab} batch {int(r.Batch)} {r.Sampling}" for r in high.itertuples()}
        ),
        "interpretation": (
            "One sampling occasion sits one to two orders of magnitude above every "
            "other sCOD value. This is consistent with a different unit or dilution "
            "basis for that occasion, but the repository cannot establish which; "
            "those rows are flagged, not converted."
        ),
    }
    return checks


def dose_checks(chem: pd.DataFrame, methane: pd.DataFrame) -> dict[str, object]:
    first = chem[(chem["Batch"] == 1) & (chem["Sampling"] == "t0")].dropna(subset=["Current_mass"])
    ratios = {}
    for condition, group in first.groupby("Cond"):
        pct = 100 * group["inoculation_biochar_g"] / group["Current_mass"]
        ratios[condition] = [round(float(pct.min()), 3), round(float(pct.max()), 3)]
    cycles = methane.drop_duplicates(["lab", "batch_id", "bottle_id"])
    initial = (
        cycles[cycles["batch_id"] == 1]
        .groupby(["lab", "biochar_label_ampts"])["inoculation_biochar_g"]
        .agg(lambda s: sorted({float(v) for v in s}))
    )
    topups = cycles[cycles["batch_id"] > 1]
    ratio_rows = []
    for (lab, batch), group in topups.groupby(["lab", "batch_id"]):
        one = group.loc[group["biochar_label_ampts"] == 1, "inoculation_biochar_g"]
        two = group.loc[group["biochar_label_ampts"] == 2, "inoculation_biochar_g"]
        if len(one) and len(two):
            ratio_rows.append(float(two.mean() / one.mean()))
    return {
        "LBE_batch1_biochar_percent_of_recorded_reactor_mass": ratios,
        "batch1_biochar_g_by_lab_label": {
            f"{lab} label {int(label)}": values for (lab, label), values in initial.items()
        },
        "BRL_reactor_mass_recorded": bool(
            chem.loc[chem["Lab"] == "BRL", "Current_mass"].notna().any()
        ),
        "topup_ratio_label2_over_label1": {
            "min": round(min(ratio_rows), 4),
            "max": round(max(ratio_rows), 4),
        },
        "interpretation": (
            "LBE batch-1 grams equal 1% and 2% of the recorded reactor mass, "
            "matching the deposit's w:w description. BRL used 4 g and 8 g but no "
            "BRL reactor mass is recorded, so BRL's w:w basis is unverifiable "
            "here. Later batches add smaller top-up masses whose purpose is not "
            "documented; the label-2/label-1 ratio stays about 2. Labels 1 and 2 "
            "are therefore not interchangeable g/L doses across labs."
        ),
    }


def methane_checks(methane: pd.DataFrame) -> dict[str, object]:
    rows = methane.dropna(
        subset=["methane_yield_nml_gvs", "volume_corrected_nml", "inoculation_substrate_vs_g"]
    )
    residual = (
        rows["volume_corrected_nml"] / rows["inoculation_substrate_vs_g"]
        - rows["methane_yield_nml_gvs"]
    )
    corrected = rows[rows["volume_raw_nml"] != rows["volume_corrected_nml"]]
    factor = corrected["volume_corrected_nml"] / corrected["volume_raw_nml"]
    return {
        "yield_equals_corrected_volume_over_substrate_vs": {
            "rows_checked": len(rows),
            "rows_within_1e-6": int((residual.abs() < 1e-6).sum()),
            "max_abs_residual": float(residual.abs().max()),
        },
        "volume_correction": {
            "rows_raw_differs_from_corrected_by_lab": {
                lab: int(n) for lab, n in corrected.groupby("lab").size().items()
            },
            "corrected_over_raw_range": [float(factor.min()), float(factor.max())],
            "interpretation": (
                "Only LBE applies a correction (factor 1.001-1.090); BRL corrected "
                "equals raw. The correction method is not documented in the "
                "repository. Within-lab ratios are unaffected; cross-lab absolute "
                "yield comparison inherits an undocumented lab-specific processing "
                "difference."
            ),
        },
        "unit_interpretation": (
            "Source headers are 'Volume_raw', 'Volume', 'Flow' and 'Methane yield' "
            "without units. The candidate builder names them *_nml, *_nml_h and "
            "*_nml_gvs; that naming is not backed by committed source evidence. "
            "The exact identity above proves yield and volume share a volume unit "
            "per substrate-VS unit, but not which volume unit or normalization."
        ),
    }


def variable_dictionary(chem: pd.DataFrame, methane: pd.DataFrame, qc: dict) -> pd.DataFrame:
    rows = []
    for variable, (meaning, meaning_status) in CHEMISTRY_VARIABLES.items():
        unit, unit_status, evidence, admission = "", "unresolved", "", "context_only"
        if variable == "pH":
            unit, unit_status = "dimensionless", "resolved_by_definition"
            evidence = "pH is a dimensionless scale; range is physically plausible."
            admission = "cross_source_comparable"
        elif variable == "FAN":
            evidence = (
                "Numerically derived from TAN and pH (see FAN_derivation_probe); "
                "BRL only; not an independent measurement."
            )
            admission = "prohibited_as_independent_feature"
        elif variable in ("TS", "VS"):
            evidence = "Different bases between labs; BRL VS exceeds TS in every row."
            admission = "blocked_basis_conflict"
        elif variable == "sCOD":
            evidence = "One occasion is 1-2 orders of magnitude above the rest (see sCOD_scale)."
            admission = "blocked_scale_discontinuity"
        elif variable == "TAN":
            evidence = "Header has no unit; no committed source unit label."
        else:
            evidence = (
                "Header has no unit; molar, mass and COD bases are all possible and "
                "change cross-source comparison and acid ratios."
            )
        rows.append(
            {
                "variable": variable,
                "source_sheet": "Analyses",
                "source_header": variable,
                "repository_column": variable,
                "meaning": meaning,
                "meaning_status": meaning_status,
                "unit": unit,
                "unit_status": unit_status,
                "evidence": evidence,
                "admission_use": admission,
                **_stats(chem[variable]),
            }
        )
    methane_meta = {
        "volume_raw_nml": (
            "Volume_raw",
            "cumulative methane volume before source correction",
        ),
        "volume_corrected_nml": ("Volume", "cumulative methane volume after source correction"),
        "flow_nml_h": ("Flow", "methane flow"),
        "methane_yield_nml_gvs": ("Methane yield", "cumulative methane per substrate VS"),
    }
    for column, (header, meaning) in methane_meta.items():
        evidence = qc["methane"]["unit_interpretation"]
        status = "builder_asserted_unverified"
        use = "within_lab_ratio_only"
        if column == "methane_yield_nml_gvs":
            evidence = (
                "Exact identity with Volume / Inoculation 'VS Substrate' in "
                f"{qc['methane']['yield_equals_corrected_volume_over_substrate_vs']['rows_within_1e-6']}"
                " rows. Volume unit and normalization remain unverified."
            )
            status = "relation_verified_unit_unverified"
        rows.append(
            {
                "variable": column,
                "source_sheet": "AMPTShort",
                "source_header": header,
                "repository_column": column,
                "meaning": meaning,
                "meaning_status": "source_header_plus_identity"
                if column == "methane_yield_nml_gvs"
                else "source_header",
                "unit": "suffix asserted by builder",
                "unit_status": status,
                "evidence": evidence,
                "admission_use": use,
                **_stats(methane[column]),
            }
        )
    return pd.DataFrame(rows)


def event_scope(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    seen = set()
    for event in events.itertuples(index=False):
        key = event.source_event_row
        if key not in EVENT_SCOPE:
            raise ValueError(f"Unclassified source event {key}; audit fails closed")
        phrase, scope, target, kind, rationale = EVENT_SCOPE[key]
        if phrase not in str(event.Event):
            raise ValueError(f"Event text for {key} changed; re-adjudicate scope")
        seen.add(key)
        rows.append(
            {
                "source_event_row": key,
                "lab": event.Lab,
                "days": event.Days,
                "batch": event.Batch,
                "event_text": event.Event,
                "scope_supported_by_text": scope,
                "scope_target": target,
                "event_kind": kind,
                "rationale": rationale,
                "bottle_exposure_assignable": scope == "bottles_named"
                or scope == "condition_named",
            }
        )
    missing = set(EVENT_SCOPE) - seen
    if missing:
        raise ValueError(f"Expected events missing from intake: {sorted(missing)}")
    return pd.DataFrame(rows)


def _norm(label: object) -> str:
    return str(label).replace(" ", "")


def adjudicate(methane: pd.DataFrame, bottle_batches: pd.DataFrame) -> pd.DataFrame:
    """Classify every bottle/batch without altering any source value.

    Classes: source_consistent, resolvable_from_source, ambiguous, conflicting,
    excluded. ``rules`` lists every rule that fired, in order.
    """

    cycles = (
        methane.drop_duplicates(["lab", "batch_id", "bottle_id"])
        .sort_values(["lab", "bottle_id", "batch_id"])
        .reset_index(drop=True)
    )
    counts = methane.groupby(["lab", "batch_id", "bottle_id"]).size()
    starts = cycles.groupby(["lab", "batch_id"])["batch_start_days_lab"].first()
    ends = methane.groupby(["lab", "batch_id"])["absolute_days_lab"].max()
    rows = []
    conflicted_from: dict[tuple[str, str], int] = {}
    ammonium_from: dict[tuple[str, str], int] = {}
    for c in cycles.itertuples(index=False):
        rules: list[str] = []
        classes: list[str] = []
        evidence: list[str] = []
        label_ampts = _norm(c.source_condition_ampts)
        label_inoc = _norm(c.source_condition_inoculation)
        ab = c.inoculation_ammonium_bicarbonate_g
        ab_positive = pd.notna(ab) and float(ab) > 0
        te_label = f"{c.te_supplementation_ampts}/{c.te_solution_ampts}"
        te_volumes_zero = (pd.isna(c.inoculation_te1_ml) or float(c.inoculation_te1_ml) == 0) and (
            pd.isna(c.inoculation_te2_ml) or float(c.inoculation_te2_ml) == 0
        )

        if int(c.biochar_label_ampts) == 0 and float(c.inoculation_biochar_g or 0) > 0:
            rules.append("R1_control_label_positive_biochar_mass")
            classes.append("conflicting")
            evidence.append(
                f"AMPTShort Biochar=0 and Cond={c.source_condition_ampts}; "
                f"{c.source_inoculation_row} Biochar={c.inoculation_biochar_g} g"
            )
            conflicted_from.setdefault((c.lab, c.bottle_id), int(c.batch_id))
        elif (c.lab, c.bottle_id) in conflicted_from:
            rules.append("R2_carryover_after_conflicting_cycle")
            classes.append("excluded")
            evidence.append(
                "Digestate is partly recirculated; any biochar possibly added in batch "
                f"{conflicted_from[(c.lab, c.bottle_id)]} may persist in this bottle."
            )

        if label_ampts != label_inoc:
            rules.append("R3_condition_label_disagreement")
            if label_inoc.endswith("+N") and ab_positive:
                classes.append("resolvable_from_source")
                evidence.append(
                    f"AMPTShort '{c.source_condition_ampts}' vs Inoculation "
                    f"'{c.source_condition_inoculation}'; Inoculation records {ab} g "
                    "ammonium bicarbonate and Events!3 names ammonia supplementation "
                    "for MBE[2]+, so '+ N' denotes that co-intervention."
                )
            else:
                classes.append("ambiguous")
                evidence.append("Label disagreement without supporting source record.")

        if ab_positive:
            named = c.lab == "BRL" and label_inoc.startswith("MBE[2]+")
            rules.append("R4_ammonium_bicarbonate_recorded")
            if named:
                classes.append("resolvable_from_source")
                evidence.append(f"{ab} g ammonium bicarbonate; condition named in Events!3.")
            else:
                classes.append("conflicting")
                source = "Events!3 names only MBE[2]+" if c.lab == "BRL" else "no source event"
                evidence.append(
                    f"{ab} g ammonium bicarbonate recorded for {c.source_condition_inoculation}; "
                    f"{source}."
                )

        prior_ammonium = ammonium_from.get((c.lab, c.bottle_id))
        if prior_ammonium is not None and not ab_positive and not label_inoc.endswith("+N"):
            rules.append("R10_carryover_after_disputed_ammonium_addition")
            classes.append("ambiguous")
            evidence.append(
                f"Inoculation recorded ammonium bicarbonate for this bottle in batch "
                f"{prior_ammonium}; recirculated digestate can carry residual ammonia "
                "into this cycle, and the scope of that addition is disputed."
            )
        if ab_positive and not (c.lab == "BRL" and label_inoc.startswith("MBE[2]+")):
            ammonium_from.setdefault((c.lab, c.bottle_id), int(c.batch_id))

        if c.lab == "LBE" and c.batch_id >= 11 and label_inoc.endswith("+"):
            rules.append("R5_te_label_vs_volume")
            if te_volumes_zero:
                classes.append("resolvable_from_source")
                evidence.append(
                    f"TE label '{te_label}' but TE volumes are zero/empty; Events!4 states "
                    "IV.10-IV.15 receive water from batch 11."
                )
            else:
                classes.append("conflicting")
                evidence.append("TE label and volume disagree without explanation.")

        if label_inoc.endswith("+") and not ab_positive and c.batch_id < 11:
            rules.append("R6_plus_label_without_recorded_difference")
            if c.lab == "BRL":
                classes.append("resolvable_from_source")
                evidence.append(
                    "'MBE[2] +' designates the bottles that later receive ammonia "
                    "(Events!3); no recorded difference from MBE[2] before batch 11."
                )
            else:
                classes.append("ambiguous")
                evidence.append(
                    f"'{c.source_condition_inoculation}' has the same recorded biochar, TE "
                    "and substrate metadata as the unmarked condition before batch 11; "
                    "the meaning of '+' is not documented in the repository."
                )

        if c.lab == "LBE" and c.bottle_id in ("IV.5", "IV.8") and c.batch_id == 1:
            rules.append("R7_source_technical_exclusion")
            classes.append("excluded")
            evidence.append("Events!8/9: technical problem (leak?); source says remove.")

        start = float(starts[(c.lab, c.batch_id)])
        end = float(ends[(c.lab, c.batch_id)])
        # Events!5: reduced mixing from day 106 until normal operation resumed on day
        # 128. A cycle starting exactly on day 128 is after the reported period.
        if c.lab == "LBE" and start < 128 and end >= 106:
            rules.append("R8_unspecified_subset_event_overlap")
            classes.append("ambiguous")
            evidence.append(
                f"Cycle spans days {start:g}-{end:g}; Events!5 reduced mixing for "
                "unnamed LBE bottles on days 106-128."
            )

        if c.lab == "LBE" and c.batch_id >= 11 and not label_inoc.endswith("+"):
            rules.append("R9_trace_element_regime_change")
            classes.append("resolvable_from_source")
            evidence.append(
                "Events!4 and Inoculation TE 2 volumes: this bottle switches to Celtics "
                "trace elements from batch 11, unlike the '+' conditions."
            )

        order = ["excluded", "conflicting", "ambiguous", "resolvable_from_source"]
        final = next((k for k in order if k in classes), "source_consistent")
        bb = bottle_batches[
            (bottle_batches["lab"] == c.lab)
            & (bottle_batches["batch_id"] == c.batch_id)
            & (bottle_batches["bottle_id"] == c.bottle_id)
        ]
        rows.append(
            {
                "lab": c.lab,
                "batch_id": int(c.batch_id),
                "bottle_id": c.bottle_id,
                "replicate": int(c.replicate),
                "source_condition_ampts": c.source_condition_ampts,
                "source_condition_inoculation": c.source_condition_inoculation,
                "biochar_label_ampts": int(c.biochar_label_ampts),
                "inoculation_biochar_g": c.inoculation_biochar_g,
                "inoculation_ammonium_bicarbonate_g": ab,
                "te_supplementation_ampts": c.te_supplementation_ampts,
                "te_solution_ampts": c.te_solution_ampts,
                "inoculation_te1_ml": c.inoculation_te1_ml,
                "inoculation_te2_ml": c.inoculation_te2_ml,
                "batch_start_days_lab": start,
                "batch_last_observed_days_lab": end,
                "methane_rows": int(counts[(c.lab, c.batch_id, c.bottle_id)]),
                "chemistry_rows": int(bb["chemistry_rows"].iloc[0]) if len(bb) else 0,
                "source_inoculation_row": c.source_inoculation_row,
                "adjudication_class": final,
                "rules": ";".join(rules),
                "evidence": " | ".join(evidence),
            }
        )
    return pd.DataFrame(rows)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    buffer = io.StringIO()
    frame.to_csv(buffer, index=False, lineterminator="\n")
    path.write_text(buffer.getvalue(), encoding="utf-8")


def build(output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    data = load_sources()
    qc: dict[str, object] = {
        "status": "SEMANTICS_AUDIT_NO_OUTCOME_CONTRASTS",
        "input_sha256": {
            path.relative_to(ROOT).as_posix(): sha256(path) for path in SOURCES.values()
        },
        "chemistry": chemistry_checks(data["chemistry"]),
        "dose": dose_checks(data["chemistry"], data["methane"]),
        "methane": methane_checks(data["methane"]),
    }
    dictionary = variable_dictionary(data["chemistry"], data["methane"], qc)
    events = event_scope(data["events"])
    adjudication = adjudicate(data["methane"], data["bottle_batches"])
    qc["adjudication_class_counts"] = {
        k: int(v) for k, v in adjudication["adjudication_class"].value_counts().sort_index().items()
    }
    qc["rule_counts"] = {
        rule: int(adjudication["rules"].str.contains(rule, regex=False).sum())
        for rule in sorted({r for rs in adjudication["rules"] for r in rs.split(";") if r})
    }
    qc["unit_status_counts"] = {
        k: int(v) for k, v in dictionary["unit_status"].value_counts().sort_index().items()
    }
    _write_csv(dictionary, output / "sanglier_2022_variable_dictionary.csv")
    _write_csv(events, output / "sanglier_2022_event_scope.csv")
    _write_csv(adjudication, output / "sanglier_2022_treatment_adjudication.csv")
    (output / "sanglier_2022_semantics_qc.json").write_text(
        json.dumps(qc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return qc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    qc = build(args.output_dir)
    print(json.dumps(qc["adjudication_class_counts"], indent=2))


if __name__ == "__main__":
    main()
