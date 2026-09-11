# Predictive adequacy: does a zero-anchored Gompertz forecast a held-out reactor better than the existing modified Gompertz?

## Answer, first

**No, on this dataset it does not, and the hypothesis is rejected.** The zero-anchored Gompertz
challenger's treatment-balanced mean RMSE for days 11-21 (15.71 ml/g VS) is **4.0% higher**
(worse), not the prespecified 10%-or-better improvement, than the existing modified Gompertz
(15.11 ml/g VS). A paired, reactor-level bootstrap interval for the difference is
[+0.49, +0.72] ml/g VS — entirely on the "challenger is worse" side, not merely overlapping
zero. **1 of 7 prespecified decision-rule criteria passed; the hypothesis requires all 7.**
A striking secondary finding, visible directly in `figures/01_observed_vs_predicted_trajectories.png`,
is that **neither Gompertz-family model is actually a good forecaster of this later window**: a
naive local-slope linear extrapolation from the last two training days ("recent_rate") beats
both curve models outright (12.68 ml/g VS), because every held-out reactor keeps producing
methane past day 10 at a rate neither sigmoid curve, once committed to its shape from only 11
training days, predicts. See "Failure-source diagnosis" below.

## Exact scientific question this analysis answers

> For a reactor held out completely, if models are trained using sibling reactors from the same
> treatment only through day 10, which model best predicts the held-out reactor from days 11-21?

This tests **later-trajectory prediction for an unseen reactor under a known treatment**. It does
**not** test unseen-study transfer, unseen-material prediction, dose-response generalization,
causal biochar effects, biological mechanisms, or full-scale reactor forecasting. Every claim
below is scoped to exactly this question.

## Supported conclusions

- The existing modified Gompertz is not beaten by the zero-anchored Gompertz challenger on the
  primary day-10-forecast task, by a decisive margin relative to the prespecified 10% threshold
  (criterion 1: +4.0% change, requires ≤ -10%).
- The paired, reactor-level bootstrap interval for (challenger - reference) RMSE is
  [+0.49, +0.72] ml/g VS at 90% coverage — it excludes "no difference," but in the direction that
  disfavors the challenger, not the direction the hypothesis required (criterion 7 fails because
  the interval must sit *below* zero, not merely exclude it).
- The zero-anchored Gompertz's own structural claims hold: `M(0) == 0.0` exactly for every fold
  (verified by unit test, not just checked post hoc), and 0 monotonicity violations and 0
  negative predictions across all 20 challenger folds (criteria 3-4 pass).
- The zero-anchored Gompertz's `lag` parameter sits at its lower bound (0) in **100% of its 20
  folds** (criterion 5 fails at a 0.5 threshold). This is a real identifiability finding, not
  noise — see "Failure-source diagnosis."
- Excluding the two publisher-flagged reactors (`O+B3`, `O+T2`) from training is scientifically
  justified independently of this experiment's main result: the flagged-reactor stress test
  ablation more than quintuples both models' RMSE (~85 ml/g VS vs ~15 ml/g VS), confirming those
  two reactors really are inconsistent with their siblings (`figures/05_sensitivity_comparison.png`).
- The known-treatment complete-trajectory repeatability check (a *different*, non-forecasting
  design - see below) shows the simple sibling-mean trajectory is the strongest predictor of a
  held-out reactor's *full* curve (4.72 ml/g VS), ahead of every kinetic model. This is expected
  for a low-noise, tightly replicated batch design and is not evidence about the day-10 forecast
  question.

## Interesting but unproven hypotheses

- The recent-rate baseline's win suggests the true late-trajectory shape may be closer to a slow,
  still-rising process at day 10-21 than either Gompertz form assumes, at least for this specific
  21-day window and this specific dataset. This is a hypothesis about *this* batch design, not a
  general claim about anaerobic-digestion kinetics.
- The zero-anchored Gompertz's chronic `lag -> 0` behavior may indicate that, once anchored to
  M(0)=0, the fitted curve no longer needs a nonzero lag to describe an 11-point day-0-10 window -
  i.e., the zero-anchoring constraint may be absorbing what the un-anchored modified Gompertz's
  small nonzero-at-t=0 offset used to represent. This is a plausible mechanism for the observed
  bound-hit pattern, not a proven one; the parameter-profile diagnostics in
  `parameter_diagnostics.csv` and `figures/04_identifiability_diagnostics.png` are consistent
  with it but do not establish it.

## Rejected or weakened claims

- **Rejected:** "The zero-anchored Gompertz predicts a held-out reactor's later trajectory better
  than the modified Gompertz." Directly falsified by the primary result above.
- **Weakened:** "A physically consistent zero-at-origin constraint should improve forecasting."
  The zero-anchored form is *more* physically consistent (M(0)=0 is not just numerically true but
  structurally guaranteed) yet performs statistically indistinguishably-to-slightly-worse than a
  form that does not enforce it. Physical consistency of the functional form did not translate
  into forecasting benefit on this dataset.
- Per the task's own fallback rule: because 2 of 7 sensitivity ablations (`grid_48h`,
  `flagged_reactor_stress_test`) flip the sign of which model wins, while the other 5 favor the
  reference model, model ranking is **not perfectly stable** across sensitivities even though the
  primary, paired, and bootstrap evidence all agree on direction. The honest summary is: **the
  present dataset shows a small, fairly consistent RMSE disadvantage for the zero-anchored
  challenger, but not one stable enough across every design choice to call decisive** - reject the
  hypothesis as stated, but do not treat the ~4% gap as a precisely estimated effect size either.

## Failure-source diagnosis

Three independent pieces of evidence point to the same mechanism, visible directly in
`figures/01_observed_vs_predicted_trajectories.png`:

1. Every held-out reactor's observed trajectory keeps rising measurably from day 10 to day 21 -
   none has clearly plateaued by day 10.
2. Both Gompertz-family curves, fit only on sibling data through day 10, commit to an asymptote
   close to their day-10 value and extrapolate nearly flat afterward.
3. The `recent_rate` baseline, which explicitly extrapolates the sibling mean's recent slope
   instead of assuming saturation, beats both curve models - but only at the primary 10-day
   cutoff. At the day-7 sensitivity cutoff, `recent_rate`'s RMSE explodes to 168.98 ml/g VS
   (`sensitivity_summary.csv`), because a 2-day slope estimated from only 7 days of data
   overshoots badly across a 14-day extrapolation. This shows the "keeps rising" signal is real
   but the naive linear baseline is *not* a robust general solution - it only works because day
   10 happens to be late enough for its local slope to be a reasonable proxy for what days 11-21
   actually look like.

The practical reading: **the failure is a training-window problem, not necessarily a
zero-anchoring problem.** Eleven days of sibling data is short relative to how long these
reactors take to approach their true asymptote, so any model that commits to an asymptote from
that window - anchored at zero or not - underpredicts the continued late rise, while a model that
merely extrapolates the recent trend does better within the range where that trend estimate is
itself stable (cutoff >= 10, per the day-14 sensitivity where `recent_rate` again wins at 5.72
vs. modified Gompertz's 16.47).

## Limitations

- **n = 10 substrate reactors, 4 treatments, 2 treatments with only 2 reactors each
  (`food_waste_pyrolysis_600c`, `food_waste_torrefaction_240c`).** Leave-one-out folds in those
  two treatments train on a single sibling reactor; there is no within-fold replication to average
  out reactor-specific noise for those folds.
- **The whole-pipeline bootstrap is unstable, as prespecified.** Requesting whole-reactor,
  within-treatment resampling with replacement collides badly with n=2 treatments: resampling can
  (and, empirically, does ~75% of the time) draw the *same* original reactor twice for a 2-reactor
  treatment, at which point every remaining "sibling" for a held-out fold in that treatment is
  actually a duplicate of the held-out reactor itself and must be excluded (see "bootstrap
  duplicate copies" below) - collapsing that treatment's fold to zero valid training reactors and
  failing the whole resample. Of 300 requested whole-pipeline bootstrap iterations, only **71
  succeeded** (`bootstrap_summary.csv`, `analysis_metadata.json`); this ratio, not just the
  resulting interval, is itself informative about how thin this dataset's per-treatment
  replication is. The reported bootstrap CIs are conditional on this dataset's specific reactor
  set and should not be read as a general sampling distribution.
- **The reactor-level paired-difference bootstrap** (`paired_reactor_differences.csv`,
  `bootstrap_paired_difference_interval`) is a separate, lighter-weight resampling of
  already-computed fold RMSEs (for inference on n=10 paired differences), distinct from the
  whole-pipeline bootstrap above; it does not refit the modelling pipeline and is reported
  alongside, not merged with, the pipeline-level bootstrap.
- **Robust-loss sensitivity uses one fixed `f_scale` (20.0 ml/g VS) for every model**, chosen as a
  round number near the typical OLS RMSE observed here; it is not independently derived from a
  measurement-error model, and results under it should be read as a robustness check, not a
  preferred alternative estimator.
- **No exact permutation test is reported for treatment allocation**, because the source
  documentation for the Kozłowski et al. (2025) experiment does not establish that treatment
  assignment to reactors was randomized or exchangeable; only paired, reactor-level differences
  and resampling-based intervals are reported, per the task's own instruction.
- **Blank correction is recomputed from raw values inside every fold and every bootstrap
  resample** (never trusted from a precomputed column), but the 3 available inoculum blanks are
  themselves a small sample; the leave-one-blank-out ablation (`blank_leave_K1/K2/K3_out` in
  `sensitivity_summary.csv`) shows the reference-vs-challenger ranking is stable to which blank is
  dropped, but the absolute RMSE level for both models shifts by a few ml/g VS depending on which
  blank is excluded.
- **The known-treatment complete-trajectory repeatability analysis is not forecasting evidence.**
  It is reported separately (`complete_trajectory_repeatability.csv`) specifically so it is never
  read as supporting or refuting the day-10 forecast hypothesis.

## Next external-validation requirement

This entire experiment is a within-study, known-treatment, unseen-*reactor* test. It says nothing
about whether either kinetic form transfers to a new study, a new material, or a new dose - those
remain separately gated by the project's existing Stage A/B/C evidence requirements (see
`docs/PROJECT_STATUS.md` and `docs/STAGE_C_SOURCE_AUDIT.md`). Before any claim about zero-anchored
vs. modified Gompertz forecasting is extended beyond this dataset, it needs replication on at
least one more reactor-level BMP dataset with a comparably dense day-0-21 sampling grid and
multiple reactors per treatment - `docs/STAGE_C_SOURCE_AUDIT.md`'s highest-priority target
(Vayena et al. 2024) is one candidate, contingent on that data actually being reactor-level and
sufficiently sampled in the day 10-21 window, which has not yet been verified (see the "Acquisition
attempt" note already recorded there).

## How to reproduce

```bash
python scripts/run_predictive_adequacy_analysis.py --output results/predictive_adequacy --bootstrap-iterations 300
pytest -q tests/test_predictive_adequacy.py
```

`analysis_metadata.json` records the exact source commit, software versions, random seed, and
effective reactor counts for this run. Every number quoted in this README came from a checked-in
CSV/JSON in this directory - none were hand-typed as arbitrary values.

## Files in this directory

| File | Contents |
| --- | --- |
| `reactor_fold_metrics.csv` | One row per (model, held-out reactor, fitting scope) in the primary day-10 forecast task: RMSE, MAE, bias, day-21 error, early/late bias, increment error, monotonicity/negativity violations. |
| `model_summary.csv` | Treatment-balanced mean RMSE per model, across three scopes: treatment-specific day-10 forecast (primary), treatment-agnostic day-10 forecast (ablation), and complete-trajectory repeatability (separate design). |
| `parameter_diagnostics.csv` | Every nonlinear fit's converged parameters, objective, chosen/attempted starting points, bound hits, Jacobian singular values, condition number, and max parameter correlation. |
| `paired_reactor_differences.csv` | Reactor-level paired (challenger - reference) RMSE difference, one row per held-out reactor. |
| `bootstrap_raw_iterations.csv` / `bootstrap_summary.csv` | Whole-reactor/whole-blank pipeline-refit bootstrap: raw per-iteration results and the summarized median/CI, including the failure count. |
| `sensitivity_summary.csv` | Treatment-balanced mean RMSE per model under every ablation: cutoffs 7/14, hourly/48h grids, each blank left out, the flagged-reactor stress test, and the robust-loss fit. |
| `claim_decisions.csv` | Every one of the 7 prespecified decision-rule criteria, its computed value, threshold, and pass/fail, plus the overall verdict. |
| `complete_trajectory_repeatability.csv` | The separate, non-forecasting known-treatment repeatability check (full-trajectory leave-one-reactor-out), including the sibling-mean-trajectory baseline. |
| `analysis_metadata.json` | Source commit, dataset, population, validation-task definition, cutoffs, seed, exclusion reasons, effective reactor counts, and software versions for this exact run. |
| `figures/` | The 6 required figure sets (trajectories, paired differences, residuals/increment errors, identifiability diagnostics, sensitivities, day-21-observed-vs-fitted-P). |
