from biochar_ad_kinetics.research_apis import ResearchRecord, record_to_dict


def test_record_to_dict_excludes_raw_by_default():
    record = ResearchRecord(
        source="openalex",
        title="Example",
        doi="10.1000/example",
        year=2026,
        url="https://example.org",
        abstract="abstract",
        raw={"provider": "payload"},
    )

    result = record_to_dict(record)

    assert result == {
        "source": "openalex",
        "title": "Example",
        "doi": "10.1000/example",
        "year": 2026,
        "url": "https://example.org",
        "abstract": "abstract",
    }


def test_record_to_dict_can_include_raw():
    record = ResearchRecord(source="datacite", title="Dataset", raw={"id": "abc"})

    result = record_to_dict(record, include_raw=True)

    assert result["raw"] == {"id": "abc"}
