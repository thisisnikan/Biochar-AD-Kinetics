"""Lossless chemistry/event context for the quarantined Sanglier methane intake.

No interpolation, outcome modelling, dose conversion, or treatment relabelling.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from build_sanglier_2022_candidate import KEY, SOURCE_DOI, _value, sheet_records, source_hash
from openpyxl import load_workbook

MEASUREMENTS = (
    "pH",
    "TAN",
    "FAN",
    "sCOD",
    "TS",
    "VS",
    "C2",
    "C3",
    "C4",
    "C5",
    "C6",
    "IC4",
    "IC5",
    "IC6",
)
STATUS = "CANDIDATE_QC_ONLY_NOT_ADMITTED_FOR_FITTING_OR_VALIDATION"


def identity(row):
    key = tuple(row.get(c) for c in KEY)
    if any(v is None for v in key):
        raise ValueError(f"Incomplete bottle/batch identity: {key}")
    return key


def index_unique(rows):
    result = {}
    for row in rows:
        key = identity(row)
        if key in result:
            raise ValueError(f"Duplicate Inoculation identity: {key}")
        result[key] = row
    return result


def contextual_events(events, lab, days):
    """Prior/same-time lab context only; these are NOT bottle exposure assignments."""
    return ";".join(
        f"Events!{e['source_row']}" for e in events if e["Lab"] == lab and e["Days"] <= days
    )


def build_context(analyses, events, inoculations, methane, md5, sha256):
    inoc = index_unique(inoculations)
    methane_by_key = defaultdict(list)
    for row in methane:
        key = identity(row)
        if key not in inoc:
            raise ValueError(f"Methane identity not in Inoculation: {key}")
        methane_by_key[key].append(row)
    for event in events:
        if any(event.get(c) is None for c in ("Lab", "Days", "Event")):
            raise ValueError("Event missing lab, time, or description")
    seen = set()
    chemistry = []
    analysis_by_key = defaultdict(list)
    for row in analyses:
        key = identity(row)
        if key not in inoc:
            raise ValueError(f"Analysis identity not in Inoculation: {key}")
        sample = (*key, row.get("Days"), row.get("Sampling"))
        if sample[-2] is None or sample[-1] is None or sample in seen:
            raise ValueError(f"Duplicate or incomplete chemistry sample: {sample}")
        seen.add(sample)
        flags = []
        source_inoc = inoc[key]
        if key not in methane_by_key:
            flags.append("no_methane_for_bottle_batch")
        if str(row["Cond"]).replace(" ", "") != str(source_inoc["Cond"]).replace(" ", ""):
            flags.append("condition_label_disagreement")
        if row["Biochar"] == 0 and (source_inoc["Biochar"] or 0) > 0:
            flags.append("control_label_positive_inoculation_biochar")
        if row["Replicate"] != source_inoc["Replicate"]:
            flags.append("replicate_disagreement")
        if row["Experiment_ID"] != source_inoc["Experiment_ID"]:
            flags.append("experiment_id_disagreement")
        # Keep every original header/value. Chemistry units need source-method verification.
        out = {k: _value(v) for k, v in row.items() if k != "source_row"}
        out.update(
            study_id="sanglier_2022",
            source_doi=SOURCE_DOI,
            source_md5=md5,
            source_analysis_row=f"Analyses!{row['source_row']}",
            source_inoculation_row=f"Inoculation!{source_inoc['source_row']}",
            source_condition_inoculation=source_inoc["Cond"],
            inoculation_biochar_g=source_inoc["Biochar"],
            inoculation_ammonium_bicarbonate_g=source_inoc["Ammonium bicarbonate"],
            prior_lab_event_rows=contextual_events(events, row["Lab"], row["Days"]),
            qc_flags=";".join(flags),
            model_admission=False,
        )
        chemistry.append(out)
        analysis_by_key[key].append(row)
    event_rows = []
    for event in events:
        out = {k: _value(v) for k, v in event.items() if k != "source_row"}
        out.update(
            study_id="sanglier_2022",
            source_doi=SOURCE_DOI,
            source_md5=md5,
            source_event_row=f"Events!{event['source_row']}",
            scope_policy="lab_context_only_read_source_text_for_bottle_scope",
        )
        event_rows.append(out)
    cycles = []
    for key, source_inoc in sorted(inoc.items()):
        samples = analysis_by_key.get(key, [])
        gas = methane_by_key.get(key, [])
        times = [r["Days"] for r in gas + samples]
        cycles.append(
            {
                "lab": key[0],
                "batch_id": key[1],
                "bottle_id": key[2],
                "source_inoculation_row": f"Inoculation!{source_inoc['source_row']}",
                "source_condition": source_inoc["Cond"],
                "inoculation_biochar_g": source_inoc["Biochar"],
                "inoculation_ammonium_bicarbonate_g": source_inoc["Ammonium bicarbonate"],
                "methane_rows": len(gas),
                "chemistry_rows": len(samples),
                "first_observed_day": min(times) if times else None,
                "last_observed_day": max(times) if times else None,
                "source_analysis_rows": ";".join(f"Analyses!{r['source_row']}" for r in samples),
                "source_methane_rows": ";".join(f"AMPTShort!{r['source_row']}" for r in gas),
                "model_admission": False,
            }
        )
    report = {
        "status": STATUS,
        "source_doi": SOURCE_DOI,
        "source_md5": md5,
        "source_sha256": sha256,
        "chemistry_rows": len(chemistry),
        "event_rows": len(event_rows),
        "bottle_batch_rows": len(cycles),
        "methane_rows": len(methane),
        "chemistry_samples_without_methane": sum(
            not methane_by_key.get(identity(r)) for r in analyses
        ),
        "chemistry_bottle_batches": len(analysis_by_key),
        "measurement_nonmissing": {
            c: sum(r[c] is not None for r in analyses) for c in MEASUREMENTS
        },
        "measurement_zeros": {c: sum(r[c] == 0 for r in analyses) for c in MEASUREMENTS},
        "qc_flag_counts": dict(
            sorted(Counter(f for r in chemistry for f in r["qc_flags"].split(";") if f).items())
        ),
        "join_policy": "Exact Lab/Batch/Bottle linkage; no chemistry interpolation onto methane times.",
        "event_policy": "Same-lab prior events are context, not assigned exposure or duration.",
        "units_policy": "Original chemistry headers and values retained; units unverified; no conversion.",
        "gate_blockers": [
            "control_label_mass_conflicts",
            "chemistry_unit_verification",
            "bottle_specific_event_scope_and_carryover",
            "freeze_external_validation_protocol_before_outcome_analysis",
        ],
    }
    return chemistry, event_rows, cycles, report


def build(source):
    md5 = source_hash(source)
    sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    workbook = load_workbook(source, read_only=True, data_only=True)
    try:
        analyses, events, inoculations, methane = [
            sheet_records(workbook, name)
            for name in ("Analyses", "Events", "Inoculation", "AMPTShort")
        ]
    finally:
        workbook.close()
    inoculations = [r for r in inoculations if all(r.get(k) is not None for k in KEY)]
    return build_context(analyses, events, inoculations, methane, md5, sha256)


def write(outputs, destination):
    destination.mkdir(parents=True, exist_ok=True)
    for name, rows in zip(("chemistry", "events", "bottle_batches"), outputs[:3], strict=True):
        with (destination / f"sanglier_2022_{name}.csv").open(
            "w", newline="", encoding="utf-8"
        ) as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    (destination / "sanglier_2022_context_qc.json").write_text(
        json.dumps(outputs[3], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_xlsx", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("results/intake"))
    args = parser.parse_args()
    write(build(args.source_xlsx), args.output_dir)


if __name__ == "__main__":
    main()
