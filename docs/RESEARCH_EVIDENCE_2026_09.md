# Research and acquisition update — 27 September 2026

This is a targeted evidence screen, not a systematic review or a meta-analysis.
Searches covered publisher pages, Data INRAE / Recherche Data Gouv, Mendeley,
Zenodo and PubMed. Queries combined biochar, anaerobic digestion, raw data,
continuous operation and machine learning. Soil-only, rumen and generic biomass
resource datasets were excluded from acquisition. Search ranking is not evidence quality.

## What actually grew

| Source | New deliverable | Independent evidence unit | Admission |
| --- | --- | --- | --- |
| Sanglier 2022 | 923 chemistry samples, 8 event records, 363 bottle/batch links to the existing 8,403 methane rows | Same repeated-cycle study already registered | Quarantined |
| Heitkamp 2021 | 1,365 source-cell measurements across 15 variables and 91 plant/sampling days | One additional study, seven industrial plants | Chemistry candidate only |

A chemistry cell, sampling day, bottle, plant and study are different counting
units. These totals must not be added together and advertised as independent
training examples. Neither dataset is automatically passed to the fitting CLI.
The [machine-readable research screen](../data/research/evidence_screen_2026_09.csv)
records acquisition status separately from scientific relevance.

## Primary-source reading and decisions

- **Sanglier 2022**, [deposit](https://doi.org/10.57745/BUJORT):
  repeated-cycle food-waste digestion with biochar and trace elements. The source
  workbook now supplies chemistry and events as well as methane. See the
  [context audit](SANGLIER_2022_CONTEXT_AUDIT.md) for source-level findings.
- **Heitkamp 2021**, [paper](https://doi.org/10.1186/s13068-021-02034-5):
  industrial chemical monitoring, without reliable biogas productivity. Suitable
  for a future stability-transfer test, not methane-benefit validation. The
  [intake note](HEITKAMP_2021_INGESTION_GATE.md) records the unit conflict.
- **Zhang et al. 2025**, [Carbon Research](https://doi.org/10.1007/s44246-025-00226-4),
  sections 2.3, 2.6 and Data availability: experiments use glucose at 37 °C;
  the initial material screen uses 10 g/L and the iterative experiment 15 g/L.
  Their ML evaluation uses a random 80/20 split; underlying datasets are available
  on request. Our inference: material preparation and dose changes need separate
  treatment, and this split alone cannot establish transfer to unseen studies.
  No reactor-level file was obtained here. This is distinct from our Zhang 2022 source.
- **Huaraca et al. 2026**, [author abstract](https://pubmed.ncbi.nlm.nih.gov/42607778/):
  623 conditions from 107 studies; reported R² changes from 0.683 to 0.36 under
  study-grouped validation. Our decision: retain study identity through every
  preprocessing step, and compare grouped results with simple baselines.
  The abstract is evidence about a published analysis, not a downloaded dataset.
- **Vayena et al. 2024**, [author repository record](https://zenodo.org/records/15222075),
  DOI [10.1016/j.renene.2024.121569](https://doi.org/10.1016/j.renene.2024.121569):
  the deposited file is an article PDF with a linked DOCX supplement. This record
  is not itself a raw reactor dataset. Inspect the supplement before claiming
  usable trajectories, replicates or reuse rights.
- **Shao et al. 2025**, [publisher record](https://www.sciencedirect.com/science/article/pii/S1385894725038847),
  DOI [10.1016/j.cej.2025.163050](https://doi.org/10.1016/j.cej.2025.163050):
  magnetic biochar, semi-continuous operation and varying substrate C/N are a
  relevant boundary case. Only discovery metadata/abstract excerpts were accessible
  in this pass; a reusable raw file was not confirmed. Keep modified material
  classes separate from unmodified biochar.
- **Biochar-Augmented Anaerobic Digestion System (2025)**,
  [ACS publisher record](https://doi.org/10.1021/acs.est.5c05051):
  discovery excerpts describe a large literature-based SMY dataset and an
  ensemble model. Full data lineage, augmentation and grouping were not audited.
  This is a methods-screening lead, not thousands of newly acquired experiments.

## Research questions to lock before the next outcome analysis

1. **Within-study repeatability:** can a kinetic baseline predict a genuinely
   held-out reactor at a known treatment? Report control and amended arms separately.
2. **Dose transfer:** can a model predict a held-out dose of the same material?
   Hold out all sibling reactors at that dose. Material substitution is a different task.
3. **Stability transfer:** does a direction of acid/pH response recur in independent
   systems? Preserve plant-specific results and irregular sampling. Do not infer
   gas production from a fall in acids or interpret a time trend as causal attribution.
4. **Unseen-study prediction:** only attempt after independent raw studies, units,
   controls and uncertainty are sufficiently compatible. Reserve complete studies;
   fit imputation, scaling, feature selection and hyperparameters within training folds.
5. **Mechanism:** descriptor correlations and microbial relative abundance remain
   hypotheses. Distinguish buffering, nutrient supply, adsorption and electron
   transfer; do not assign a single mechanism from methane curves.

## Concrete next acquisition gates

| Priority | Action | Required deliverable |
| --- | --- | --- |
| 1 | Reconcile Sanglier methods with the preserved events | Explicit bottle-specific exposure intervals, chemistry unit dictionary, carry-over links and treatment-conflict disposition |
| 2 | Audit Heitkamp timing and chemical reporting | Verified intervention origin, VS denominator and TVFA basis; predefined plant-level stability protocol |
| 3 | Inspect Vayena supplement | Table inventory, original replicate availability, source license and checksum |
| 4 | Obtain full lineage for multi-study ML tables | Original publication IDs, duplicate/cross-publication mapping, raw-versus-augmented labels |
| 5 | Seek parallel-control continuous measurements | Matched reactor time series, OLR/HRT, feed changes, biochar dosing, methane flow/composition and chemistry |

Do not tune thresholds on the reserved external outcomes, replace unavailable
replicates with synthetic observations, or select only studies reporting benefit.
Maintain null and adverse results as valid outcomes. No outreach was sent in this update.
