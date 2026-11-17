# User guide

This guide is for someone who wants to use the project: reproduce its results, run it on
their own batch data, or plan an experiment with it. For terms (BMP, Gompertz, inoculum
blank) see [Architecture and glossary](ARCHITECTURE.md). For what is and is not
established, see [Project status](PROJECT_STATUS.md).

## 1. What the project does

It answers bounded questions about biochar-amended anaerobic digestion with one rule:
**a model is judged by its error on reactors, doses or time points it has not seen.**
Each dataset is used only for the question its design supports.

| Question | Dataset | Answer so far | Document |
| --- | --- | --- | --- |
| Which curve best predicts an unseen replicate reactor? | Kozłowski et al. (2025) | Modified Gompertz, all four treatments | [README](../README.md) |
| Does a curved dose response predict an unseen dose? | Valentin and Białowiec (2024) | No; log-linear wins on doses up to 8 g/L | [Technical report](report/report.pdf) |
| Do kinetic models beat simple extrapolation for forecasting? | Sanglier et al. (2022) | Only early in the cycle | [Forecast benchmark](FORECAST_BENCHMARK.md) |
| Can a test be stopped early with a checked error bound? | Sanglier et al. (2022) | Within one laboratory, yes; between laboratories, not yet | [Early stopping](EARLY_STOPPING.md) |
| Which dose experiment could detect an optimum? | Simulation | 6 log-spaced doses to 100 g/L, 4 replicates, low replicate variability | [Dose design](DOSE_DESIGN.md) |

## 2. Install

Python 3.10 or later.

```bash
git clone https://github.com/thisisnikan/Biochar-AD-Kinetics
cd Biochar-AD-Kinetics
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
ruff check . && pytest -q
```

Run commands from the repository folder: the datasets are not packaged with the wheel,
because each keeps its own licence.

## 3. Reproduce every result

| Result | Command | Output folder |
| --- | --- | --- |
| Curve-family benchmark | `biochar-ad benchmark-experimental --output results/experimental` | `results/experimental/` |
| Dose-response challenge | `biochar-ad benchmark-external-dose --output results/external-dose` | `results/external-dose/` |
| Blank-correction sensitivity | `python scripts/analyze_kozlowski_blank_sensitivity.py` | `results/blank-sensitivity/` |
| Within-study effects | `biochar-ad summarize-effects --output results/effects` | `results/effects/` |
| Forecasting benchmark | `python scripts/benchmark_sanglier_forecasts.py` | `results/forecasting/` |
| Early stopping | `python scripts/run_early_stopping.py` | `results/early-stopping/` |
| Dose design search | `python scripts/run_dose_design.py` | `results/dose-design/` |
| Report figures | `python scripts/make_report_figures.py` and `python scripts/make_research_figures.py` | `docs/report/figures/`, `docs/figures/` |

Compare with the committed files using `git diff --stat results/`. The
[reproduction audit](REPRODUCTION_AUDIT_2026_11.md) lists which outputs match byte for byte
and which differ slightly between machines, and why.

## 4. Use your own batch data

**Step 1: put the data in the reactor format.** Copy
`data/templates/reactor_observations.csv`. One row is one reading from one reactor at one
time. Never enter a treatment mean as if it were a reactor. Required fields and rules:
[Data contract](DATA_CONTRACT.md).

**Step 2: check it.**

```bash
biochar-ad validate-intake my_reactors.csv
```

Errors (exit status 2) make the file unsafe to model: duplicate readings, missing units,
negative times. Warnings mark limits, such as no inoculum blank or unreplicated
treatments.

**Step 3: fit and validate a dose series.**

```bash
biochar-ad fit-stage-a my_reactors.csv --output outputs/stage-a
```

This writes two separate tests: leave one reactor out (can the model predict a replicate?)
and leave one dose out (can it predict a dose it has not seen, with every replicate at that
dose removed?). The frozen decision rule in `data/validation/stage_a_dose_v1.json` keeps
the simplest model unless a more complex one lowers held-out error by more than 10%.

**Step 4: grade the evidence.**

```bash
biochar-ad check-evidence my_reactors.csv
biochar-ad audit-regime-dose my_context.csv
```

These report which minimum-information items are missing (biochar properties, inoculum to
substrate ratio, dose basis) before any cross-study comparison is attempted.

## 5. Decide when to stop a running test

The calibrated rule from [Early stopping](EARLY_STOPPING.md), in Python:

```python
import math
from biochar_ad_kinetics.forecast_benchmark import prefix_baselines

def stop_now(time_days, cumulative, planned_end_day, quantile=0.696, tolerance=1.10):
    """True when the 90% interval for the end yield is within the tolerance factor."""
    f = prefix_baselines(time_days, cumulative, time_days[-1], planned_end_day)
    projected_gain = math.log(f["recent_rate"] / f["persistence"])
    return quantile * max(projected_gain, 0.01) <= math.log(tolerance), f["recent_rate"]
```

The quantile 0.696 was calibrated on the Sanglier repeated-batch cycles and **did not
transfer between its two laboratories**. Before relying on it, recalibrate on at least
20 completed bottles from your own laboratory with `calibrate()` in
`biochar_ad_kinetics.early_stopping`, and keep running the 1%-for-3-days check alongside.

## 6. Plan a dose experiment

Read [Dose design](DOSE_DESIGN.md) first. In short: spend reactors on the dose range and on
replicates rather than on many dose levels; space doses evenly in ln(1 + dose); include a
high-dose arm; and reduce replicate variability. To check your own planned grid, run
`share_selected()` from `biochar_ad_kinetics.dose_design` with your doses, replicates and an
honest estimate of replicate variability.

## 7. Evidence rules that apply to everything

- Report held-out error first; R² and information criteria are secondary.
- Never split a reactor between fitting and testing; never let a replicate of a held-out
  dose into the fit.
- Freeze the question, the data selection and the decision rule in a committed file before
  computing the outcome. Changing them creates a new protocol with a new identifier.
- Report negative results and failed criteria in the same place as positive ones.
- No mechanism claims (for example direct interspecies electron transfer) without the
  measurements listed in [Mechanism evidence](MECHANISM_EVIDENCE.md).
- Different datasets answer different questions; do not pool their accuracies.

## 8. Where things are

| Path | Content |
| --- | --- |
| `src/biochar_ad_kinetics/` | The package: kinetic models, baselines, validation splits, audits |
| `scripts/` | One script per analysis; each writes to `results/` |
| `data/experimental/` | Derived public datasets with provenance in `data/README.md` |
| `data/validation/` | Frozen protocols (JSON), each committed before its analysis |
| `results/` | Committed outputs, with hashes of their inputs |
| `docs/` | Methods, decisions, audits, this guide |
| `tests/` | Automated tests, run by continuous integration on every change |
