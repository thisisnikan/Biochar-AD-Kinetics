# Sanglier 2022: external-validation admission decision

Decision date: 27 September 2026. Spec: [`data/validation/sanglier_2022_validation_spec.json`](../data/validation/sanglier_2022_validation_spec.json)
(`sanglier_2022_admission_v1`, frozen in commit `940cf49` before any outcome contrast).

## Decision

**Partially admissible.** Sanglier et al. (2022) is **not** admitted as an external
validation dataset for any model in this repository. A defined subset (18 bottles,
166 bottle/batch cycles, two laboratories) is admitted for one pre-registered,
within-study descriptive question. All other uses stay quarantined.

| Use | Status | Reason (evidence below) |
| --- | --- | --- |
| Locked external validation of kinetic, dose-response, global or Daskaloudis models | Blocked | No commensurate transferable prediction; dose basis differs; no material descriptors; development evidence gives no sign for early yield |
| Calibration or transfer learning | Prohibited by spec | Would require refitting on the target study |
| Model updating | Prohibited by spec | Same |
| Pre-registered descriptive effect estimate (question A, within study) | Admitted for the subset | Bottle-level units, fixed horizon, co-interventions excluded |
| Machine learning or hybrid residual models | Prohibited | 18 admitted bottles, one biochar material, zero committed descriptors |
| Causal biochar claims, industrial or continuous translation | Prohibited | Not supported by design or data |

## Order of work (audit trail)

1. `scripts/audit_sanglier_2022_semantics.py` reads only committed intake tables and
   writes the variable dictionary, event scope table, treatment adjudication and
   semantic QC. No treatment contrast is computed.
2. The spec was written and frozen. `scripts/run_sanglier_2022_admission.py`
   applies it without methane volume, flow or yield columns (the admission function
   raises if one is passed), runs the leakage audit and records the spec SHA-256.
3. Commit `940cf49` was pushed before step 4.
4. `scripts/run_sanglier_2022_locked_evaluation.py` refuses to run unless the spec
   hash matches the admission report and the development comparator matches its
   frozen hash.

Disclosure recorded in the spec: before freezing, final per-cycle yields of LBE
bottles IV.1, IV.2, IV.3, IV.5 and IV.8 were viewed to check event statements. The
source deposit itself states that biochar improved yield. Agreement in direction is
therefore not a blind test.

## 1. Variable semantics

`results/validation/sanglier_2022_variable_dictionary.csv`. Units are never guessed.

| Variable | Unit status | Evidence and permitted use |
| --- | --- | --- |
| pH | resolved (dimensionless) | Only variable comparable across sources |
| TAN, C2 to C6, IC4 to IC6 | unresolved | Headers carry no unit; molar, mass and COD bases all remain possible |
| FAN | unresolved; derived | FAN/TAN varies with pH (CV 53%), but FAN divided by an equilibrium free-ammonia transform of TAN and pH has CV 1.3% (31 BRL rows). FAN is a calculated quantity and must not be used as an independent feature |
| TS, VS | unresolved; basis conflict | BRL VS exceeds TS in all 10 rows (TS 5.7 to 10.9, VS 70 to 81); LBE values are 0.02 to 0.10. Bases differ between laboratories |
| sCOD | unresolved; scale discontinuity | BRL batch 13 final samples (8 rows) are 1,100 to 2,000 against 13 to 100 elsewhere |
| Methane volume, flow | builder-asserted, unverified | Source headers `Volume_raw`, `Volume`, `Flow` have no units; the `_nml` suffix in the candidate table is not backed by committed evidence |
| Methane yield | relation verified, unit unverified | `Methane yield = Volume / VS Substrate` holds in 8,055 of 8,055 rows (max residual 1.2e-7) |

Additional findings: only LBE applies a raw-to-corrected volume factor (1.001 to
1.090); BRL corrected equals raw. The correction method is undocumented, so
absolute yields are not comparable between laboratories. The log response ratio
used below is unaffected because it is computed within a laboratory from one column.

## 2. Intervention reconstruction

Event scope (`sanglier_2022_event_scope.csv`) is classified from each event's own text.
An event assigns bottle exposure only when it names bottles or a condition.

| Intervention | What the repository can establish | What it cannot |
| --- | --- | --- |
| Biochar | Bottle-level regime from batch 1. LBE batch-1 grams equal 0.99% and 1.97% of recorded reactor mass, matching the deposit's 1%/2% w:w. Later batches add top-up grams at a constant 2:1 ratio | BRL w:w basis (no BRL reactor mass is recorded; 4 g and 8 g initial). Purpose of top-ups. Material descriptors |
| Ammonium bicarbonate | Inoculation records 3.11 g for **all 12 BRL bottles** at batch 11, then 0.15 to 0.42 g only for MBE[2] + N | Events!3 says one condition only. The two sources conflict for 9 bottles; no BRL TAN measurement after batch 10 can adjudicate |
| Trace elements | LBE switches IV.1 to IV.9 to Celtics solution from batch 11 and gives IV.10 to IV.15 water (Events!4 and TE volumes agree). BRL is "High" throughout | Meaning of the LBE `+` label before batch 11: no recorded metadata differs from the unmarked arm |
| Reduced mixing | Days 106 to 128 in LBE | Which bottles; cycles 9 and 10 are ambiguous for every LBE bottle |
| Undocumented addition | LBE control IV.2 receives 4.26 g ammonium bicarbonate at batch 12 | Any event explaining it |
| Technical faults | IV.5 and IV.8 flagged "should be removed" at batch 1 | Whether the fault persisted |
| Failures | IV.3 and IV.2 (controls) stop producing | These are outcomes, never exclusion criteria |

Carry-over: digestate is partly recirculated, so any exposure or fault in one cycle
can persist. The adjudication propagates conflicts to later cycles of the same bottle.

## 3. Treatment adjudication

`sanglier_2022_treatment_adjudication.csv` holds one row per bottle/batch (348 cycles
with methane), the original labels, grams and volumes, the rules that fired and the
evidence text. No source value is changed.

| Class | Cycles | Main rules |
| --- | ---: | --- |
| source_consistent | 151 | none |
| resolvable_from_source | 71 | R3 `+ N` label explained by ammonium grams and Events!3; R5 TE label vs water; R6 BRL `+` pre-ammonia; R9 LBE TE change |
| ambiguous | 102 | R6 LBE `+` meaning (90); R8 mixing overlap (45); R10 residual ammonia carry-over |
| conflicting | 13 | R1 II.4 control label with 0.51 to 0.64 g biochar (batches 2 to 5); R4 ammonium grams outside the named condition |
| excluded | 11 | R2 II.4 carry-over after conflict; R7 source technical exclusion |

## 4. Admission gate and leakage audit

Admission (`sanglier_2022_admission.csv`, `sanglier_2022_admission_report.json`):

- Clean windows end before the first laboratory-scope confounder: BRL batches 1 to
  10 (ammonium at 11), LBE batches 1 to 8 (mixing event from 9).
- A bottle is admitted only if every window cycle is admissible, because carry-over
  propagates exposure. II.4, IV.5 and IV.8 are excluded; LBE `+` arms are excluded
  from the primary analysis as ambiguous.
- Admitted: BRL MBE[0] (II.5, II.6), MBE[1] (3), MBE[2] (3), MBE[2]+ (3); LBE [0]
  (IV.1 to IV.3), [1] (IV.4, IV.6), [2] (IV.7, IV.9).

Leakage audit: 34 files (33 at freeze; the statistics module added afterwards also passes) under every development path (package source, effect tables,
kinetic benchmark, external dose table, synthetic results, pyrolysis table,
experimental data, templates, outputs) contain no Sanglier DOI, name or source hash.
Any hit stops the admission script. The only development comparator used
(Kozłowski 2025 effect rows) is pinned by SHA-256. Material-level leakage cannot be
excluded because the Sanglier biochar is not characterised in the repository.

## 5. Results (Level A, pre-registered)

Target: cumulative methane yield at a fixed within-batch horizon; unit of analysis:
bottle (mean of ln yield over window batches); Welch 95% interval; exact permutation.
File: `sanglier_2022_locked_effects.csv`.

**Locked primary.** LBE [1] +33% (95% CI -39% to +191%), LBE [2] +36% (-38% to
+198%): inconclusive, Welch df about 2, permutation p = 0.30. BRL is **not evaluable**:
the frozen horizon rule floored the shortest last-observed time (5.51 d) to 5.5 d,
but BRL batch 6 has no 5.5 d observation, so every BRL bottle lost a window batch.
This is a defect in the spec and is reported, not repaired silently.

**Post-hoc deviation D1 (not locked).** The corrected rule (largest 0.5 d multiple
observed in every admitted cycle) gives 5.0 d. BRL MBE[1] +10% (5% to 15%),
MBE[2] +14% (9% to 19%), MBE[2]+ +15% (8% to 22%); LBE unchanged (inconclusive).

**Sensitivity.** Removing failed control IV.3 moves LBE to [1] +11% (4% to 18%) and
[2] +13% (7% to 20%). Including the LBE `+` arms gives +32% and +37%, matching the
unmarked arms. Using LBE batches 2 to 8 with IV.5 and IV.8 restored gives +35% and
+41%, still inconclusive.

Interpretation:

- Point estimates are positive in every arm of both laboratories, and the two
  healthy-control analyses agree on roughly +10% to +15%. That is consistent with the
  source authors' claim, but it rests on a post-hoc horizon and on excluding one
  failed control, and it is not a blind test.
- The LBE interval is wide because one of three controls (IV.3) collapsed from batch
  5 onward (yield falls to 11% of the biochar median by batch 8). Whether that
  failure is a biochar-preventable acidification or a random bottle failure cannot
  be separated with one failure among three controls.
- The design cannot produce strong inferential evidence: with 2 or 3 bottles per arm
  the smallest attainable exact two-sided p-value is 0.10 to 0.33 for every contrast.
- Ammonium-free MBE[2]+ behaves like MBE[2] before batch 11 (+15% vs +14%), which
  supports the adjudication that the label had no recorded effect before ammonia.

Development comparator (context only, marked non-commensurate): Kozłowski 2025
pyrolysis biochar reports +4.5% (0.1% to 9.0%) in fitted potential and -7.4% in
maximum rate. The D1 BRL intervals lie above the potential interval; this is not
scored as agreement or failure because the targets differ.

## 6. Levels B to D

**Level B, kinetics (exploratory, within study).** 1.2% of admitted cycles meet the
1%/day stop criterion; the median last-day increment is 8% of cumulative yield.
Modified Gompertz fitted to the first 6.5 d of the 14 admitted cycles that run
longer (LBE batches 1 and 3) under-predicts their final yield by a median 42%, while
the nominal Jacobian standard error of the potential is only 2.4% on full cycles.
The asymptote is not identified by 7-day cycles, and the nominal SE is overconfident.
17% of per-cycle fits hit a parameter bound; median |corr(potential, rate)| is 0.66.

**Level C, variance structure.** On ln yield at 5.0 d (balanced design, per lab):

| Component | BRL | LBE |
| --- | ---: | ---: |
| Batch (shared across bottles) | 64% | 38% |
| Arm | 15% | 12% |
| Bottle within arm | 1% | 15% |
| Bottle-by-batch residual | 20% | 35% |

Observations are not IID. Any model for this study needs at least a batch effect and
a bottle effect; treating 2,928 time rows or 166 cycles as independent would overstate
information by orders of magnitude.

**Level D, ML.** Not defensible: 18 bottles, 7 arms, 2 laboratories, 1 material, 0
descriptors.

## 7. Three generalization questions

| Question | What Sanglier can answer now |
| --- | --- |
| A. Within study | Partly. Descriptive arm contrasts inside each laboratory, with the limits above |
| A'. Cross-laboratory inside one study | Direction of point estimates agrees; interval verdicts do not (BRL increase under D1, LBE inconclusive). Not question B: same study, protocol family and authors |
| B. Cross-study | Not answerable. No locked, commensurate prediction exists to test |
| C. Batch to continuous or industrial | Not answerable. Repeated batch with recirculation; Heitkamp has no productivity data |

## 8. Heitkamp use

`scripts/analyze_heitkamp_2021_envelope.py` summarises seven plants with the plant as
the unit. Industrial pH plant medians lie between 7.69 and 8.35. BRL samples fall
inside that band 85% of the time, LBE samples 45% (LBE includes acidifying bottles).
TVFA falls below acetic acid alone on 9 of 88 plant-days (BGP3, BGP4), so TVFA is not
a sum on one basis. All other cross-source comparisons are blocked by unresolved
Sanglier units. Heitkamp is not used for methane validation or causal claims.

## 9. Why generalization is not established

`sanglier_2022_generalization_failure_partition.csv`:

| Failure mode | Status |
| --- | --- |
| Biological variability | Supported (IV.3 failure; bottle share 15% in LBE) |
| Missing biochar descriptors | Unknown due to missing data |
| Missing operating conditions | Supported (no BRL mass, no temperature field, different TE regimes) |
| Study/batch heterogeneity | Supported (batch 38% to 64% of variance) |
| Kinetic structural inadequacy | Plausible but unproven (no alternative structure tested) |
| Parameter non-identifiability | Supported (42% truncation error) |
| Treatment reconstruction uncertainty | Supported (182 of 348 cycles not admitted) |
| Measurement/normalization differences | Supported (13 of 14 chemistry units unresolved; lab-specific volume correction) |
| Insufficient independent data | Supported (p floor 0.10 to 0.33) |
| Batch-to-continuous shift | Unknown due to missing data |
| Incorrect assumptions | Supported (labels are not one dose; FAN derived; ammonium scope conflict) |

Later exploratory evidence ([evidence requirements](EVIDENCE_REQUIREMENTS.md),
section 6) revises "kinetic structural inadequacy" to contradicted as the main
cause: every curve family fits whole long cycles within about 4%, while fits to
the first 6.5 days miss cycle ends by 21% to 43%.

## 10. Remaining blockers

1. Units of every Sanglier chemistry column and of the methane volume columns. The
   workbook `README` sheet (64 rows) is inventoried but its content is not committed.
2. Scope of the BRL batch-11 ammonium bicarbonate addition (Events!3 vs Inoculation).
3. Meaning of the LBE `+` label before batch 11.
4. II.4 biochar grams in batches 2 to 5.
5. IV.2 ammonium addition at batch 12.
6. BRL reactor mass and therefore BRL w:w dose basis.
7. Biochar material descriptors.
8. A development-side model whose prediction is commensurate with fixed-horizon
   repeated-batch yield, frozen before it sees Sanglier.

## 11. Modelling consequence

Allowed now: pre-registered within-laboratory descriptive contrasts on admitted
bottles; exploratory per-cycle kinetics labelled as such; hierarchical descriptive
models with batch and bottle terms inside Sanglier.

Prohibited now: calling any Sanglier analysis external validation; refitting a
development model on Sanglier and reporting it as transfer; pooling laboratories or
labels as a dose axis; using FAN, TS, VS or sCOD quantitatively; ML or hybrid models;
industrial or causal claims.

## 12. Next step

Fix the horizon rule in a version 2 spec (the corrected rule is already implemented
as D1), and before viewing any new outcome, freeze a development-side prediction for
fixed-horizon yield in a repeated-batch design from a study that is not Sanglier.
The single highest-value action is to resolve the unit and scope blockers 1 to 3 from
the workbook `README` sheet and the authors' `Python code.zip`, both public under
Etalab 2.0, by committing their relevant definitions with hashes.
