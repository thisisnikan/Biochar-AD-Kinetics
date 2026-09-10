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

- Day 235 is duplicated in Phase III. The two rows should be compared exactly before one is removed in any processed dataset.
- Missingness must be handled variable-by-variable. Earlier inspection suggested apparent placeholder behaviour in the workbook, but the principal continuous-model variables do not support a blanket `0 = missing` rule. No global zero replacement is allowed.
- Whole-phase averages do not exactly reproduce values reported in the associated paper, suggesting the publication may have used steady-state windows or selected subsets. The model must therefore preserve raw trajectories and explicitly define any steady-state filtering.

### Current scientific questions

1. How does reactor performance evolve across the full start-up → Phase I → II → III → IV trajectory?
2. Which changes at phase transitions are attributable to operating changes versus long-term drift?
3. What is the immediate and delayed response after biochar introduction?
4. Do methane, VFA, TAN, pH, COD/VS and microbial shifts tell a mutually consistent story?
5. Which response metric best represents useful continuous-reactor performance: methane fraction, methane production, specific methane yield, stability, or a multi-metric endpoint?

## 2026-09-10 — HRT-window and transition analysis

The reactor HRT is 20 d throughout the usable main time series. That gives a physically meaningful first segmentation after the Phase IV intervention boundary at day 309:

- 0–1 HRT after Phase IV start: day 309 to <329
- 1–2 HRT: day 329 to <349
- >2 HRT: day 349 onward

These windows are not automatically called steady state. They are response windows used to distinguish immediate, delayed and later behaviour.

### Phase IV response by HRT window

Mean values from the available measurements:

| Window | Biogas (L/d) | Methane (%) | CH4 (L/d) | pH reactor | COD removal (%) |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0–1 HRT | 250.85 | 69.67 | 174.65 | 7.572 | 88.95 |
| 1–2 HRT | 248.37 | 69.50 | 172.42 | 7.598 | 89.50 |
| >2 HRT | 243.67 | 72.58 | 176.79 | 7.539 | 89.58 |

Interpretation: methane fraction rises mainly in the later (>2 HRT) part of Phase IV. Total methane production does not show a comparable increase. This supports treating methane fraction and methane productivity as separate response variables.

### Immediate pre/post comparison using HRT-based windows

For a conservative comparison, the last ~1 HRT of Phase III (day >=289) was used as the immediate pre-intervention reference and the >2-HRT portion of Phase IV (day >=349) as the later response window.

| Metric | Late Phase III | Phase IV >2 HRT | Relative change |
| --- | ---: | ---: | ---: |
| Biogas (L/d) | 267.50 | 243.67 | -8.9% |
| Methane (%) | 67.00 | 72.58 | +8.3% |
| CH4 (L/d) | 179.22 | 176.79 | -1.4% |
| Methane yield (N mL CH4/gVS, workbook field) | 627.29 | 521.78 | -16.8% |
| VS removal (%) | 47.47 | 46.38 | -2.3% |
| COD removal (%) | 88.98 | 89.58 | +0.7% |
| pH reactor | 7.508 | 7.539 | +0.4% |
| OLR (gVS/L/d) | 1.583 | 1.892 | +19.5% |

The OLR increase is a major confounder. Therefore these pre/post differences are descriptive and must not be interpreted as causal biochar effects.

### Within-phase trend check

Simple linear trend checks across each phase show that Phase III was already drifting before Phase IV: biogas, methane fraction and CH4 production decline across Phase III. In Phase IV, methane fraction trends upward, while CH4 production is approximately flat across the full phase. This makes a simple `Phase III mean vs Phase IV mean` comparison insufficient.

### VFA evidence boundary

The VFA workbook contains phase-level means/dispersion rather than a day-resolved VFA trajectory. It can support phase-to-phase consistency checks, but it cannot currently support day-scale lag estimation. Reported phase means show acetate falling strongly in Phase IV, while propionate and butyrate rise relative to Phase III. The correct statement is that VFA composition shifts; total-VFA improvement should not be claimed without reconstructing a justified aggregate.

### Current interpretation

The first HRT-based analysis does not support a simple statement that Phase IV 'improved methane production'. The later Phase IV period has higher methane concentration but similar absolute CH4 production despite higher OLR, and lower specific methane yield. The dataset therefore reinforces the need for a multi-metric continuous-performance definition.

### Next modelling gate

Before any ADM1 or ML model is added:

1. Resolve Phase I–III operating/intervention definitions from source documentation.
2. Confirm exact duplicate handling for day 235.
3. Build a reproducible processed table with provenance and missingness/QC flags.
4. Define candidate stable windows using both HRT and statistical stability criteria rather than arbitrary calendar cuts.
5. Fit an interrupted/segmented time-series model around the Phase III → IV boundary with OLR and other measurable operating variables as covariates.
6. Treat microbial and phase-level VFA measurements as supporting evidence, not high-frequency predictors.
7. Compare alternative continuous performance targets: CH4 L/d, specific methane yield, methane fraction, removal efficiency and a transparent multi-metric stability score.

### Analysis plan

1. Resolve phase definitions from source documents where possible.
2. Build a clean long-format reactor table with provenance and QC flags.
3. Deduplicate confirmed duplicate records.
4. Classify missing placeholders versus true measured zeros without a blanket rule.
5. Segment the full trajectory into phase and candidate steady-state windows.
6. Compare full-phase and steady-state statistics.
7. Perform time-lag/intervention analysis around Phase III → IV.
8. Examine VFA, pH, TAN, COD/VS and microbial changes jointly with gas outputs.
9. Only after the above, decide whether a mechanistic, statistical or hybrid continuous model is identifiable from this dataset.

## Modelling boundary

Do not add an ADM1, digital-twin, sensor or control implementation merely because continuous data now exist. Continuous modelling is considered evidence-supported only after the source data, phase definitions, QC and dynamic-response structure have been resolved.
