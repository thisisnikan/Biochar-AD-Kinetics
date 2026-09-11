# Stage C source audit

This note records the current evidence boundary for material-aware transfer modelling. It intentionally separates verified model-ready evidence from sources that are only partially recovered.

## García-Prats CYPRUS2025 — private, model-ready within study

Author-shared unpublished material contains nine biochars tested at 5% and 10% TS with dose-specific controls, modified-Gompertz lag, Rmax and Ymax, plus pH, EC, C/N/O/H, H/C, O/C, feedstock and pyrolysis temperature.

Use only in the private pipeline. The two dose campaigns used substrate/inoculum collected at different times, so effects must be normalized to the corresponding campaign control. Do not commit the unpublished numeric tables to this public repository.

One source-value anomaly must remain explicit: Q500 at 10% is printed as Rmax = 6.2 in the source table even though surrounding values and manuscript prose suggest a possible typographical error. Preserve 6.2 as source-exact and treat 62 only as a labeled sensitivity scenario.

## Cai / Tongji BMP records 583–594 — blocked

The Liu et al. (2024) BMP database supplement verifies that query IDs 583–594 map to Cai Jiao's Tongji University master's thesis, "Promoting Anaerobic Digestion by Biochar: Preliminary Study on Technology Optimization and Mechanism Analysis."

Current recovery status:

- 12 target query identifiers verified.
- 0 official row exports recovered.
- 0 model-import-ready rows.
- Public Cai et al. (2016) article provides only ISR-level response ranges and best-dose summaries, not the 12 row-level observations.

Decision: retain as provenance-registered but blocked. Do not convert aggregate ranges into synthetic rows and do not fill unknown values with zero. Promotion requires an official BMP export or a primary thesis table/figure that verifies treatment mapping, units, outcome definitions and values.

## Ataa 2026 — quarantined from methane-specific modelling

DOI: 10.12911/22998993/216571 (*Journal of Ecological Engineering*, Table 5).

`data/experimental/ataa_2026_parameters.csv` preserves the published biochar-dose kinetic
parameters, but the source paper's own results distinguish cumulative gas production from a
separately reported methane-yield percentage. Table 5's `Bmax`/`Rmax` columns are total
biogas, not methane, so the CSV columns are named `bmax_ml_total_biogas` /
`rmax_ml_total_biogas_day` and every row carries `response_basis = total_biogas_not_methane`
to make this explicit at the data level, not only in prose.

Decision: this source must never be merged into `delta_potential`/`delta_max_rate`/methane
kinetic fingerprints, because its Pmax/Rmax analogue measures a different physical quantity
than every other study in the fingerprint table. Native dose (5 g biochar per 20 g food waste)
is also not convertible to g/L without an unverified assumption, which independently blocks it
from the current dose-response model. `scripts/analyze_batch_kinetic_fingerprints.py` registers
it as `quarantined_from_methane_specific_modelling` and does not read the CSV into the
fingerprint pipeline. Promotion would require either a reported methane fraction per condition
(to convert biogas to methane) or a primary source that reports methane volume directly.

## Vayena et al. 2024 — highest-priority public acquisition

DOI: 10.1016/j.renene.2024.121569

Why it matters: seven biochars span multiple feedstocks and pyrolysis/activation conditions and are characterized with surface area, pore structure, electrical conductivity and other physicochemical descriptors. The article reports that study data are included in the article and supplementary material; Supplementary Data 1 contains digestion-related data and Gompertz results.

Acquisition objective: recover Supplementary Data 1 and construct a provenance-preserving treatment table linking kinetic outputs to biochar descriptors. Keep native dose units and convert only where the denominator is explicit.

Acquisition attempt (2026-09-10): the sandbox this session ran in could not reach `sciencedirect.com`, `doi.org`, or `orbit.dtu.dk` (all connections egress-blocked), so Supplementary Data 1's actual sheet/column structure could not be inspected. No ingestion script was written for this source, because this project's own rule is to encode a transcription schema only after seeing the real table structure (see the García-Prats CYPRUS2025 script for that pattern) - guessing column names here would look like a verified schema without being one. `scripts/inventory_xlsx_source.py` and `src/biochar_ad_kinetics/xlsx_reader.py` are ready to inventory and read the file as soon as someone with real network/journal access downloads it locally. This remains the highest-priority acquisition target.

## Stage C scientific decision

Current cross-study result rejects dose + pyrolysis temperature as a transferable predictor. The next test is therefore not "more rows" but whether measured material properties and reactor/substrate context improve whole-study transfer.

Priority order:

1. Recover and ingest Vayena Supplementary Data 1.
2. Obtain official Cai/Tongji rows 583–594 when Marta sends the prepared Excel/export.
3. Add another independent descriptor-rich kinetic study before fitting a cross-study rich-feature model.
4. Evaluate M0 study-mean baseline, M1 dose, M2 dose + pyrolysis temperature, M3 material descriptors, and M4 material + reactor/substrate context on identical grouped splits.

No rich-feature claim is allowed until at least three independent studies contain the target and requested descriptors.
