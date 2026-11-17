# Calibrated early stopping outputs

Regenerate: `python scripts/run_early_stopping.py`. Protocol:
`data/validation/early_stopping_v1.json`. Write-up: `docs/EARLY_STOPPING.md`.

| File | Content |
| --- | --- |
| `pairs.csv` | One row per cycle and whole-day cutoff: forecasts, projected gain, scores |
| `stops.csv` | Per validation fold, rule and cycle: stop day, whether fired, error, coverage |
| `summary.csv` | Bottle-weighted coverage, accuracy and days saved per scheme, population and rule |
| `report.json` | Pre-registered criteria with pass or fail, and input SHA-256 hashes |

Retrospective and within one study; not prospective validation.
