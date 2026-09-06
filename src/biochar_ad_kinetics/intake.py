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
