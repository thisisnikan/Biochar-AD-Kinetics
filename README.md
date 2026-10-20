# Biochar–AD Kinetics

[![CI](https://github.com/thisisnikan/Biochar-AD-Kinetics/actions/workflows/ci.yml/badge.svg)](https://github.com/thisisnikan/Biochar-AD-Kinetics/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-1B3FC4)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-1B3FC4)](LICENSE)
[![Scientific status: research prototype](https://img.shields.io/badge/status-research%20prototype-B06A22)](docs/PROJECT_STATUS.md)

Reproducible kinetic modelling and evidence audits for biochar-amended anaerobic
digestion (AD). The toolkit analyses batch biomethane potential (BMP) experiments —
kinetic-model comparison, parameter uncertainty and leakage-safe validation — and
records, for every dataset, what the evidence can and cannot support.

> **Scientific status: research prototype.** The demonstration dataset is synthetic
> and labelled as such. The dose-response term is a falsifiable, phenomenological
> hypothesis rather than a biological mechanism, and it is not supported on the one
> independent dose challenge available so far. No dataset in the repository yet meets
> the minimum information required for cross-study prediction, and the software is not
> an operational digital twin. See [Project status](docs/PROJECT_STATUS.md).

**Contents:** [Motivation](#motivation) · [Current evidence](#current-evidence) ·
[Latest results](#latest-results) · [Quick start](#quick-start) ·
[Command reference](#command-reference) · [Using your own data](#using-your-own-data) ·
[Data access and privacy](#data-access-and-privacy) ·
[Repository layout](#repository-layout) · [Documentation](#documentation) ·
[Citation](#citation)

## Motivation

Biochar-assisted anaerobic digestion has a translation problem, not only a
curve-fitting problem:

- Experimental evidence is fragmented across substrates, inocula, temperatures,
  biochar feedstocks, production conditions, doses and reporting conventions. Raw reactor
  trajectories, blanks and material descriptors are often unavailable or incompatible.
- A high score on pooled literature data can overstate generalisation. In a 623-condition,
  107-study analysis, random-forest R² fell from 0.683 under conventional validation to
  0.36 when entire studies were held out, exposing substantial study-to-study heterogeneity
  ([Huaraca et al., 2026](https://doi.org/10.1016/j.biortech.2026.135652)).
- Methane improvement alone cannot establish a mechanism. Conductivity, surface area, pH,
  pyrolysis temperature and feedstock can change together, so correlations must not be
  presented as proof of direct interspecies electron transfer or adsorption.
- A fitted batch curve is not a digital twin. Operational use would additionally require
  a dynamic process model, continuous-reactor data, sensors, state estimation, online
  calibration, uncertainty bounds and prospective plant validation.

### Approach

| Problem | Repository response | Evidence gate |
| --- | --- | --- |
| Incompatible or incomplete reactor data | A provenance-aware intake contract preserves reactor identity, blanks, controls, units, QC and raw/processed values | `validate-intake` must pass; source-level review is still required |
| One curve fit per treatment gives inconsistent comparisons | Shared kinetic candidates are evaluated on identical data and folds | Held-out error is primary; AIC/AICc/BIC are descriptive |
| Replicates can leak into an allegedly unseen dose | Reactor and dose generalisation are tested separately | `fit-stage-a` removes every sibling reactor at the held-out dose |
| Flexible models can look convincing while parameters remain confounded | Every global fit reports parameter correlation and the Gram-matrix condition number | A low-error but non-identifiable fit does not pass the scientific gate |
| Positive results are easier to publish than negative ones | Independent challenges and failed hypotheses remain visible | The log-quadratic dose response is reported as unsupported on the current external challenge |
| Process response can be mistaken for mechanism | Each dataset receives an explicit mechanism-evidence grade | Mechanistic language cannot exceed the measurements that support it |

**Current boundary.** This repository is a batch kinetic-modelling and statistical-
benchmarking framework. Its dose-response term is phenomenological: a falsifiable curve
shape, not a biological mechanism. It has no ADM1 mass balance, reactor hydrodynamics,
sensor connection or live data-assimilation loop. The staged long-term direction, and the
evidence each stage requires, is described in the [Roadmap](docs/ROADMAP.md).

## Current evidence

Outcome evidence (methane data that can support or challenge the model) and context
resources (material, design or process-chemistry data with no usable methane outcome) are
kept in separate tables so that the two are not read as equally strong.

**Outcome evidence**

| Evidence layer | Dataset | What it supports | What it does not support |
| --- | --- | --- | --- |
| Software demonstration | Labelled synthetic BMP curves | End-to-end fitting, uncertainty and held-out-batch workflow | Scientific validation |
| Reactor-level benchmark | Kozłowski et al. (2025), 12 trajectories | Reproducible kinetic-family comparison | A universal biochar mechanism |
| Author-shared summary analysis | Zhang et al. (2022), treatment means and SDs | Kinetic/VFA analysis with explicit limitations | Replicate-held-out validation or new significance tests |
| Independent dose challenge | Valentin & Białowiec (2024), five fitted-dose endpoints | Falsifies the log-quadratic form as tested | Full reactor-trajectory validation |
| Published pyrolysis-temperature summary | CDU / Wang (2026) thesis, six biochars (400–900 °C) | Descriptive temperature-response check, with pyrolysis temperature/BET/conductivity/pH collinearity reported explicitly | Attributing any trend to one material property, a causal claim, or DIET evidence (see [mechanism grading](docs/MECHANISM_EVIDENCE.md)) |
| Author-shared summary (private) | García-Prats, González & Sánchez (2024) workbook, 119 methane mean/SD observations | Descriptive within-feeding summary analysis once timing is reconciled ([intake record](docs/GARCIA_PRATS_2024_SUMMARY_INTAKE.md)) | Raw-reactor validation, public reproduction or redistribution |
| Author-shared unpublished summary (private) | García-Prats et al., CYPRUS2025 extended abstract | Nine-biochar feedstock × pyrolysis-temperature dose-response dataset for private model testing | Public reproduction, peer review status, independent validation |
| Quarantined long-term candidate | Sanglier et al. (2022), Data INRAE | Within-study, pre-registered contrasts ([admission decision](docs/SANGLIER_2022_VALIDATION_ADMISSION.md)) | External validation of any model in this repository |

**Context resources (no usable methane outcome data)**

| Resource | Dataset | What it supports | What it does not support |
| --- | --- | --- | --- |
| Public design/material tables | García-Prats et al. (2024) | Tests metadata and material-aware structure | Any methane-outcome claim on their own |
| Industrial chemistry monitoring | Heitkamp et al. (2021), seven plants | Plant-level pH/VFA context ([intake record](docs/HEITKAMP_2021_INGESTION_GATE.md)) | Methane-outcome or causal claims |

**Literature context (not usable as data)**

| Evidence layer | Source | What it supports | What it does not support |
| --- | --- | --- | --- |
| Literature synthesis | Chiappero et al. (2022) meta-analysis | Motivates the non-monotonic dose-response form and gives a literature-derived optimal property range and dose-cost heuristic | Reactor-level validation; it is aggregated meta-analysis output, not primary data |

The readiness assessment, limitations and next validation gate are maintained in
[`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md).

### Known statistical limitations

These are checked automatically and reported in every relevant output.

- **Parameter identifiability.** `fit_global` reports `max_parameter_correlation`
  and `parameter_gram_condition_number` for the 8-parameter global model. On the
  bundled synthetic dataset, two parameters are already confounded (correlation ≈ 0.96,
  above the 0.95 flag threshold). No real dataset in this repository varies both dose
  and temperature with replicates, so the full parameter set has not been shown to be
  identifiable from real data. The CLI prints `identifiability_warning` whenever the
  threshold is crossed.
- **Interpolation vs. extrapolation.** `leave_one_batch_out` tags each held-out batch
  `is_boundary_condition`; only boundary rows inform extrapolation to untested
  conditions. `fit` and `demo` report interior and boundary held-out RMSE separately.
- **Small-n effect sizes.** `summarize-effects` reports a 95% CI on every
  percent-change effect size (delta method on the log response ratio) and flags
  `low_replication` when a treatment or control arm has fewer than three reactors, or
  when the source is a published point estimate without replicate spread (the
  Valentin & Białowiec table). Several of the larger percent changes have confidence
  intervals that cross zero.

## Latest results

Each item links to its reproducible record. The dated history is in the
[changelog](CHANGELOG.md).

- **Forecasting benchmark.** Seven methods are compared on identical long Sanglier cycles
  with equal bottle weights and paired uncertainty. With 12.5 days observed, a simple
  recent-rate baseline has 8.4% mean absolute relative endpoint error versus 13.7% for the
  two-pool kinetic model. This is an exploratory within-study result
  ([benchmark](docs/FORECAST_BENCHMARK.md)).
- **Frozen forecast protocol.** A fixed day-21 workflow saves day-12.5 prefix predictions
  before endpoints are read, preserves the registered bottle roster and scores every
  bottle against frozen baselines. It awaits genuinely new measurements and independent
  verification of pre-outcome registration ([protocol](docs/FUTURE_BATCH_FORECAST.md)).
- **Effect-credibility audit.** Shared-control covariance and whole-reactor deletion
  sensitivity are now reported. One kinetic contrast changes point-estimate direction
  under deletion, and both responses remain blocked for cross-study generalization
  ([audit](results/effect-credibility/README.md)).
- **Sanglier admission decision.** A frozen specification, outcome-blind admission and a
  leakage audit conclude that the Sanglier (2022) dataset is only partially admissible
  and cannot externally validate any model here
  ([decision record](docs/SANGLIER_2022_VALIDATION_ADMISSION.md)).
- **Evidence requirements.** No dataset in the repository meets the minimum information
  for cross-study prediction. The [requirements](docs/EVIDENCE_REQUIREMENTS.md) state what
  to measure, and `biochar-ad check-evidence` grades a data package against them.
- **Quarantined data candidates.** Sanglier chemistry (923 samples and eight operating
  events linked to 8,403 methane records through 363 bottle/batch identities) and
  Heitkamp industrial chemistry (1,365 measurements, seven plants, 91 sampling occasions,
  15 variables) are source-verified but are not training replicates or completed external
  validation ([research update](docs/RESEARCH_EVIDENCE_2026_09.md),
  [data registry](docs/DATA_EXPANSION_REGISTRY.md)).

## Research question and hypothesis

**Question.** Does explicitly modelling biochar dose and temperature explain and predict
cumulative methane production better than a condition-agnostic kinetic baseline?

**Hypothesis.** A shared dose–temperature model will improve held-out-batch prediction and
AICc relative to a three-parameter modified Gompertz curve. The hypothesis is rejected if
that gain disappears on independent experimental data.

The included dose-response layer remains an exploratory, testable hypothesis. The openly
licensed reactor-level benchmark has one temperature and one carbon-material dose per
treatment, so it does **not** validate the global dose–temperature hypothesis.

## Model

For cumulative methane `M(t)`, the global model uses a modified Gompertz curve:

```text
M(t) = P · exp{-exp[(e·R/P)(λ - t) + 1]}
```

`P` and `R` vary with `log(1 + dose)`, allowing enhancement at moderate dose and inhibition
at excessive dose. Temperature changes `R` through a Q10 factor referenced to 37 °C; at a
single training temperature Q10 is fixed rather than estimated. Parameters are estimated
by robust global least squares, with residual-bootstrap uncertainty that preserves batch
structure. Constant-Gompertz, log-linear and log-quadratic dose/temperature candidates are
compared on identical leave-one-batch-out folds and ranked by mean held-out RMSE. See
[`src/biochar_ad_kinetics/model.py`](src/biochar_ad_kinetics/model.py) for the exact
implementation and [`docs/VALIDATION_PLAN.md`](docs/VALIDATION_PLAN.md) for split
definitions and assumptions.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
biochar-ad demo --output outputs --bootstrap 100
```

The demo writes, to `outputs/`:

| File | Content |
| --- | --- |
| `synthetic_bmp_data.csv` | Explicitly labelled synthetic demonstration data |
| `fit_summary.json` | Fitted parameters and diagnostics, including identifiability metrics |
| `bootstrap_summary.csv` | Parameter-uncertainty summary |
| `model_comparison.csv` | Baseline comparison and ΔAICc (descriptive) |
| `leave_one_batch_out.csv` | Held-out error for every model and batch, tagged `is_boundary_condition` |
| `held_out_model_comparison.csv` | Candidate models ranked by mean held-out RMSE |
| `fitted_curves.png` | Observed and fitted profiles |

## Command reference

All functionality is available through one console command, `biochar-ad`. Run
`biochar-ad <command> --help` for arguments and defaults.

| Command | Purpose | Reference output |
| --- | --- | --- |
| `demo` | Generate labelled synthetic data and run the full workflow | `results/synthetic/` |
| `fit` | Fit the global dose–temperature model to a BMP CSV | — |
| `benchmark-experimental` | Compare first-order, modified Gompertz and logistic curves by leave-one-reactor-out RMSE | `results/experimental/` |
| `benchmark-external-dose` | Challenge dose-response forms by leave-one-dose-out prediction on published parameters | `results/external-dose/` |
| `summarize-effects` | Within-study effect sizes relative to controls, with 95% CIs | `results/effects/` |
| `benchmark-pyrolysis-temperature` | Descriptive pyrolysis-temperature response check with descriptor collinearity | `results/pyrolysis-temperature/` |
| `validate-intake` | Validate a reactor-level contribution against the data contract | `results/intake/` |
| `fit-stage-a` | Fit one ready dose series with separate whole-reactor and whole-dose holdouts | — |
| `check-evidence` | Grade a data package against the minimum information for cross-study prediction | — |

### Reproducing the reference results

- **Reactor-level benchmark.** `data/experimental/kozlowski_2025_bmp.csv` is mechanically
  derived from the CC BY 4.0 supplement to Kozłowski et al. (2025),
  [Scientific Reports 15, 18728](https://doi.org/10.1038/s41598-025-02564-0): 12 food-waste
  reactor trajectories over 21 days at 37 °C (no carbon material, torrefaction product,
  pyrolysis biochar, hydrochar). `biochar-ad benchmark-experimental` ranks curve families
  within each treatment by leave-one-reactor-out RMSE; information criteria are secondary
  because points within a cumulative trajectory are autocorrelated.
- **Independent dose challenge.** Valentin & Białowiec (2024) report modified-Gompertz
  parameters at five wheat-straw-biochar doses (0–8 g/L). Under strict leave-one-dose-out
  prediction (`biochar-ad benchmark-external-dose`), a log-linear response has lower
  held-out error than the project's log-quadratic form for both methane potential and
  maximum rate, so the quadratic form is **not supported over this dose range**. Published
  lag estimates also change from 0.76 to 0.10 days across doses, which the current
  dose-invariant lag assumption does not capture. This is a parameter-level challenge; the
  raw triplicate time series are available from the authors on request only.
- **Author-shared summary data.** The Zhang et al. (2022) workbook contains treatment
  means and SDs (original triplicates were lost; methane curves are already blank
  corrected). A hash-verified private ingestion script analyses it without publishing the
  workbook or treating summaries as reactor trajectories.

Provenance, licences, hashes and data-quality decisions for every dataset are documented
in [`data/README.md`](data/README.md); interpretation of each reference output is in
[`results/README.md`](results/README.md).

## Using your own data

**Fit a BMP dataset.** Required columns are `batch_id`, `time_days`, `dose_g_l`,
`temperature_c` and `methane_ml_g_vs`:

```bash
biochar-ad fit path/to/bmp_data.csv --output outputs --bootstrap 100
```

The full comparison needs at least three batches. `--bootstrap` defaults to `0` for
`fit` because resampling large datasets is slow. Extrapolation to an unseen temperature
from a single training temperature is rejected.

**Contribute reactor-level data.** The [data contract](docs/DATA_CONTRACT.md) keeps raw and
blank-corrected measurements together, preserves reactor identity and controls, and
attaches QC and provenance to every observation. Start from the template and validate
before modelling:

```bash
biochar-ad validate-intake data/templates/reactor_observations.csv
biochar-ad fit-stage-a path/to/reactor_observations.csv --output outputs/stage-a
biochar-ad check-evidence path/to/reactor_observations.csv
```

`fit-stage-a` writes separate `leave_one_reactor_out.csv` and `leave_one_dose_out.csv`
results; the whole-dose split removes every replicate at the held-out dose and is the
primary Stage A prediction test. It refuses silent conversion from `%TS`, `g/g VS` or
other dose bases to g/L. Passing these structural gates does not turn a limited design
into causal or globally predictive evidence. A complete worked example — all 15
Kozłowski source reactors, including individual inoculum blanks — is in
[`results/intake/`](results/intake/README.md).

To propose a dataset, open a [data-contribution issue](.github/ISSUE_TEMPLATE/data_contribution.yml)
before writing an ingestion script.

## Data access and privacy

Only openly licensed or redistributable data are committed. Author-shared files
(Zhang et al., 2022; García-Prats et al., 2024; the CYPRUS2025 extended abstract) are
processed by public, hash-verified scripts, but the source files and anything derived
directly from them stay in the git-ignored `data/private/` and `results/private/`
directories. No pseudo-replicates are generated from summary statistics. The exact
boundary is documented in [`data/README.md`](data/README.md) and
[`SECURITY.md`](SECURITY.md).

## Repository layout

```text
src/biochar_ad_kinetics/   installable package: models, validation, audits and CLI
tests/                     unit and end-to-end tests
data/                      provenance-documented datasets, templates, specifications and manifests
scripts/                   deterministic ingestion and analysis entry points
results/                   reproducible reference outputs with interpretation
docs/                      methods, project status, decision records and roadmap
presentation/              single-file project-overview slide deck
```

[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) explains each part and how a run flows
between them, in plain language and with a glossary.

## Documentation

- [Documentation index](docs/README.md) — every document, grouped by purpose
- [Architecture and glossary](docs/ARCHITECTURE.md) · [Project status](docs/PROJECT_STATUS.md) ·
  [Roadmap](docs/ROADMAP.md)
- [Data contract](docs/DATA_CONTRACT.md) · [Validation plan](docs/VALIDATION_PLAN.md) ·
  [Evidence requirements](docs/EVIDENCE_REQUIREMENTS.md) ·
  [Mechanism-evidence grading](docs/MECHANISM_EVIDENCE.md)
- [Presentation](presentation/README.md) — an animated single-file deck built from the
  committed results

## Interpretation rules

- Held-out error is the primary predictive check; training R² is descriptive only.
- `delta_aicc = 0` identifies the best-supported candidate within a limited set; it is
  descriptive, not a validation.
- Model selection cannot establish a causal biochar mechanism.
- Biochar effects can be positive, neutral or negative depending on inoculum, substrate,
  loading, material properties, dose, temperature and operating conditions.
- Independent data and additional mechanistic baselines remain required before
  publication-level claims are appropriate.

## Development

```bash
ruff check .
pytest -q
```

GitHub Actions runs both checks on Python 3.10 and 3.12. Contribution rules are in
[`CONTRIBUTING.md`](CONTRIBUTING.md) and the change history in [`CHANGELOG.md`](CHANGELOG.md).

## Citation

If this software supports your work, please cite it using the metadata in
[`CITATION.cff`](CITATION.cff) and cite the original articles for any dataset you use.

Developed by Nikan Haghighatjue, building on MSc research on biochar characterization
for anaerobic digestion.

## License

[MIT](LICENSE). Bundled third-party datasets keep their original licences, as recorded in
[`data/README.md`](data/README.md).
