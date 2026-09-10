"""Inventory a raw XLSX before source-specific ingestion.

This utility is intentionally source-agnostic. It records a SHA-256 checksum,
workbook sheet names, worksheet dimensions, and a small header preview without
altering any values. It is the first gate for newly acquired external datasets.

Usage:
    python scripts/inventory_xlsx_source.py raw.xlsx --output results/raw_inventory.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from biochar_ad_kinetics.xlsx_reader import read_shared_strings, read_sheet_paths

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def workbook_sheets(z: zipfile.ZipFile) -> list[tuple[str, str]]:
    return list(read_sheet_paths(z).items())


def cell_value(cell: ET.Element, ss: list[str]):
    if cell.attrib.get("t") == "inlineStr":
        node = cell.find(f"{{{MAIN}}}is")
        return "".join(t.text or "" for t in node.iter(f"{{{MAIN}}}t")) if node is not None else None
    v = cell.find(f"{{{MAIN}}}v")
    if v is None or v.text is None:
        return None
    if cell.attrib.get("t") == "s":
        return ss[int(v.text)]
    return v.text


def sheet_inventory(z: zipfile.ZipFile, path: str, ss: list[str]) -> dict:
    root = ET.fromstring(z.read(path))
    dim = root.find(f"{{{MAIN}}}dimension")
    dimension = dim.attrib.get("ref") if dim is not None else None
    preview = []
    for row in root.iter(f"{{{MAIN}}}row"):
        values = [cell_value(c, ss) for c in row.findall(f"{{{MAIN}}}c")]
        if any(v not in (None, "") for v in values):
            preview.append({"row": int(row.attrib.get("r", "0")), "values": values[:25]})
        if len(preview) >= 8:
            break
    return {"dimension": dimension, "preview_first_nonempty_rows": preview}


def inventory(path: Path) -> dict:
    with zipfile.ZipFile(path) as z:
        ss = read_shared_strings(z)
        sheets = []
        for name, sheet_path in workbook_sheets(z):
            item = {"name": name, "xml_path": sheet_path}
            item.update(sheet_inventory(z, sheet_path, ss))
            sheets.append(item)
    return {
        "source_filename": path.name,
        "source_size_bytes": path.stat().st_size,
        "sha256": sha256(path),
        "xlsx_valid_zip": True,
        "sheet_count": len(sheets),
        "sheets": sheets,
        "policy": {
            "raw_values_modified": False,
            "zero_to_missing_conversion": False,
            "purpose": "pre-ingestion provenance and structure inventory",
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source_xlsx", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    result = inventory(args.source_xlsx)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
