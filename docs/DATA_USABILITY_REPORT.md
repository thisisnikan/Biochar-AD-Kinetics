# Data usability report

Project policy (issue #28): a dataset that cannot be used for the active
validation gate must never silently disappear from the workflow. This page
collects every dataset the project has screened, acquired, or attempted to
acquire and is currently **not fully usable** for its intended purpose, in one
place, with the same fields for each:

- **Intended use** — what the dataset was being evaluated for.
- **Status** — `usable`, `partially usable`, or `not usable`.
- **Blocking reason(s)** — exactly why, as of the date recorded.
- **Resolvable by requesting more data/metadata?** — yes / no / partially.
- **What would unlock use** — the concrete missing item.

A dataset only usable for descriptive context or a parameter-level challenge
is recorded here as **partially usable** and its restriction is stated
explicitly, so it is never later cited as reactor-level Stage A/B validation.
Fully usable datasets (Kozłowski et al. 2025, Daskaloudis 2026) are not
repeated here; their own known limitations are tracked in
[`results/intake/README.md`](../results/intake/README.md) and
[`docs/DATA_EXPANSION_REGISTRY.md`](DATA_EXPANSION_REGISTRY.md) respectively.

## Not usable — access blocked

### Cai Jiao Tongji thesis, BMP query records 583–594
- **Intended use:** Stage A dose × ISR interaction kinetic validation (lag, Pmax, Rmax) — [issue #30](https://github.com/thisisnikan/Biochar-AD-Kinetics/issues/30).
- **Status:** not usable for training/validation. The two committed manifests
  (`data/candidate_manifests/cai_jiao_bmp_records_583_594.csv` and
  `cai_2016_aggregate_evidence.csv`) are provenance-only and are not model input.
- **Blocking reason(s):** on 2026-09-10 `https://bmp.wmdatabase.cn/` returned an
  expired-certificate error before the registration/login page, so no secure
  official export was possible (see [`docs/CAI_BMP_INGESTION_GATE.md`](CAI_BMP_INGESTION_GATE.md)).
  Re-checked from this repository's execution environment on 2026-09-17: the
  outbound network policy itself now returns `403` for this domain before any
  TLS handshake is attempted, so the certificate state could not be re-verified
  this session either. Neither result should be read as the source being
  permanently unreachable — both are environment-side blocks, not a source
  outage confirmed from an unrestricted network.
- **Resolvable by requesting more data/metadata?** Partially. The certificate
  problem is the database operator's to fix, not something a data request
  resolves. A primary thesis table/figure obtained directly (library
  request, inter-library loan, or the author) would bypass the database
  entirely and is the more tractable path.
- **What would unlock use:** the official database export (once reachable
  over a verifiable HTTPS connection) or a primary thesis table/figure,
  with a recorded file checksum and a verified per-query-ID mapping to ISR
  and biochar dose (see the ten admission checks in
  [`docs/CAI_BMP_INGESTION_GATE.md`](CAI_BMP_INGESTION_GATE.md)).

### Wambugu et al. (2019) — paired continuous UASB reactors
- **Intended use:** parallel control/treatment continuous-reactor Stage A/B candidate (DOI `10.3389/fenrg.2019.00014`).
- **Status:** not usable. Only paper-reported summary values (e.g. 47% vs.
  77% average COD removal at OLR 6.9–7.8 g COD/L/d) are available; no
  reactor-level time series has been located.
- **Blocking reason(s):** a targeted search did not confirm a public
  machine-readable raw longitudinal file or an accompanying thesis dataset.
- **Resolvable by requesting more data/metadata?** Yes, in principle —
  contacting the authors for the underlying per-day time series is the
  standard next step; it has not been attempted yet.
- **What would unlock use:** author-supplied per-reactor daily time series
  (COD, pH, VFA, gas production) for both reactors, or a confirmed public
  dataset/thesis link. Figure digitisation remains a last-resort path only,
  per [`docs/DATA_EXPANSION_REGISTRY.md`](DATA_EXPANSION_REGISTRY.md).

## Not usable — not yet ingested (public raw data exists)

### Sanglier et al. (2022) — INRAE/SUEZ repeated-cycle food-waste AD
- **Intended use:** dynamic semi-continuous external validation of methane
  trajectory and VFA response to biochar (1%, 2% w/w) — DOI `10.57745/BUJORT`.
- **Status:** not usable yet. `Process.xlsx`, `SeqArchaea.xlsx`,
  `SeqBacteria.xlsx` and `Python code.zip` are confirmed public, but none has
  been downloaded, cycle-reconstructed or QC'd in this repository
  ([`docs/CONTINUOUS_EXTERNAL_VALIDATION.md`](CONTINUOUS_EXTERNAL_VALIDATION.md)).
- **Blocking reason(s):** cycle identifiers, intervention timing, biochar
  dose and the confounding trace-element co-intervention still need to be
  reconstructed from the raw workbook, and no source-specific QC report has
  been produced.
- **Resolvable by requesting more data/metadata?** No new request is
  needed — the blocker is ingestion engineering, not access.
- **What would unlock use:** an ingestion script that reconstructs cycle
  identifiers and intervention timing, separates the biochar and
  trace-element interventions, preserves raw units/zeros, and emits a
  machine-readable QC report per the admission rules in
  [`docs/DATA_EXPANSION_REGISTRY.md`](DATA_EXPANSION_REGISTRY.md).

### Heitkamp et al. (2021) — seven industrial CSTR digesters
- **Intended use:** external process-stability validation (acetate,
  propionate, butyrate, pH, NH4-N, FOS/TAC, TS/VS) across seven full-scale
  reactors — DOI `10.1186/s13068-021-02034-5`.
- **Status:** not usable yet. The public supplementary workbook
  (`13068_2021_2034_MOESM1_ESM.xlsx`) is filename-confirmed on both Springer
  and PubMed Central but has not been downloaded or ingested.
- **Blocking reason(s):** the file has not yet been materialized into the
  repository; no reactor identity, dose-timing or QC reconstruction exists yet.
- **Resolvable by requesting more data/metadata?** No new request is
  needed — the file is already public.
- **What would unlock use:** downloading and hash-verifying the workbook,
  then reconstructing reactor identity and the two-stage dose schedule
  (1.8 kg/t reactor content, then 1.8 kg/t substrate). Even once ingested,
  this dataset stays **restricted to process-stability validation**: the
  authors explicitly state reliable biogas-productivity data were
  unavailable, so it must never be presented as methane-productivity
  (BMP) validation.

## Partially usable — restricted to a narrower claim than reactor-level validation

### Valentin & Białowiec (2024) — independent glucose BMP dose-response table
- **Intended use:** originally screened as Stage A dose-response validation.
- **Status:** partially usable. It is usable, and already used, as an
  independent **parameter-level challenge** to this project's log-quadratic
  dose-response form (a simpler log-linear form wins on leave-one-dose-out
  RMSE for both methane potential and maximum rate). It is **not usable** as
  Stage A reactor-level validation.
- **Blocking reason(s):** the table has no raw reactor trajectories and no
  per-replicate standard deviation, so no confidence interval can be
  computed for its effect sizes (every row is flagged `low_replication`);
  see [`docs/PROJECT_STATUS.md`](PROJECT_STATUS.md).
- **Resolvable by requesting more data/metadata?** Partially — the
  authors could in principle be asked for per-replicate raw trajectories,
  which is not yet attempted.
- **What would unlock reactor-level use:** raw per-bottle replicate
  trajectories, a zero-dose control and inoculum blanks, matching the
  Stage A dataset contract in [`docs/VALIDATION_PLAN.md`](VALIDATION_PLAN.md).
  Until then, cite this source only as a dose-response functional-form
  challenge, never as reactor-level validation.

### Zhang et al. (2022)
- **Intended use:** reactor-level kinetic validation with intact replicate structure.
- **Status:** partially usable. Author-shared **summary-level** data can be
  analysed and are analysed in this repository, without redistributing the
  private workbook. Replicate-level validation is **not usable**.
- **Blocking reason(s):** the original per-replicate triplicate measurements
  were lost by the source; only summary values remain
  ([`docs/PROJECT_STATUS.md`](PROJECT_STATUS.md)).
- **Resolvable by requesting more data/metadata?** No — the underlying
  raw data no longer exists at the source.
- **What would unlock use:** nothing recoverable is known; this ceiling is
  permanent unless the authors locate an independent copy of the original
  triplicate records.

### CDU / Wang (2026) thesis — pyrolysis-temperature summary table
- **Intended use:** originally of interest for a possible DIET
  (direct interspecies electron transfer) mechanism claim.
- **Status:** partially usable. The six-biochar summary table is usable for
  the specific, narrow check `benchmark-pyrolysis-temperature` performs: a
  descriptive temperature-vs-yield trend, reported alongside the
  temperature/BET/conductivity/pH collinearity among the table's own
  descriptors. It is **not usable** for a DIET or other mechanism claim, and
  not usable for full reactor-level validation.
- **Blocking reason(s):** the ingested table carries none of the thesis's
  microbial or electrochemical data, so it grades only Moderate-at-most on
  the [mechanism-evidence rubric](MECHANISM_EVIDENCE.md); pyrolysis
  temperature, BET, conductivity and pH are collinear in this table, so no
  trend can be attributed to one descriptor; and the thesis's own
  access/distribution terms have not been independently confirmed from this
  repository's network environment.
- **Resolvable by requesting more data/metadata?** Yes, for the mechanism
  and attribution questions — raw reactor-level and microbial data have
  already been requested from the thesis author (tracked in the project's
  outreach pipeline; see [`docs/MECHANISM_EVIDENCE.md`](MECHANISM_EVIDENCE.md)).
  Not resolvable by request for the descriptor-collinearity limitation,
  which is a property of the six biochars actually reported.
- **What would unlock broader use:** reactor-level raw trajectories and the
  thesis's microbial-community data (for mechanism grading), and an
  independent temperature series without confounded descriptors (for
  attributing the trend to one property).

## Not usable — structurally excluded regardless of access

### Kalantzis et al. (2023) — continuous GAC pilot reactor
- **Intended use:** none as biochar validation. Retained only as a candidate
  mechanistic comparator for conductive-carbon amendment in general
  (DOI `10.1016/j.biortech.2023.128908`).
- **Status:** not usable as biochar evidence, structurally, regardless of
  access: granular activated carbon (GAC) is not biochar and must never be
  pooled into a biochar treatment class or used as direct biochar external
  validation.
- **Blocking reason(s):** raw reactor-level data has also not been
  confirmed public, which is a secondary reason even if the material
  restriction were lifted.
- **Resolvable by requesting more data/metadata?** No — the material-class
  restriction is not a data-access problem.
- **What would unlock use:** nothing unlocks use as biochar validation. Raw
  reactor data would only unlock its existing, narrower role as a
  conductive-carbon mechanism comparator.

## Not usable — screened only, not yet acquired

These three sources come from the [5 September 2026 source screening](VALIDATION_PLAN.md#source-screening-on-5-september-2026)
for Stage A dose-response candidates. None has been contacted for raw data.

| Source | Intended use | Status | Blocking reason | Resolvable by request? | What would unlock use |
| --- | --- | --- | --- | --- | --- |
| Garcia-Prats et al. (2024) | Stage A dose-response (three materials, 1/5/10 %-TS doses) | not usable | Raw bottle trajectories, blanks and dose-conversion metadata not yet obtained | Yes — a prior author contact is already listed in issue #11 | Per-bottle raw time series, blanks, dose-unit conversion basis |
| Qiu (2026) | Independent triplicate-batch Stage A candidate | not usable | Raw time-point replicate access not verified; the existing `data/qiu-2026-imperial` branch holds only literature parameter tables, not raw trajectories | Not yet attempted | Confirmed access to per-bottle/per-replicate raw trajectories |
| Vayena (2024) | Material-response lead | not usable | Zenodo record lists an article PDF and a linked supplementary DOCX (CC BY 4.0), but this does not establish a downloadable reactor-level table | Supplement not yet inspected | Inspection of the supplementary DOCX to confirm whether a reactor-level table exists |

## Maintenance rule

Whenever a dataset is screened, an acquisition attempt is made, or an
existing entry's blocker changes, update this page in the same change that
touches the dataset — do not let this list fall out of sync with
[`docs/DATA_EXPANSION_REGISTRY.md`](DATA_EXPANSION_REGISTRY.md),
[`docs/VALIDATION_PLAN.md`](VALIDATION_PLAN.md) or the source-specific
ingestion-gate pages. If a dataset becomes fully usable for its originally
intended purpose, move its entry out of this report and into the relevant
"ready" section of `docs/DATA_EXPANSION_REGISTRY.md`.
