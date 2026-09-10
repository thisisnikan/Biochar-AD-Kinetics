"""Build a tidy experimental BMP dataset from Kozłowski et al. (2025).

The source workbook is an openly licensed supplement to:
https://doi.org/10.1038/s41598-025-02564-0

The legacy transformation uses only the standard library. The optional intake
export uses the installed package validator; no Excel engine is required.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from biochar_ad_kinetics.xlsx_reader import column_number, read_shared_strings, read_sheet_paths

SOURCE_URL = (
    "https://media.springernature.com/original/springer-static/esm/"
    "art%3A10.1038%2Fs41598-025-02564-0/MediaObjects/"
    "41598_2025_2564_MOESM1_ESM.xlsx"
)
SOURCE_SHA256 = "a5be0c25990acbdd0a6ac14dfa202398e61713fea8496884018e97f1cf87b983"
SOURCE_DOI = "10.1038/s41598-025-02564-0"
SHEET_NAME = "Godzinowe"
XML_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

SUBSTRATE_VS_G = 4.425592386264921


BLANK_COLUMNS = (5, 6, 7)
TREATMENTS = (
    ("food_waste", "none", None, 0.0, ((8, 1, True), (9, 2, True), (10, 3, True))),
    (
        "food_waste_torrefaction_240c",
        "torrefaction_product",
        240.0,
        5.0,
        ((11, 1, True), (12, 2, False), (13, 3, True)),
    ),
    (
        "food_waste_pyrolysis_600c",
        "biochar",
        600.0,
        5.0,
        ((14, 1, True), (15, 2, True), (16, 3, False)),
    ),
    (
        "food_waste_hydrochar_240c",
        "hydrochar",
        240.0,
        5.0,
        ((17, 1, True), (18, 2, True), (19, 3, True)),
    ),
)

def _read_cells(path: Path) -> dict[tuple[int, int], float | str]:
    with zipfile.ZipFile(path) as archive:
        strings = read_shared_strings(archive)
        paths = read_sheet_paths(archive)
        if SHEET_NAME not in paths:
            raise ValueError(f"Worksheet not found: {SHEET_NAME}")
        root = ET.fromstring(archive.read(paths[SHEET_NAME]))

    cells: dict[tuple[int, int], float | str] = {}
    for cell in root.iter(f"{{{XML_NS}}}c"):
        reference = cell.attrib["r"]
        row = int("".join(character for character in reference if character.isdigit()))
        column = column_number(reference)
        value_node = cell.find(f"{{{XML_NS}}}v")
        if value_node is None or value_node.text is None:
            continue
        raw = value_node.text
        if cell.attrib.get("t") == "s":
            value: float | str = strings[int(raw)]
        else:
            try:
                value = float(raw)
            except ValueError:
                value = raw
        cells[(row, column)] = value
    return cells


def _obtain_source(source: Path | None) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    temporary = None
    if source is None:
        temporary = tempfile.TemporaryDirectory(prefix="biochar_ad_source_")
        source = Path(temporary.name) / "supplement.xlsx"
        urllib.request.urlretrieve(SOURCE_URL, source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError(f"Source SHA-256 mismatch: expected {SOURCE_SHA256}, received {digest}")
    return source, temporary


def build_dataset(source: Path, destination: Path) -> int:
    """Transform the publisher workbook into a long, traceable CSV."""

    cells = _read_cells(source)
    blank_columns = BLANK_COLUMNS  # E:G, inoculum-only controls
    fieldnames = (
        "study_id",
        "treatment",
        "replicate",
        "time_hours",
        "time_days",
        "source_day_label",
        "source_reported_time_days",
        "temperature_c",
        "carbon_material",
        "process_temperature_c",
        "dose_g_l",
        "raw_cumulative_methane_ml",
        "blank_mean_cumulative_methane_ml",
        "methane_ml_g_vs",
        "included_in_benchmark",
        "exclusion_reason",
        "data_origin",
        "source_doi",
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in range(18, 523):
            hour = float(cells[(row, 3)])
            blank_mean = sum(float(cells[(row, col)]) for col in blank_columns) / 3
            for treatment, material, process_temperature, dose, reactors in TREATMENTS:
                for column, replicate, included in reactors:
                    raw_methane = float(cells[(row, column)])
                    corrected = (raw_methane - blank_mean) / SUBSTRATE_VS_G
                    writer.writerow(
                        {
                            "study_id": "kozlowski_2025_scientific_reports",
                            "treatment": treatment,
                            "replicate": replicate,
                            "time_hours": f"{hour:.0f}",
                            # The workbook's derived time column divides by 96. The article,
                            # raw hourly index, and day label all support division by 24.
                            "time_days": f"{hour / 24:.8f}",
                            "source_day_label": f"{float(cells[(row, 4)]):.0f}",
                            "source_reported_time_days": f"{float(cells[(row, 21)]):.8f}",
                            "temperature_c": "37",
                            "carbon_material": material,
                            "process_temperature_c": (
                                "" if process_temperature is None else f"{process_temperature:.0f}"
                            ),
                            "dose_g_l": f"{dose:.1f}",
                            "raw_cumulative_methane_ml": f"{raw_methane:.8f}",
                            "blank_mean_cumulative_methane_ml": f"{blank_mean:.8f}",
                            "methane_ml_g_vs": f"{corrected:.8f}",
                            "included_in_benchmark": str(included).lower(),
                            "exclusion_reason": (
                                ""
                                if included
                                else "excluded_from_publisher_mean; inconsistent_raw_signal"
                            ),
                            "data_origin": "experimental_publisher_supplement",
                            "source_doi": SOURCE_DOI,
                        }
                    )
                    rows_written += 1
    return rows_written


def build_intake_dataset(source: Path, destination: Path, report_path: Path) -> dict:
    """Export all physical reactors, including blanks, from a verified workbook.

    IDs identify columns in this study, not independent material/inoculum batches.
    Keep conflicting source metadata alongside the documented analysis mapping.
    """
    import pandas as pd

    from biochar_ad_kinetics.intake import (
        REQUIRED_OBSERVATION_COLUMNS,
        validate_reactor_observations,
    )

    _obtain_source(source)
    cells = _read_cells(source)
    records = []
    treatments = (
        ("inoculum_blank", "none", None, 0.0, tuple((c, c - 4, True) for c in BLANK_COLUMNS)),
        *TREATMENTS,
    )
    for row in range(18, 523):
        hour = float(cells[(row, 3)])
        blank_mean = sum(float(cells[(row, c)]) for c in BLANK_COLUMNS) / 3
        for treatment, material, process_temperature, dose, reactors in treatments:
            is_blank = treatment == "inoculum_blank"
            for column, replicate, included in reactors:
                letter = chr(ord("A") + column - 1)  # Source columns E:S only.
                raw = float(cells[(row, column)])
                substrate_vs = float(cells[(9, column)])
                inoculum_vs = float(cells[(6, column)])
                source_dose = cells.get((12, column))
                flags = []
                if float(cells[(row, 21)]) != hour / 24:
                    flags.append("source_time_divisor_conflict")
                if source_dose is not None and float(source_dose) != dose:
                    flags.append("source_control_dose_conflict")
                if not included:
                    flags.extend(["excluded_from_publisher_mean", "inconsistent_raw_signal"])
                records.append(
                    {
                        "study_id": "kozlowski_2025_scientific_reports",
                        "experiment_id": "publisher_godzinowe",
                        "reactor_id": str(cells[(17, column)]),
                        "treatment_id": treatment,
                        "replicate_id": replicate,
                        "time_days": round(hour / 24, 8),
                        "temperature_c": 37,
                        "is_control": material == "none",
                        "is_inoculum_blank": is_blank,
                        "substrate_id": "none" if is_blank else "kozlowski_2025_food_waste",
                        "inoculum_id": "kozlowski_2025_digestate",
                        "material_id": "none" if material == "none" else treatment,
                        "dose_value": dose,
                        "dose_unit": "none" if is_blank else "g_l",
                        "raw_cumulative_methane_ml": round(raw, 8),
                        "blank_corrected_methane_ml_g_vs": (
                            None if is_blank else round((raw - blank_mean) / substrate_vs, 8)
                        ),
                        "qc_include": included,
                        "qc_flags": ";".join(flags),
                        "data_origin": "experimental_publisher_supplement",
                        "source_record_id": f"{SHEET_NAME}!{letter}{row}",
                        "source_doi": SOURCE_DOI,
                        "source_sha256": SOURCE_SHA256,
                        "source_reactor_number": cells[(3, column)],
                        "time_hours": hour,
                        "source_reported_time_days": cells[(row, 21)],
                        "source_day_label": cells[(row, 4)],
                        "blank_mean_cumulative_methane_ml": round(blank_mean, 8),
                        "blank_source_records": ";".join(
                            f"{SHEET_NAME}!{chr(ord('A') + c - 1)}{row}" for c in BLANK_COLUMNS
                        ),
                        "substrate_vs_g": substrate_vs,
                        "substrate_vs_source_record": f"{SHEET_NAME}!{letter}9",
                        "inoculum_vs_g": inoculum_vs,
                        "inoculum_vs_source_record": f"{SHEET_NAME}!{letter}6",
                        "inoculum_to_substrate_vs_ratio": (
                            None if is_blank else inoculum_vs / substrate_vs
                        ),
                        "source_carbon_mass_g": cells.get((10, column)),
                        "source_carbon_mass_record": f"{SHEET_NAME}!{letter}10",
                        "source_dose_g_l": source_dose,
                        "source_dose_record": f"{SHEET_NAME}!{letter}12",
                        "carbon_material": material,
                        "process_temperature_c": process_temperature,
                    }
                )
    frame = pd.DataFrame.from_records(records)
    # Contract first, followed by explicit source and calculation context.
    extra = [c for c in frame.columns if c not in REQUIRED_OBSERVATION_COLUMNS]
    frame = frame.loc[:, [*REQUIRED_OBSERVATION_COLUMNS, *extra]]
    report = validate_reactor_observations(frame).to_dict()
    if not report["valid"]:
        raise ValueError(f"Source-derived intake failed validation: {report}")
    report["source"] = {"doi": SOURCE_DOI, "sha256": SOURCE_SHA256, "sheet": SHEET_NAME}
    ordered = frame.sort_values(["reactor_id", "time_hours"])
    ordered = ordered.assign(
        change_ml=ordered.groupby("reactor_id").raw_cumulative_methane_ml.diff().round(8)
    )
    decreases = ordered.change_ml.lt(0)
    report["decreasing_raw_records"] = ordered.loc[
        decreases, ["reactor_id", "time_hours", "change_ml", "source_record_id", "qc_include"]
    ].to_dict(orient="records")
    report["design"] = {
        "blank_reactors": int(frame.loc[frame.is_inoculum_blank, "reactor_id"].nunique()),
        "substrate_reactors": int(frame.loc[~frame.is_inoculum_blank, "reactor_id"].nunique()),
        "included_substrate_reactors": int(
            frame.loc[~frame.is_inoculum_blank & frame.qc_include, "reactor_id"].nunique()
        ),
        "temperatures_c": sorted(frame.temperature_c.unique().tolist()),
        "amended_doses_g_l": sorted(frame.loc[frame.dose_value > 0, "dose_value"].unique().tolist()),
        "independent_studies": 1,
    }
    report["source_conflicts"] = [
        {
            "code": flag,
            "rows": int(frame.qc_flags.str.contains(flag, regex=False).sum()),
            "reactors": sorted(
                frame.loc[frame.qc_flags.str.contains(flag, regex=False), "reactor_id"].unique()
            ),
        }
        for flag in ("source_time_divisor_conflict", "source_control_dose_conflict")
    ]
    report["evidence_gaps"] = [
        {
            "code": "nonmonotonic_blank",
            "status": "unresolved_source_qc",
            "needed": (
                "Check K1 at 469 and 484 hours (E487 and E502). The blank remains included "
                "to preserve the historical correction; no clipping or repair is applied."
            ),
        },
        {
            "code": "single_temperature",
            "status": "absent_from_design",
            "needed": "Reactor trajectories at additional digestion temperatures.",
        },
        {
            "code": "single_amended_dose_per_material",
            "status": "absent_from_design",
            "needed": "Several doses of the same material with matched controls and replicates.",
        },
        {
            "code": "no_independent_study_holdout",
            "status": "absent_from_this_import",
            "needed": "An independent reactor-level study for preregistered external validation.",
        },
        {
            "code": "control_dose_conflict",
            "status": "unresolved_source_conflict",
            "needed": (
                "Confirm H:J rows 10 and 12 with authors. Canonical control dose remains zero "
                "following article design, worksheet labels and legacy mapping; source values retained."
            ),
        },
        {
            "code": "batch_identity",
            "status": "not_established_by_import",
            "needed": (
                "Verify inoculum collection and material production batch identifiers. "
                "Study-scoped IDs do not establish independent batches."
            ),
        },
        {
            "code": "additional_process_and_material_context",
            "status": "not_harmonized_in_this_import",
            "needed": (
                "Harmonize working volume and gas reference conditions, material descriptors "
                "and process chemistry from their sources. Not imported does not mean unreported."
            ),
        },
    ]
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.suffix == ".gz":
        # Stable gzip bytes: no wall-clock timestamp or output filename in the header.
        with (
            destination.open("wb") as raw_handle,
            gzip.GzipFile(filename="", mode="wb", fileobj=raw_handle, mtime=0) as compressed,
            io.TextIOWrapper(compressed, encoding="utf-8", newline="") as handle,
        ):
            frame.to_csv(handle, index=False, lineterminator="\n")
    else:
        frame.to_csv(destination, index=False, lineterminator="\n")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Optional local copy of the verified XLSX")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/experimental/kozlowski_2025_bmp.csv"),
    )
    parser.add_argument("--intake-output", type=Path, help="Also export all 15 source reactors")
    parser.add_argument("--intake-report", type=Path, help="JSON validation and evidence-gap report")
    args = parser.parse_args()
    if bool(args.intake_output) != bool(args.intake_report):
        parser.error("--intake-output and --intake-report must be supplied together")
    source, temporary = _obtain_source(args.source)
    try:
        rows = build_dataset(source, args.output)
        if args.intake_output:
            report = build_intake_dataset(source, args.intake_output, args.intake_report)
            print(
                f"Intake: {report['row_count']} observations, {report['reactor_count']} reactors, "
                f"{report['errors']} errors, {report['warnings']} warnings"
            )
    finally:
        if temporary is not None:
            temporary.cleanup()
    print(f"Wrote {rows} experimental observations to {args.output}")


if __name__ == "__main__":
    main()
