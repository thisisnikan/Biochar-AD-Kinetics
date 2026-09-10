# Continuous transition sensitivity — Daskaloudis dataset

Date: 2026-09-10

This note records sensitivity checks for the exploratory Phase III → Phase IV interrupted-time-series analysis. It is deliberately narrow: one reactor, no parallel untreated control, and Phase IV is associated with biochar plus possible operating changes. Results are therefore associational, not causal.

## Model

For each response, the segmented model is

`response = intercept + pre-trend + Phase-IV level change + post-Phase-IV slope change + OLR`

with the primary boundary at day 309.

A simpler `time + OLR` model is used as the descriptive baseline. The repository script `scripts/continuous_transition_sensitivity.py` reproduces the coefficient/AIC sensitivity analysis from a QC-approved processed CSV.

## Primary full-window result

Using all available Phase III–IV gas-output observations (n = 38):

| Response | Phase-IV level change | Post-slope change/day | ΔAIC: simple − segmented |
| --- | ---: | ---: | ---: |
| Methane fraction (%) | +2.56 pp | +0.109 pp/d | +31.16 |
| CH4 production (L/d) | -3.95 | +0.336 | +2.69 |
| Methane yield (workbook field) | -22.34 | +0.917 | +3.83 |
| Biogas (L/d) | -15.81 | +0.091 | -0.36 |

Positive ΔAIC favours the segmented model. The strongest evidence for a trajectory change is therefore in methane fraction, not in absolute methane production or biogas.

## Transition-window sensitivity

The same model was re-fitted using symmetric windows around day 309. For methane fraction:

| Window around day 309 | n | Level change (pp) | Post-slope change (pp/d) |
| --- | ---: | ---: | ---: |
| ±30 d | 16 | +4.58 | +0.056 |
| ±40 d | 20 | +4.49 | +0.098 |
| ±50 d | 24 | +3.53 | +0.101 |
| ±60 d | 28 | +2.99 | +0.108 |
| ±80 d / full Phase III–IV span | 38 | +2.56 | +0.109 |

The sign of the methane-fraction level change is stable across all tested windows. Its magnitude shrinks as more distant observations are included, which is expected when long-term drift and phase heterogeneity are admitted. The positive post-boundary slope change is also stable from ±40 d onward, while the narrowest ±30 d window is too small to support a stable slope interpretation.

For CH4 production, methane yield and biogas, slope estimates vary materially with window width. Those responses should therefore not be presented as having a robust intervention-associated dynamic shift from this single reactor.

## Missing-value sensitivity

For the Phase III–IV observations used in the four primary gas-output models:

- OLR contains no zero values.
- Biogas contains no zero values among observed entries.
- Methane fraction contains no zero values among observed entries.
- CH4 production contains no zero values among observed entries.
- Methane yield contains no zero values among observed entries.

Therefore the current gas-output transition result is **not sensitive to a `zero = missing` rule**, because no such zero values enter these fits. The repository must still avoid any blanket zero-replacement rule for the wider dataset.

## Duplicate-day sensitivity

Day 235 appears twice in Phase III, but the two rows are complementary rather than exact duplicates: core operating/solids/COD values agree, while phenol/TAN fields are populated in different rows. Neither row contains the gas-output measurements used in the four primary transition models.

Consequently, removing one day-235 row versus coalescing the two rows does not change the current methane/biogas transition fits. The correct permanent ingestion rule should be to coalesce non-conflicting duplicate-day measurements while flagging any conflicting non-null values, rather than simply dropping one row.

## Evidence-qualified conclusion

The methane-fraction trajectory change is robust to reasonable transition-window choices and is not an artefact of zero handling or the day-235 duplicate. Comparable robustness is not present for absolute methane production, methane yield or biogas.

The defensible statement remains:

> Phase IV is associated with a robust change in methane composition trajectory, but this single-reactor dataset does not establish a corresponding improvement in absolute methane productivity or a causal biochar effect.

## Next gate

1. Build the QC-approved processed long table with duplicate coalescing and provenance flags.
2. Resolve Phase I–III intervention definitions from source documentation.
3. Add statistical-stability criteria to the HRT-based response windows.
4. Seek a second continuous/semi-continuous biochar dataset for external validation before generalising the Phase-IV pattern.
