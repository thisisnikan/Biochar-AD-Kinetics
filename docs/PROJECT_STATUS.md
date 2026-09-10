# Project status

Last reviewed: 9 September 2026

## Readiness snapshot

| Area | Status | Evidence |
| --- | --- | --- |
| Package and CLI | Working | Installable package with modelling, benchmarking, effect-summary and intake-validation commands |
| Automated quality | Working | Ruff plus automated tests on Python 3.10 and 3.12 in GitHub Actions |
| Data contribution gate | Working | Minimum reactor-time-point contract plus machine-readable Stage A dose-series readiness assessment; source-level review remains mandatory |
| Intake-to-model path | Working, awaiting qualifying data | `fit-stage-a` preserves reactor identity and separates whole-reactor from whole-dose holdouts; dose units other than g/L require documented conversion before fitting |
| Real-data contract import | Reproducible, source conflict flagged | 7,575 observations from 15 Kozłowski reactors, including individual blanks; [validation and gaps](../results/intake/README.md) |
| Synthetic workflow | Reproducible | Labelled synthetic input and deterministic reporting pipeline |
| Open experimental benchmark | Reproducible | Kozłowski et al. (2025) reactor-level trajectories and reference output |
| Zhang integration | Limited by source | Hash-verified private ingestion and summary analysis; original triplicates were lost |
| Independent dose-response challenge | Falsified as tested | Valentin & Białowiec (2024) external table: log-linear beats the project's log-quadratic form on leave-one-dose-out RMSE |
| Global dose–temperature hypothesis | Not independently validated | Requires multi-dose, multi-temperature reactor trajectories; the dose-response *form* is now externally challenged (see above) |
| Parameter identifiability | Checked, and currently failing on the demo | `fit_global` reports parameter correlation and condition number; the 8-parameter model is already confounded (correlation ≈ 0.96) on the bundled synthetic demo |
| Effect-size uncertainty | Partially reported | Reactor-level percent-change effects now carry a 95% CI and a `low_replication` flag; published-table effects still carry no uncertainty at all |
| Pyrolysis-temperature descriptor confounding | Checked and confounded | CDU / Wang (2026) six-biochar summary table: temperature, BET, conductivity and pH correlate above the checked threshold, so `benchmark-pyrolysis-temperature` refuses to attribute a trend to any one of them |
| Mechanism-evidence grading | Documented | `docs/MECHANISM_EVIDENCE.md` grades every dataset Weak/Moderate/Strong (Pilarska 2026); no dataset in this repository currently reaches Strong |
| Stage C material-aware transfer (H1: dose + pyrolysis temperature) | Tested and rejected | Leave-one-study-out Ridge on 3 independent studies (Kozłowski 2025, Valentin & Białowiec 2024, Chiappero 2021): 0 of 3 held-out studies beat the training-study mean baseline for `delta_potential` or `delta_max_rate` (`scripts/run_stage_c_material_fingerprint.py`) |
| Stage C material-aware transfer (H2: measured biochar properties + AD context) | Not evaluated — blocked | Only 1 of 3 fingerprinted studies (Chiappero 2021) reports `surface_area_m2_g`/`pore_volume_cm3_g` alongside kinetic effects; the 3-independent-study gate in `material_fingerprint.py` blocks any richer-descriptor claim until that changes (`docs/STAGE_C_DATA_GAPS.md`) |

## What can be claimed now

- The software executes an auditable end-to-end BMP modelling workflow.
- Reactor-level contributions can be checked for identity, controls, replicate structure,
  raw/processed coexistence, QC and row-level provenance before modelling.
- Modified Gompertz has the lowest mean reactor-held-out RMSE within each treatment of the
  included Kozłowski et al. (2025) experiment.
- Author-shared Zhang et al. (2022) summaries can be analysed without inventing
  pseudo-replicates or publishing the private workbook.
- An independent 2024 glucose BMP dataset (Valentin & Białowiec) was used to stress-test the
  project's log-quadratic dose-response form against simpler alternatives, and the
  repository reports the negative result rather than hiding it.
- Every global fit reports whether its own 8 parameters are practically identifiable
  (`max_parameter_correlation`, `parameter_gram_condition_number`), instead of only
  reporting goodness of fit.
- A qualifying reactor-level intake can be fitted without collapsing replicate identity;
  `fit-stage-a` reports replicate reproducibility separately from dose generalization and
  removes all sibling reactors at a held-out dose from training together.
- `leave_one_batch_out` distinguishes held-out batches at the edge of the observed
  dose/temperature range (`is_boundary_condition`) from interior ones, so interpolation
  and extrapolation error are never silently averaged together.
- Reactor-level percent-change effect sizes carry a 95% confidence interval (delta method
  on the log response ratio) and a `low_replication` flag for any arm with fewer than
  3 reactors.
- Every dataset in this repository is graded Weak/Moderate/Strong for what kind of
  mechanism evidence it actually contains (`docs/MECHANISM_EVIDENCE.md`), so a good
  process-level fit is never described using stronger mechanistic language than the
  underlying data supports.
- The CDU / Wang (2026) pyrolysis-temperature summary table is checked for a smooth
  temperature-response trend *and* for collinearity among its own descriptors
  (temperature, BET, conductivity, pH), which the CLI reports as confounded rather
  than picking one as the "driver."
- The project's log-based, non-monotonic dose term has literature precedent: Chiappero
  et al. (2022, https://doi.org/10.1016/j.jece.2022.108870) report a non-monotonic
  aggregated dose-response across their meta-analysis (moderate doses helping,
  excessive doses trending toward inhibition) and a dose-cost regression that argues
  against very high doses on economic grounds alone. This *motivates* the functional
  form chosen here — it does not validate this project's specific fitted parameters.

## What cannot be claimed now

- That biochar causally improves anaerobic digestion across studies.
- That the exploratory dose–temperature response generalises beyond the demonstration.
- That the project's log-quadratic dose-response form is supported by independent data —
  on the Valentin & Białowiec (2024) table, held-out prediction favours a simpler log-linear
  form instead, for both methane potential and maximum rate.
- That an external kinetic-parameter table validates full reactor trajectories — it is a
  parameter-level challenge only; the paper's raw reactor time series were not obtained.
- That summary-curve residuals replace biological replicate uncertainty.
- That this research prototype is already an operational plant digital twin (see
  [README § What this project can become](../README.md#what-this-project-can-become)): there is no
  mass/energy balance, reactor hydrodynamics, or live data-assimilation loop here.
- That the 8-parameter global model's individual parameter values are meaningful on their
  own — on the bundled synthetic demo dataset itself, the identifiability diagnostic already
  finds two parameters confounded at correlation ≈ 0.96, above the 0.95 warning threshold.
  No real dataset in this repository varies both dose and temperature with replicates, so
  this has never been checked on real data, only ruled out as achievable on the easiest
  possible (synthetic, noise-controlled) case.
- That the larger reported percent-change effects (e.g. the Valentin & Białowiec dose-response
  table) are statistically distinguishable from no effect — that table has no per-replicate
  standard deviation at all, so no confidence interval can be computed for it, and every row
  from it is flagged `low_replication` for that reason.
- That any dataset in this repository, including CDU / Wang (2026), demonstrates direct
  interspecies electron transfer (DIET) — every dataset here is graded Moderate or Weak in
  `docs/MECHANISM_EVIDENCE.md`; none has the electrochemical or molecular evidence a Strong
  grade requires.
- That the CDU / Wang (2026) pyrolysis-temperature trend is attributable to conductivity
  specifically — pyrolysis temperature, BET surface area, electrical conductivity and pH all
  increase together across the six biochars in that table, and `benchmark-pyrolysis-temperature`
  reports that collinearity rather than picking a "best" descriptor.
- That the CDU / Wang (2026) thesis's own access/distribution terms are confirmed — this
  repository could not independently verify them from its network environment; only the
  specific published numeric values already summarised in issue #10 are transcribed, with
  full citation, pending that confirmation.
- That measured biochar properties (surface area, pore volume, elemental composition) plus
  AD context improve held-out-study transfer beyond dose and pyrolysis temperature (the
  "H2" material-descriptor hypothesis). This has not been tested, let alone validated: only
  one of the three studies currently in the kinetic-fingerprint table reports surface/pore
  descriptors alongside kinetic effects, so `leave_one_study_out` refuses to evaluate the
  richer feature set until at least three independent, descriptor-complete studies exist.
  Rejecting the simpler H1 (dose + pyrolysis temperature) is not evidence for H2.

## Next validation gate

Validation proceeds in two stages; one dataset need not satisfy both at once.
The [staged protocol and source screening](VALIDATION_PLAN.md) records acceptance
criteria and the remaining acquisition work.

1. **Dose first:** independent reactor trajectories at one digestion temperature,
   with a zero-dose substrate control, at least three amended doses of the same
   material, intact replicates, blanks and traceable metadata.
2. **Temperature second:** replicated dose-by-digestion-temperature designs,
   followed by temperature prediction and parameter-identifiability checks —
   concretely, `max_parameter_correlation` below `IDENTIFIABILITY_CORRELATION_THRESHOLD`
   when the 8-parameter model is fitted to that dataset. A low-RMSE fit with
   confounded parameters does not satisfy this stage.
3. Freeze QC, model candidates and held-out criteria before evaluating new raw
   outcomes. Within-study refitting is not held-out-study transfer.

The Valentin & Białowiec table remains a parameter-level challenge, not Stage A
reactor validation. The 15-reactor Kozłowski intake adds no independent study,
dose or temperature. Its blank QC and control-dose source conflicts remain
unresolved. No new independent raw dataset was acquired in this update.

All three model candidates now share whole-batch folds, robust loss and common
parameter bounds. Mean fold RMSE is primary; AICc is descriptive. At one training
temperature Q10 is fixed to 1. This improves the software comparison but supplies
no new external scientific evidence.

Until that gate is passed, the repository should be described as a **reproducible research
prototype for falsifiable kinetic modelling**, not as a validated predictive product.

## Maintenance checklist

- Keep `main` green on every merge.
- Regenerate committed reference results after model or data-processing changes.
- Record every public dataset's license, DOI, source hash and transformation decisions.
- Never commit author-shared files without explicit redistribution permission.
- Update this page whenever the scientific evidence boundary changes.
