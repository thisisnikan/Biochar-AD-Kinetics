# Research gateway

The repository exposes an optional FastAPI service for research-source discovery and candidate ranking.

## Install

```bash
python -m pip install -e ".[service]"
uvicorn biochar_ad_kinetics.api_service:app --reload
```

## Endpoints

### `GET /health`

Simple service health check.

### `GET /research/search`

Searches OpenAlex, Crossref, DataCite, Zenodo, and Semantic Scholar, then returns de-duplicated normalized research records.

Example:

```text
/research/search?q=continuous%20anaerobic%20digestion%20biochar&limit_per_source=10
```

### `GET /research/candidates`

Searches the same providers, then ranks candidates for scientific follow-up.

Example:

```text
/research/candidates?q=biochar%20anaerobic%20digestion&reactor=continuous&require_time_series=true&require_control=true&year_from=2022
```

The response includes a machine-readable manifest with:

- score,
- decision (`acquire_and_audit`, `manual_screen`, or `low_priority`),
- reasons,
- DOI and source URL,
- explicit candidate-only status,
- a mandatory manual-source-audit flag,
- `eligible_for_model_fit=false`.

## Scientific boundary

The API gateway is a discovery and triage layer only. It does not make a paper or repository record scientifically valid for modelling.

The permitted workflow is:

```text
research API discovery
    -> candidate ranking
    -> original-source audit
    -> raw/supplementary data acquisition
    -> provenance registration
    -> existing intake/QC validation
    -> model fitting / effect estimation
    -> external validation
```

This boundary is deliberate. Keyword-based ranking can prioritize likely useful sources, but it cannot verify reactor completeness, replicate structure, blank correction, dose basis, missing time points, or experimental exclusions.

## ChatGPT / agent integration

The HTTP service provides a stable machine-readable surface for an agent or ChatGPT-compatible tool layer. The recommended tool operations are:

- `search_research_sources`
- `rank_dataset_candidates`
- later: `audit_candidate_manifest`
- later: `validate_acquired_dataset`
- later: `run_external_validation`

The first two are now supported by the service endpoints. The later operations should reuse the repository's existing provenance and intake/QC contracts rather than creating parallel scientific rules.
