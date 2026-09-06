# Mechanism-evidence grading

A good held-out fit says a response is predictable, not why it happens. This
repository keeps that distinction explicit, especially for claims about
direct interspecies electron transfer (DIET) — a specific, testable
mechanism, not a synonym for "biochar helped."

## The rubric

Following Pilarska (2026, *Catalysts* 16(6), 502), who argues that improved
methane production after a conductive-material addition is not, by itself,
evidence of DIET, every dataset in this repository is graded on what *kind*
of evidence it actually contains:

| Grade | What is present |
| --- | --- |
| **Weak** | Process response only (methane/biogas yield, rate, lag, VFA, stability). Consistent with DIET but equally consistent with adsorption, buffering, trace-element supply, or biodegradation of the added material. |
| **Moderate** | Process response **and** a compatible microbial-community shift (e.g. enrichment of exoelectrogens/methanogens known to participate in DIET). Still not direct proof: a community shift can also follow from a changed substrate or buffering environment. |
| **Strong** | Process **and** microbial **and** direct electrochemical, structural, or molecular evidence (e.g. measured conductivity contribution in situ, cyclic voltammetry, gene expression of DIET-associated pathways). |

A dataset earns the grade of its weakest necessary ingredient: process data
alone is always Weak, regardless of how good the fit is.

## Grading the datasets in this repository

| Dataset | Process data | Microbial data | Electrochemical/molecular data | Grade |
| --- | --- | --- | --- | --- |
| Kozłowski et al. (2025) | Yes | No | No | Weak |
| Valentin & Białowiec (2024) | Yes (kinetic parameters only) | No | No | Weak |
| Zhang et al. (2022) | Yes | Yes (16S community analysis reported in the source article) | No | Moderate |
| García-Prats et al. (2024) | Not yet ingested (metadata/design only) | No | No | Not applicable — no outcome data in this repository yet |
| CDU / Wang (2026) thesis | Yes (methane yield, VFA/fibre) | Yes (microbial-community analysis reported in the thesis) | No | **Moderate at most** |

## Why this matters for the CDU pyrolysis-temperature table

`data/experimental/cdu_wang_2026_pyrolysis_temperature.csv` and
`biochar-ad benchmark-pyrolysis-temperature` test only whether methane yield
follows a smooth trend across pyrolysis temperature — a Weak-grade,
process-only question by construction, since the ingested summary table
carries none of the thesis's microbial data. Within that table, pyrolysis
temperature, BET surface area, electrical conductivity and pH all increase
together (the CLI reports their pairwise correlation and flags it above
`DESCRIPTOR_COLLINEARITY_THRESHOLD`), so even a clean temperature trend
cannot be attributed to conductivity specifically, let alone to DIET. Raw
reactor-level and microbial data have been requested from the thesis author
(tracked in the project's outreach pipeline) to test the process-level
prediction claim properly; the mechanism claim would still require the
Strong-grade evidence this repository does not have access to.

## Rule for contributors

Never describe a Weak- or Moderate-grade result using Strong-grade language
("proves", "confirms DIET", "demonstrates electron transfer"). Use
outcome-level language instead ("predicts", "is associated with", "improves
held-out RMSE").
