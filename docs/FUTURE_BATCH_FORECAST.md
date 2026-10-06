# Frozen forecast workflow for a genuinely new batch

**Current status: ready for registration and new measurements; no prospective
experimental result exists.** The development evidence is the retrospective
[forecast benchmark](FORECAST_BENCHMARK.md). It informed the choices below and
must not be relabelled as unseen validation.

## Fixed v1 question

Can a recent-rate forecast using only the first **12.5 days** predict the
blank-corrected methane yield measured at **day 21**, better than persistence,
on every bottle of one new experimental batch?

The committed specification is
`data/validation/future_batch_forecast_v1.json`. Changing it creates a new
protocol; v1 refuses altered cutoffs, horizons, methods or metrics.

| Item | Frozen choice |
| --- | --- |
| Eligible batch | Collection starts on or after 7 October 2026; novelty and outcome blinding require source review |
| Experimental units | At least four distinct bottles, one laboratory, one batch |
| Time origin | Elapsed days from the same batch start, preserved for every bottle |
| Prefix | At least six readings per bottle, all at or before day 12.5; latest reading at day 12.0–12.5 |
| Endpoint | Exactly one measured day-21 yield per registered bottle; no interpolation or last-record substitution |
| Yield basis | Inoculum-blank-corrected dry mL CH4 at 273.15 K and 101.325 kPa per g substrate VS; gas-standardization and denominator evidence must be independently reviewed |
| Primary method | Recent-rate baseline: OLS slope of the last three prefix readings, negative slope clipped to zero |
| Primary comparator | Persistence: last observed prefix yield |
| Additional comparator | Fixed first-order curve, prefix-only fitting with existing bounds; bound-hit fits retained and labelled |
| Primary score | Mean absolute endpoint error in the declared units, equal weight per bottle |
| Secondary score | Mean absolute relative endpoint error, only if every endpoint is positive |
| Missing/faulted bottle | No silent exclusion; incomplete endpoints block scoring |
| Zero endpoint | Retained in primary score; blocks the entire relative-error summary |
| Statistical scope | Descriptive within one batch; no p-value, population interval or causal claim |

Absolute error is primary because a genuinely new batch can contain a failed,
zero-production bottle. Choosing a relative-error metric and silently dropping
that bottle would make the result look better. Negative corrected yields require
source adjudication under a separate protocol; v1 does not silently clip them.

## Files and sequence

1. Before collecting the new batch, register this specification and the code
   commit in a durable timestamped record. Record the entire planned bottle
   roster and the start/time convention in the source record. The code cannot
   check whether an omitted bottle existed in the experiment.
2. Review units, blank correction, normalization, source identity and the start
   date. Complete `data/templates/forecast_cohort.json`; its booleans default to
   false so the unfilled template cannot pass admission. Declarations are stored
   as declarations and are not promoted to verified facts.
3. At the prefix cutoff, prepare `forecast_prefix.csv` using the matching template.
   It contains only `lab,batch_id,bottle_id,time_days,methane_yield`. Extra columns,
   future readings, missing/nonfinite cells and duplicate bottle/time records
   fail. Prefix values remain intact; baseline negative slopes alone are clipped.
4. Save the predictions with the command below, then publish the prediction
   artifact in the durable record **before** seeing day-21 outcomes. Verify the
   artifact's bottle roster against the original planned roster.
5. Collect a separate `forecast_endpoints.csv` with
   `lab,batch_id,bottle_id,target_day,methane_yield`, keeping all registered bottles.
   Evaluate the saved forecasts. There is no fitting during evaluation.

```bash
python scripts/run_prospective_forecast.py predict \
  --prefix /path/to/forecast_prefix.csv \
  --cohort /path/to/forecast_cohort.json \
  --output /path/to/saved_predictions.json

# Only after the endpoint measurements become available:
python scripts/run_prospective_forecast.py evaluate \
  --predictions /path/to/saved_predictions.json \
  --prefix /path/to/forecast_prefix.csv \
  --endpoints /path/to/forecast_endpoints.csv \
  --output /path/to/endpoint_report.json
```

Output paths must be new: existing prediction and evaluation artifacts are never
overwritten. Keep experimental files private unless their source permission
explicitly allows release. No email or collaborator contact is performed by this
workflow.

## What the safeguards establish

The prediction record binds the frozen specification, cohort declarations,
prefix-file hash, method-file hashes, predictions, fitted first-order parameters
and bound-hit flags. Evaluation checks artifact integrity, the original prefix,
the frozen methods and protocol, exact target day, and complete bottle identity.
It reports primary-minus-comparator error; a negative value favours recent rate.
Missing bottles block evaluation rather than changing the analysed population.

Hashes detect changes relative to saved artifacts. They cannot establish a
publication date, stop someone from resealing a changed record, verify an unseen
outcome declaration, or prove that a historical study was not relabelled. All
reports therefore retain **prospective status unverified**. A real prospective
claim additionally needs independently reviewed source records and evidence that
the protocol and predictions were published before their respective outcomes.

Even after that review, one batch tests forecasting under its own conditions.
It does not demonstrate cross-study prediction, a causal biochar benefit, or a
continuous-reactor digital twin. The cross-study evidence gate stays closed.

## Validation

```bash
pytest -q tests/test_prospective_forecast.py
```

Tests use explicitly synthetic equations only. They exercise protocol changes,
future-read rejection, stale/short prefixes, unknown units, historical starts,
missing/extra bottles, wrong endpoint days, zero endpoints, artifact integrity,
overwrite protection and both CLI stages. No synthetic result is committed as
experimental evidence.
