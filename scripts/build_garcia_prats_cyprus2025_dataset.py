"""Build private tidy tables from the author-shared García-Prats CYPRUS2025 abstract.

García-Prats, M., González, D. & Sánchez, A. shared an extended abstract,
"Unveiling the relationships between biochar characteristics and its
beneficial effects in the anaerobic digestion of the organic fraction of
municipal solid waste (OFMSW)", presented at CYPRUS2025, directly with this
project by email on 2 September 2026. The full paper is explicitly stated by
the author to be under revision and not yet public. This script exists so the
abstract's tables can be analysed privately without ever committing the
source file, its full text, its figures, or any of its numeric values to this
public repository — the same restriction this project applies to the Zhang
et al. (2022) private workbook.

This script never hardcodes a single measurement from the abstract. It only
encodes the *schema* the abstract's tables use (biochar identifiers, column
names) and the transformation logic. The abstract itself is not a spreadsheet,
so before running this script a human must transcribe its three tables into a
plain workbook with the sheet names and columns documented below — exactly as
printed, never estimated from a chart. Supply that private workbook
explicitly:

    python scripts/build_garcia_prats_cyprus2025_dataset.py --source /path/to/garcia_prats_cyprus2025.xlsx

Expected worksheets and columns (one header row, one row per record):

- ``characteristics`` (Table 1): ``biochar_id``, ``ph``, ``ec_us_cm``,
  ``carbon_pct``, ``nitrogen_pct``, ``oxygen_pct``, ``hydrogen_pct``,
  ``h_c_ratio``, ``o_c_ratio``. All nine biochars
  (``PP300``/``PP400``/``PP500``/``PH300``/``PH400``/``PH500``/``Q300``/
  ``Q400``/``Q500``) must be present exactly once.
- ``kinetics`` (Table 2): ``biochar_id`` (a biochar id or ``control``),
  ``dose_pct`` (5 or 10), ``lambda_days``, ``r_max_ml_g_vs_d``,
  ``y_max_ml_g_vs``.
- ``correlations`` (Table 3): ``property``, ``outcome``, ``dose_pct``,
  ``pearson_r``, ``p_value``. ``property`` is one of pyrolysis temperature,
  pH, EC, C, N, O, H, O/C or H/C; ``outcome`` is one of CMY, methane content,
  lambda, Rmax or Ymax.
- ``ad_performance``: ``biochar_id`` (a biochar id, ``control`` or
  ``cellulose_control``), ``dose_pct``, ``metric`` (``cmy_ml_g_vs`` or
  ``methane_content_pct``), ``value``, ``reported_standard_deviation``,
  ``percent_change_vs_control``, ``not_machine_extractable`` (``TRUE`` for a
  value that is only visible as a bar-chart height in the source, with no
  number stated in the text; leave ``value`` blank for those rows rather than
  reading it off the chart).

None of these values are known to this script or invented by it; they exist
only in the private source workbook a maintainer supplies at run time.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

from biochar_ad_kinetics.xlsx_reader import read_workbook as _read_workbook

SOURCE_DOI = None
SOURCE_NOTE = (
    "Unpublished CYPRUS2025 extended abstract, shared directly by the author "
    "(Marta García-Prats) on 2026-09-02; the full paper is under revision and "
    "not yet public."
)
STUDY_ID = "garcia_prats_cyprus2025"

# No public copy of the source file has ever been available to this script,
# so there is no hash to pin yet. Once a maintainer confirms a specific
# transcribed workbook is authentic, record its digest here (as the Zhang
# script does with SOURCE_SHA256) so later runs are verified rather than
# merely reported.
EXPECTED_SOURCE_SHA256: str | None = None

EXPECTED_BIOCHAR_IDS = (
    "PP300", "PP400", "PP500",
    "PH300", "PH400", "PH500",
    "Q300", "Q400", "Q500",
)

SHEETS = ("characteristics", "kinetics", "correlations", "ad_performance")


def read_workbook(path: Path) -> dict[str, list[list[object]]]:
    """Read the four expected worksheets without an Excel engine dependency."""

    return _read_workbook(path, sheet_names=SHEETS)


def _rows_as_dicts(sheet: list[list[object]]) -> list[dict[str, object]]:
    header = [str(name).strip() for name in sheet[0]]
    return [
        dict(zip(header, row, strict=False))
        for row in sheet[1:]
        if any(value is not None for value in row)
    ]


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _boolean(value: object) -> bool:
    return str(value).strip().upper() in {"TRUE", "1", "YES"}


def _feedstock_and_temperature(biochar_id: str) -> tuple[str, int]:
    match = re.fullmatch(r"([A-Z]+)(\d+)", str(biochar_id).strip())
    if not match:
        raise ValueError(f"Unrecognized biochar id: {biochar_id!r}")
    feedstock, temperature = match.groups()
    return feedstock, int(temperature)


def transform_characteristics(sheet: list[list[object]]) -> list[dict[str, object]]:
    """Transcribe Table 1 exactly; all nine biochars must be present."""

    rows = _rows_as_dicts(sheet)
    seen = {str(row["biochar_id"]).strip() for row in rows}
    missing = set(EXPECTED_BIOCHAR_IDS).difference(seen)
    unexpected = seen.difference(EXPECTED_BIOCHAR_IDS)
    if missing or unexpected:
        raise ValueError(
            f"characteristics sheet does not match the nine expected biochars: "
            f"missing={sorted(missing)}, unexpected={sorted(unexpected)}"
        )
    result = []
    for row in rows:
        biochar_id = str(row["biochar_id"]).strip()
        feedstock, pyrolysis_temperature_c = _feedstock_and_temperature(biochar_id)
        result.append(
            {
                "study_id": STUDY_ID,
                "biochar_id": biochar_id,
                "feedstock": feedstock,
                "pyrolysis_temperature_c": pyrolysis_temperature_c,
                "ph": _number(row.get("ph")),
                "ec_us_cm": _number(row.get("ec_us_cm")),
                "carbon_pct": _number(row.get("carbon_pct")),
                "nitrogen_pct": _number(row.get("nitrogen_pct")),
                "oxygen_pct": _number(row.get("oxygen_pct")),
                "hydrogen_pct": _number(row.get("hydrogen_pct")),
                "h_c_ratio": _number(row.get("h_c_ratio")),
                "o_c_ratio": _number(row.get("o_c_ratio")),
                "data_origin": "author_shared_unpublished_abstract",
                "source_note": SOURCE_NOTE,
            }
        )
    return result


def transform_kinetics(sheet: list[list[object]]) -> list[dict[str, object]]:
    """Transcribe Table 2 exactly, for every biochar and the control, at both doses."""

    rows = []
    for row in _rows_as_dicts(sheet):
        dose_pct = _number(row.get("dose_pct"))
        if dose_pct is None:
            continue
        rows.append(
            {
                "study_id": STUDY_ID,
                "biochar_id": str(row.get("biochar_id")).strip(),
                "dose_pct": dose_pct,
                "lambda_days": _number(row.get("lambda_days")),
                "r_max_ml_g_vs_d": _number(row.get("r_max_ml_g_vs_d")),
                "y_max_ml_g_vs": _number(row.get("y_max_ml_g_vs")),
                "data_origin": "author_shared_unpublished_abstract",
                "source_note": SOURCE_NOTE,
            }
        )
    return rows


def transform_correlations(sheet: list[list[object]]) -> list[dict[str, object]]:
    """Transcribe Table 3 exactly; the relevance flag is derived, not transcribed."""

    rows = []
    for row in _rows_as_dicts(sheet):
        dose_pct = _number(row.get("dose_pct"))
        pearson_r = _number(row.get("pearson_r"))
        p_value = _number(row.get("p_value"))
        if dose_pct is None or pearson_r is None or p_value is None:
            continue
        rows.append(
            {
                "study_id": STUDY_ID,
                "property": str(row.get("property")).strip(),
                "outcome": str(row.get("outcome")).strip(),
                "dose_pct": dose_pct,
                "pearson_r": pearson_r,
                "p_value": p_value,
                "is_relevant": abs(pearson_r) >= 0.7 and p_value < 0.05,
                "data_origin": "author_shared_unpublished_abstract",
                "source_note": SOURCE_NOTE,
            }
        )
    return rows


def transform_ad_performance(sheet: list[list[object]]) -> list[dict[str, object]]:
    """Transcribe stated AD-performance numbers only; chart-only values stay unset."""

    rows = []
    for row in _rows_as_dicts(sheet):
        dose_pct = _number(row.get("dose_pct"))
        if dose_pct is None:
            continue
        not_machine_extractable = _boolean(row.get("not_machine_extractable"))
        value = _number(row.get("value"))
        if value is None and not not_machine_extractable:
            continue
        rows.append(
            {
                "study_id": STUDY_ID,
                "biochar_id": str(row.get("biochar_id")).strip(),
                "dose_pct": dose_pct,
                "metric": str(row.get("metric")).strip(),
                "value": value,
                "reported_standard_deviation": _number(row.get("reported_standard_deviation")),
                "percent_change_vs_control": _number(row.get("percent_change_vs_control")),
                "not_machine_extractable": not_machine_extractable,
                "data_origin": "author_shared_unpublished_abstract",
                "source_note": SOURCE_NOTE,
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _verify_source_hash(path: Path) -> str:
    """Verify the source hash if one is recorded; otherwise report it.

    Unlike the Zhang script, no hash has ever been recorded for this source,
    since this project has never had access to the real file. On first use,
    the computed digest is printed so a maintainer can confirm it out of band
    and record it as ``EXPECTED_SOURCE_SHA256`` for future, verified runs.
    """

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if EXPECTED_SOURCE_SHA256 is None:
        print(
            "No expected hash is recorded yet for the García-Prats CYPRUS2025 "
            f"source. Computed SHA-256: {digest}\n"
            "Confirm this file with the author out of band, then record this "
            "value as EXPECTED_SOURCE_SHA256 in this script so future runs are "
            "verified rather than merely reported."
        )
        return digest
    if digest != EXPECTED_SOURCE_SHA256:
        raise ValueError(f"Source SHA-256 mismatch: expected {EXPECTED_SOURCE_SHA256}, received {digest}")
    return digest


def build_dataset(source: Path, output_directory: Path) -> dict[str, object]:
    """Build private characteristics, kinetics, correlation and AD-performance CSVs."""

    digest = _verify_source_hash(source)
    workbook = read_workbook(source)
    characteristics = transform_characteristics(workbook["characteristics"])
    kinetics = transform_kinetics(workbook["kinetics"])
    correlations = transform_correlations(workbook["correlations"])
    ad_performance = transform_ad_performance(workbook["ad_performance"])
    _write_csv(output_directory / "characteristics.csv", characteristics)
    _write_csv(output_directory / "kinetics.csv", kinetics)
    _write_csv(output_directory / "correlations.csv", correlations)
    _write_csv(output_directory / "ad_performance.csv", ad_performance)
    manifest = {
        "study_id": STUDY_ID,
        "source_sha256": digest,
        "source_doi": SOURCE_DOI,
        "source_note": SOURCE_NOTE,
        "characteristics_rows": len(characteristics),
        "kinetics_rows": len(kinetics),
        "correlations_rows": len(correlations),
        "ad_performance_rows": len(ad_performance),
        "not_machine_extractable_rows": sum(
            1 for row in ad_performance if row["not_machine_extractable"]
        ),
        "limitations": [
            "unpublished extended abstract; full paper under revision and not public",
            "author-shared directly by email, not redistributed",
            "abstract only, not the full paper's methods or complete results",
            (
                "chart-only values without a stated number are flagged "
                "not_machine_extractable and left unset, never estimated from the chart"
            ),
            "single extended abstract; no independent replication of its own findings",
        ],
    }
    (output_directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("data/private/garcia_prats_cyprus2025"))
    args = parser.parse_args()
    print(json.dumps(build_dataset(args.source, args.output), indent=2))


if __name__ == "__main__":
    main()
