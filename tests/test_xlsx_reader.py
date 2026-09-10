"""Round-trip tests for the shared minimal XLSX reader.

Before ``xlsx_reader.py`` existed, none of the five scripts that duplicated
this parsing logic had a test that actually exercised it against a real
.xlsx file. These tests build minimal, valid workbooks by hand (no Excel
engine dependency, matching the project's own constraint) and read them
back through the shared module.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from biochar_ad_kinetics.xlsx_reader import (
    column_number,
    read_shared_strings,
    read_sheet_paths,
    read_workbook,
)

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
{sheet_overrides}
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

WORKBOOK = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets>
{sheet_entries}
</sheets>
</workbook>"""

WORKBOOK_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rIdSS" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
{sheet_rels}
</Relationships>"""

SHARED_STRINGS_TEMPLATE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{count}" uniqueCount="{count}">
{items}
</sst>"""


def _build_xlsx(path: Path, sheets: dict[str, str], strings: list[str]) -> None:
    """Write a minimal valid .xlsx with the given raw <sheetData> bodies."""
    sheet_names = list(sheets)
    sheet_entries = "\n".join(
        f'<sheet name="{name}" sheetId="{index + 1}" r:id="rIdSheet{index + 1}"/>'
        for index, name in enumerate(sheet_names)
    )
    sheet_rels = "\n".join(
        (
            f'<Relationship Id="rIdSheet{index + 1}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{index + 1}.xml"/>'
        )
        for index in range(len(sheet_names))
    )
    sheet_overrides = "\n".join(
        (
            f'<Override PartName="/xl/worksheets/sheet{index + 1}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        )
        for index in range(len(sheet_names))
    )
    items = "\n".join(f"<si><t>{text}</t></si>" for text in strings)

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml", CONTENT_TYPES.format(sheet_overrides=sheet_overrides)
        )
        archive.writestr("_rels/.rels", ROOT_RELS)
        archive.writestr("xl/workbook.xml", WORKBOOK.format(sheet_entries=sheet_entries))
        archive.writestr(
            "xl/_rels/workbook.xml.rels", WORKBOOK_RELS.format(sheet_rels=sheet_rels)
        )
        archive.writestr(
            "xl/sharedStrings.xml",
            SHARED_STRINGS_TEMPLATE.format(count=len(strings), items=items),
        )
        for index, name in enumerate(sheet_names):
            archive.writestr(f"xl/worksheets/sheet{index + 1}.xml", sheets[name])


SHEET_XML_NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'


def _sheet_xml(rows_xml: str) -> str:
    return f'<worksheet {SHEET_XML_NS}><sheetData>{rows_xml}</sheetData></worksheet>'


def test_read_workbook_handles_shared_strings_numbers_and_inline_strings(tmp_path):
    path = tmp_path / "sample.xlsx"
    sheet_one = _sheet_xml(
        '<row r="1">'
        '<c r="A1" t="s"><v>0</v></c>'
        '<c r="B1"><v>12.5</v></c>'
        "</row>"
        '<row r="2">'
        '<c r="A2" t="inlineStr"><is><t>inline note</t></is></c>'
        '<c r="B2"><v>0</v></c>'
        "</row>"
    )
    sheet_two = _sheet_xml('<row r="1"><c r="A1" t="s"><v>1</v></c></row>')
    _build_xlsx(
        path,
        {"characteristics": sheet_one, "kinetics": sheet_two},
        strings=["header", "second_sheet_value"],
    )

    workbook = read_workbook(path)

    assert workbook["characteristics"] == [
        ["header", 12.5],
        ["inline note", 0.0],
    ]
    assert workbook["kinetics"] == [["second_sheet_value"]]


def test_read_workbook_can_restrict_to_named_sheets(tmp_path):
    path = tmp_path / "sample.xlsx"
    sheet_one = _sheet_xml('<row r="1"><c r="A1"><v>1</v></c></row>')
    sheet_two = _sheet_xml('<row r="1"><c r="A1"><v>2</v></c></row>')
    _build_xlsx(path, {"one": sheet_one, "two": sheet_two}, strings=[])

    only_one = read_workbook(path, sheet_names=("one",))

    assert set(only_one) == {"one"}
    assert only_one["one"] == [[1.0]]


def test_read_workbook_reports_missing_requested_sheet(tmp_path):
    path = tmp_path / "sample.xlsx"
    sheet_one = _sheet_xml('<row r="1"><c r="A1"><v>1</v></c></row>')
    _build_xlsx(path, {"one": sheet_one}, strings=[])

    with pytest.raises(ValueError, match="Missing worksheets: two"):
        read_workbook(path, sheet_names=("two",))


def test_column_number_matches_spreadsheet_letter_convention():
    assert column_number("A1") == 1
    assert column_number("Z10") == 26
    assert column_number("AA1") == 27
    assert column_number("AB12") == 28


def test_read_sheet_paths_and_shared_strings_are_queryable_independently(tmp_path):
    path = tmp_path / "sample.xlsx"
    sheet_one = _sheet_xml('<row r="1"><c r="A1" t="s"><v>0</v></c></row>')
    _build_xlsx(path, {"only_sheet": sheet_one}, strings=["hello"])

    with zipfile.ZipFile(path) as archive:
        paths = read_sheet_paths(archive)
        strings = read_shared_strings(archive)

    assert paths == {"only_sheet": "xl/worksheets/sheet1.xml"}
    assert strings == ["hello"]
