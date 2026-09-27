"""Pre-registered admission gates for candidate validation datasets.

This module is study-agnostic. A frozen JSON specification decides, before any
outcome contrast is computed, which experimental units may enter an analysis,
which analysis category the result belongs to, and whether any development
artifact already contains the candidate study (leakage). Every check fails
closed: a missing field, an unexpected window, a drifted hash, an outcome column
passed to the admission step or a leaked identifier raises instead of warning.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

REQUIRED_SPEC_FIELDS = (
    "spec_id",
    "status",
    "study_id",
    "scientific_question",
    "prediction_target",
    "dataset_roles",
    "unit_of_analysis",
    "independence_rule",
    "inclusion_criteria",
    "exclusion_criteria",
    "allowable_treatments",
    "treatment_reconstruction_rules",
    "temporal_definition",
    "repeated_batch_handling",
    "carryover_handling",
    "co_intervention_handling",
    "normalization",
    "required_metadata",
    "leakage_prevention",
    "transfer_rules",
    "metrics",
    "uncertainty_reporting",
    "decision_rule",
    "failure_criteria",
    "outcome_exposure_disclosure",
)

VALIDATION_CATEGORIES = (
    "locked_external_validation",
    "calibration_transfer",
    "model_updating",
    "exploratory",
)

ADMISSIBLE_CLASSES = frozenset({"source_consistent", "resolvable_from_source"})

# Rules that describe a co-intervention. A cycle carrying any of them never
# enters a biochar-versus-control contrast, even when its label is resolvable.
CO_INTERVENTION_RULES = frozenset({"R3", "R4", "R5", "R9", "R10"})

# Rules that end a laboratory's clean window when they appear in any cycle.
WINDOW_ENDING_RULES = frozenset({"R8", "R9"})

# Admission must be blind to outcomes: none of these may reach admit_cycles.
OUTCOME_COLUMNS = frozenset(
    {
        "volume_raw_nml",
        "volume_corrected_nml",
        "flow_nml_h",
        "methane_yield_nml_gvs",
    }
)

TEXT_SUFFIXES = {".py", ".csv", ".json", ".md", ".txt", ".gz", ".cff", ".toml", ".yml"}


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_spec(path: str | Path) -> dict:
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_spec(spec)
    return spec


def validate_spec(spec: dict) -> None:
    """Reject an incomplete or unfrozen specification."""

    missing = [field for field in REQUIRED_SPEC_FIELDS if field not in spec]
    if missing:
        raise ValueError(f"Validation spec missing required fields: {', '.join(missing)}")
    if not str(spec["status"]).startswith("FROZEN"):
        raise ValueError("Validation spec must be frozen before admission")
    roles = spec["dataset_roles"]
    unknown = set(roles) - set(VALIDATION_CATEGORIES)
    if unknown or set(VALIDATION_CATEGORIES) - set(roles):
        raise ValueError(
            "dataset_roles must list exactly the four validation categories: "
            + ", ".join(VALIDATION_CATEGORIES)
        )
    temporal = spec["temporal_definition"]
    for key in ("expected_windows", "expected_horizon_days", "time_tolerance_days"):
        if key not in temporal:
            raise ValueError(f"temporal_definition.{key} is required")
    if temporal.get("interpolation") != "prohibited":
        raise ValueError("This gate only supports specs that prohibit interpolation")
    leakage = spec["leakage_prevention"]
    if leakage.get("on_hit") != "fail_closed" or not leakage.get("identifiers"):
        raise ValueError("leakage_prevention must list identifiers and fail closed")


def classify_validation_role(
    refit_parameters: Iterable[str],
    calibration_parameters: Iterable[str],
    hypothesis_chosen_after_viewing_data: bool,
) -> str:
    """Name the analysis category honestly.

    Refitting anything beyond declared calibration parameters on the external
    study makes the result model updating, never external validation.
    """

    if hypothesis_chosen_after_viewing_data:
        return "exploratory"
    refit = set(refit_parameters)
    if not refit:
        return "locked_external_validation"
    if refit <= set(calibration_parameters):
        return "calibration_transfer"
    return "model_updating"


def _rule_codes(rules: object) -> set[str]:
    if not isinstance(rules, str) or not rules:
        return set()
    return {rule.split("_", 1)[0] for rule in rules.split(";") if rule}


def _normalize_label(label: object) -> str:
    return str(label).replace(" ", "")


def clean_windows(adjudication: pd.DataFrame) -> dict[str, tuple[int, int]]:
    """Batch window per laboratory, ending before the first lab-scope confounder.

    A window-ending rule is R8 or R9 anywhere in the lab, or R4 on a cycle whose
    ammonium addition is not attributed to a named condition (class conflicting).
    """

    windows: dict[str, tuple[int, int]] = {}
    for lab, group in adjudication.groupby("lab", sort=True):
        first_batch = int(group["batch_id"].min())
        ending = []
        for row in group.itertuples(index=False):
            codes = _rule_codes(row.rules)
            if codes & WINDOW_ENDING_RULES:
                ending.append(int(row.batch_id))
            if "R4" in codes and row.adjudication_class == "conflicting":
                ending.append(int(row.batch_id))
        last = (min(ending) - 1) if ending else int(group["batch_id"].max())
        if last < first_batch:
            raise ValueError(f"Laboratory {lab} has no clean batch window")
        windows[str(lab)] = (first_batch, last)
    return windows


def admit_cycles(
    adjudication: pd.DataFrame, spec: dict, cycle_durations: pd.DataFrame
) -> tuple[pd.DataFrame, dict]:
    """Apply the frozen admission rules to bottle/batch cycles.

    ``cycle_durations`` carries lab, batch_id, bottle_id and last_within_batch_days
    only. Passing any outcome column raises, so admission cannot depend on yield.
    """

    for frame in (adjudication, cycle_durations):
        leaked = OUTCOME_COLUMNS.intersection(frame.columns)
        if leaked:
            raise ValueError(f"Admission must be outcome-blind; got {sorted(leaked)}")

    temporal = spec["temporal_definition"]
    windows = clean_windows(adjudication)
    expected = {lab: tuple(v) for lab, v in temporal["expected_windows"].items()}
    if windows != expected:
        raise ValueError(f"Clean windows {windows} differ from frozen {expected}")

    treatments = spec["allowable_treatments"]
    frame = adjudication.merge(
        cycle_durations, on=["lab", "batch_id", "bottle_id"], how="left", validate="1:1"
    )
    if frame["last_within_batch_days"].isna().any():
        raise ValueError("Every cycle needs a recorded duration")

    reasons: list[str] = []
    for row in frame.itertuples(index=False):
        lab = str(row.lab)
        start, end = windows[lab]
        arm = _normalize_label(row.source_condition_inoculation)
        allowed = {_normalize_label(a) for a in treatments.get(lab, [])}
        codes = _rule_codes(row.rules)
        if not start <= int(row.batch_id) <= end:
            reasons.append("outside_clean_window")
        elif arm not in allowed:
            reasons.append("arm_not_allowable")
        elif row.adjudication_class not in ADMISSIBLE_CLASSES:
            reasons.append(f"class_{row.adjudication_class}")
        elif codes & CO_INTERVENTION_RULES:
            reasons.append("co_intervention_" + "_".join(sorted(codes & CO_INTERVENTION_RULES)))
        else:
            reasons.append("")
    frame["cycle_reason"] = reasons

    in_window = frame.apply(
        lambda r: windows[str(r.lab)][0] <= int(r.batch_id) <= windows[str(r.lab)][1], axis=1
    )
    frame["in_window"] = in_window
    bottle_failures = (
        frame.loc[in_window & (frame["cycle_reason"] != "")]
        .groupby(["lab", "bottle_id"])["cycle_reason"]
        .agg(lambda s: ";".join(sorted(set(s))))
    )
    window_batches = {lab: set(range(a, b + 1)) for lab, (a, b) in windows.items()}
    present = frame.loc[in_window].groupby(["lab", "bottle_id"])["batch_id"].agg(set)
    bottle_reason = {}
    for (lab, bottle), batches in present.items():
        if (lab, bottle) in bottle_failures.index:
            bottle_reason[(lab, bottle)] = "bottle_" + bottle_failures[(lab, bottle)]
        elif batches != window_batches[lab]:
            bottle_reason[(lab, bottle)] = "bottle_incomplete_window"
        else:
            bottle_reason[(lab, bottle)] = ""
    frame["bottle_reason"] = [
        bottle_reason.get((r.lab, r.bottle_id), "bottle_no_window_cycles")
        for r in frame.itertuples(index=False)
    ]
    frame["admitted_primary"] = (
        frame["in_window"] & (frame["cycle_reason"] == "") & (frame["bottle_reason"] == "")
    )
    frame["exclusion_reason"] = [
        "" if r.admitted_primary else (r.cycle_reason or r.bottle_reason)
        for r in frame.itertuples(index=False)
    ]

    admitted = frame.loc[frame["admitted_primary"]]
    shortest = float(admitted["last_within_batch_days"].min())
    horizon = math.floor(shortest / 0.5 + 1e-9) * 0.5
    if abs(horizon - float(temporal["expected_horizon_days"])) > temporal["time_tolerance_days"]:
        raise ValueError(
            f"Horizon {horizon} differs from frozen {temporal['expected_horizon_days']}"
        )

    arms = (
        admitted.drop_duplicates(["lab", "bottle_id"])
        .assign(arm=lambda d: d["source_condition_inoculation"].map(_normalize_label))
        .groupby(["lab", "arm"])["bottle_id"]
        .agg(lambda s: sorted(s))
    )
    summary = {
        "windows": {lab: list(v) for lab, v in windows.items()},
        "horizon_days": horizon,
        "admitted_cycles": int(frame["admitted_primary"].sum()),
        "total_cycles": len(frame),
        "admitted_bottles_by_arm": {f"{lab} {arm}": b for (lab, arm), b in arms.items()},
        "excluded_bottles": {
            f"{lab} {bottle}": reason
            for (lab, bottle), reason in sorted(bottle_reason.items())
            if reason
        },
    }
    columns = [
        "lab",
        "batch_id",
        "bottle_id",
        "source_condition_inoculation",
        "adjudication_class",
        "rules",
        "last_within_batch_days",
        "in_window",
        "admitted_primary",
        "exclusion_reason",
    ]
    return frame[columns].sort_values(["lab", "bottle_id", "batch_id"]).reset_index(drop=True), (
        summary
    )


def _iter_text_files(root: Path, relative: str) -> Iterable[Path]:
    base = root / relative
    if base.is_file():
        yield base
        return
    if not base.exists():
        return
    for path in sorted(base.rglob("*")):
        if path.is_file() and path.suffix in TEXT_SUFFIXES and "__pycache__" not in path.parts:
            yield path


def _read_text(path: Path) -> str:
    if path.suffix == ".gz":
        import gzip

        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    return path.read_text(encoding="utf-8", errors="replace")


def leakage_audit(root: str | Path, spec: dict) -> dict:
    """Search development artifacts for any identifier of the candidate study.

    Development artifacts are the paths that feed parameter estimation, feature
    engineering, preprocessing, model selection or descriptor construction.
    Any hit sets ``passed`` to False; callers must stop.
    """

    root = Path(root)
    leakage = spec["leakage_prevention"]
    identifiers = [token.lower() for token in leakage["identifiers"]]
    allowed = {Path(p).as_posix() for p in leakage.get("allowed_modules", [])}
    hits = []
    scanned = 0
    for relative in leakage["development_paths"]:
        for path in _iter_text_files(root, relative):
            rel = path.relative_to(root).as_posix()
            if rel in allowed:
                continue
            scanned += 1
            text = _read_text(path).lower()
            for token in identifiers:
                if token in text:
                    hits.append({"path": rel, "identifier": token})
    return {
        "passed": not hits,
        "files_scanned": scanned,
        "development_paths": list(leakage["development_paths"]),
        "hits": hits,
    }
