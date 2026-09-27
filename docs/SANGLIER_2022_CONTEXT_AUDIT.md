# Sanglier chemistry and operational context

Source: [Sanglier et al. (2022), DOI 10.57745/BUJORT](https://doi.org/10.57745/BUJORT),
`Process.xlsx`; Etalab Open License 2.0. This update transposes and links source
records; it does not fit outcomes or resolve labels by assumption.

```bash
python scripts/build_sanglier_2022_context.py /path/to/Process.xlsx
```

Outputs under `results/intake/`:

- `sanglier_2022_chemistry.csv`: all 923 nonempty Analyses rows, original headers,
  values and source-row identities; exact Inoculation linkage.
- `sanglier_2022_events.csv`: all eight actual events. Worksheet dimensions include
  hundreds of empty formatted rows; these are not events.
- `sanglier_2022_bottle_batches.csv`: 363 Inoculation identities with lists of
  chemistry and methane source rows, without a time-point Cartesian join.
- `sanglier_2022_context_qc.json`: source MD5/SHA-256, coverage, zeros and blockers.

There are 315 bottle/batch identities with chemistry. Fifteen chemistry samples
lack a methane trajectory for the same bottle/batch and remain visible. Coverage:
673 pH values, 212 TAN, 32 FAN, 239 sCOD, and 673 values for each of eight acid
columns. Missing cells stay empty; measured zeros stay zero. Chemistry units are
not inferred from column names. No nearest-time interpolation or total-VFA sum
is introduced.

## Source events and unresolved interpretation

| Source row | Recorded context | Analysis consequence |
| --- | --- | --- |
| Events!2 | BRL start, day 0 | Lab-specific time origin |
| Events!3 | BRL ammonium bicarbonate addition to MBE[2]+, day 70 | Later differences require an ammonia co-intervention term; not biochar alone |
| Events!4 | LBE trace-element solution change for IV.1–IV.9, day 128; water for IV.10–IV.15 | Reconstruct bottle-specific supplementation |
| Events!5 | Some LBE bottles have altered mixing, days 106–128 | Bottle subset unspecified; do not assume all bottles affected |
| Events!6–7 | IV.3 and IV.2 cease producing after stated cycles | Investigate failure/censoring; do not delete based on poor outcome |
| Events!8–9 | Suspected technical issues in IV.5 and IV.8 at batch 1 | Preserve source exclusion recommendation and verify its duration |

The later `MBE[2]+` / `MBE[2] + N` discrepancy now has supporting ammonia context,
but both original labels remain. Six chemistry rows show this disagreement;
four chemistry rows reproduce the control-label/positive-biochar-mass conflict.
The latter is still unresolved.

`prior_lab_event_rows` means only same-lab events recorded at or before sampling.
It is **not** exposure assignment: an event can concern another bottle, and its
presence does not imply an ongoing intervention. It must not be used directly as
a model feature. Full event text and source IDs are retained for adjudication.

All observations remain unadmitted. Next: verify units and carry-over, map scoped
exposure intervals, adjudicate conflicts, and freeze the external comparison
before fitting. Workbook checksum and row provenance make these decisions auditable.
