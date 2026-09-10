# Continuous / Dynamic Data Pipeline Status

This file is the operational source of truth for unfinished dynamic-data work. A stage is marked complete only when its output exists and is reproducible from the original source.

| Study | Source acquired | QC builder | QC report | Processed table reproducible | Dynamic analysis | External-validation eligible | Current blocker |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Daskaloudis 2026 | yes | complete | complete | complete locally, deterministic rebuild verified | complete for Phase III→IV sensitivity | development dataset only | Phase I–III meanings unresolved; processed CSV still generated from source rather than committed as a large static artifact |
| Sanglier 2022 | public source confirmed | not started | not started | no | no | no | `Process.xlsx` binary must be acquired and intervention/cycle structure reconstructed |
| Wambugu 2019 | paper/source design confirmed | not started | not started | no | no | potentially strong | raw machine-readable daily UASB time series not yet located |
| Heitkamp 2021 | public supplementary XLSX confirmed | not started | not started | no | no | process-stability only | supplementary binary download currently unresolved in this environment |

## Daskaloudis closure achieved on 2026-09-10

The source workbook was rebuilt through `scripts/build_daskaloudis_2026_continuous_dataset.py` and produced a 98-row processed table spanning day 0–389. A second rebuild was compared byte-for-byte with the first generated CSV and was identical. Therefore the processed longitudinal table is deterministic under the current parser and QC rules.

The Phase III→IV transition analysis was then rerun using that QC-approved generated table. The persisted machine-readable output is `outputs/continuous_transition_sensitivity.csv`. It reproduces the previously documented full-window results, including:

- methane fraction: level change ≈ +2.56 percentage points, post-slope change ≈ +0.109 percentage points/day, ΔAIC(simple−segmented) ≈ +31.16;
- CH4 production: level change ≈ −3.95 L/day, post-slope change ≈ +0.336 L/day/day, ΔAIC ≈ +2.69;
- methane-yield workbook field: level change ≈ −22.34, post-slope change ≈ +0.917/day, ΔAIC ≈ +3.83;
- biogas: level change ≈ −15.81 L/day, post-slope change ≈ +0.091 L/day/day, ΔAIC ≈ −0.36.

These values confirm that methane composition changes robustly around the Phase-IV boundary while absolute productivity metrics do not show an equally robust improvement.

## Pipeline rules

1. Development and validation studies remain separated by study identity.
2. External-validation candidates cannot be added to model fitting before ingestion and QC are frozen.
3. Binary source access failure is reported as a blocker; figures are not digitised merely to create more rows when raw files are known to exist.
4. Parallel control/treatment studies receive higher acquisition priority than additional single-reactor before/after studies.
5. Industrial datasets without reliable methane-productivity measurements are used only for the process-stability claims they can support.

## Immediate queue

1. Acquire Sanglier `Process.xlsx` and authors' analysis archive; reconstruct cycle, dose and trace-element interventions.
2. Acquire Heitkamp supplementary XLSX; build plant-level VFA longitudinal intake with intervention-relative time.
3. Search thesis/repository records for Wambugu daily UASB measurements before considering figure digitisation.
4. Resolve Daskaloudis Phase I–III intervention semantics from source documentation.
5. Only after at least one external dataset passes QC, run locked transferability tests and compare direction/effect stability against the Daskaloudis hypotheses.
