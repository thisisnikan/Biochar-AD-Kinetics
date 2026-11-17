# Independent reproduction audit, 16 November 2026

Scope: `main` at commit `b35ad1e`. Every command below was executed from a clean clone
on Linux x86-64. Outputs were written to a scratch directory and compared with the
committed files. No committed result file was changed by this audit.

## Environments

| Environment | Install | Test result |
| --- | --- | --- |
| Python 3.13.18, pandas 3.1.1, numpy 2.5.5, scipy 1.18.1, matplotlib 3.11.2 | editable | `ruff check .` passed; 300 tests passed |
| Python 3.12, pandas 3.0.6, numpy 2.5.4, scipy 1.18.1, matplotlib 3.11.2 | built wheel | 300 tests passed |
| Python 3.10.20, pandas 2.3.3, numpy 2.2.6, scipy 1.15.3, matplotlib 3.10.9 | built wheel | 300 tests passed |

`python -m build` produced the wheel and the source distribution. Neither contains a
spreadsheet, PDF or other author-shared source file.

## Central claims

| Claim | Command | Committed output | Result |
| --- | --- | --- | --- |
| Modified Gompertz has the lowest leave-one-reactor-out RMSE in all four Kozłowski treatments | `biochar-ad benchmark-experimental` | `results/experimental/` | Byte-identical |
| Log-linear dose response beats log-quadratic on the Valentin & Białowiec table (11.1% against 31.6% for methane potential) | `biochar-ad benchmark-external-dose` | `results/external-dose/` | Byte-identical |
| Recent-rate baseline 8.4% against 13.7% (two-pool) at 12.5 days | `python scripts/benchmark_sanglier_forecasts.py` | `results/forecasting/` | `scores.csv` and `summary.csv` byte-identical from the committed inputs |
| Curve ranking is insensitive to the blank correction | `python scripts/analyze_kozlowski_blank_sensitivity.py` | `results/blank-sensitivity/` | Byte-identical |
| Summary figure | `python scripts/make_summary_figure.py` | `docs/figures/key_findings.png` | Byte-identical before the caption correction below |

Input hashes recorded in `results/forecasting/report.json` match the committed inputs.

## Findings

### 1. Reactor count in the headline (corrected)

The README, the release notes and the summary figure described the curve-family
benchmark as using 12 reactors. The dataset holds 12 substrate trajectories, but the
benchmark uses 10: torrefaction replicate 2 (no methane recorded) and pyrolysis
replicate 3 are marked `included_in_benchmark = false`, following the source workbook
(`data/README.md`). The three texts now say 10 of 12.

Sensitivity check, run for this audit: with all 12 reactors included, modified Gompertz
still ranks first in every treatment, but the margins collapse where a failed reactor
dominates the error (pyrolysis 37.8 against 38.1 for logistic; torrefaction 236.65
against 236.68 mL CH4 per g VS). The ranking claim survives; the size of the advantage
depends on the exclusion.

### 2. The Sanglier kinetic audit is not bit-reproducible across machines

`scripts/analyze_sanglier_2022_kinetic_structure.py` produces the prefix-fitted kinetic
forecasts that the forecasting benchmark reuses. Regenerated here, in both the Python
3.12 and the Python 3.13 environment, the output differs from the committed
`results/requirements/sanglier_2022_structure_by_cycle.csv`:

- 53 of 1,500 fit rows differ in `final_relative_error`. The median difference is
  1 × 10⁻⁷ and the largest is 0.24, in fits that stop at a parameter bound.
- The two regenerated environments agree with each other exactly, so the difference
  comes from the machine (linear-algebra backend), not from the Python version.
- Rerunning the forecasting benchmark from the regenerated file changes one headline
  value at the reported precision: two-pool error at 6.5 days, 19.0% to 18.9%. At
  12.5 days the two-pool error stays 13.7% and the paired difference against the
  recent-rate baseline stays +5.3 points with interval 2.5 to 7.3.

This is a property of the models, not a coding error: bounded multi-start least
squares on short prefixes has several near-equivalent solutions, and 81% to 96% of
two-pool fits end at a bound. The committed files remain the reference. The forecasting
conclusion is stable under this variation; individual prefix fits are not, and should
not be interpreted.

### 3. Effect tables reproduce to about nine significant digits

`biochar-ad summarize-effects` and `scripts/audit_effect_credibility.py` reproduce the
committed Kozłowski values to a relative difference near 10⁻⁹, not byte for byte,
because the files store full double precision from an iterative fit. Every reported
effect and interval is unchanged at the reported precision.

### 4. Benchmark commands need a repository checkout

The wheel installs and imports outside the checkout, and `biochar-ad --help` works.
The benchmark commands read `data/` by relative path, and the datasets are deliberately
not packaged because they keep their own licences. Run them from a clone.

## What is a limitation, not a defect

| Item | Type | Can it be fixed without new data? |
| --- | --- | --- |
| Reactor count wording | Reporting | Yes, corrected |
| Cross-machine variation of weakly identified prefix fits | Numerical, documented | Only by changing the frozen analysis; not done |
| Two or three reactors per treatment; no interval on RMSE differences | Scientific | No |
| Five published dose points, no replicate spread, doses up to 8 g/L only | Scientific | No |
| Sanglier units, intervention metadata and retrospective horizons | Scientific | No, needs the data authors |
| No dataset with at least three doses, replicates and blanks (Stage A) | Scientific | No |
