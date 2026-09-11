# Cross-study generalization readiness

## Scientific purpose

The project should not fit a pooled or machine-learning model across studies merely because rows can be concatenated. Before any leave-one-study-out (LOSO) validation is interpreted, the evidence must be sufficient for an honest out-of-study experiment.

`biochar_ad_kinetics.generalization` therefore implements a conservative readiness audit. It does **not** estimate a universal biochar effect and does **not** assert that studies are exchangeable.

## Minimum gate

For each response, LOSO modelling is blocked unless all of the following are true:

1. At least three independent studies are represented.
2. Every effect row has an uncertainty estimate.
3. Every effect row is based on replicate-level evidence.
4. Every effect row has been explicitly admitted for cross-study pooling.

These conditions are deliberately stricter than what is required to fit a numerical model. They are intended to prevent a statistically neat result from being mistaken for biological generalization.

## Domain-shift diagnostics

The audit also records pairwise differences between studies:

- overlap of observed biochar-dose ranges;
- number of exactly shared doses;
- whether studies share a material label;
- whether studies share an operating temperature.

These are diagnostics, not proof of comparability. A model can pass the minimum evidence gate and still face severe extrapolation across materials, temperature, substrate, inoculum, or other unmeasured conditions.

## Interpretation

`ready_for_loso = False` means the project should remain at the level of within-study effects, independent parameter-table checks, or explicitly exploratory hypotheses.

`ready_for_loso = True` means only that a LOSO experiment is scientifically permissible as the next test. It does not mean the pooled relationship is valid, causal, or publishable.

A future LOSO analysis should report each held-out study separately, compare against simple study-naive baselines, and treat failure to generalize as a scientifically useful result rather than an implementation defect.
