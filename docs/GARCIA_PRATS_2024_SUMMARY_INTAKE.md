# Marta's Frontiers workbook: private summary-data integration

Author-shared file: `Data Frontiers.xlsx`, received 18 September 2026.
Article: [García-Prats, González and Sánchez (2024)](https://doi.org/10.3389/fceng.2024.1384495).
The public repository contains the importer, synthetic safeguard tests and source
metadata. The original workbook and derived observation tables remain private;
permission to use data for validation is not a redistribution license.

## Run

Place the workbook in the ignored `data/private/garcia_prats_2024/` directory:

```bash
python scripts/build_garcia_prats_2024_summary.py \
  --source data/private/garcia_prats_2024/Data_Frontiers.xlsx
```

Outputs default to ignored `results/private/garcia_prats_2024/`:
`methane_summary.csv` and `intake_qc.json`. The SHA-256 check rejects changed files.
Use the exact author source, not a workbook reconstructed from published figures.

The table contains 143 design slots, including 119 observed mean/SD pairs and 24
explicit unavailable second-feeding slots. There are 77 first-feeding and 42
second-feeding observations. Conditions comprise cellulose, unamended control
and three materials at three doses. Reported replication is three per condition;
individual reactor trajectories are not supplied. No artificial replicates,
blank trajectories, standard errors or inverse-variance weights are generated.

The existing public treatment-design table supplies condition/material IDs,
temperature and nominal mass/volume dose conversion, with its own checksum in
QC. Original %TS doses remain alongside nominal g/L. The single shared control
is represented once per feeding/time rather than copied for each material.
Cellulose remains a positive control, not an unamended food-waste reactor.

## Feeding and validation boundary

The article's methods and Figure 6 place refeeding at day 22; the author workbook
records a new zero at day 23. Both absolute time and time relative to the recorded
phase zero are retained. The latter is **not a confirmed kinetic time origin**
for feeding 2. All second-feeding rows carry this flag. Do not silently shift the
source or fit across the cumulative reset.

The article states that different substrate batches were used, so treatment
comparisons must stay within a feeding. Feeding 2 is a repeated exposure of
selected bottles, not an independent study or proof of acclimation.

Summary curves can support a separate descriptive kinetic/dose-response analysis
once normalization and timing are reconciled. They cannot pass the repository's
raw-reactor validation gate. All rows have `model_admission=False`; they are not
automatically dispatched to `fit-stage-a`. Zero SD at reported time zero must not
become infinite statistical weight. Cross-time covariance is unavailable.

Source cells for mean, SD and both time grids remain attached to each row.
The imported workbook, rather than rounded or inconsistent prose percentages,
is the numerical source of truth for any later author-data analysis.
