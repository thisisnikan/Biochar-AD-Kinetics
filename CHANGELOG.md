# Changelog

## 2026-09-05

- Compare constant, log-linear and log-quadratic candidates on identical batch
  holdouts, with shared fitting settings and per-model summaries.
- Fix Q10 at one training temperature, reject unsupported temperature holdouts,
  and surface failed optimizer convergence.
- Document dose-first, temperature-second validation and public-source access;
  independent raw data acquisition remains pending.
- Added a hash-verified real-data intake export for all 15 Kozłowski reactors,
  including individual blanks, cell references, VS denominators and source-dose conflicts.
- Added the deterministic compressed CSV, validation JSON and remaining-evidence report;
  preserved the original benchmark CSV and exclusions.
- Hardened the experimental intake gate against empty files, non-finite numeric values,
  missing dose units and positive doses without a physical unit.
- Compare parsed times and metadata consistently while preserving source values.
- Distinguish substrate controls from inoculum blanks and count only QC-included
  reactors for control and replication warnings, retaining all submitted records.

## 2026-09-03

- Added a minimum experimental record for reactor-level Biochar–AD contributions.
- Added `biochar-ad validate-intake` with machine-readable errors and scientific-limit warnings.
- Added a worked CSV template and tests for duplicate keys, changing reactor metadata and missing blanks.

All notable project changes are documented here. The project follows a research-prototype
release model while the public API remains experimental.

## Unreleased

### 2026-09-27: Evidence requirements

- Test five curve families on 100 long Sanglier cycles: all describe whole cycles
  within about 4%, but fits to the first 6.5 d miss cycle ends by 21% to 43%;
  short records, not the equation, limit inference (`kinetic_structure`).
- Derive design requirements from variance components: at least 4 bottles per arm,
  repeated batches, and runs of about 14 to 20 d for food waste
  (`design_requirements`).
- Grade eight repository datasets against 16 minimum-information items with
  curated evidence cross-checked against committed data; none is ready for
  cross-study use (`evidence_requirements`).
- Add `biochar-ad check-evidence`, material-descriptor and intervention-log
  templates, and declarations that cannot override data-checked items.

### 2026-09-27: Sanglier admission gate

- Audit Sanglier variable semantics from committed tables: pH is the only resolved
  unit; FAN is shown to be derived from TAN and pH; TS/VS bases and one sCOD occasion
  conflict; methane unit suffixes are builder-asserted.
- Classify event scope and adjudicate all 348 bottle/batch cycles
  (source-consistent, resolvable, ambiguous, conflicting, excluded) without
  overwriting source values; add carry-over rules.
- Add a frozen machine-readable validation spec, an outcome-blind admission step,
  a fail-closed leakage audit and a role classifier that never calls refitted
  results external validation (`biochar_ad_kinetics.validation_admission`).
- Run the pre-registered analysis with bottle-level Welch intervals and exact
  permutation floors (`biochar_ad_kinetics.locked_effects`); report the BRL
  horizon-rule defect and a clearly labelled post-hoc deviation.
- Add exploratory kinetics (plateau audit, truncation extrapolation), variance
  components, an evidence-graded generalization failure partition and a
  plant-level Heitkamp pH/VFA envelope.
- Decision: Sanglier is partially admissible; external validation stays blocked.

- Connected the reactor-level intake contract to the kinetic model with
  `biochar-ad fit-stage-a`, preserving physical-reactor identity and source hashes.
- Split Stage A validation into explicit whole-reactor and whole-dose holdouts; the
  latter removes every replicate at the held-out dose together to prevent leakage.
- Refuse silent conversion of non-g/L dose bases in the current kinetic model.
- Reframed the README around the research problem, the current evidence-gated
  solution, and a primary-literature-backed roadmap from batch kinetics to a
  possible future operational digital twin.
- Renamed the public project, Python distribution, import package, README,
  presentation deck and `CITATION.cff` from "Biochar–AD Digital Twin" to
  **Biochar–AD Kinetics** because "digital twin" overstated the current scope.
- Added `docs/MECHANISM_EVIDENCE.md`, a Weak/Moderate/Strong evidence-grading rubric
  (Pilarska 2026) applied to every dataset in the repository, so a good process-level
  fit is never described using stronger mechanistic (e.g. DIET) language than the
  underlying data supports.
- Added the CDU / Wang (2026) pyrolysis-temperature summary table (six biochars,
  400-900 °C) and `biochar-ad benchmark-pyrolysis-temperature`, which reports
  leave-one-biochar-out RMSE for candidate temperature-response forms alongside the
  pairwise collinearity among temperature, BET, conductivity and pH — the CLI flags
  these as confounded rather than attributing a trend to one descriptor.
- Fixed silent data-validation and analysis gaps: a missing `dose_unit` no longer passes
  intake validation, `batch_id` nulls no longer bypass `validate_dataset`, unreplicated
  treatments and non-positive response means are rejected instead of producing NaN/Inf,
  `leave_one_batch_out` fails clearly instead of crashing on exactly two batches, the
  fitted-curves plot no longer silently drops a third temperature group, and the Zhang
  day-10 lookup and Durbin-Watson calculation no longer crash or divide by zero.
- Added parameter-identifiability diagnostics to `fit_global` (`max_parameter_correlation`,
  `parameter_gram_condition_number`), surfaced as a CLI warning when parameters are
  practically confounded.
- Split `leave_one_batch_out` into interior vs. boundary (`is_boundary_condition`) held-out
  error instead of pooling interpolation and extrapolation performance into one mean.
- Made residual-bootstrap uncertainty available on real `fit` runs, not only `demo`
  (`--bootstrap`, opt-in and off by default for `fit`).
- Added 95% confidence intervals (delta method on the log response ratio) and a
  `low_replication` flag to every effect size in `summarize-effects`.
- Reworked the presentation deck to chart the actual committed results (Kozłowski 2025
  kinetic-baseline comparison and the Valentin & Białowiec 2024 dose-response challenge)
  instead of illustrative figures, so the deck argues from data.
- Added an independent dose-response challenge against Valentin & Białowiec (2024): the
  project's log-quadratic dose response is not supported over this external dose range,
  where a simpler log-linear form has lower held-out error.
- Improved repository navigation, contribution guidance and scientific-status reporting.
- Added `docs/ARCHITECTURE.md`, a plain-language map and glossary for readers new to
  biomethane potential (BMP) modelling.
- Consolidated the two presentation decks into a single general-audience overview deck
  (`presentation/index.html`) and removed the meeting-specific Hohenheim deck.
- Added the open Kozłowski et al. (2025) reactor-level kinetic benchmark.
- Added private, hash-verified Zhang et al. (2022) ingestion and summary-analysis workflows.

## 0.1.0 — 2026-08-20

- Released the initial global dose–temperature BMP modelling workflow.
- Added model comparison, batch-aware bootstrap uncertainty and held-out-batch validation.
