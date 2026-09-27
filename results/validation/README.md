# Validation admission outputs

Everything here is regenerated deterministically from committed files. Run from the
repository root, in order:

```bash
python scripts/audit_sanglier_2022_semantics.py       # semantics, events, adjudication
python scripts/run_sanglier_2022_admission.py         # outcome-blind admission + leakage
python scripts/run_sanglier_2022_locked_evaluation.py # refuses to run if the spec changed
python scripts/analyze_heitkamp_2021_envelope.py      # plant-level process envelope
```

| File | Content |
| --- | --- |
| `sanglier_2022_variable_dictionary.csv` | Meaning, unit status and permitted use per variable |
| `sanglier_2022_event_scope.csv` | Scope each source event's text supports |
| `sanglier_2022_treatment_adjudication.csv` | One row per bottle/batch: source values, class, rules, evidence |
| `sanglier_2022_semantics_qc.json` | FAN derivation, TS/VS basis, sCOD scale, dose basis, yield identity |
| `sanglier_2022_admission.csv` / `_report.json` | Admission per cycle, windows, horizon, spec SHA-256, leakage audit |
| `sanglier_2022_locked_effects.csv` | Primary, sensitivity and post-hoc (unlocked) contrasts |
| `sanglier_2022_bottle_summaries.csv` | One value per bottle, the inferential unit |
| `sanglier_2022_variance_components.csv` | Batch, arm, bottle and residual shares |
| `sanglier_2022_cycle_kinetics.csv` | Exploratory per-cycle plateau and Gompertz diagnostics |
| `sanglier_2022_truncation_extrapolation.csv` | Early-fit prediction of longer cycles |
| `sanglier_2022_generalization_failure_partition.csv` | Evidence status per failure mode |
| `sanglier_2022_locked_evaluation.json` | Verdicts, deviations, units, comparator context |
| `heitkamp_2021_plant_envelope.csv` / `_report.json` | Plant-level pH/VFA/NH4-N envelope and blocked comparisons |

None of these files is an external validation result. See
[the decision record](../../docs/SANGLIER_2022_VALIDATION_ADMISSION.md).
