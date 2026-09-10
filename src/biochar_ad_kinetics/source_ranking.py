"""Scientific screening of research API records before data intake.

The scoring here is intentionally conservative: it ranks discovery candidates,
not scientific evidence. Records must still pass source audit and the existing
reactor-level intake/QC gates before entering fitting or validation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from .research_apis import ResearchRecord


@dataclass(frozen=True)
class SourceCriteria:
    reactor: str | None = None
    require_time_series: bool = False
    require_control: bool = False
    require_biochar: bool = True
    year_from: int | None = None


@dataclass(frozen=True)
class RankedSource:
    score: float
    decision: str
    reasons: tuple[str, ...]
    record: ResearchRecord

    def to_manifest(self) -> dict[str, object]:
        return {
            "score": round(self.score, 3),
            "decision": self.decision,
            "reasons": list(self.reasons),
            "source": self.record.source,
            "title": self.record.title,
            "doi": self.record.doi,
            "year": self.record.year,
            "url": self.record.url,
            "status": "candidate_only",
            "requires_manual_source_audit": True,
            "eligible_for_model_fit": False,
        }


def _text(record: ResearchRecord) -> str:
    return f"{record.title} {record.abstract or ''}".lower()


def rank_record(record: ResearchRecord, criteria: SourceCriteria) -> RankedSource:
    text = _text(record)
    score = 0.0
    reasons: list[str] = []

    if "biochar" in text:
        score += 0.22
        reasons.append("biochar mentioned")
    elif criteria.require_biochar:
        score -= 0.30
        reasons.append("biochar not evident")

    if any(term in text for term in ("anaerobic digestion", "methane", "biogas")):
        score += 0.18
        reasons.append("AD/methane relevance")

    if any(term in text for term in ("time series", "time-series", "daily methane", "cumulative methane")):
        score += 0.18
        reasons.append("time-series signal")
    elif criteria.require_time_series:
        score -= 0.10
        reasons.append("time series not evident")

    if any(term in text for term in ("control", "untreated", "blank")):
        score += 0.12
        reasons.append("control/comparator signal")
    elif criteria.require_control:
        score -= 0.08
        reasons.append("control not evident")

    reactor = (criteria.reactor or "").lower().strip()
    if reactor:
        reactor_terms = {
            "continuous": ("continuous", "cstr", "semi-continuous", "semicontinuous"),
            "batch": ("batch", "bmp", "biochemical methane potential"),
        }.get(reactor, (reactor,))
        if any(term in text for term in reactor_terms):
            score += 0.14
            reasons.append(f"{reactor} reactor relevance")
        else:
            score -= 0.06
            reasons.append(f"{reactor} reactor not evident")

    if record.source in {"datacite", "zenodo"}:
        score += 0.08
        reasons.append("repository/dataset-oriented source")

    if record.doi:
        score += 0.05
        reasons.append("DOI provenance")
    if record.url:
        score += 0.02
        reasons.append("resolvable source URL")

    if criteria.year_from is not None:
        if record.year is not None and record.year >= criteria.year_from:
            score += 0.05
            reasons.append("within requested year range")
        elif record.year is not None:
            score -= 0.05
            reasons.append("older than requested year range")

    score = max(0.0, min(1.0, score))
    if score >= 0.65:
        decision = "acquire_and_audit"
    elif score >= 0.40:
        decision = "manual_screen"
    else:
        decision = "low_priority"
    return RankedSource(score=score, decision=decision, reasons=tuple(reasons), record=record)


def rank_sources(records: Iterable[ResearchRecord], criteria: SourceCriteria) -> list[RankedSource]:
    ranked = [rank_record(record, criteria) for record in records]
    return sorted(ranked, key=lambda item: (-item.score, item.record.year or 0, item.record.title))


def build_candidate_manifest(
    query: str,
    ranked: Iterable[RankedSource],
    criteria: SourceCriteria,
) -> dict[str, object]:
    entries = [item.to_manifest() for item in ranked]
    return {
        "schema_version": "1.0",
        "query": query,
        "criteria": asdict(criteria),
        "candidate_count": len(entries),
        "scientific_boundary": (
            "Discovery ranking only. No candidate becomes model-fitting or validation data until "
            "the original source is audited and the repository intake/QC contract passes."
        ),
        "candidates": entries,
    }
