# Open-data screen for Stage A, 15 November 2026

**Purpose.** Stage A needs an independent reactor-level dose series: a zero-dose
control, at least three doses of one material, intact replicates, blanks and raw
methane trajectories ([validation plan](VALIDATION_PLAN.md)). This screen asked
whether such a dataset is already openly downloadable, so that Stage A would not
depend on author requests.

**Outcome.** No openly downloadable dataset that meets the Stage A gate was found.
One new candidate study was identified; its data are available on request only.
Stage A therefore still depends on author-shared data. Per the reporting policy,
every inspected record is listed with the reason it cannot be used.

## Records inspected

Inspection depth is the landing page and its file list only. No file was downloaded.

| Record | What it is | Status for Stage A | Blocking reason |
| --- | --- | --- | --- |
| [Zenodo 14921811](https://zenodo.org/records/14921811) (Leitat, 2025, CC BY 4.0) | AMPTS-II BMP data for food residues from a market in Ghana | Not usable | No biochar treatment or dose series is described |
| [Mendeley Data s7kxh4663k](https://data.mendeley.com/datasets/s7kxh4663k/1) (2026, CC BY 4.0) | Biochar-dosed anammox reactors: nitrogen budget, EPS, 16S | Not usable | Not anaerobic digestion; no methane outcome |
| [Mendeley Data ry4tjjwm42](https://data.mendeley.com/datasets/ry4tjjwm42) (2026, CC BY 4.0) | Pig-manure biochar for purification of digested slurry | Not usable | Adsorption study; no methane outcome and no zero-dose control |
| [Mendeley Data mtsksgpjf2](https://data.mendeley.com/datasets/mtsksgpjf2/1) (2026, CC BY 4.0) | 16S tables for volatile tar compounds in syngas digestion | Not usable | No biochar; no methane time series |
| [Raw Data Library entry for Valentin & Białowiec (2024)](https://rawdatalibrary.net/rdl/publication/impact-of-using-glucose-as-a-sole-carbon-source-to-analyze-the-effect-of-biochar-on-the-kinetics-of-biomethane-production) | Metadata page for a study already used here at parameter level | Not usable | Lists no dataset or file; raw triplicate series remain on request |

## New candidate

| Study | Reported design | Status for Stage A | What would unlock it |
| --- | --- | --- | --- |
| Galván, Badin, Becker & Bruno (2026), [preprint](https://www.researchsquare.com/article/rs-10373863/v1), digestate-derived biochar in agro-industrial co-digestion | Control without biochar plus 0.25, 0.5, 1, 1.5 and 2% w/w; triplicates; 38 °C; 30 d; daily biogas by water displacement with GC composition | Candidate, not acquired | Per-bottle time series and blanks from the authors; a measured basis to convert % w/w to g/L; peer-review status. Biogas volume with separate composition must be converted to methane before use |

The design as reported has six dose levels with a zero-dose control. The Stage A
simulation (`scripts/simulate_stage_a_power.py`) can assess such a design before any
outcome is seen.

## Limits of this screen

Five keyword searches across general web search, restricted to what the landing pages
state. Repositories were not queried through their own search interfaces, and
supplementary files of journal articles were not opened. Absence of a result here is
not evidence that no open dataset exists.
