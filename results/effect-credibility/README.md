# Effect credibility audit

This audit adds three falsifiable safeguards to the existing effect analysis:
strict evidence admission, shared-control dependence and reactor influence.
It adds no independent experiment and performs no pooled modelling.

## Reproduce

From the repository root, after `pip install -e ".[dev]"`:

```bash
python scripts/audit_effect_credibility.py
```

The script uses only the two public CSVs already committed in
`data/experimental`: Kozlowski reactor trajectories and Valentin & Bialowiec
published parameters. It re-fits the current modified Gompertz per reactor,
regenerates 14 stratified effects and records input, method and output SHA-256
hashes plus package versions in `audit_report.json`. Numeric results can vary
slightly between solver/library versions; the recorded environment identifies
the generation run. No private or quarantined source is promoted into training.

## Findings on the existing inputs

| Diagnostic | Result | Interpretation |
| --- | --- | --- |
| Evidence count | 14 effect rows, two studies; uncertainty available for six rows | Neither response passes the cross-study gate |
| Conditional shared-control correlation | 0.864–0.992 between distinct same-response Kozlowski effects | Effect rows within a study are highly dependent; six rows are not six independent experiments |
| Reactor influence | 32 deletion cases across six contrasts | Five contrasts keep their point-estimate direction; one changes sign |
| Torrefaction maximum rate | Original −1.59%; deletion range −2.74% to +0.46% | Direction depends on reactor inclusion; this is not a stable directional finding |
| Generalization gate | Both responses blocked | Fewer than three study IDs, missing uncertainty, summary-level evidence and no pooling admission |

These are conditional sensitivity results, **not** external validation,
confidence intervals, significance tests or evidence of causality. Keeping a
point-estimate direction under deletion does not establish a nonzero effect.
Some deletion cases leave a single treatment reactor and are marked
`unreplicated_remainder`; their point estimates are descriptive only.

## Dependence calculation

For effect `ln(mean(T_i)/mean(C))`, its delta-method variance is
`SD(T_i)^2/(n_i*mean(T_i)^2) + SD(C)^2/(n_C*mean(C)^2)`.
For distinct disjoint treatment groups sharing the *same actual* control
sample, the covariance is the latter control term. The diagonal reproduces
the existing effect standard errors squared. This implements the shared-control
case in [Lajeunesse (2011), Ecology 92:2049–2055](https://doi.org/10.1890/11-0423.1).
The upper triangle is exported; mirror off-diagonal entries to construct a
symmetric within-study/response matrix. Separate responses are separate blocks;
this output does not claim zero cross-response covariance.

Preconditions: control labels identify the same actual group, treatment arms
are disjoint and reactors are independent. The same blank correction can create
additional dependence between arms. That correction uncertainty, kinetic-fit
uncertainty, paired/repeated-bottle structure and cross-response covariance are
**not** estimated here. Kozlowski's blank decreases and control-dose source
conflicts remain unresolved; the covariance diagnostic does not resolve them.
The published parameter table has no per-arm SD; its covariance stays missing.

## Admission hardening

Native booleans and explicit CSV strings `True`/`False` are interpreted by value.
Missing or ambiguous flags, including numeric `0`/`1`, are rejected. A single
study returns an explicit blocker instead of crashing. Infinite/negative doses
are rejected; non-finite effect estimates and non-positive/missing standard
errors block readiness. A zero SE is not accepted as credible sampling
uncertainty under this conservative gate. Unique study IDs are a software count;
independence of experiments still requires a source audit.

## Next scientific requirement

Resolve the source conflicts and acquire an independent, replicated Stage A
dose design with raw reactor trajectories and correction inputs. Freeze the
prediction and QC protocol before inspecting its outcomes. A new equation or
more rows from the same study cannot substitute for this evidence.

## Files

- `within_study_effects.csv`: regenerated stratified point estimates and existing CIs.
- `shared_control_covariance.csv`: conditional covariance blocks, missing where unavailable.
- `leave_one_reactor_out.csv`: every deletion, its arm and reactor identity.
- `reactor_influence_summary.csv`: deletion ranges and sign changes by contrast.
- `generalization_readiness.csv`: explicit current evidence blockers.
- `audit_report.json`: hashes, environment, summary and limitations.
