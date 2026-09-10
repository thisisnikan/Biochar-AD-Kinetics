# Continuous Analysis Log

This file records the evidence, assumptions, QC decisions, and modelling steps for the continuous/semi-continuous anaerobic-digestion branch. It is intentionally separate from speculative future-work notes.

## 2026-09-10 — Daskaloudis dataset intake

Source dataset: `Anaerobic digestion with digestate recirculation and biochar` (author-shared/public repository data; local working archive contained `recirculation&biochar.xlsx` plus VFA/ethanol and microbial-community files).

### Scope established

- Main reactor time series spans approximately day 0 to day 389.
- Dataset is organised into start-up plus Phases I–IV.
- Phase IV is strongly supported as the biochar period by matching the microbial shifts reported in the associated pilot-scale biochar work.
- Phase III is therefore treated as the immediate pre-biochar reference for the first intervention analysis, but the entire 389-day trajectory must be analysed to avoid attributing pre-existing drift to biochar.
- Phase I–III intervention definitions remain unresolved and must not be guessed.

### Variables identified

Operating/input variables include OLR, HRT, feed flow and solids/COD-related measurements where available.

Process/state variables include pH, alkalinity, TAN, soluble COD, VFA species and microbial-community measurements.

Outputs include biogas production, methane fraction, methane production and specific methane-yield metrics.

### Important first observations

- Phase IV shows higher methane fraction than Phase III, while total biogas, methane production and specific methane yield do not increase in parallel.
- This means methane concentration alone cannot be used as a proxy for overall continuous-reactor improvement.
- VFA composition changes across phases rather than moving uniformly in one direction.
- Archaea composition changes strongly from Phase III to Phase IV, including a marked increase in Methanothrix and a smaller increase in Methanospirillum.

### QC issues found

- Day 235 appears duplicated in the main workbook and should be deduplicated after confirming rows are identical.
- Several zero values are likely missing-data placeholders rather than measured zeros. These must be handled with variable-specific/source-specific QC rules and never globally converted without evidence.
- Whole-phase averages do not exactly reproduce values reported in the associated paper, suggesting the publication may have used steady-state windows or selected subsets. The model must therefore preserve raw trajectories and explicitly define any steady-state filtering.

### Current scientific questions

1. How does reactor performance evolve across the full start-up → Phase I → II → III → IV trajectory?
2. Which changes at phase transitions are attributable to operating changes versus long-term drift?
3. What is the immediate and delayed response after biochar introduction?
4. Do methane, VFA, TAN, pH, COD/VS and microbial shifts tell a mutually consistent story?
5. Which response metric best represents useful continuous-reactor performance: methane fraction, methane production, specific methane yield, stability, or a multi-metric endpoint?

### Analysis plan

1. Resolve phase definitions from source documents where possible.
2. Build a clean long-format reactor table with provenance and QC flags.
3. Deduplicate confirmed duplicate records.
4. Classify missing placeholders versus true measured zeros.
5. Segment the full trajectory into phase and candidate steady-state windows.
6. Compare full-phase and steady-state statistics.
7. Perform time-lag/intervention analysis around Phase III → IV.
8. Examine VFA, pH, TAN, COD/VS and microbial changes jointly with gas outputs.
9. Only after the above, decide whether a mechanistic, statistical or hybrid continuous model is identifiable from this dataset.

## Modelling boundary

Do not add an ADM1, digital-twin, sensor or control implementation merely because continuous data now exist. Continuous modelling is considered evidence-supported only after the source data, phase definitions, QC and dynamic-response structure have been resolved.
