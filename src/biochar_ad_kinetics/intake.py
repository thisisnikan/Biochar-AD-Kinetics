"""Validation for reactor-level data contributions.

The intake contract deliberately separates data quality from model fitting.  A
dataset can therefore be rejected (or accepted with warnings) before any model
has a chance to hide missing controls, collapsed replicates or weak provenance.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np
import pandas as pd

IssueSeverity = Literal["error", "warning"]

REQUIRED_OBSERVATION_COLUMNS = (
    "study_id",
    "experiment_id",
    "reactor_id",
    "treatment_id",
    "replicate_id",
    "time_days",
    "temperature_c",
    "is_control",
    "is_inoculum_blank",
    "substrate_id",
    "inoculum_id",
    "material_id",
    "dose_value",
    "dose_unit",
    "raw_cumulative_methane_ml",
    "blank_corrected_methane_ml_g_vs",
    "qc_include",
    "qc_flags",
    "data_origin",
    "source_record_id",
)

IDENTIFIER_COLUMNS = (
    "study_id",
    "experiment_id",
    "reactor_id",
    "treatment_id",
    "replicate_id",
    "substrate_id",
    "inoculum_id",
    "material_id",
    "data_origin",
    "source_record_id",
)

NUMERIC_COLUMNS = (
    "time_days",
    "temperature_c",
    "dose_value",
    "raw_cumulative_methane_ml",
    "blank_corrected_methane_ml_g_vs",
)

BOOLEAN_COLUMNS = ("is_control", "is_inoculum_blank", "qc_include")

STATIC_REACTOR_COLUMNS = (
    "study_id",
    "experiment_id",
    "treatment_id",
    "replicate_id",
    "temperature_c",
    "is_control",
    "is_inoculum_blank",
    "substrate_id",
    "inoculum_id",
    "material_id",
    "dose_value",
    "dose_unit",
)

ALLOWED_DOSE_UNITS = {"g_l", "g_g_vs", "pct_ts", "mg_reactor", "none"}


@dataclass(frozen=True)
class IntakeIssue:
    """One machine-readable intake finding."""

    severity: IssueSeverity
    code: str
    message: str


@dataclass(frozen=True)
class IntakeReport:
    """Validation result suitable for CLI output and CI checks."""

    row_count: int
    reactor_count: int
    experiment_count: int
    issues: tuple[IntakeIssue, ...]

    @property
    def valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def to_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "row_count": self.row_count,
            "reactor_count": self.reactor_count,
            "experiment_count": self.experiment_count,
            "errors": sum(issue.severity == "error" for issue in self.issues),
            "warnings": sum(issue.severity == "warning" for issue in self.issues),
            "issues": [asdict(issue) for issue in self.issues],
        }


@dataclass(frozen=True)
class StageASeriesAssessment:
    """Machine-checkable readiness of one material/dose series for Stage A.

    ``ready_for_manual_review`` deliberately does not mean that the source is
    accepted as complete. Software can verify design structure, but only a
    source-level audit can establish that a trajectory is the full record and
    that no reactors or time points were omitted.
    """

    study_id: str
    experiment_id: str
    material_id: str
    dose_unit: str
    temperature_c: float
    substrate_id: str
    inoculum_id: str
    amended_doses: tuple[float, ...]
    has_matched_zero_dose_control: bool
    minimum_reactors_per_required_arm: int
    all_required_arms_replicated: bool
    all_reactors_have_three_time_points: bool
    all_reactors_start_at_day_zero: bool
    all_required_rows_have_processed_methane: bool
    blank_evidence: str
    traceable_provenance: bool

    @property
    def ready_for_manual_review(self) -> bool:
        return (
            len(self.amended_doses) >= 3
            and self.has_matched_zero_dose_control
            and self.all_required_arms_replicated
            and self.all_reactors_have_three_time_points
            and self.all_reactors_start_at_day_zero
            and self.all_required_rows_have_processed_methane
            and self.blank_evidence
            in {"inoculum_blank_trajectory", "documented_blank_correction"}
            and self.traceable_provenance
        )

    def to_dict(self) -> dict[str, object]:
        return {
            **asdict(self),
            "amended_doses": list(self.amended_doses),
            "ready_for_manual_review": self.ready_for_manual_review,
            "manual_review_required": (
                "Confirm against the original source that trajectories are complete, "
                "all experimental reactors are represented, exclusions are justified, "
                "and blank correction is scientifically valid."
            ),
        }


def _issue(severity: IssueSeverity, code: str, message: str) -> IntakeIssue:
    return IntakeIssue(severity=severity, code=code, message=message)


def _coerce_boolean(series: pd.Series) -> pd.Series:
    mapping = {
        True: True,
        False: False,
        "true": True,
        "false": False,
        "1": True,
        "0": False,
        "yes": True,
        "no": False,
    }
    return series.map(
        lambda value: mapping.get(value.strip().lower(), pd.NA)
        if isinstance(value, str)
        else mapping.get(value, pd.NA)
    )


def assess_stage_a_readiness(frame: pd.DataFrame) -> tuple[StageASeriesAssessment, ...]:
    """Assess candidate series against the machine-checkable Stage A gate.

    A series holds study, experiment, material, dose unit, temperature,
    substrate and inoculum constant. This prevents incomparable doses from
    being counted as one dose-response design. The optional
    ``blank_correction_reference`` column identifies an auditable correction
    method when raw inoculum-blank trajectories cannot be shared.
    """

    if set(REQUIRED_OBSERVATION_COLUMNS).difference(frame.columns):
        return ()

    data = frame.copy()
    for column in NUMERIC_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    for column in BOOLEAN_COLUMNS:
        data[column] = _coerce_boolean(data[column])

    included = data.loc[data["qc_include"].fillna(False).astype(bool)].copy()
    if included.empty:
        return ()

    nonblank = included.loc[~included["is_inoculum_blank"].fillna(False).astype(bool)]
    amended = nonblank.loc[
        nonblank["dose_value"].gt(0)
        & ~nonblank["is_control"].fillna(False).astype(bool)
        & nonblank["material_id"].notna()
        & nonblank["material_id"].astype(str).str.strip().ne("")
        & nonblank["material_id"].astype(str).str.lower().ne("none")
    ]
    series_columns = [
        "study_id",
        "experiment_id",
        "material_id",
        "dose_unit",
        "temperature_c",
        "substrate_id",
        "inoculum_id",
    ]
    assessments: list[StageASeriesAssessment] = []

    for key, series in amended.groupby(series_columns, dropna=False, sort=True):
        (
            study_id,
            experiment_id,
            material_id,
            dose_unit,
            temperature_c,
            substrate_id,
            inoculum_id,
        ) = key
        experiment = included.loc[
            included["study_id"].eq(study_id)
            & included["experiment_id"].eq(experiment_id)
        ]
        matched_control = experiment.loc[
            ~experiment["is_inoculum_blank"].fillna(False).astype(bool)
            & experiment["is_control"].fillna(False).astype(bool)
            & experiment["dose_value"].eq(0)
            & experiment["temperature_c"].eq(temperature_c)
            & experiment["substrate_id"].eq(substrate_id)
            & experiment["inoculum_id"].eq(inoculum_id)
        ]

        required = pd.concat([series, matched_control], ignore_index=True)
        reactor_key = ["study_id", "experiment_id", "reactor_id"]
        reactor_rows = required.drop_duplicates(reactor_key)
        arm_counts = reactor_rows.groupby(
            ["is_control", "dose_value"], dropna=False
        )["reactor_id"].nunique()
        minimum_reactors = int(arm_counts.min()) if len(arm_counts) else 0
        reactor_time = required.groupby(reactor_key)["time_days"]
        time_counts = reactor_time.nunique()
        starts = reactor_time.min()

        blanks = experiment.loc[
            experiment["is_inoculum_blank"].fillna(False).astype(bool)
        ]
        correction_reference = experiment.get("blank_correction_reference")
        has_correction_reference = bool(
            correction_reference is not None
            and correction_reference.notna().all()
            and correction_reference.astype(str).str.strip().ne("").all()
        )
        if not blanks.empty:
            blank_evidence = "inoculum_blank_trajectory"
        elif has_correction_reference:
            blank_evidence = "documented_blank_correction"
        elif nonblank["blank_corrected_methane_ml_g_vs"].notna().all():
            blank_evidence = "corrected_values_without_method"
        else:
            blank_evidence = "none"

        provenance = required[["data_origin", "source_record_id"]]
        traceable_provenance = bool(
            provenance.notna().all().all()
            and provenance.astype(str).apply(lambda values: values.str.strip().ne("").all()).all()
        )
        assessments.append(
            StageASeriesAssessment(
                study_id=str(study_id),
                experiment_id=str(experiment_id),
                material_id=str(material_id),
                dose_unit=str(dose_unit),
                temperature_c=float(temperature_c),
                substrate_id=str(substrate_id),
                inoculum_id=str(inoculum_id),
                amended_doses=tuple(
                    float(value) for value in sorted(series["dose_value"].dropna().unique())
                ),
                has_matched_zero_dose_control=not matched_control.empty,
                minimum_reactors_per_required_arm=minimum_reactors,
                all_required_arms_replicated=minimum_reactors >= 2,
                all_reactors_have_three_time_points=bool(
                    len(time_counts) and time_counts.ge(3).all()
                ),
                all_reactors_start_at_day_zero=bool(len(starts) and starts.eq(0).all()),
                all_required_rows_have_processed_methane=bool(
                    required["blank_corrected_methane_ml_g_vs"].notna().all()
                ),
                blank_evidence=blank_evidence,
                traceable_provenance=traceable_provenance,
            )
        )

    return tuple(assessments)


def validate_reactor_observations(frame: pd.DataFrame) -> IntakeReport:
    """Validate one-row-per-reactor-time-point BMP observations.

    Errors identify violations that make the dataset unsafe to ingest. Warnings
    preserve useful but scientifically limited datasets without overstating what
    they can validate.
    """

    issues: list[IntakeIssue] = []
    missing = sorted(set(REQUIRED_OBSERVATION_COLUMNS).difference(frame.columns))
    if missing:
        issues.append(
            _issue("error", "missing_columns", f"Missing required columns: {', '.join(missing)}")
        )
        return IntakeReport(len(frame), 0, 0, tuple(issues))

    data = frame.loc[:, REQUIRED_OBSERVATION_COLUMNS].copy()
    if data.empty:
        issues.append(_issue("error", "empty_dataset", "At least one observation is required"))
        return IntakeReport(0, 0, 0, tuple(issues))

    for column in IDENTIFIER_COLUMNS:
        empty = data[column].isna() | data[column].astype(str).str.strip().eq("")
        if empty.any():
            issues.append(
                _issue(
                    "error",
                    "missing_identifier",
                    f"{column} is empty in {int(empty.sum())} row(s)",
                )
            )

    numeric: dict[str, pd.Series] = {}
    for column in NUMERIC_COLUMNS:
        numeric[column] = pd.to_numeric(data[column], errors="coerce")
        invalid = data[column].notna() & (
            numeric[column].isna() | ~np.isfinite(numeric[column])
        )
        if invalid.any():
            issues.append(
                _issue(
                    "error",
                    "invalid_numeric",
                    f"{column} contains {int(invalid.sum())} non-numeric or non-finite value(s)",
                )
            )

    boolean: dict[str, pd.Series] = {}
    for column in BOOLEAN_COLUMNS:
        boolean[column] = _coerce_boolean(data[column])
        invalid = boolean[column].isna()
        if invalid.any():
            issues.append(
                _issue(
                    "error",
                    "invalid_boolean",
                    f"{column} contains {int(invalid.sum())} value(s) outside true/false",
                )
            )

    if numeric["time_days"].isna().any() or (numeric["time_days"] < 0).any():
        issues.append(_issue("error", "invalid_time", "time_days must be present and non-negative"))
    if numeric["temperature_c"].isna().any():
        issues.append(
            _issue("error", "missing_temperature", "temperature_c is required for every row")
        )
    if numeric["dose_value"].isna().any() or (numeric["dose_value"] < 0).any():
        issues.append(
            _issue("error", "invalid_dose", "dose_value must be present and non-negative")
        )

    invalid_units = ~data["dose_unit"].isin(ALLOWED_DOSE_UNITS)
    if invalid_units.any():
        issues.append(
            _issue(
                "error",
                "invalid_dose_unit",
                f"{int(invalid_units.sum())} row(s) have missing or unsupported dose_unit",
            )
        )

    unspecified_positive_dose = data["dose_unit"].eq("none") & numeric["dose_value"].gt(0)
    if unspecified_positive_dose.any():
        issues.append(
            _issue("error", "missing_dose_basis", "Positive doses require a physical dose unit")
        )

    # Compare typed values, so e.g. time 1 and "1.0" identify the same observation.
    # Work on the copy only; original source values remain untouched.
    for column, values in numeric.items():
        data[column] = values
    for column, values in boolean.items():
        data[column] = values

    key = ["study_id", "experiment_id", "reactor_id", "time_days"]
    duplicate = data.duplicated(key, keep=False)
    if duplicate.any():
        issues.append(
            _issue(
                "error",
                "duplicate_observation_key",
                f"{int(duplicate.sum())} row(s) duplicate study/experiment/reactor/time keys",
            )
        )

    reactor_key = ["study_id", "experiment_id", "reactor_id"]
    for column in STATIC_REACTOR_COLUMNS:
        inconsistent = data.groupby(reactor_key, dropna=False)[column].nunique(dropna=False) > 1
        if inconsistent.any():
            reactors = ", ".join(
                "/".join(map(str, item)) for item in inconsistent[inconsistent].index[:5]
            )
            issues.append(
                _issue(
                    "error",
                    "inconsistent_reactor_metadata",
                    f"{column} changes within reactor(s): {reactors}",
                )
            )

    include = boolean["qc_include"].fillna(False).astype(bool)
    blank = boolean["is_inoculum_blank"].fillna(False).astype(bool)
    missing_raw = include & numeric["raw_cumulative_methane_ml"].isna()
    if missing_raw.any():
        issues.append(
            _issue(
                "error",
                "missing_raw_measurement",
                f"{int(missing_raw.sum())} included row(s) have no raw cumulative methane",
            )
        )
    missing_processed = include & ~blank & numeric["blank_corrected_methane_ml_g_vs"].isna()
    if missing_processed.any():
        issues.append(
            _issue(
                "warning",
                "missing_processed_measurement",
                f"{int(missing_processed.sum())} included non-blank row(s) have no blank-corrected yield",
            )
        )

    experiment_keys = ["study_id", "experiment_id"]
    for experiment, group in data.groupby(experiment_keys, dropna=False):
        experiment_name = "/".join(map(str, experiment))
        eligible = group.loc[group["qc_include"].fillna(False).astype(bool)]
        group_control = eligible["is_control"].fillna(False).astype(bool)
        group_blank = eligible["is_inoculum_blank"].fillna(False).astype(bool)
        if eligible.empty:
            issues.append(
                _issue(
                    "warning",
                    "no_included_observations",
                    f"Experiment {experiment_name} has no QC-included observations",
                )
            )
        if not (group_control & ~group_blank).any():
            issues.append(
                _issue(
                    "warning",
                    "missing_control",
                    f"Experiment {experiment_name} has no QC-included non-blank control",
                )
            )
        if not group_blank.any():
            issues.append(
                _issue(
                    "warning",
                    "missing_inoculum_blank",
                    f"Experiment {experiment_name} has no QC-included inoculum-only blank",
                )
            )

    treatment_key = ["study_id", "experiment_id", "treatment_id"]
    all_treatments = data.groupby(treatment_key, dropna=False).size().index
    reactor_metadata = data.loc[include].drop_duplicates(reactor_key)
    treatment_counts = (
        reactor_metadata.groupby(treatment_key, dropna=False)["reactor_id"]
        .nunique()
        .reindex(all_treatments, fill_value=0)
    )
    unreplicated = treatment_counts[treatment_counts < 2]
    if len(unreplicated):
        issues.append(
            _issue(
                "warning",
                "unreplicated_treatment",
                f"{len(unreplicated)} treatment(s) contain fewer than two QC-included reactors",
            )
        )

    ordered = data.assign(_raw=numeric["raw_cumulative_methane_ml"]).sort_values(
        ["study_id", "experiment_id", "reactor_id", "time_days"]
    )
    decreases = ordered.groupby(["study_id", "experiment_id", "reactor_id"])["_raw"].diff() < 0
    if decreases.any():
        issues.append(
            _issue(
                "warning",
                "decreasing_cumulative_raw",
                f"Raw cumulative methane decreases at {int(decreases.sum())} time point(s)",
            )
        )

    reactor_count = data[["study_id", "experiment_id", "reactor_id"]].drop_duplicates().shape[0]
    experiment_count = data[["study_id", "experiment_id"]].drop_duplicates().shape[0]
    return IntakeReport(len(data), reactor_count, experiment_count, tuple(issues))
