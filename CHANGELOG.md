# Changelog

All notable project changes are documented here. The project follows a research-prototype
release model while the public API remains experimental. Entries are listed newest first.

## Unreleased

### 2026-10-20: Repository presentation

- Rewrote the README as a concise landing page: scientific-status notice first, an evidence
  overview, a neutral "Latest results" section, a command reference and a documentation
  index. Dated announcements moved to this changelog.
- Moved the staged long-term vision to `docs/ROADMAP.md` and added `docs/README.md`, an
  index of every document grouped by purpose.
- Replaced informal first-name references to a data contributor with formal citations.
- Added argument help text and a descriptive summary to `biochar-ad --help`.
- Reordered this changelog so the newest entries come first.

### 2026-10-07: Lint fixes

- Fixed ruff findings: reformatted a minified script, removed a lambda assignment and
  relocated a misplaced import.

### 2026-10-06: Forecast benchmark and frozen forecast protocol

- Benchmarked kinetic endpoint forecasts against paired prefix-only baselines on identical
  long Sanglier cycles with equal bottle weights and paired uncertainty. With 12.5 days
  observed, the recent-rate baseline has 8.4% mean absolute relative endpoint error versus
  13.7% for the two-pool model; this is an exploratory within-study result
  (`docs/FORECAST_BENCHMARK.md`).
- Froze a day-21 forecast protocol that saves day-12.5 prefix predictions before endpoints
  are read, preserves the registered bottle roster and separates predictions from outcome
  evaluation (`docs/FUTURE_BATCH_FORECAST.md`). It awaits genuinely new measurements.

### 2026-10-02: Effect-credibility audit

- Audited effect credibility with strict admission, shared-control covariance and
  whole-reactor deletion sensitivity. One kinetic contrast changes point-estimate direction
  under deletion; both responses remain blocked for cross-study generalization
  (`results/effect-credibility/`).

### 2026-09-27: Research expansion and author-shared summary workbook

- Linked 923 Sanglier chemistry samples and eight operating events to the existing 8,403
  methane records through 363 bottle/batch identities.
- Ingested 1,365 chemistry measurements from seven Heitkamp industrial plants (91 sampling
  occasions, 15 variables) as a quarantined candidate.
- Screened seven source records with DOI, access status, inspection depth and next
  acquisition gate (`docs/RESEARCH_EVIDENCE_2026_09.md`).
- Added a private, hash-verified importer for the author-shared García-Prats, González and
  Sánchez (2024) Frontiers workbook: 119 methane mean/SD observations linked to the public
  material/dose design, with feeding periods separated and the second feeding's time-origin
  discrepancy flagged. Source data and generated tables remain private.

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

### 2026-09-25: Sanglier methane candidate

- Ingested the Sanglier et al. (2022) methane data as a quarantined candidate with source QC.

### 2026-09-10 to 2026-09-11: Generalization gate, Cai and continuous-data candidates

- Added a cross-study generalization readiness audit; missing pooling or replicate evidence
  flags are rejected instead of silently passing.
- Registered the Cai BMP candidate records with an explicit admission boundary.
- Added the Daskaloudis (2026) continuous-reactor builder and transition sensitivity analysis.

### 2026-09-05: Batch-holdout comparison and Kozłowski intake

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

### 2026-09-03: Reactor-level data contract

- Added a minimum experimental record for reactor-level Biochar–AD contributions.
- Added `biochar-ad validate-intake` with machine-readable errors and scientific-limit warnings.
- Added a worked CSV template and tests for duplicate keys, changing reactor metadata and missing blanks.

### Other changes since 0.1.0 (not individually dated)

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
