# Stage C data gaps and acquisition priorities

## Current hypothesis

The first Stage C transfer test showed that dose plus biochar processing temperature does not outperform a training-study mean baseline when a complete study is held out.

The next hypothesis is that transferable kinetic effects require material and digestion-context descriptors rather than dose and process temperature alone.

## Evidence currently linked to kinetic fingerprints

| Study | Kinetic effects | Dose | Process temperature | BET / surface area | Pore volume | Feedstock / activation | Reactor-level trajectories |
|---|---|---|---|---|---|---|---|
| Kozlowski 2025 | yes | yes | yes | no | no | limited | yes |
| Valentin/Bialowiec 2024 | yes | yes | yes | no | no | limited | no; published parameters |
| Chiappero 2021 | yes | yes | yes | yes | yes | yes | no; published parameters |

With the present linked fingerprints, `surface_area_m2_g` and `pore_volume_cm3_g` are therefore available in only one independent study. A rich-surface transfer model must remain blocked by the three-study evidence gate.

## Rich descriptors already present elsewhere in the repository

The repository already contains material-context tables that should be reused rather than recollected:

- `data/experimental/garcia_prats_2024_biochar_characteristics.csv`: feedstock, pyrolysis temperature, BET surface area, mean pore size, elemental composition, pH and EC.
- `data/experimental/garcia_prats_2024_material_context.csv`: substrate/inoculum density, TS, VS and pH.
- `data/experimental/garcia_prats_2024_treatment_design.csv`: dose, working volume, temperature and replicate counts.
- `data/experimental/zhang_2022_biochar_characteristics.csv`: pyrolysis temperature/duration, XPS O:C-related descriptors and Raman ID/IG.

These descriptors should only enter Stage C after they are linked to compatible kinetic outcomes. Endpoint methane yield must not be silently relabelled as fitted methane potential.

## Highest-value external dataset target

Quintana-Najera et al. (2023), *Understanding the Influence of Biochar Augmentation in Anaerobic Digestion by Principal Component Analysis*, DOI `10.3390/en16062523`, compiled literature experiments using eight variables directly relevant to the failed Stage C hypothesis:

- pyrolysis temperature,
- ash content,
- O:C ratio,
- inoculum-to-substrate ratio (ISR),
- biochar load,
- effect on BMP,
- methane production rate,
- lag phase.

The paper states that the PCA dataset is provided in Supplementary Table S2. This source should be treated as a literature-derived context benchmark, not reactor-level experimental evidence. Each original study should retain its provenance/group identity so validation can be grouped by source study and not by individual rows.

## Acquisition priority

1. Link compatible kinetic outcomes to the existing Garcia-Prats material/context tables when raw or fitted time-series data are available.
2. Acquire and audit Quintana-Najera Supplementary Table S2 and retain original-study provenance.
3. Prefer new studies with control, time-resolved methane, replicates, dose, BET/surface area, pore properties, feedstock, ash/O:C, ISR and digestion temperature.
4. Re-run feature ablation only when each richer feature set has at least three independent studies; do not impute study-wide missing descriptor blocks merely to satisfy the gate.
