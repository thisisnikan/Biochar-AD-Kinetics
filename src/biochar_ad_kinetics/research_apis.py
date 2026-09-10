"""Lightweight clients for public research-metadata APIs.

This module intentionally uses only the Python standard library so API-based
source discovery does not add runtime dependencies or affect scientific model
logic. All functions return normalized dictionaries suitable for provenance
tracking and downstream source-selection workflows.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_USER_AGENT = "Biochar-AD-Kinetics/0.1 (+https://github.com/thisisnikan/Biochar-AD-Kinetics)"


@dataclass(frozen=True)
class ResearchRecord:
    source: str
    title: str
    doi: str | None = None
    year: int | None = None
    url: str | None = None
    abstract: str | None = None
    raw: dict[str, Any] | None = None


def _get_json(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    request_headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    request = Request(url, headers=request_headers)
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def search_openalex(
    query: str,
    per_page: int = 25,
    api_key: str | None = None,
) -> list[ResearchRecord]:
    """Search OpenAlex works and normalize core bibliographic fields."""
    params = {"search": query, "per-page": max(1, min(per_page, 100))}
    key = api_key or os.getenv("OPENALEX_API_KEY")
    if key:
        params["api_key"] = key
    payload = _get_json(f"https://api.openalex.org/works?{urlencode(params)}")
    records: list[ResearchRecord] = []
    for item in payload.get("results", []):
        primary = item.get("primary_location") or {}
        records.append(
            ResearchRecord(
                source="openalex",
                title=item.get("display_name") or item.get("title") or "",
                doi=(item.get("doi") or "").removeprefix("https://doi.org/") or None,
                year=item.get("publication_year"),
                url=primary.get("landing_page_url") or item.get("id"),
                raw=item,
            )
        )
    return records


def search_crossref(
    query: str,
    rows: int = 25,
    mailto: str | None = None,
) -> list[ResearchRecord]:
    """Search Crossref works using the polite pool when an email is provided."""
    params: dict[str, Any] = {
        "query.bibliographic": query,
        "rows": max(1, min(rows, 1000)),
    }
    email = mailto or os.getenv("CROSSREF_MAILTO")
    if email:
        params["mailto"] = email
    payload = _get_json(f"https://api.crossref.org/works?{urlencode(params)}")
    records: list[ResearchRecord] = []
    for item in payload.get("message", {}).get("items", []):
        titles = item.get("title") or []
        published = item.get("published-print") or item.get("published-online") or {}
        parts = published.get("date-parts") or []
        year = parts[0][0] if parts and parts[0] else None
        records.append(
            ResearchRecord(
                source="crossref",
                title=titles[0] if titles else "",
                doi=item.get("DOI"),
                year=year,
                url=item.get("URL"),
                abstract=item.get("abstract"),
                raw=item,
            )
        )
    return records


def search_datacite(query: str, page_size: int = 25) -> list[ResearchRecord]:
    """Search DataCite DOI metadata, useful for datasets and repository records."""
    params = {"query": query, "page[size]": max(1, min(page_size, 1000))}
    payload = _get_json(f"https://api.datacite.org/dois?{urlencode(params)}")
    records: list[ResearchRecord] = []
    for item in payload.get("data", []):
        attrs = item.get("attributes", {})
        titles = attrs.get("titles") or []
        title = titles[0].get("title", "") if titles else ""
        year = attrs.get("publicationYear")
        doi = attrs.get("doi") or item.get("id")
        records.append(
            ResearchRecord(
                source="datacite",
                title=title,
                doi=doi,
                year=(
                    int(year)
                    if isinstance(year, (int, str)) and str(year).isdigit()
                    else None
                ),
                url=attrs.get("url") or (f"https://doi.org/{doi}" if doi else None),
                raw=item,
            )
        )
    return records


def search_zenodo(query: str, size: int = 25) -> list[ResearchRecord]:
    """Search published Zenodo records for datasets, software, and related outputs."""
    params = {"q": query, "size": max(1, min(size, 100))}
    payload = _get_json(f"https://zenodo.org/api/records?{urlencode(params)}")
    records: list[ResearchRecord] = []
    for item in payload.get("hits", {}).get("hits", []):
        metadata = item.get("metadata", {})
        publication_date = metadata.get("publication_date") or ""
        year = int(publication_date[:4]) if publication_date[:4].isdigit() else None
        records.append(
            ResearchRecord(
                source="zenodo",
                title=metadata.get("title") or "",
                doi=item.get("doi") or metadata.get("doi"),
                year=year,
                url=(item.get("links") or {}).get("html"),
                abstract=metadata.get("description"),
                raw=item,
            )
        )
    return records


def search_semantic_scholar(
    query: str,
    limit: int = 25,
    api_key: str | None = None,
) -> list[ResearchRecord]:
    """Search Semantic Scholar; API key is optional but useful for higher limits."""
    fields = "title,year,url,externalIds,abstract"
    params = {"query": query, "limit": max(1, min(limit, 100)), "fields": fields}
    headers: dict[str, str] = {}
    key = api_key or os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    if key:
        headers["x-api-key"] = key
    payload = _get_json(
        f"https://api.semanticscholar.org/graph/v1/paper/search?{urlencode(params)}",
        headers=headers,
    )
    records: list[ResearchRecord] = []
    for item in payload.get("data", []):
        external_ids = item.get("externalIds") or {}
        records.append(
            ResearchRecord(
                source="semantic_scholar",
                title=item.get("title") or "",
                doi=external_ids.get("DOI"),
                year=item.get("year"),
                url=item.get("url"),
                abstract=item.get("abstract"),
                raw=item,
            )
        )
    return records


def search_all(query: str, limit_per_source: int = 20) -> list[ResearchRecord]:
    """Search all configured public research APIs and de-duplicate by DOI/title."""
    collectors = (
        lambda: search_openalex(query, limit_per_source),
        lambda: search_crossref(query, limit_per_source),
        lambda: search_datacite(query, limit_per_source),
        lambda: search_zenodo(query, limit_per_source),
        lambda: search_semantic_scholar(query, limit_per_source),
    )

    merged: list[ResearchRecord] = []
    seen: set[str] = set()
    for collect in collectors:
        try:
            records = collect()
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            continue
        for record in records:
            key = (record.doi or record.title).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(record)
    return merged


def record_to_dict(
    record: ResearchRecord,
    include_raw: bool = False,
) -> dict[str, Any]:
    data = {
        "source": record.source,
        "title": record.title,
        "doi": record.doi,
        "year": record.year,
        "url": record.url,
        "abstract": record.abstract,
    }
    if include_raw:
        data["raw"] = record.raw
    return data
