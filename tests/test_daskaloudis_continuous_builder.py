import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_daskaloudis_2026_continuous_dataset.py"
spec = importlib.util.spec_from_file_location("dask_builder", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def base_record(row, time, phase="phase III", **values):
    record = {"source_row": row}
    for name in mod.COLS:
        record[name] = None
    record["time"] = float(time)
    record["phase"] = phase
    record.update(values)
    return record


def test_complementary_duplicate_rows_are_coalesced_and_traced():
    a = base_record(65, 235, OLR=2.0, TAN_in=0.4, TAN_out=543.0)
    b = base_record(66, 235, OLR=2.0, phenols_in_gGAeq_L=3.4, phenols_out_gGAeq_L=1.4)

    rows = mod.coalesce([a, b])

    assert len(rows) == 1
    row = rows[0]
    assert row["OLR"] == 2.0
    assert row["TAN_in"] == 0.4
    assert row["phenols_in_gGAeq_L"] == 3.4
    assert row["source_rows"] == "Table!65;Table!66"
    assert row["source_record_count"] == 2
    assert row["qc_flags"] == "coalesced_complementary_duplicate"


def test_conflicting_duplicate_rows_fail_loudly():
    a = base_record(65, 235, OLR=2.0)
    b = base_record(66, 235, OLR=2.1)

    with pytest.raises(ValueError, match="conflicting duplicate at day 235"):
        mod.coalesce([a, b])


def test_numeric_zero_is_preserved_not_treated_as_missing():
    row = base_record(10, 12, methane_pct=0.0)
    result = mod.coalesce([row])[0]
    assert result["methane_pct"] == 0.0
