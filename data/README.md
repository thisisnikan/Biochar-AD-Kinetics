# Experimental data provenance

## Contribution contract

New reactor-level contributions should use
`templates/reactor_observations.csv` and pass the automated intake gate before an
ingestion script or model is added:

```bash
biochar-ad validate-intake data/templates/reactor_observations.csv
```

See `docs/DATA_CONTRACT.md` for field definitions, validation rules and evidence
limits. Existing historical datasets keep their source-faithful schemas; they should
be mapped explicitly rather than silently renamed.

## Kozłowski et al. (2025)

`experimental/kozlowski_2025_bmp.csv` is a tidy, mechanically derived version of the
publisher's XLSX supplement to:

> Kozłowski, M., Papaj, B., Sobieraj, K., Świechowski, K., Kosiorowska, K. &
> Białowiec, A. *The effect of different carbon materials' addition on the
> biomethane production from food waste*. Scientific Reports 15, 18728 (2025).
> https://doi.org/10.1038/s41598-025-02564-0

- Article and supplement license: CC BY 4.0.
- Publisher supplement: `41598_2025_2564_MOESM1_ESM.xlsx`.
- Verified source SHA-256:
  `a5be0c25990acbdd0a6ac14dfa202398e61713fea8496884018e97f1cf87b983`.
- Experiment: triplicate mesophilic (37 °C) batch digestion for 21 days, with food
  waste alone or a 5 g/L carbon-material addition.
- Raw source columns retained: reactor-level cumulative methane volume and the
  corresponding inoculum-control mean.
- Processed response: blank-corrected cumulative methane divided by substrate VS,
  matching the source workbook's calculation.

### Explicit data-quality decisions

The source workbook's derived `Days` column ends at 5.25 while its hourly index and
day label end at 504 hours and day 21. The tidy dataset therefore defines
`time_days = time_hours / 24` and retains the inconsistent source value in
`source_reported_time_days` for auditability.

Torrefaction replicate 2 and pyrolysis replicate 3 are retained but marked
`included_in_benchmark = false`. The publisher workbook excludes these same reactor
signals from its displayed treatment averages, and their raw trajectories are
inconsistent with sibling reactors. No observations are deleted or silently clipped.

Rebuild the CSV from a local or downloaded source workbook:

```bash
python scripts/build_kozlowski_2025_dataset.py
```

The script verifies the source hash before parsing it.

### Complete reactor-observation export

`experimental/kozlowski_2025_reactor_observations.csv.gz` adds all three individual
inoculum-only blank trajectories to the existing twelve substrate reactors. It
contains 7,575 source-linked observations in the minimum intake contract, with
source metadata and correction inputs retained as extra columns. Blanks have no
substrate-normalized yield. The original benchmark file and exclusions are preserved.

The exporter also records a source conflict in the food-waste control's carbon
mass/dose cells. Zero canonical dose follows the established treatment mapping;
the conflicting source values remain visible pending author clarification.

See the [intake report and gap list](../results/intake/README.md) for commands,
field interpretation, validation findings and scientific limitations.

## Valentin & Białowiec (2024)

`experimental/valentin_bialowiec_2024_parameters.csv` transcribes the five dose
conditions and published modified-Gompertz estimates from Table 3 of:

> Valentin, M. T. & Białowiec, A. *Impact of using glucose as a sole carbon
> source to analyze the effect of biochar on the kinetics of biomethane
> production*. Scientific Reports 14, 8656 (2024).
> https://doi.org/10.1038/s41598-024-59313-y

- Article license: CC BY 4.0.
- Experiment: triplicate 37 °C reactors with glucose, wheat-straw biochar
  produced at 900 °C, and doses of 0, 2, 4, 6, and 8 g/L.
- Scope: exact table-level cumulative BMP, fit statistics, potential, maximum
  rate, rate constant, and lag; these are published estimates, not raw reactor
  trajectories.
- The article reports 86,400 raw cases but states that those data are available
  from the corresponding author on reasonable request. They are not reconstructed
  or represented here as open raw data.

## Zhang et al. (2022)

`experimental/zhang_2022_biochar_characteristics.csv` contains the five
pyrolysis-temperature biochar descriptors reported in Table 1 and the Raman
`I_D/I_G` values reported in the article text:

> Zhang, C., Yang, R., Sun, M. et al. Wood waste biochar promoted anaerobic
> digestion of food waste: focusing on the characteristics of biochar and
> microbial community analysis. Biochar 4, 62 (2022).
> https://doi.org/10.1007/s42773-022-00187-6

- Article license: CC BY 4.0.
- Experiment: triplicate 37 °C food-waste batch digestion with 10 g/L wood-waste
  biochar prepared at several pyrolysis temperatures and residence times.
- The public table records surface O/C ratio, XPS-derived oxygen-containing bond
  percentages, and Raman `I_D/I_G`; it does not infer missing properties.

On 2026-08-26, Chao Zhang also shared a workbook containing post-processed
treatment means and standard deviations for cumulative methane, pH, and six VFAs.
The methane series are already inoculum-blank corrected. The original triplicate
files are no longer available, so the shared workbook cannot support
replicate-held-out validation or empirical replicate resampling.

The workbook is not redistributed while public-repository permission is pending.
`scripts/build_zhang_2022_dataset.py` verifies the private source hash and builds
ignored long-form methane and process-monitoring tables:

```bash
python scripts/build_zhang_2022_dataset.py --source /path/to/Data.xlsx
```

No pseudo-replicates are generated. Any model fitted to these summary curves must
identify its uncertainty and validation limits explicitly.

## CDU / Wang (2026)

`experimental/cdu_wang_2026_pyrolysis_temperature.csv` transcribes the published
summary values (final methane yield mean/SD, BET surface area, electrical
conductivity, pH) for six green-waste biochars and one activated-carbon
comparator from:

> Wang, C. *Anaerobic Digestion of Mixed Green Waste to Produce Methane-rich
> Biogas*. PhD thesis, Charles Darwin University (2026).
> https://doi.org/10.25913/xgzk-zs88

- **Access/licence status: not independently verified.** This project could not
  confirm the thesis's open-access terms from this environment (the DOI resolver
  and institutional-repository domains were unreachable). Only the specific
  numeric values already summarised in the project's own outreach tracking
  (issue #10) are transcribed here, with full citation; treat this as a
  published-summary transcription pending explicit confirmation of the
  thesis's distribution terms, not as a redistribution of the thesis itself.
- Experiment: triplicate 37 °C mixed-green-waste batch digestion, biochar dose
  10 g/L (1% w/v), biochars pyrolyzed at 400-900 °C, compared against activated
  carbon and a no-conductive-material control. Reported over a 50-day
  conductive-material experiment.
- Scope: six-point pyrolysis-temperature summary series (methane yield only for
  the six biochars; descriptors only, no yield, for activated carbon). No
  reactor-level trajectories, no control's own methane yield, and no raw
  microbial or electrochemical data are included — the thesis reports
  microbial-community analysis, but it is not transcribed here since ingesting
  it would need its own reviewed data contract.
- Deliberately **not** transcribed: the thesis's ~128% "methane-potential
  enhancement" claim. The three published kinetic models yield different
  P900/control ratios for that figure, and the control's own absolute methane
  yield is not given in the material this repository has access to — see
  `docs/MECHANISM_EVIDENCE.md` and issue #10 for the open request to the author
  for clarification and raw reactor-level data.
- `biochar-ad benchmark-pyrolysis-temperature` reports leave-one-biochar-out
  RMSE for temperature-response forms *and* the pairwise correlation among
  temperature, BET, conductivity and pH — the four descriptors move together
  by construction in this six-point series, so the CLI flags them as confounded
  rather than attributing any trend to one specific property.

## Chiappero et al. (2022)

> Chiappero, M., Fiore, S. & Berruti, F. *Impact of biochar on anaerobic
> digestion: Meta-analysis and economic evaluation*. Journal of Environmental
> Chemical Engineering 10, 108870 (2022).
> https://doi.org/10.1016/j.jece.2022.108870

- **Closed-access, standard-copyright source.** Unlike every other article cited
  in this file, this is a standard Elsevier copyright publication, not CC BY. No
  table, figure or figure-derived number from the paper is reproduced here.
- **Literature synthesis, not primary data.** This is a meta-analysis aggregating
  408 batch conditions from 76 published studies and 83 semi-continuous conditions
  from 18 published studies. It reports pooled statistics across other authors'
  experiments, not a single reactor trajectory of its own.
- **No file is added to `data/experimental/` for this source**, and none should
  be: a meta-analysis has no reactor-level or condition-level rows of its own to
  transcribe into this project's per-observation schema, and its closed-copyright
  status would forbid transcribing its summary tables even if it did. Its only
  role in this project is as literature context that motivates the *shape* of the
  dose-response term in `src/biochar_ad_kinetics/model.py` — it is not evidence for or
  against this project's specific fitted parameters, and it is not used by any
  script or benchmark.
- Cited findings (the paper's own stated summary statistics and formulas; verify
  against the source before citing further):
  - Overall meta-analytic effect of biochar addition: Hedges' g = 2.43 (95% CI
    2.02–2.84) on cumulative methane yield; g = 2.54 (95% CI 1.86–3.22) on maximum
    production rate (Rmax); g = -1.74 (95% CI -2.60 to -0.88) on lag-phase duration
    (a negative g here means a shorter lag).
  - Suggested optimal biochar physico-chemical property ranges for enhancing
    methane yield: high ash content (≥20%), low total carbon (<50%), high O/C
    molar ratio (≥0.3), high oxygen content (≥20%), high nitrogen content (≥0.6%),
    acidic pH (<7.0), and low surface area (<10 m²/g). The paper notes sludge- and
    manure-derived biochars tend to meet this profile, while wood-derived biochars
    tend not to.
  - Economic model relating maximum sustainable biochar unit cost to dose:
    log(y) = 1.545 − 1.313·log(x), where y is the maximum sustainable biochar cost
    in USD per tonne and x is the biochar dose in g biochar/g VS (R² = 0.8076). The
    paper reads this as an argument against doses above roughly 0.45–0.76 g
    biochar/g VS on economic grounds alone, independent of any biochar-property
    effect.
  - The paper's own aggregated dose-response was non-monotonic: moderate doses
    were associated with enhancement, while excessive doses (particularly above
    15-20 g/L in the studies it aggregates) trended toward inhibition. This is
    literature support for — not independent validation of — this project's choice
    of a non-monotonic, log-based dose term (see
    [`docs/PROJECT_STATUS.md`](../docs/PROJECT_STATUS.md) for the exact framing).

## García-Prats CYPRUS2025 extended abstract (author-shared, unpublished)

> García-Prats, M., González, D. & Sánchez, A. *Unveiling the relationships
> between biochar characteristics and its beneficial effects in the anaerobic
> digestion of the organic fraction of municipal solid waste (OFMSW)*.
> Extended abstract presented at CYPRUS2025.

- **Unpublished, author-shared, not redistributed.** Marta García-Prats shared
  this extended abstract directly with this project by email on 2026-09-02, as
  part of an active research collaboration. She has stated explicitly that the
  full paper is under revision and not yet public. Following the same
  restriction already applied to the Zhang et al. (2022) private workbook, no
  part of it — not the source file, not its full text, not its figures, and
  not its numeric values — is committed to this public repository without her
  explicit redistribution permission.
- **No data file is added to `data/experimental/` for this source.** The
  abstract contains structured tables (biochar characteristics, kinetic
  parameters and a property/outcome correlation analysis for nine biochars:
  ``PP300``/``PP400``/``PP500``/``PH300``/``PH400``/``PH500``/``Q300``/
  ``Q400``/``Q500``), but every value in them is unpublished author-shared
  data, not this project's own.
- `scripts/build_garcia_prats_cyprus2025_dataset.py` mirrors the Zhang
  ingestion pattern: a maintainer transcribes the abstract's tables into a
  private local workbook (schema documented in the script's own docstring),
  the script verifies the source file's SHA-256 hash, and it writes ignored,
  gitignored long-form CSVs under `data/private/garcia_prats_cyprus2025/` —
  never into a tracked path:

  ```bash
  python scripts/build_garcia_prats_cyprus2025_dataset.py --source /path/to/garcia_prats_cyprus2025.xlsx
  ```

  Unlike the Zhang script, this project has never had access to the real
  source file, so no hash could be pre-recorded; the script computes and
  prints the source hash on first use so a maintainer can confirm it with the
  author out of band and record it for future, verified runs.
- Any value in the abstract that is only visible as a bar-chart height, with
  no number stated in the text, is transcribed into the private workbook as
  `not_machine_extractable = TRUE` with no value, rather than estimated from
  the chart. No pseudo-replicates are generated, and no chart-derived number
  is invented.
- This dataset is for private model testing under the existing research
  collaboration only. It is not a substitute for public reproduction,
  independent validation, or peer review, and none of those claims should be
  made from it.
