# Research API integration

The repository can discover candidate literature, datasets, and research outputs through a small API layer without changing any kinetic equations or fitting logic.

## Providers

- **OpenAlex** — broad scholarly discovery across works, authors, institutions, and topics.
- **Crossref** — DOI-centric bibliographic metadata and provenance.
- **DataCite** — particularly useful for datasets, software, and repository-issued DOIs.
- **Zenodo** — research outputs and deposited datasets/software.
- **Semantic Scholar** — optional literature enrichment and abstract retrieval.

The implementation lives in `src/biochar_ad_kinetics/research_apis.py` and uses only the Python standard library.

## Usage

Install the package in editable mode, then run:

```bash
python -m pip install -e .
python scripts/search_research_apis.py "biochar anaerobic digestion methane"
```

Save normalized results:

```bash
python scripts/search_research_apis.py \
  "continuous anaerobic digestion biochar" \
  --limit 20 \
  --output outputs/api_search.json
```

Each normalized record contains:

```json
{
  "source": "openalex",
  "title": "...",
  "doi": "10.xxxx/...",
  "year": 2026,
  "url": "https://...",
  "abstract": null
}
```

Duplicate records are removed using DOI when available and title otherwise.

## Optional environment variables

```bash
export OPENALEX_API_KEY="..."
export CROSSREF_MAILTO="your-email@example.com"
export SEMANTIC_SCHOLAR_API_KEY="..."
```

These are optional. Never commit API keys to the repository.

## Intended workflow

```text
Research APIs
    ↓
normalized candidate records
    ↓
source relevance / provenance screening
    ↓
dataset acquisition or manual author-provided files
    ↓
existing intake/QC pipeline
    ↓
kinetic fitting + effect estimation
    ↓
external validation
```

This separation is deliberate: API discovery does **not** automatically convert a paper or repository record into scientific evidence. Candidate data still pass through the existing provenance and QC workflow before model fitting.

## Recommended next step

Add a source-ranking command that scores records for:

1. actual time-series methane/biogas data,
2. biochar treatment/control comparability,
3. continuous vs batch reactor relevance,
4. raw/supplementary data availability,
5. independent-validation value,
6. DOI/repository provenance quality.

That ranking should produce a manifest for `intake.py`, rather than bypassing the current scientific data checks.
