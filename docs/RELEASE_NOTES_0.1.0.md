# Release notes: 0.1.0 (draft, not yet published)

Status: prepared on 15 November 2026. Publication needs the owner's explicit
approval and the remaining steps in [RELEASING.md](RELEASING.md). No tag, GitHub
release or DOI exists yet.

## What this release is

The first citable research-prototype release of Biochar–AD Kinetics: a Python package
and command-line tool for reproducible kinetic modelling of batch biomethane potential
(BMP) experiments with biochar, together with the audited datasets, reference results
and decision records in this repository.

## What it shows

1. Modified Gompertz has the lowest leave-one-reactor-out RMSE in all four treatments
   of the Kozłowski et al. (2025) benchmark (10 benchmark-eligible reactors of 12;
   the ranking is unchanged when the two source-excluded reactors are included).
2. The project's log-quadratic dose-response form is not supported on the independent
   Valentin & Białowiec (2024) table: a log-linear form has lower leave-one-dose-out
   error for methane potential (11.1% against 31.6%) and for maximum rate.
3. With 12.5 days observed, a recent-rate baseline forecasts end-of-cycle methane with
   8.4% mean absolute relative error against 13.7% for the best kinetic model
   (Sanglier et al., 2022; 100 long cycles from 27 bottles; exploratory).

## What it does not show

- Retrospective batch benchmarks only. No prospective experimental result,
  cross-study validation or operational digital twin is established.
- No committed dataset meets the 12 critical information items for cross-study
  prediction (best: 6). The cross-study admission gate stays closed.
- Sanglier (2022) is only partially admissible and validates no model here. Its
  unit-metadata limitation is unresolved: pH is the only resolved unit, TS/VS bases
  and one sCOD occasion conflict, and methane unit suffixes are asserted by the
  builder rather than by the source.
- Author-shared workbooks (Zhang et al., 2022; García-Prats et al., 2024; the
  CYPRUS2025 abstract) are not part of the archive. Only their public,
  hash-verified ingestion scripts are.
- The MIT licence covers the code. Bundled third-party datasets keep their original
  licences, recorded in [`data/README.md`](../data/README.md).

## Verification record

Rebuilt and retested on 16 November 2026 from `main` at `b35ad1e` plus the
release-candidate branch. Full record: [reproduction audit](REPRODUCTION_AUDIT_2026_11.md).

| Check | Result |
| --- | --- |
| `ruff check .` | passed |
| `python -m build` | wheel and sdist built; no author-shared source file in either |
| Wheel installed outside the checkout, `import` and `biochar-ad --help` | passed |
| Full suite, Python 3.10.20, pandas 2.3.3, numpy 2.2.6, scipy 1.15.3 (wheel) | 300 passed |
| Full suite, Python 3.12, pandas 3.0.6, numpy 2.5.4, scipy 1.18.1 (wheel) | 300 passed |
| Full suite, Python 3.13.18, pandas 3.1.1, numpy 2.5.5, scipy 1.18.1 (editable) | 300 passed |
| Curve-family, dose-response, forecasting and blank-sensitivity outputs | byte-identical to the committed files |

Known reproducibility limits, described in the audit: the Sanglier prefix-fit audit is
not bit-reproducible across machines (the forecasting conclusion is unchanged), effect
tables agree to about nine significant digits, and the benchmark commands need a
repository checkout because the datasets are not packaged.

The exact release commit and the CI run for it are to be added here when the tag is
created.

## Remaining steps before publication

1. Owner approval to publish.
2. If a DOI is wanted: enable this repository in Zenodo before the GitHub release
   is published.
3. Final commit setting the publication date in `CITATION.cff` and `CHANGELOG.md`.
4. Tag that commit `v0.1.0` and publish the GitHub release with these notes.
5. After Zenodo issues the DOI, add it to `CITATION.cff` in a follow-up commit.
