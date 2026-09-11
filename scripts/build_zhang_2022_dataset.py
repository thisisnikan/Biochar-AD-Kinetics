"""Build private tidy tables from the author-shared Zhang et al. (2022) workbook.

The workbook contains post-processed treatment means and reported standard
deviations, not the lost reactor-level triplicates. The methane values are
already inoculum-blank corrected. This script preserves summary statistics and
never reconstructs pseudo-replicates.

Supply the private workbook explicitly:

    python scripts/build_zhang_2022_dataset.py --source /path/to/Data.xlsx
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

from biochar_ad_kinetics.xlsx_reader import read_workbook as _read_workbook

SOURCE_DOI = "10.1007/s42773-022-00187-6"
SOURCE_SHA256 = "daa8e32b07b3db8051ae718181068053cec37c9d569a9467f014b8bfbf8b8cda"
STUDY_ID = "zhang_2022_biochar"

SHEETS = {
    "Pyrolysis Temp – Methane": ("pyrolysis_temperature", "methane"),
    "Pyrolysis Time – Methane": ("pyrolysis_duration", "methane"),
    "Pyrolysis Temp – pH": ("pyrolysis_temperature", "ph"),
    "Pyrolysis Time – pH": ("pyrolysis_duration", "ph"),
    "Pyrolysis Temp – VFA": ("pyrolysis_temperature", "vfa"),
    "Pyrolysis Time – VFA": ("pyrolysis_duration", "vfa"),
}


def read_workbook(path: Path) -> dict[str, list[list[object]]]:
    """Read the six expected worksheets without an Excel engine dependency."""

    return _read_workbook(path, sheet_names=tuple(SHEETS))


def _condition(label: object) -> tuple[str, int | None, int | None] | None:
    text = str(label or "").strip()
    if text in {"C", "Control"}:
        return "control", None, None
    match = re.fullmatch(r"B-?(\d+)-(\d+)", text)
    if not match:
        return None
    temperature, duration = (int(value) for value in match.groups())
    return f"biochar_{temperature}c_{duration}min", temperature, duration


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _base_row(
    axis: str,
    treatment: str,
    pyrolysis_temperature: int | None,
    pyrolysis_duration: int | None,
    time_days: float,
) -> dict[str, object]:
    return {
        "study_id": STUDY_ID,
        "experiment_axis": axis,
        "treatment": treatment,
        "pyrolysis_temperature_c": pyrolysis_temperature,
        "pyrolysis_duration_min": pyrolysis_duration,
        "time_days": time_days,
        "digestion_temperature_c": 37,
        "biochar_dose_g_l": 0 if treatment == "control" else 10,
        "summary_statistic": "mean_and_reported_standard_deviation",
        "replicate_level_available": False,
        "data_origin": "author_shared_postprocessed_summary",
        "source_doi": SOURCE_DOI,
    }


def transform_methane(sheet: list[list[object]], axis: str) -> list[dict[str, object]]:
    """Convert a wide methane summary sheet to one row per treatment and time."""

    conditions = []
    for value_column in range(1, len(sheet[0]), 2):
        parsed = _condition(sheet[0][value_column])
        if parsed is not None:
            conditions.append((value_column, parsed))
    rows = []
    for source_row in sheet[1:]:
        time_days = _number(source_row[0])
        if time_days is None:
            continue
        for value_column, (treatment, temperature, duration) in conditions:
            mean = _number(source_row[value_column])
            sd = _number(source_row[value_column + 1])
            if mean is None:
                continue
            rows.append(
                {
                    **_base_row(axis, treatment, temperature, duration, time_days),
                    "cumulative_methane_ml": mean,
                    "reported_standard_deviation_ml": sd,
                    "inoculum_blank_corrected": True,
                }
            )
    return rows


def transform_ph(sheet: list[list[object]], axis: str) -> list[dict[str, object]]:
    """Convert a wide pH summary sheet to long process-monitoring rows."""

    conditions = []
    for value_column in range(1, len(sheet[0]), 2):
        parsed = _condition(sheet[0][value_column])
        if parsed is not None:
            conditions.append((value_column, parsed))
    rows = []
    for source_row in sheet[1:]:
        time_days = _number(source_row[0])
        if time_days is None:
            continue
        for value_column, (treatment, temperature, duration) in conditions:
            mean = _number(source_row[value_column])
            sd = _number(source_row[value_column + 1])
            if mean is None:
                continue
            rows.append(
                {
                    **_base_row(axis, treatment, temperature, duration, time_days),
                    "measurement": "ph",
                    "analyte": "",
                    "value": mean,
                    "reported_standard_deviation": sd,
                    "unit": "dimensionless",
                }
            )
    return rows


def transform_vfa(sheet: list[list[object]], axis: str) -> list[dict[str, object]]:
    """Convert paired VFA mean/SD columns to a tidy analyte table."""

    headers = sheet[0]
    analytes = [
        (value_column, str(headers[value_column]).strip().lower().replace("-", "_"))
        for value_column in range(2, len(headers), 2)
        if headers[value_column] not in {None, "--"}
    ]
    rows = []
    current_day: float | None = None
    for source_row in sheet[1:]:
        day_match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*day\s*", str(source_row[0] or ""))
        if day_match:
            current_day = float(day_match.group(1))
        parsed = _condition(source_row[1] if len(source_row) > 1 else None)
        if current_day is None or parsed is None:
            continue
        treatment, temperature, duration = parsed
        for value_column, analyte in analytes:
            mean = _number(source_row[value_column])
            sd = _number(source_row[value_column + 1])
            if mean is None:
                continue
            rows.append(
                {
                    **_base_row(axis, treatment, temperature, duration, current_day),
                    "measurement": "vfa",
                    "analyte": analyte,
                    "value": mean,
                    "reported_standard_deviation": sd,
                    "unit": "mg_l",
                }
            )
    return rows


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_dataset(source: Path, output_directory: Path) -> dict[str, object]:
    """Build private methane and process-monitoring CSVs plus an audit manifest."""

    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError(f"Source SHA-256 mismatch: expected {SOURCE_SHA256}, received {digest}")
    workbook = read_workbook(source)
    methane_rows: list[dict[str, object]] = []
    process_rows: list[dict[str, object]] = []
    for sheet_name, (axis, measurement) in SHEETS.items():
        if measurement == "methane":
            methane_rows.extend(transform_methane(workbook[sheet_name], axis))
        elif measurement == "ph":
            process_rows.extend(transform_ph(workbook[sheet_name], axis))
        else:
            process_rows.extend(transform_vfa(workbook[sheet_name], axis))
    _write_csv(output_directory / "methane_summary.csv", methane_rows)
    _write_csv(output_directory / "process_summary.csv", process_rows)
    manifest = {
        "study_id": STUDY_ID,
        "source_sha256": digest,
        "source_doi": SOURCE_DOI,
        "methane_rows": len(methane_rows),
        "process_rows": len(process_rows),
        "methane_treatments": sorted({row["treatment"] for row in methane_rows}),
        "limitations": [
            "author-shared post-processed treatment means",
            "original triplicate files unavailable",
            "methane already inoculum-blank corrected",
            "replicate-level holdout validation is not possible",
        ],
    }
    (output_directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/private/zhang_2022"))
    args = parser.parse_args()
    print(json.dumps(build_dataset(args.source, args.output), indent=2))


if __name__ == "__main__":
    main()
