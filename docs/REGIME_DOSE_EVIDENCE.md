# Loading-regime and dose-basis context gate

**Status (2026-11-16):** implemented as an exploratory, fail-closed *preflight*
on evidence metadata. It does not change existing data, fit a dose response,
admit datasets to Stage A, or conduct leave-one-study-out validation.

## Motivation and scientific source

Jiahui Hu (2024), *Effects of Biochar Application on Anaerobic Digestion
Processes*, University of Kassel doctoral dissertation:
https://www.uni-kassel.de/fb11agrar/index.php?eID=dumpFile&f=5390&t=f&token=1414e6c28dcda15f6e489d6e8f86e98bc9bfbf1f

Hu's experimental comparisons separate inoculum-to-substrate ratios (ISR)
2, 1 and 0.5 and biochar doses 0, 10 and 25% on a substrate volatile-solids
basis. They caution against interpreting changes observed under substantial
substrate/acid stress as an unconditional improvement across AD systems.
In particular, a reported ~5.6% yield increase at ISR 0.5 and p=0.06 is
**not** significant at a conventional 5% threshold; rate/yield/variability
must be distinct endpoints. No Hu experimental series has been imported into
this repository: this is a study-informed audit, not a reproduction of her
experiments or a validation against her data.

## Run

```bash
biochar-ad audit-regime-dose data/templates/regime_dose_context_example.csv \
  --output outputs/regime_dose_context_report.json
```

The **example is synthetic metadata**, not an observed experiment and not
evidence for a biological effect. Data rows are arms/response definitions
rather than independent reactor measurements. For real use, replace every
example/source identifier with a traceable source record.

The result contains:
- `regimes`: one per study, experiment, regime and endpoint, with
  `context_blockers` and `context_documented`;
- `cross_study_pairs`: only different-study, same-response pairs with
  `blocking_reasons`, dose-range overlap and contextual screening status;
- explicit `cross_study_pooling_performed: false` and
  `loso_validated: false` flags.

## Required columns and semantics

| Column | Meaning |
| --- | --- |
| `study_id`, `experiment_id`, `regime_id`, `arm_id` | Stable source-level identifiers; one arm/response row per experimental condition |
| `response` | Endpoint identity; e.g. `final_methane_yield` versus `rate_constant`; mismatched outcomes are not paired |
| `digestion_mode` | Explicit `batch` or `continuous` |
| `is_control` | Explicit boolean; control dose must equal zero |
| `dose_value`, `dose_unit`, `dose_denominator` | Original dose with explicit physical denominator; not silently normalized or converted |
| `isr_vs` | Inoculum VS / substrate VS in batch studies, if source reports it; missing is a blocker |
| `olr_g_vs_l_d`, `hrt_days` | Continuous-reactor operating loading and hydraulic residence time; both required for contextual matching |
| `stress_status`, `stress_evidence` | Source-supported `normal`, `overloaded`, `acid_stressed` or `unknown` and the reason/record; do **not** infer from ISR threshold alone |
| `substrate_id`, `inoculum_id`, `material_id` | Label the actual materials; identifiers are local to study and not proof of common composition across studies |
| `source_record_id` | Traceable location in paper/thesis/instrument record for each arm |

Dose units and accepted denominators are deliberately strict:
- `g_l` → `working_volume_l`;
- `g_g_vs` → `substrate_vs_g`;
- `pct_substrate_vs` → `substrate_vs_g`;
- `pct_ts` → `substrate_ts_g`;
- `mg_reactor` → `per_reactor`;
- `none` → `none` (controls only).

A converted dosage (for example % VS to g/L) must be prepared in a separate
provenance-preserving transformation supported by experimentally reported
substrate VS mass and reactor working volume. This preflight **does not**
perform conversions, and never assumes identical numbers imply identical
material doses. It does not use numerical ISR to label acid stress. Report
`unknown` when source evidence is absent.

## Interpretation, limitations and next validation step

A context-passing pair means *only* that the metadata are sufficiently
explicit and identical in the compared dimensions. It does **not** establish
exchangeability, matched substrate composition, biological replicates,
comparable methane normalization, reactor independence or a causal mechanism.
Different feedstocks/materials are only exposed as descriptive diagnostics.

The gate checks same ISR (batch) or same OLR and HRT (continuous) conservatively:
a small shift is still a flagged mismatch. Dose overlap is computed only in
the identical original unit and denominator, and the overlap fraction uses
the continuous amended-dose ranges. No overlap does not prove that all
cross-study interpretation is impossible; it flags extrapolation and blocks
automatic contextual admission. A passing comparison can still contain
unobserved covariate shift.

**No existing datasets are reclassified as admissible by adding this tool.**
The next research task is to curate regime/stress provenance for the existing
datasets, without inventing absent ISR, dose denominator, gas-normalization
or VFA/alkalinity measurements. Then intersect these diagnostics with the
existing minimum-information check and the independent effect credibility
and generalization readiness gates in `docs/EVIDENCE_REQUIREMENTS.md` and
`docs/GENERALIZATION_READINESS.md`. Only then can cross-study testing begin.
