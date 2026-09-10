"""Optional HTTP gateway for research discovery and source ranking.

Install with ``pip install -e '.[service]'`` and run:
``uvicorn biochar_ad_kinetics.api_service:app --reload``.
"""

from __future__ import annotations

from typing import Any

try:
    from fastapi import FastAPI, Query
except ImportError as exc:  # pragma: no cover - exercised only without service extra
    raise RuntimeError(
        "FastAPI service dependencies are not installed. Use: pip install -e '.[service]'"
    ) from exc

from .research_apis import record_to_dict, search_all
from .source_ranking import SourceCriteria, build_candidate_manifest, rank_sources

app = FastAPI(
    title="Biochar-AD-Kinetics Research Gateway",
    version="0.1.0",
    description=(
        "Research-source discovery and scientific screening gateway. "
        "It does not bypass repository intake/QC or alter kinetic-model logic."
    ),
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/research/search")
def research_search(
    q: str = Query(..., min_length=3),
    limit_per_source: int = Query(10, ge=1, le=50),
) -> dict[str, Any]:
    records = search_all(q, limit_per_source=limit_per_source)
    return {
        "query": q,
        "count": len(records),
        "records": [record_to_dict(record) for record in records],
    }


@app.get("/research/candidates")
def research_candidates(
    q: str = Query(..., min_length=3),
    reactor: str | None = Query(None),
    require_time_series: bool = Query(False),
    require_control: bool = Query(False),
    year_from: int | None = Query(None, ge=1900, le=2100),
    limit_per_source: int = Query(10, ge=1, le=50),
) -> dict[str, object]:
    criteria = SourceCriteria(
        reactor=reactor,
        require_time_series=require_time_series,
        require_control=require_control,
        year_from=year_from,
    )
    records = search_all(q, limit_per_source=limit_per_source)
    ranked = rank_sources(records, criteria)
    return build_candidate_manifest(q, ranked, criteria)
