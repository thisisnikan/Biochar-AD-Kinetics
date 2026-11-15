# Can the Stage A test tell dose-response forms apart?

**Question.** Stage A ranks three candidates (no dose effect, log-linear, log-quadratic)
by mean whole-dose-held-out RMSE. If a known truth generated the data, how often would
that procedure recover it, and with which dose grid?

**Method.** Daily 21-day trajectories are simulated from the package's own model for
four designs, three truths and two levels of between-reactor variability (3%, close to
the Kozłowski replicates; 7%, close to the Sanglier bottle-by-batch component). The
linear and quadratic truths both raise methane potential by 15% at 8 g/L; the quadratic
truth peaks there and returns toward baseline at high dose. Each simulated experiment
is scored by the unmodified `leave_one_dose_out` routine. 24 simulations per cell,
576 in total, fixed seeds.

| Design | Doses (g/L), three reactors each |
| --- | --- |
| `minimum_gate` | 0, 5, 10, 20 |
| `narrow_five_dose` | 0, 2, 4, 6, 8 (grid of Valentin & Białowiec, 2024) |
| `dense_eight_dose` | 0, 5, 10, 15, 20, 25, 30, 40 |
| `wide_six_dose` | 0, 2, 4, 8, 30, 70 |

## Result: how often the true form is selected

Frozen rule (simplest candidate unless a more complex one is more than 10% better):

| Design | Reactor SD | No dose effect | Log-linear | Log-quadratic |
| --- | ---: | ---: | ---: | ---: |
| `minimum_gate` | 3% | 22/24 | 22/24 | 7/24 |
| `minimum_gate` | 7% | 24/24 | 21/24 | 2/24 |
| `narrow_five_dose` | 3% | 24/24 | 22/24 | 12/24 |
| `narrow_five_dose` | 7% | 22/24 | 15/24 | 4/24 |
| `dense_eight_dose` | 3% | 24/24 | 23/24 | 23/24 |
| `dense_eight_dose` | 7% | 24/24 | 22/24 | 4/24 |
| `wide_six_dose` | 3% | 20/24 | 22/24 | 24/24 |
| `wide_six_dose` | 7% | 24/24 | 23/24 | 18/24 |

Plain lowest-RMSE rule, for comparison:

| Design | Reactor SD | No dose effect | Log-linear | Log-quadratic |
| --- | ---: | ---: | ---: | ---: |
| `minimum_gate` | 3% | 22/24 | 22/24 | 8/24 |
| `minimum_gate` | 7% | 22/24 | 20/24 | 4/24 |
| `narrow_five_dose` | 3% | 16/24 | 21/24 | 13/24 |
| `narrow_five_dose` | 7% | 17/24 | 19/24 | 5/24 |
| `dense_eight_dose` | 3% | 20/24 | 22/24 | 23/24 |
| `dense_eight_dose` | 7% | 23/24 | 20/24 | 8/24 |
| `wide_six_dose` | 3% | 17/24 | 22/24 | 24/24 |
| `wide_six_dose` | 7% | 16/24 | 20/24 | 22/24 |

## What this supports

1. **The plain lowest-RMSE rule finds dose effects that are not there.** With no true
   dose effect it selects a dose-response model in up to 8 of 24 simulations. The 10%
   parsimony margin reduces this to at most 4 of 24 and is therefore frozen as the
   Stage A decision rule ([specification](../../data/validation/stage_a_dose_v1.json)).
2. **The minimum Stage A gate cannot detect curvature.** With doses 0, 5, 10 and 20 g/L
   a truly curved response is recovered in 7 of 24 simulations at best.
3. **A narrow grid cannot separate a curved response from a monotone one when the
   optimum lies at the top dose.** On the 0 to 8 g/L grid the curved truth is recovered
   in 12 of 24 simulations at 3% variability and 4 of 24 at 7%. The published challenge
   on that grid therefore shows that log-quadratic curvature is not needed below
   8 g/L; it cannot exclude an optimum at or above 8 g/L.
4. **A high-dose arm is what makes curvature detectable.** The grid reaching 70 g/L
   recovers the curved truth in 24 of 24 and 18 of 24 simulations. Replicate
   variability matters as much as the number of doses: the dense grid to 40 g/L drops
   from 23 of 24 to 4 of 24 when variability rises from 3% to 7%.

## Interpretation boundary

Simulation only. It describes the test, not biochar. The generating model is the
project's own, with one effect size and one curve family per truth, so real data can
behave worse. With 24 simulations per cell a reported share is uncertain by roughly
±10 percentage points, so small differences between cells should not be read.
The parameter-level analysis of the Valentin & Białowiec table is a different procedure
from the trajectory-level test simulated here.

## Reproduce

```bash
python scripts/simulate_stage_a_power.py --simulations 24 --workers 2
```

About 50 minutes on two cores. Files: `simulations.csv` (per-simulation mean RMSE for
every candidate), `recovery.csv` (selection shares for five rules), `report.json`.
