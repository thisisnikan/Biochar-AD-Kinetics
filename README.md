# Biochar–AD Digital Twin

[![CI](https://github.com/thisisnikan/biochar-ad-digital-twin/actions/workflows/ci.yml/badge.svg)](https://github.com/thisisnikan/biochar-ad-digital-twin/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-1B3FC4)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-1B3FC4)](LICENSE)
[![Scientific status: research prototype](https://img.shields.io/badge/status-research%20prototype-B06A22)](docs/PROJECT_STATUS.md)

A reproducible Python workflow for analysing batch biomethane potential (BMP)
experiments with biochar amendment. It fits all dose–temperature conditions
simultaneously, quantifies goodness of fit, and estimates parameter uncertainty
with a batch-aware residual bootstrap.

**New to this project? Start with the map:** [Architecture and glossary](docs/ARCHITECTURE.md)
explains the idea, the repository layout and the code path in plain language.

**Then:** [Scientific status](docs/PROJECT_STATUS.md) ·
[Data contract](docs/DATA_CONTRACT.md) · [Data provenance](data/README.md) ·
[Mechanism-evidence grading](docs/MECHANISM_EVIDENCE.md) ·
[Reproducible results](results/README.md) ·
[Presentation](presentation/README.md) · [Contributing](CONTRIBUTING.md)

## Scope and terminology

This repository names itself a "digital twin" for continuity with the author's
earlier research, but the software is narrower than that term usually implies:
it is a **batch kinetic-modelling and statistical-benchmarking framework**, not
a live, sensor-connected process twin. There is no mass/energy balance (e.g.
ADM1), no reactor hydrodynamics, and no data-assimilation loop against a
running digester. The dose-response term in `model.py` is also **phenomenological,
not mechanistic**: it is a flexible curve shape chosen to be testable against
data, not derived from a specific biological mechanism (e.g. direct
interspecies electron transfer or VFA/ammonia adsorption). Both simplifications
are deliberate for a research prototype, but should not be assumed away when
reading the results.

## Current evidence at a glance

Outcome evidence (methane data that can support or challenge the model) and
metadata-only resources (data about materials or designs, with no methane
outcome) are kept in separate tables so the two are not read as equally strong.

**Outcome evidence:**

| Evidence layer | Dataset | What it supports | What it does not support |
| --- | --- | --- | --- |
| Software demonstration | Labelled synthetic BMP curves | End-to-end fitting, uncertainty and held-out-batch workflow | Scientific validation |
| Reactor-level benchmark | Kozłowski et al. (2025), 12 trajectories | Reproducible kinetic-family comparison | A universal biochar mechanism |
| Author-shared summary analysis | Zhang et al. (2022), treatment means and SDs | Kinetic/VFA analysis with explicit limitations | Replicate-held-out validation or new significance tests |
| Independent dose challenge | Valentin & Białowiec (2024), five fitted-dose endpoints | Falsifies the log-quadratic form as tested | Full reactor-trajectory validation |
| Published pyrolysis-temperature summary | CDU / Wang (2026) thesis, six biochars (400–900 °C) | Descriptive temperature-response check, with pyrolysis temperature/BET/conductivity/pH collinearity reported explicitly | Attributing any trend to one material property, a causal claim, or DIET evidence (see `docs/MECHANISM_EVIDENCE.md`) |

**Metadata-only resources (no methane outcome data):**

| Resource | Dataset | What it supports | What it does not support |
| --- | --- | --- | --- |
| Public design/material tables | García-Prats et al. (2024) | Tests metadata and material-aware structure | Any methane-outcome claim; not usable as evidence for or against the model |

The exact readiness assessment, limitations and next validation gate are maintained in
[`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md).

### Known statistical limitations (checked automatically, not hidden)

- **Parameter identifiability.** `fit_global` reports `max_parameter_correlation`
  and `parameter_gram_condition_number` for the 8-parameter global model. On
  the bundled synthetic demo dataset itself, two parameters are already
  confounded (correlation ≈ 0.96, above the 0.95 flag threshold) — no real
  dataset in this repository varies both dose and temperature with replicates,
  so the full parameter set has never been shown to be identifiable from real
  data. The CLI prints `identifiability_warning` whenever this threshold is
  crossed.
- **Interpolation vs. extrapolation.** `leave_one_batch_out` tags each held-out
  batch `is_boundary_condition`; only boundary rows say anything about
  extrapolation to untested conditions. `biochar-ad fit`/`demo` report
  interior and boundary held-out RMSE separately rather than one pooled mean.
- **Small-n effect sizes.** `summarize-effects` reports a 95% CI on every
  percent-change effect size (delta method on the log response ratio) and
  flags `low_replication` whenever a treatment or control arm has fewer than
  3 reactors, or whenever the underlying source is a published point estimate
  with no reported replicate spread at all (the Valentin & Białowiec table).
  Several of the larger reported percent changes have confidence intervals
  that cross zero.

## Research question and falsifiable hypothesis

**Question.** Does explicitly modelling biochar dose and temperature explain and
predict cumulative methane production better than a condition-agnostic kinetic
baseline?

**Hypothesis.** A shared dose–temperature model will improve held-out-batch
prediction and AICc relative to a three-parameter modified Gompertz curve. The
hypothesis is rejected if that gain disappears on independent experimental data.

This project connects chemical-engineering kinetics, anaerobic digestion and
scientific Python. It was designed by **Nikan Haghighatjue**, building on his MSc
research on biochar characterization for anaerobic digestion.

> **Scientific status:** the included dose-response layer remains an exploratory,
> testable modelling hypothesis. A separate, openly licensed experimental dataset
> is now included for kinetic-baseline benchmarking, but it has one temperature and
> one carbon-material dose. It therefore does **not** validate the global
> dose-temperature hypothesis.

## Why this is useful

Most BMP curves are fitted one at a time. That makes it difficult to compare
operating conditions consistently. This tool uses a shared parameter set and
represents biochar dose and temperature explicitly:

- modified Gompertz methane-production kinetics;
- smooth, non-monotonic biochar dose response;
- Q10 temperature correction for production rate;
- robust global least-squares estimation;
- parameter-identifiability diagnostics (correlation and condition number) reported
  alongside every fit, so a good RMSE is never mistaken for well-separated parameters;
- residual-bootstrap uncertainty that preserves batch structure, available for both
  the demo and real fits (`--bootstrap`);
- comparison of constant-Gompertz, log-linear and log-quadratic dose/temperature
  baselines on identical leave-one-batch-out folds, ranked by mean held-out RMSE
  (with descriptive training AIC, AICc and BIC);
- that held-out comparison also separates interior (interpolation) from boundary
  (extrapolation) error instead of pooling them;
- reproducible CSV, JSON and publication-ready PNG outputs.
- a minimum reactor-time-point data contract with automated intake validation.

## Model

For cumulative methane `M(t)`, the model uses:

```text
M(t) = P · exp{-exp[(e·R/P)(λ - t) + 1]}
```

`P` and `R` vary with `log(1 + dose)`, allowing both enhancement at moderate
dose and inhibition at excessive dose. Temperature changes `R` through a Q10
factor referenced to 37 °C. See `src/biochar_ad_twin/model.py` for the exact,
auditable implementation.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
biochar-ad demo --output outputs --bootstrap 100
```

The command creates:

- `synthetic_bmp_data.csv` — explicitly labelled demonstration data;
- `fit_summary.json` — fitted parameters and diagnostic metrics, including
  `max_parameter_correlation` and `parameter_gram_condition_number`;
- `bootstrap_summary.csv` — uncertainty summary;
- `model_comparison.csv` — baseline comparison and ΔAICc;
- `leave_one_batch_out.csv` — prediction error for every model and held-out batch,
  tagged `is_boundary_condition` to separate interpolation from extrapolation;
- `held_out_model_comparison.csv` — the three candidate models ranked by mean
  held-out RMSE;
- `fitted_curves.png` — observed and fitted profiles.

## Real experimental benchmark

`data/experimental/kozlowski_2025_bmp.csv` contains reactor-level measurements
mechanically derived from the CC BY 4.0 publisher supplement to Kozłowski et al.
(2025), [Scientific Reports 15, 18728](https://doi.org/10.1038/s41598-025-02564-0).
It covers 12 food-waste reactor trajectories over 21 days at 37 °C: no carbon
material, torrefaction product, pyrolysis biochar, and hydrochar. Raw volumes,
blank correction, provenance, inclusion flags, and two source-data quality issues
are documented in `data/README.md`.

Run the experimental comparison with:

```bash
biochar-ad benchmark-experimental --output outputs/experimental
```

The benchmark compares first-order, modified Gompertz, and logistic cumulative
methane models separately within each treatment. The primary selection criterion
is leave-one-reactor-out RMSE. AIC/AICc/BIC are reported only as descriptive
secondary measures because points within a cumulative trajectory are
autocorrelated. The reproducible reference output and cautious interpretation are
stored in `results/experimental/`.

## Independent dose-response challenge

An independent 2024 glucose BMP study provides exact published kinetic
parameters at five wheat-straw-biochar doses (0–8 g/L). Run:

```bash
biochar-ad benchmark-external-dose --output outputs/external-dose
```

The command compares a dose-invariant baseline, a log-linear response, and the
digital twin's log-quadratic response by strict leave-one-dose-out prediction.
On this small external table, log-linear dose response has lower held-out error
for both methane potential and maximum rate. The flexible quadratic hypothesis
is therefore **not supported over this dose range**. This is a parameter-level
challenge, not full trajectory validation: the paper's raw triplicate reactor
time series are available only on request. The published lag estimate also
changes from 0.76 to 0.10 days across doses, exposing a second limitation: the
current digital twin assumes one dose-invariant lag parameter.

## Author-shared summary-data integration

An author-shared Zhang et al. (2022) workbook adds a complementary experiment:
wood-waste biochars produced at 550–950 °C and at 30–120 min residence times,
tested at 10 g/L in 37 °C food-waste batch digestion. It contains consolidated
cumulative methane, pH, and individual VFA means with reported standard
deviations.

The original reactor-level triplicates were lost, and the shared methane curves
are already inoculum-blank corrected. The repository therefore provides a
hash-verified private ingestion script without publishing the workbook or
pretending that summary statistics are independent reactor trajectories. Public
biochar descriptors from the CC BY 4.0 article are included with exact
provenance. See `data/README.md` for the access boundary and rebuild command.

To fit an experimental dataset:

```bash
biochar-ad fit path/to/bmp_data.csv --output outputs --bootstrap 100
```

Required columns are `batch_id`, `time_days`, `dose_g_l`, `temperature_c`, and
`methane_ml_g_vs`. `--bootstrap` defaults to `0` (skipped) for `fit`, unlike
`demo`, because resampling a large real dataset can be slow; pass a positive
iteration count to get the same residual-bootstrap uncertainty on real data.

The full comparison requires at least three batches. At one training temperature,
Q10 is fixed rather than estimated; extrapolation to an unseen temperature from
one training temperature is rejected. Each batch receives equal weight in the
summary. See the [staged validation protocol](docs/VALIDATION_PLAN.md) for split
definitions, model assumptions and independent-data requirements.

## Contribute reactor-level data

The reusable intake contract keeps raw and blank-corrected measurements together,
preserves reactor identity and controls, and attaches QC plus provenance to every
observation. Start from the template and validate it before modelling:

```bash
biochar-ad validate-intake data/templates/reactor_observations.csv
```

Passing this structural gate does not turn a limited design into causal or globally
predictive evidence. Field definitions and warnings are documented in
[`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md).

The [first complete real-data intake](results/intake/README.md) contains all 15
Kozłowski source reactors, including individual inoculum blanks, traceable cell
references, validation findings and an explicit evidence-gap report:

```bash
biochar-ad validate-intake data/experimental/kozlowski_2025_reactor_observations.csv.gz
```

## Presentation

An animated, single-file HTML deck at [`presentation/index.html`](presentation/index.html)
walks through the whole idea end to end: the problem, the research question, the modelling
pipeline, the evidence assembled, an honest status readout, and the roadmap. See the
[presentation guide](presentation/README.md) for controls and editing instructions.

## Quality controls

```bash
ruff check .
pytest -q
```

GitHub Actions runs both checks on Python 3.10 and 3.12.

## Repository map

```text
src/biochar_ad_twin/   installable modelling and reporting package
tests/                 unit and end-to-end workflow tests
data/experimental/     redistributable, provenance-documented inputs
data/templates/        reusable reactor-level contribution contract
scripts/               deterministic ingestion and analysis entry points
results/               reproducible reference outputs and interpretation
presentation/          animated project-overview deck
docs/                  architecture map, project status, scope and validation roadmap
```

For a longer, beginner-friendly walkthrough of what each part does and how a run flows
between them, see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

Private author-shared inputs and their derived private outputs are intentionally excluded
through `.gitignore`; see [`data/README.md`](data/README.md) for the access boundary.

## Responsible use and next validation step

Synthetic data tests software behaviour, not scientific validity. The real-data
benchmark tests kinetic curve families and reproducible data handling, not the
causal effect of biochar. The external table challenges the dose-response form,
but cannot validate complete trajectories. A meaningful next step is access to
independent reactor-level trajectories, followed by a multi-temperature dataset
with replicates, preregistered comparison criteria, residual diagnostics, and
practical parameter-identifiability analysis.

## Interpretation rules

- `delta_aicc = 0` identifies the best-supported candidate within this limited set.
- Held-out error is the primary predictive check; training R² is descriptive only.
- Model selection cannot establish a causal biochar mechanism.
- Independent data and additional mechanistic baselines remain required before
  publication-level claims are appropriate.

## License

MIT
