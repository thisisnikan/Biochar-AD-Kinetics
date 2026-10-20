# Documentation

The documents below are grouped by purpose. New readers should start with
[Architecture and glossary](ARCHITECTURE.md) and then [Project status](PROJECT_STATUS.md).

## Start here

| Document | Purpose |
| --- | --- |
| [Architecture and glossary](ARCHITECTURE.md) | Plain-language map of the idea, repository layout, code path and terminology |
| [Project status](PROJECT_STATUS.md) | Current readiness, what can and cannot be claimed, and the next validation gate |
| [Roadmap](ROADMAP.md) | Staged long-term direction and the evidence each stage requires |

## Methods and evidence standards

| Document | Purpose |
| --- | --- |
| [Data contract](DATA_CONTRACT.md) | Minimum reactor-level record accepted by `biochar-ad validate-intake` |
| [Validation plan](VALIDATION_PLAN.md) | Staged, leakage-safe validation protocol (dose first, temperature second) |
| [Evidence requirements](EVIDENCE_REQUIREMENTS.md) | Minimum information for cross-study prediction, checked by `biochar-ad check-evidence` |
| [Generalization readiness](GENERALIZATION_READINESS.md) | Gate that must pass before any leave-one-study-out result is interpreted |
| [Mechanism-evidence grading](MECHANISM_EVIDENCE.md) | Rubric limiting mechanistic language (for example DIET) to what measurements support |

## Results and decision records

| Document | Purpose |
| --- | --- |
| [Forecast benchmark](FORECAST_BENCHMARK.md) | Retrospective comparison of kinetic forecasts with simple prefix-only baselines |
| [Frozen forecast workflow](FUTURE_BATCH_FORECAST.md) | Pre-registered day-21 forecast protocol awaiting genuinely new measurements |
| [Sanglier 2022 admission decision](SANGLIER_2022_VALIDATION_ADMISSION.md) | Frozen-spec admission outcome: partially admissible, external validation blocked |

## Dataset intake records

| Document | Dataset |
| --- | --- |
| [Data expansion registry](DATA_EXPANSION_REGISTRY.md) | Status of every ready and candidate dataset |
| [Sanglier 2022 ingestion gate](SANGLIER_2022_INGESTION_GATE.md) | Long-term food-waste digestion with biochar and trace elements (Data INRAE) |
| [Sanglier 2022 context audit](SANGLIER_2022_CONTEXT_AUDIT.md) | Chemistry and operating-event records linked to the Sanglier methane data |
| [Heitkamp 2021 ingestion gate](HEITKAMP_2021_INGESTION_GATE.md) | Chemistry monitoring of seven industrial digesters supplied with biochar |
| [Cai BMP ingestion gate](CAI_BMP_INGESTION_GATE.md) | BMP database records 583–594 (candidate) |
| [García-Prats et al. (2024) summary intake](GARCIA_PRATS_2024_SUMMARY_INTAKE.md) | Author-shared methane summary workbook (private; importer only) |
| [Research and acquisition update, September 2026](RESEARCH_EVIDENCE_2026_09.md) | Targeted screen of candidate sources and their acquisition status |

## Continuous-reactor work

| Document | Purpose |
| --- | --- |
| [Continuous pipeline status](CONTINUOUS_PIPELINE_STATUS.md) | Source of truth for unfinished dynamic-data stages |
| [Continuous external-validation candidates](CONTINUOUS_EXTERNAL_VALIDATION.md) | Candidate continuous datasets and their eligibility |
| [Continuous analysis log](CONTINUOUS_ANALYSIS_LOG.md) | Dated record of evidence, assumptions and QC decisions |

Data provenance and the private-data boundary are documented in
[`../data/README.md`](../data/README.md); reproducible reference outputs are described in
[`../results/README.md`](../results/README.md).
