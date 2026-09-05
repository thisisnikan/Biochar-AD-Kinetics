# Changelog

## 2026-09-03

- Added a minimum experimental record for reactor-level Biochar–AD contributions.
- Added `biochar-ad validate-intake` with machine-readable errors and scientific-limit warnings.
- Added a worked CSV template and tests for duplicate keys, changing reactor metadata and missing blanks.

All notable project changes are documented here. The project follows a research-prototype
release model while the public API remains experimental.

## Unreleased

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
  digital twin's log-quadratic dose response is not supported over this external dose range,
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
