# Data Expansion Registry

This registry separates datasets that are already modelling-ready from datasets that are only candidates. A dataset must not enter training or external validation until its source-specific ingestion and QC gate is complete.

## Ready / reproducible

### Daskaloudis 2026 — pilot continuous reactor
- Dataset DOI: `10.17632/r84yctsxx6.1`
- Associated paper DOI: `10.30955/gnc2025.00357`
- Design: one 180 L mesophilic pilot reactor, start-up + phases I–IV, digestate recirculation; Phase IV supported as the biochar period.
- Longitudinal span: day 0–389.
- QC-approved unique observations: 98.
- Duplicate day 235 is complementary and is coalesced with both source-row identifiers retained.
- Numeric zero is never globally converted to missing.
- Processed dataset was regenerated deterministically from the original workbook and the Phase III→IV sensitivity analysis was rerun from that permanent QC output.
- Status: `INGESTION_REPRODUCIBLE_DYNAMIC_ANALYSIS_REPRODUCED`
- Remaining scientific limitation: Phase I–III intervention definitions are unresolved, and there is no contemporaneous untreated reactor.

## External-validation intake

### Sanglier et al. 2022 — repeated-cycle / semi-continuous food-waste AD
- Dataset DOI: `10.57745/BUJORT`
- Public files confirmed: `Process.xlsx`, `SeqArchaea.xlsx`, `SeqBacteria.xlsx`, `Python code.zip`.
- Design: successive lab-scale AD batches with digestate recirculation; trace-element interventions plus biochar at 1% and 2% w/w.
- Valuable endpoints: methane trajectory/yield, VFA re-consumption, TAN/acidosis response, microbial-community changes.
- Critical confounder: trace elements and biochar interventions must be reconstructed separately.
- Status: `PUBLIC_RAW_DATA_CONFIRMED_BINARY_NOT_YET_INGESTED`
- Rule: keep completely outside model fitting until cycle/intervention reconstruction and source-specific QC are complete.

### Wambugu et al. 2019 — paired continuous UASB reactors
- Paper DOI: `10.3389/fenrg.2019.00014`
- Design: two identical 2.25 L UASB reactors operated at 30 °C; one control and one biochar-amended reactor.
- Biochar: treated-waste-wood pyrochar in the test reactor.
- OLR: 3.4–7.8 g COD/L/d; HRT 24 h.
- The paper reports daily/longitudinal reactor behaviour for COD removal, pH, VFA and gas production and documents a control-vs-treatment contrast.
- At OLR 6.9–7.8 g COD/L/d, reported average COD removal was 47% in the control and 77% in the biochar-amended reactor.
- Strong feature: parallel contemporaneous control makes the design structurally stronger for attribution than the single-reactor Daskaloudis trajectory.
- Known operating disturbances include feed/pipe problems and a control-reactor pH drop; these must be represented as operational events and never silently smoothed.
- A targeted search did not confirm a public machine-readable raw longitudinal file or thesis dataset. Figure digitisation therefore remains a last-resort acquisition path, not the default.
- Status: `HIGH_VALUE_CANDIDATE_RAW_LONGITUDINAL_FILE_NOT_CONFIRMED_AFTER_TARGETED_SEARCH`

### Heitkamp et al. 2021 — seven industrial CSTR digesters
- Paper DOI: `10.1186/s13068-021-02034-5`
- Design: seven full-scale industrial CSTR digesters supplied with biochar for approximately one year.
- Biochar intervention: initial reactor supplementation of 1.8 kg/t reactor content, followed by 1.8 kg/t substrate.
- Public supplementary workbook confirmed by both Springer and PubMed Central: `13068_2021_2034_MOESM1_ESM.xlsx` (~82.8 KB), described as recorded raw data for acetic, propionic and butyric acid.
- Main useful variables: acetate, propionate, butyrate / TVFA. The paper also reports pH, NH4-N, FOS/TAC, TS and VS observations.
- Important limitation: authors explicitly state that reliable biogas-productivity data were unavailable.
- Value to this repository: external process-stability validation across seven real industrial reactors, not methane-productivity validation.
- Status: `PUBLIC_RAW_SUPPLEMENT_FILENAME_CONFIRMED_BINARY_NOT_YET_MATERIALIZED`

## Adjacent mechanistic comparator — do not pool as biochar

### Kalantzis et al. 2023 — continuous GAC pilot reactor
- Paper DOI: `10.1016/j.biortech.2023.128908`
- Design: 180 L anaerobic digester in an integrated pilot system, with continuous addition of conductive granular activated carbon (GAC) at 5 g/L.
- Reported result: biogas production increased by about 32% after GAC addition and Methanosaeta relative abundance increased.
- Why useful: this is a continuous conductive-carbon intervention in a pilot-scale agro-industrial wastewater digester and can challenge whether dynamic signatures attributed to biochar are more generally signatures of conductive-carbon amendment.
- Critical boundary: GAC is not biochar. It must never be merged into a biochar treatment class or used as direct biochar external validation.
- Status: `MECHANISTIC_COMPARATOR_PAPER_FOUND_RAW_DATA_NOT_CONFIRMED`

## Admission rules

A candidate becomes modelling-ready only after all of the following are satisfied:

1. Original source file or author-shared raw data are available.
2. File checksum and source citation are recorded.
3. Reactor / batch / replicate identity is preserved.
4. Intervention timing and dose are explicitly reconstructed.
5. Co-interventions and known operating incidents are represented as metadata or exclusion flags.
6. Units are preserved or converted only through explicit documented transforms.
7. Missing values and zeros receive source-specific treatment; no blanket replacement rule.
8. Duplicate observations are either provenance-preserving coalesces or explicit conflicts.
9. Training/validation role is declared before modelling to avoid leakage.
10. A machine-readable QC report is emitted.

## Current expansion strategy

The goal is not maximum row count. The priority order is:

1. independent dynamic reactor systems;
2. parallel control/treatment continuous designs;
3. raw longitudinal stability variables (VFA, TAN, pH, COD/VS) alongside methane outputs;
4. independent biochar materials/doses with descriptors;
5. endpoint-only BMP studies after the dynamic evidence base is stronger;
6. clearly separated adjacent conductive-carbon comparators for mechanism-transfer tests.

This keeps the repository focused on transferability and reproducibility rather than creating an artificially large pooled table with incompatible experimental units.
