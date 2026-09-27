# Heitkamp industrial chemistry intake

[Heitkamp et al. (2021)](https://doi.org/10.1186/s13068-021-02034-5),
*Monitoring of seven industrial anaerobic digesters supplied with biochar*.
Publisher Additional file 1, `13068_2021_2034_MOESM1_ESM.xlsx`;
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Changes: wide worksheet blocks transposed to source-cell-level CSV; no imputation,
normalization, conversion or inferred replicates. Source download URL and SHA-256
are in `results/intake/heitkamp_2021_qc.json`.

```bash
python scripts/build_heitkamp_2021_candidate.py /path/to/13068_2021_2034_MOESM1_ESM.xlsx
```

The output preserves 1,365 cells: 15 analytes at 91 plant/sampling days across
seven plants, spanning days 0–367. There are 402 numeric zeros and ten literal
`n.a` tokens, kept distinct. Each value and sampling time has its original cell
address. These are not 1,365 independent experiments.

The VS worksheet labels fresh-biomass percentage; the article figure caption
labels percentage of TS. This conflict is flagged, not corrected silently.
TVFA totals are retained without assuming a simple acid-mass sum. NH4-N kg/t is
not converted to g/L without a density basis. Day zero is not independently
verified as each plant's dosing time.

This uncontrolled industrial series is reserved for process-stability work.
Reliable gas-productivity data were unavailable; methane validation and causal
biochar claims are prohibited. Resolve units/timing and freeze a plant-level
protocol before admission. Do not pool plants as interchangeable replicates.
