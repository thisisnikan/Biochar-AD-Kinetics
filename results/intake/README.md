# Kozłowski real-data intake and remaining gaps

This import passes the structural reactor-observation contract. It does **not**
pass the global dose–temperature validation gate.

## Rebuild and validate

Install the package with `pip install -e ".[dev]"`, then run from the repository root:

```bash
python scripts/build_kozlowski_2025_dataset.py \
  --intake-output data/experimental/kozlowski_2025_reactor_observations.csv.gz \
  --intake-report results/intake/kozlowski_2025_validation.json
biochar-ad validate-intake data/experimental/kozlowski_2025_reactor_observations.csv.gz
```

The importer downloads and verifies the publisher supplement against the recorded
SHA-256. For offline rebuilding, add `--source /path/to/verified-supplement.xlsx`.
The original benchmark CSV remains the default `--output`; its rebuilt bytes are
unchanged. To keep a rebuild separate, set `--output outputs/rebuilt_bmp.csv`.
An uncompressed intake CSV can be requested by using a `.csv` output suffix.
The committed gzip CSV has deterministic compression and is read directly by pandas
and `validate-intake`. No private data are involved.

## What was recovered

| Component | Submitted reactors | QC-included reactors | Observations |
| --- | ---: | ---: | ---: |
| Inoculum-only blanks | 3 | 3 | 1,515 |
| Food-waste control | 3 | 3 | 1,515 |
| Torrefaction product | 3 | 2 | 1,515 |
| Pyrolysis biochar | 3 | 2 | 1,515 |
| Hydrochar | 3 | 3 | 1,515 |
| Total | 15 | 13 | 7,575 |

The three blank trajectories are direct source measurements from columns E:G,
not estimated replicates. Source reactor labels from row 17 are retained as IDs.
Every raw observation has a worksheet/cell reference. The source hash, DOI,
raw time fields, blank-cell references, substrate and inoculum VS masses and
their source cells are retained alongside the normalized contract.

For substrate reactors, corrected yield is `(raw methane - mean of three blanks)
/ substrate VS mass`. All source reactors contain the same inoculum VS mass.
Blank reactors have zero substrate VS; their corrected substrate yield and ISR
are left empty. The three individual blank values reproduce the existing mean.
The two historically excluded substrate reactors remain present and excluded.

`experiment_id`, `substrate_id`, `inoculum_id` and amended `material_id` are
study-scoped curation keys. They do not claim independently verified collection
or production batches. `reactor_id` preserves the source row-17 label; the numeric
row-3 label is retained separately because the workbook contains inconsistent
old/new instrument headings.

## Validation and source conflicts

The JSON report separates structural findings from source conflicts and evidence
gaps. Structural validation returns **zero errors and one warning**: raw cumulative
methane decreases at two time points. Source values are retained without clipping.
The JSON identifies both affected source cells and their inclusion status.
Both decreases occur in included blank K1: -2.9 mL at hour 469 (`E487`) and
-3.9 mL at hour 484 (`E502`). This is an unresolved source QC issue that also
affects the shared blank correction. K1 remains included to reproduce the
historical calculation; passing structural validation does not resolve it.

Two other issues remain explicit in row-level flags and the report:

- **Time:** the source derived-day field ends at 5.25 although the hourly index
  ends at 504. The established mapping remains `time_hours / 24`, ending at 21 days.
- **Control dose:** H:J rows 10 and 12 contain 2 g and 5 g/L for the food-waste
  control. The source treatment labels and article design distinguish food waste
  without carbon material from the three amended treatments. The canonical dose
  remains zero, matching the existing benchmark mapping, while the contradictory
  source mass/dose and cell references are preserved. This is a documented
  interpretation, not an author-confirmed correction. Author clarification is still
  needed before treating control metadata as resolved.

Source: [Kozłowski et al. (2025), methods and publisher supplement](https://doi.org/10.1038/s41598-025-02564-0),
CC BY 4.0. Full file provenance is in [data/README.md](../../data/README.md).

## Exact next evidence needs

| Gap | Current evidence | Next action |
| --- | --- | --- |
| Blank trajectory QC | K1 decreases at hours 469 and 484 | Check source readings E487 and E502 before revising blank correction |
| Temperature response | Only 37 °C | Obtain reactor curves at additional digestion temperatures |
| Within-material dose response | Only one amended dose, 5 g/L, for each material | Obtain several doses of the same material with matched controls and replicates |
| External reactor-level validation | One study in this import | Obtain an independent study and specify held-out comparisons before fitting |
| Control dose provenance | Conflicting worksheet entries | Request clarification of H:J rows 10 and 12 |
| Independent batch identity | Study-scoped labels only | Verify inoculum collection and material production batch identifiers |
| Additional metadata | Working volume, gas reference conditions, material descriptors and process chemistry not harmonized here | Extract/verify these from their sources before cross-study use; do not label them absent merely because this import lacks them |

The new observations make blank correction and reactor provenance inspectable.
They do not add a new study, dose or temperature. Preserve this distinction when
presenting the dataset or requesting further data.

## Regression checks

```bash
pytest -q tests/test_kozlowski_intake.py
```

Tests reconcile every historical reactor/time key, raw value, blank mean, corrected
yield and exclusion; independently recompute the correction from individual blanks;
check source conflicts remain visible; reject an unverified workbook; and compare
the held-out benchmark calculated from the new intake with the historical input.
The source reported-day audit field retains full source precision, whereas the
historical CSV rounded it to eight decimals. It is not used as modelling time.

The initial rebuild was also checked against the committed historical CSV byte for
byte, and a second rebuild reproduced the compressed intake and JSON identically.


## 27 September 2026 source expansion

Sanglier chemistry/events and the independent Heitkamp industrial chemistry
candidate are documented in `docs/RESEARCH_EVIDENCE_2026_09.md`. Both remain
outside fitting and validation. Derived source data retain their source licenses
(Sanglier: Etalab Open License 2.0; Heitkamp: CC BY 4.0), not the software MIT license.
Rebuild with `scripts/build_sanglier_2022_context.py` and
`scripts/build_heitkamp_2021_candidate.py`; both verify the audited source hash.
