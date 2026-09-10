# Continuous external validation candidates

## Sanglier et al. (2022) — INRAE / SUEZ

Dataset: **Supplementation of biochar and trace elements to increase the resilience of food waste anaerobic digestion: a long-term study**  
Persistent identifier: `10.57745/BUJORT`

### Why it is relevant

The dataset follows successive mesophilic anaerobic-digestion batches in which part of the digestate is recirculated into the next batch and fresh food-waste substrate is added. The experimental programme includes trace-element supplementation and biochar at 1% and 2% (w:w). The public repository states that biochar improved methane yield, accelerated VFA re-consumption and prevented acidosis under high TAN, and links the effect to microbial-community changes.

The public data package includes process data and analysis code. The process file is described as containing feeding information, VFA measurements and methane production, while additional files contain bacterial and archaeal sequencing information.

### Validation value

This is a stronger external-validation target for the continuous/semi-continuous branch than a conventional endpoint BMP study because it contains repeated process cycles, digestate carry-over, intervention changes, methane-production dynamics and VFA response. It is independent of the Daskaloudis pilot dataset.

### Important design difference

It is **not a true continuously fed single-reactor time series**. It is a sequence of linked batch reactors with digestate recirculation. Therefore it should be treated as a *dynamic semi-continuous / repeated-cycle external validation dataset*, not as a direct replication of the Daskaloudis reactor design.

### Proposed validation questions

1. Does biochar coincide with a reproducible shift in methane-production trajectory after accounting for pre-existing cycle trend?
2. Is any methane benefit accompanied by faster VFA clearance and improved resistance to acidification?
3. Are conclusions robust when the validation target is methane production/yield rather than methane fraction alone?
4. Does a model or summary rule learned from Daskaloudis retain the same qualitative direction in this independent repeated-cycle system?
5. Which claims fail to transfer because reactor architecture, feeding mode, dose definition and inhibition regime differ?

### Readiness status

`candidate_found_public_data_not_yet_ingested`

Before using it for external validation:

- download and inventory the original process workbook and code package;
- reconstruct cycle identifiers, intervention timing, biochar dose and trace-element co-interventions;
- preserve all raw measurements and source units;
- distinguish true zeros from missing measurements using source-specific evidence;
- identify untreated/control periods and any confounded intervention transitions;
- build a separate QC report before fitting any validation model.

This dataset should remain outside model training until those gates pass.
