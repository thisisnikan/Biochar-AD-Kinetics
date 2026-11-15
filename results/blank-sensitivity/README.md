# Blank-correction sensitivity of the Kozłowski (2025) benchmark

**Question.** Do the benchmark conclusions depend on the inoculum-blank correction?
Blank K1 decreases at hours 469 and 484 and ends at 461 mL, against 534 mL (K2) and
543 mL (K3). The [validation plan](../../docs/VALIDATION_PLAN.md) requires a labelled
sensitivity analysis before the correction may be changed.

**Method.** Blank-corrected yields are recomputed from the committed raw trajectories
under five corrections, and the same curve-family comparison and within-study effects
are rerun for each:

| Scenario | Blank correction |
| --- | --- |
| `published_three_blank_mean` | Mean of K1, K2 and K3 (reference; reproduces the committed yields to 5 × 10⁻⁹) |
| `k1_running_maximum` | K1 replaced by its running maximum |
| `exclude_k1`, `exclude_k2`, `exclude_k3` | Mean of the two remaining blanks |

**Result.**

- The curve-family ranking is identical in every scenario and treatment. Modified
  Gompertz keeps the lowest leave-one-reactor-out RMSE throughout.
- Final blank-corrected yields move by at most 1.64% (excluding K1).
- Within-study effects move by at most 1.44 percentage points and none changes sign.
  The largest shift is the torrefaction maximum-rate effect, from −1.59% to −3.03%
  when K1 is excluded.
- Repairing the two decreasing K1 readings changes no reported conclusion.

**Interpretation boundary.** The published three-blank correction remains the
reference. No source value is repaired and no blank is removed from the dataset. The
cause of the K1 behaviour is still unknown and needs the authors; what this analysis
settles is that the benchmark conclusions do not depend on it. Three blanks cannot
estimate blank variability well, so the leave-one-blank-out range is a sensitivity
diagnostic, not a confidence interval.

**Reproduce.**

```bash
python scripts/analyze_kozlowski_blank_sensitivity.py
```

Files: `rankings.csv`, `effects.csv`, `final_yields.csv`, `report.json` (with input hashes).
