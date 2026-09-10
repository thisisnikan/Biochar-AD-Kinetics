from biochar_ad_kinetics.research_apis import ResearchRecord
from biochar_ad_kinetics.source_ranking import (
    SourceCriteria,
    build_candidate_manifest,
    rank_record,
    rank_sources,
)


def test_high_value_continuous_candidate_scores_above_generic_paper():
    strong = ResearchRecord(
        source="zenodo",
        title=(
            "Continuous anaerobic digestion with biochar: time-series methane data "
            "with untreated control"
        ),
        doi="10.5281/zenodo.123",
        year=2026,
        url="https://zenodo.org/records/123",
    )
    weak = ResearchRecord(
        source="crossref",
        title="Review of carbon materials",
        year=2026,
    )
    criteria = SourceCriteria(
        reactor="continuous",
        require_time_series=True,
        require_control=True,
        year_from=2022,
    )

    ranked = rank_sources([weak, strong], criteria)

    assert ranked[0].record == strong
    assert ranked[0].decision == "acquire_and_audit"
    assert ranked[-1].record == weak


def test_manifest_never_marks_candidate_as_model_ready():
    record = ResearchRecord(
        source="datacite",
        title="Biochar anaerobic digestion methane dataset",
        doi="10.1234/example",
        year=2025,
        url="https://example.org",
    )
    criteria = SourceCriteria()
    ranked = [rank_record(record, criteria)]

    manifest = build_candidate_manifest("biochar AD", ranked, criteria)
    candidate = manifest["candidates"][0]

    assert candidate["status"] == "candidate_only"
    assert candidate["requires_manual_source_audit"] is True
    assert candidate["eligible_for_model_fit"] is False
