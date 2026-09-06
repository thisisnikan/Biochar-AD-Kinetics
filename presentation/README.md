# Presentation

This folder contains `index.html`, an animated, single-file, 20-slide HTML deck
explaining the whole idea of the Biochar–AD Digital Twin: the confounding problem it
addresses, the falsifiable research question, what the software pipeline actually does,
parameter identifiability and effect-size uncertainty, the evidence-tiering and
mechanism-evidence grading systems, the Chiappero et al. (2022) literature context, the
García-Prats collaboration (both the public 2024 dataset and the private, unpublished
CYPRUS2025 abstract), an honest current-status readout, the repository structure and
quality controls, and the next validation gate. It has no build step and no required
JavaScript packages; Google Fonts is the only external visual dependency.

Four slides are real data, not illustrations: the bar charts are computed directly from
`results/experimental/kinetic_baseline_comparison.csv`,
`results/external-dose/dose_response_comparison.csv`,
`results/pyrolysis-temperature/temperature_response_comparison.csv` (plus its
`descriptor_collinearity.csv` correlations), and the effect-size confidence intervals are
taken from `results/effects/within_study_effects__*.csv`. These are the same reproducible
outputs `biochar-ad benchmark-experimental`, `biochar-ad benchmark-external-dose`,
`biochar-ad benchmark-pyrolysis-temperature` and `biochar-ad summarize-effects`
regenerate. Only the confounding-problem schematic on slide 3 is illustrative, and it is
labelled as such in the deck.

If you have never touched this project, [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md)
is the more detailed, plain-language companion to this deck.

## Open locally

Download `index.html` and open it in a modern web browser.

- `Left` / `Right`, `Page Up` / `Page Down`, or click: navigate
- `Home` / `End`: first or last slide
- `F`: enter or exit fullscreen
- Swipe horizontally on a touch device

## Edit and publish

Edit `index.html`, commit the change, and verify the deck locally before publishing. If a
committed result CSV changes, re-check the two data slides' bar heights and value labels
by hand against the new CSV — they are static SVG, not generated from the file at load
time — and update `data/README.md`/`results/README.md` cross-references if needed.

The deck intentionally avoids unverified paper titles, invented results and claims beyond
the evidence documented in [`../docs/PROJECT_STATUS.md`](../docs/PROJECT_STATUS.md).
