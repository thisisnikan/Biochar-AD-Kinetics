# Sanglier 2022 external-validation ingestion gate

Dataset: Sanglier et al. (2022), *Supplementation of biochar and trace elements to increase the resilience of food waste anaerobic digestion: a long-term study*.

Persistent identifier: `10.57745/BUJORT`

Status: **source hash verified; methane plus chemistry/event context ingested and quarantined**.

27 September follow-up: [chemistry/event context audit](SANGLIER_2022_CONTEXT_AUDIT.md).
The section below records the original 25 September methane-only intake.

## Reproducible candidate intake (25 September 2026)

Download the official [Process.xlsx](https://entrepot.recherche.data.gouv.fr/api/access/datafile/152903)
and rebuild from the repository root:

```bash
python scripts/build_sanglier_2022_candidate.py /path/to/Process.xlsx
pytest -q tests/test_sanglier_candidate.py
```

The script refuses a file whose MD5 differs from the published deposit checksum.
It writes `results/intake/sanglier_2022_candidate.csv.gz` and the machine-readable
`results/intake/sanglier_2022_qc.json`. The original workbook is not committed.
The candidate preserves source sheet rows, bottle, batch, lab, raw and corrected
cumulative methane volume, flow, yield, inoculation mass, and separate intervention
labels. The 0/1/2 `Biochar` label is not treated as a g/L dose. `Days` is an
absolute day count within each lab; within-batch time subtracts the earliest
observed time for that lab and batch. Numeric zero remains distinct from empty.

All 8,403 `AMPTShort` time points join uniquely to one of 363 Inoculation
bottle/batch records. There are no duplicate `(lab, batch, bottle, Days)` keys.
The source contains two unresolved discordances:

- BRL bottle `II.4`, batches 2–5: 64 methane rows retain a zero/control
  `Biochar` label while Inoculation records positive biochar mass (0.5115 or
  0.6424 g). These four cycles cannot be assigned an unambiguous treatment.
- BRL bottles `II.13`–`II.15`, batches 11–14: 318 methane rows say `MBE[2]+`,
  while Inoculation says `MBE[2] + N`. The label difference may encode an
  additional intervention; the intake flags it without guessing its meaning.

There are 348 empty values and 348 measured zeros in each cumulative-volume
column. `Analyses` (VFA/TAN/pH) and `Events` are inventoried but not joined.
The candidate must not enter fitting, a methane-benefit claim, or external
validation until those sheets and the intervention chronology are reconciled.

## Confirmed source inventory

The public Recherche Data Gouv / Data INRAE deposit exposes:

- `Process.xlsx` — 6.7 MB; MD5 `282f5076857dd4f8ca38089a6d499909`; description: process data including amount fed at each batch, VFA measurements and CH4 production.
- `SeqArchaea.xlsx` — 69.5 KB; MD5 `8c367e44fd22483c308559a486b86de3`.
- `SeqBacteria.xlsx` — 1.3 MB; MD5 `af3e4aac2b46e4236ca7b00d98af2dc0`.
- `Python code.zip` — 8.9 MB; MD5 `da843edcff3f6220ce65832b11e58461`; code used by the authors for figures, statistical analysis and COD balance.

License on the deposit: Etalab Open License 2.0.

## Experimental-design boundary

The deposit describes **successive anaerobic-digestion batch reactors with partial digestate recirculation between batches**, not a continuously fed single-reactor trajectory. Fresh food-waste substrate was supplied at the start of each batch. Trace-element supplementation and biochar at 1% and 2% (w:w) were tested.

Therefore this study may be used as a **dynamic / repeated-cycle external-validation dataset**, but it must not be represented as a direct replication of the Daskaloudis continuous pilot reactor.

## Locked validation role

Until ingestion and QC are complete, Sanglier must remain outside all fitting/training steps. It is reserved for testing transferability of conclusions derived from the Daskaloudis analysis.

Candidate validation questions are:

1. Does a biochar-associated change in methane trajectory appear independently when the experimental architecture changes?
2. Is any methane benefit accompanied by faster VFA re-consumption and improved resistance to acidification?
3. Do methane-production or methane-yield conclusions agree with methane-composition conclusions, or do the response metrics diverge?
4. Do conclusions change once trace-element co-interventions, TAN inhibition and repeated-batch carry-over are represented explicitly?
5. Which effects fail to transfer from the Daskaloudis single-reactor system, and can those failures be explained by reactor architecture, feeding regime, dose definition or inhibition state?

## Required source-to-QC pipeline

No modelling should begin until the following are completed from the original `Process.xlsx`:

1. Inventory every sheet, header block, formula field and hidden/merged structure.
2. Identify the canonical chronological variable and distinguish absolute experiment time from within-batch time.
3. Reconstruct batch/cycle identifiers and digestate carry-over links.
4. Reconstruct all intervention labels directly from source data or source documentation:
   - untreated/control state,
   - trace-element additions,
   - biochar 1% w:w,
   - biochar 2% w:w,
   - combined/co-intervention states,
   - inhibition/recovery states where explicitly defined.
5. Preserve original units and raw values before normalization.
6. Determine blank/missing/zero semantics field-by-field. No blanket `0 = missing` rule is permitted.
7. Detect duplicate time/cycle records and coalesce only complementary, non-conflicting observations while preserving source-row provenance.
8. Flag interventions that are inseparable from trace-element or other operating changes rather than assigning the effect to biochar alone.
9. Generate a machine-readable QC report with row counts, duplicate/conflict counts, missingness and source hashes.
10. Only then create a processed analysis table.

## Minimum processed schema

The final long-format table should contain, where the source permits:

- `study_id`
- `reactor_or_series_id`
- `batch_id`
- `absolute_time`
- `within_batch_time`
- `digestate_carryover_source`
- `feed_amount`
- `biochar_dose`
- `trace_element_state`
- `intervention_label`
- `TAN`
- individual VFA species
- total VFA only if reconstructable without unjustified assumptions
- methane production / rate
- methane yield
- pH and other stability variables
- `source_sheet`
- `source_rows`
- `qc_flags`

Exact column names and units must be determined from the workbook rather than guessed from this gate document.

## Interpretation rule

The dataset deposit reports improved methane yield, faster VFA re-consumption and prevention of acidosis under biochar supplementation even at TAN above 4 g/L, with microbial-community changes. These statements are useful as hypotheses to reproduce from the raw source; they are **not** values to encode into the processed data or use as labels.

The external-validation result should be allowed to be negative. Failure of the Daskaloudis response pattern to transfer is scientifically informative and should be reported rather than optimized away.
