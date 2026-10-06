# Do kinetic forecasts beat simple baselines?

This exploratory benchmark compares the five existing kinetic families with two
prefix-only baselines on the same Sanglier long cycles. It adds the missing
comparison to the [kinetic structure audit](EVIDENCE_REQUIREMENTS.md): a good
whole-cycle fit is insufficient, and a forecast needs a simple comparator.

## Result on current committed data

There are 100 eligible long cycles from 27 distinct lab/bottle identities at each
cutoff. Every method is scored on exactly the same cycles. The primary analysis
retains failing controls; the committed summary also reports a sensitivity
excluding IV.2 and IV.3. This structure-audit population is distinct from the
restricted population admitted for the locked treatment-effect analysis.

The score below is **equal-bottle mean absolute relative endpoint error**: first
average cycle errors within each bottle, then average the 27 bottle means.
It describes endpoint prediction, not methane enhancement or biological mechanism.

| Observed prefix | Persistence | Recent-rate baseline | First order | Gompertz | Two pool |
| --- | ---: | ---: | ---: | ---: | ---: |
| 6.5 days | 40.7% | 51.0% | 23.1% | 29.7% | 19.0% |
| 9.5 days | 28.5% | 14.7% | 16.4% | 22.9% | 14.8% |
| 12.5 days | 18.6% | 8.4% | 14.4% | 17.4% | 13.7% |

The two-pool minus recent-rate paired error differences are:

| Prefix | Difference (percentage points) | Conditional bootstrap 95% interval |
| --- | ---: | ---: |
| 6.5 days | −32.0 | −43.3 to −21.2 |
| 9.5 days | +0.2 | −5.4 to +5.2 |
| 12.5 days | +5.3 | +2.5 to +7.3 |

Negative differences favour the kinetic model. These results provide no universal
winner: on these retrospectively selected cycles the recent-rate baseline catches
up as the prefix grows, and outperforms the two-pool model at 12.5 days. All seven
methods, both references, and both populations are retained in `summary.csv`.
No family is selected using full-cycle AICc. No multiple-comparison-adjusted
inference is claimed; the comparisons remain exploratory.

## Protocol and uncertainty

- **Persistence:** hold the last prefix reading constant to the target day.
- **Recent rate:** fit a straight-line slope to the final three prefix readings,
  clip a negative slope to zero, and extrapolate from the last reading. Future
  values do not determine its slope, clipping or starting value.
- **Kinetic models:** reuse the existing structure audit's six-significant-digit
  endpoint errors, fitted only on each prefix. No refitting or outcome-based
  family selection is performed here. Model predictions at parameter bounds are
  retained: two-pool bound-hit fractions are 81%, 96% and 89% across the cutoffs.
  Forecast accuracy does not make those parameters identifiable.
- **Pairing:** every method must have every cycle at a cutoff. Duplicate identities,
  missing comparisons and nonfinite errors fail closed.
- **Uncertainty:** 5,000 seeded bootstrap resamples of whole bottles within labs,
  retaining all repeated cycles. The same draws are used for both sides of each
  comparison. Each bottle has equal weight even if it contributes more cycles.

These intervals are conditional descriptive intervals. Bottles within a batch
may share shocks; that additional dependence is **not** modelled. Neither source
unit uncertainty nor optimizer/model-selection uncertainty is included. Labs are
held fixed and no inference to a population of laboratories is attempted.

## Scientific boundary

The observed final recording time supplies the target horizon, and eligibility
requires a long observed cycle. Both are retrospective design choices. The
analysis cannot establish prospective fixed-horizon accuracy, unseen-bottle
performance, cross-study generalization, a causal biochar benefit, or continuous
reactor control. Unresolved source-unit and intervention conflicts remain in
force. The benchmark does not change any validation admission decision.

The concrete next experiment is to freeze one target horizon, method and cutoff
before acquiring a new batch, then test on whole held-out bottles against both
baselines. A larger model should be justified by that result.

## Reproduce

```bash
python -m pip install -e '.[dev]'
python scripts/benchmark_sanglier_forecasts.py
pytest -q tests/test_forecast_benchmark.py
```

Outputs are `results/forecasting/scores.csv`, `summary.csv` and `report.json`.
The report records SHA-256 hashes of inputs, methods and scored outputs. Tests
verify prefix-only baseline behaviour, equal bottle weights, paired populations,
input failures, deterministic resampling and numerical reproduction of the
committed outputs. The upstream model audit can be independently regenerated
with `scripts/analyze_sanglier_2022_kinetic_structure.py`.
