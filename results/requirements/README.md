# Evidence requirement outputs

Regenerate from the repository root:

```bash
python scripts/analyze_sanglier_2022_kinetic_structure.py
python scripts/analyze_design_requirements.py
python scripts/score_dataset_requirements.py
```

| File | Content |
| --- | --- |
| `sanglier_2022_structure_by_cycle.csv` | Per cycle, family and cut: whole-cycle fit and end-of-cycle extrapolation error |
| `sanglier_2022_structure_summary.csv` | Medians by population, family and cut |
| `sanglier_2022_cycle_length_requirement.csv` | Days until the daily increment falls below 1% and 2% |
| `sanglier_2022_structure_report.json` | Headline structure and cycle-length findings |
| `design_variance_components.csv` | Bottle, residual and batch variance per scenario |
| `design_power_table.csv` | Standard error, interval width, power and permutation floor by design |
| `design_requirements.json` | Bottles per arm for 5%, 10% and 20% effects |
| `dataset_scorecard.csv` / `dataset_item_matrix.csv` | Minimum-information status per dataset |
| `scorecard_report.json` | Automatic cross-check results and headline counts |

These are exploratory, planning outputs. See [the requirements](../../docs/EVIDENCE_REQUIREMENTS.md).
