"""Shared minimal XLSX reader used by the dataset-ingestion and inventory scripts.

Every ingestion script under ``scripts/`` needs to read a plain ``.xlsx``
workbook without pulling in a full Excel-engine dependency, because these
scripts handle files that must never be committed to this repository
(private author-shared data) or that the project deliberately keeps
dependency-light and auditable. Before this module existed, several
scripts each carried their own near-identical copy of this
zipfile/ElementTree parsing. This is now the one shared implementation of
the boilerplate every one of them needs: column-letter parsing,
shared-string lookup, sheet-name-to-path resolution, and a typed cell
reader for scripts that transform tabular data. Callers that need
different cell semantics (for example, raw provenance inventory, which
must show unmodified text rather than coerced floats) still own that
logic themselves, built on top of the shared primitives here.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

XML_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def column_number(reference: str) -> int:
    """Convert a cell reference such as "AB12" to a 1-indexed column number."""
    letters = "".join(character for character in reference if character.isalpha())
    result = 0
    for character in letters.upper():
        result = result * 26 + ord(character) - ord("A") + 1
    return result


def read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    """Return the workbook's shared-string table, or [] if it has none."""
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return ["".join(node.text or "" for node in item.iter(f"{{{XML_NS}}}t")) for item in root]


def read_sheet_paths(archive: zipfile.ZipFile) -> dict[str, str]:
    """Return {worksheet name: internal zip path} for every sheet in the workbook."""
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        node.attrib["Id"]: node.attrib["Target"]
        for node in relationships.iter(f"{{{PACKAGE_REL_NS}}}Relationship")
    }
    paths = {}
    for sheet in workbook.iter(f"{{{XML_NS}}}sheet"):
        target = targets[sheet.attrib[f"{{{REL_NS}}}id"]].lstrip("/")
        paths[sheet.attrib["name"]] = target if target.startswith("xl/") else f"xl/{target}"
    return paths


def read_sheet_grid(archive: zipfile.ZipFile, path: str, strings: list[str]) -> list[list[object]]:
    """Read one worksheet as a dense, row-major grid anchored at cell A1.

    Numeric cells are returned as float, shared/inline strings as str, and
    a cell with no value node as None. This is the typed reader used by
    scripts that transform tabular data.
    """
    root = ET.fromstring(archive.read(path))
    cells: dict[tuple[int, int], object] = {}
    max_row = 0
    max_column = 0
    for cell in root.iter(f"{{{XML_NS}}}c"):
        reference = cell.attrib["r"]
        row = int("".join(character for character in reference if character.isdigit()))
        column = column_number(reference)
        value_node = cell.find(f"{{{XML_NS}}}v")
        if cell.attrib.get("t") == "inlineStr":
            value: object = "".join(node.text or "" for node in cell.iter(f"{{{XML_NS}}}t"))
        elif value_node is None or value_node.text is None:
            value = None
        elif cell.attrib.get("t") == "s":
            value = strings[int(value_node.text)]
        else:
            try:
                value = float(value_node.text)
            except ValueError:
                value = value_node.text
        cells[(row, column)] = value
        max_row = max(max_row, row)
        max_column = max(max_column, column)
    return [
        [cells.get((row, column)) for column in range(1, max_column + 1)]
        for row in range(1, max_row + 1)
    ]


def read_workbook(
    path: Path, sheet_names: tuple[str, ...] | None = None
) -> dict[str, list[list[object]]]:
    """Read some or all worksheets of a .xlsx workbook as row-major grids.

    ``sheet_names`` restricts and validates which worksheets are expected;
    a missing requested sheet raises ``ValueError``. Omit it to read every
    worksheet the workbook contains.
    """
    with zipfile.ZipFile(path) as archive:
        strings = read_shared_strings(archive)
        paths = read_sheet_paths(archive)
        wanted = sheet_names if sheet_names is not None else tuple(paths)
        missing = set(wanted).difference(paths)
        if missing:
            raise ValueError(f"Missing worksheets: {', '.join(sorted(missing))}")
        return {name: read_sheet_grid(archive, paths[name], strings) for name in wanted}
