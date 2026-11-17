# Dose-experiment design outputs (simulation only)

Regenerate: `python scripts/run_dose_design.py`. Protocol:
`data/validation/dose_design_v1.json`. Write-up: `docs/DOSE_DESIGN.md`.

| File | Content |
| --- | --- |
| `scenarios.csv` | Share correct for every design, effect size, replicate variability and truth |
| `designs.csv` | Worst-case share correct and largest false-curvature rate per design |
| `maximin.csv` | Best design per budget, effect size and replicate variability |
| `agreement.csv` | Surrogate against the trajectory-level simulation for four designs |
| `report.json` | Search size, smallest budget reaching 0.80, input hashes |

No experimental data are used.
