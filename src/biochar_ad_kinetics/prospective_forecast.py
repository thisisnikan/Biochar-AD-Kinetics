"""Fixed-horizon predictions, saved separately from subsequent endpoint scores.

Hash integrity cannot establish when outcomes were observed. Real prospective
status still requires pre-outcome publication and an independent source audit.
"""

from __future__ import annotations

import hashlib
import json
import platform
from datetime import date
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd

from .forecast_benchmark import prefix_baselines
from .kinetic_structure import FAMILIES, fit_family

# Changing any item is a new protocol, requiring a new pre-outcome registration.
PROTOCOL = {
    "id": "future-batch-endpoint-v1",
    "status": "AWAITING_NEW_DATA_AND_PRE_OUTCOME_REGISTRATION",
    "eligible_collection_start_on_or_after": "2026-10-07",
    "cut_days": 12.5,
    "target_day": 21.0,
    "max_prefix_age_days": 0.5,
    "minimum_prefix_readings": 6,
    "minimum_bottles": 4,
    "methods": ["recent_rate", "persistence", "first_order"],
    "primary_method": "recent_rate",
    "primary_comparator": "persistence",
    "primary_metric": "equal_bottle_mean_absolute_endpoint_error",
    "secondary_metric": "mean_absolute_relative_endpoint_error_if_all_endpoints_positive",
    "yield_unit": "mL_CH4_STP_per_g_substrate_VS",
    "gas_reference_temperature_k": 273.15,
    "gas_reference_pressure_kpa": 101.325,
    "gas_basis": "dry_methane",
    "yield_correction": "inoculum_blank_corrected",
    "endpoint_rule": "one exact day-21 measurement per registered bottle; no interpolation",
    "independence_scope": "one lab and one new batch; no cross-study inference",
    "selection_rule": "all registered bottles retained; incomplete endpoints block evaluation",
}
IDENTITY = ["lab", "batch_id", "bottle_id"]
PREFIX_COLUMNS = IDENTITY + ["time_days", "methane_yield"]
ENDPOINT_COLUMNS = IDENTITY + ["target_day", "methane_yield"]


def digest(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_protocol(protocol: dict) -> None:
    if protocol != PROTOCOL:
        raise ValueError("Protocol differs from the registered v1 specification")


def _table(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    if set(frame.columns) != set(columns) or frame.empty:
        raise ValueError(f"Input must contain exactly {columns} and at least one row")
    result = frame.copy()
    if result.isna().any().any():
        raise ValueError("Missing cells are not silently excluded")
    for column in IDENTITY:
        if not result[column].map(lambda x: isinstance(x, str) and bool(x.strip())).all():
            raise ValueError("Identities must be nonempty strings")
    for column in set(columns) - set(IDENTITY):
        result[column] = pd.to_numeric(result[column], errors="raise")
        if not np.isfinite(result[column]).all():
            raise ValueError("Measurements must be finite")
    if result["methane_yield"].lt(0).any():
        raise ValueError("Negative yields require separate source adjudication")
    if result["lab"].nunique() != 1 or result["batch_id"].nunique() != 1:
        raise ValueError("v1 admits exactly one lab and one batch")
    return result


def validate_cohort(cohort: dict, protocol: dict) -> None:
    required = {
        "cohort_id",
        "collection_start_date",
        "yield_unit",
        "source_reference",
        "unit_audit_reference",
        "new_batch_declared",
        "outcomes_unseen_declared",
    }
    if set(cohort) != required:
        raise ValueError("Cohort metadata must supply every required declaration")
    for field in required - {"new_batch_declared", "outcomes_unseen_declared"}:
        if not isinstance(cohort[field], str) or not cohort[field].strip():
            raise ValueError(f"Nonempty text required: {field}")
    if cohort["new_batch_declared"] is not True or cohort["outcomes_unseen_declared"] is not True:
        raise ValueError("New batch and unseen outcomes must be explicitly declared true")
    if cohort["yield_unit"] != protocol["yield_unit"]:
        raise ValueError("Yield unit and normalization must match the frozen protocol")
    if date.fromisoformat(cohort["collection_start_date"]) < date.fromisoformat(
        protocol["eligible_collection_start_on_or_after"]
    ):
        raise ValueError("Historical cohorts cannot enter the future-batch protocol")


def predict(prefix_path: Path, cohort: dict, protocol: dict) -> dict:
    """Read only prefix observations; return a hash-sealed prediction record."""
    validate_protocol(protocol)
    validate_cohort(cohort, protocol)
    frame = _table(pd.read_csv(prefix_path, dtype={c: str for c in IDENTITY}), PREFIX_COLUMNS)
    if frame["time_days"].lt(0).any() or frame["time_days"].gt(protocol["cut_days"]).any():
        raise ValueError("Prediction input must contain prefix readings only; future rows rejected")
    if frame.duplicated(IDENTITY + ["time_days"]).any():
        raise ValueError("Duplicate bottle/time readings")
    if frame["bottle_id"].nunique() < protocol["minimum_bottles"]:
        raise ValueError("At least four registered bottles required")
    rows = []
    for key, bottle in frame.groupby(IDENTITY, sort=True):
        bottle = bottle.sort_values("time_days")
        t = bottle["time_days"].to_numpy(float)
        y = bottle["methane_yield"].to_numpy(float)
        if len(t) < protocol["minimum_prefix_readings"]:
            raise ValueError(f"Insufficient prefix readings for {key}")
        if protocol["cut_days"] - t[-1] > protocol["max_prefix_age_days"]:
            raise ValueError(f"Stale prefix for {key}")
        baseline = prefix_baselines(t, y, protocol["cut_days"], protocol["target_day"])
        fit = fit_family(FAMILIES["first_order"], t, y)
        if not fit["converged"]:
            raise ValueError(f"First-order solver failed for {key}; no bottle silently dropped")
        forecast = float(
            FAMILIES["first_order"].function(
                np.asarray([protocol["target_day"]]), *fit["parameters"]
            )[0]
        )
        rows.append(
            dict(zip(IDENTITY, key, strict=True))
            | {
                "prefix_readings": len(t),
                "last_prefix_day": float(t[-1]),
                "predictions": baseline | {"first_order": forecast},
                "first_order_parameters": fit["parameters"].tolist(),
                "first_order_at_bound": fit["at_bound"],
            }
        )
    record = {
        "protocol": protocol,
        "protocol_sha256": digest(protocol),
        "cohort": cohort,
        "prefix_sha256": file_hash(prefix_path),
        "environment": {
            "python": platform.python_version(),
            **{name: version(name) for name in ("numpy", "pandas", "scipy")},
        },
        "method_sha256": {
            name: file_hash(Path(__file__).parent / name)
            for name in (
                "prospective_forecast.py",
                "forecast_benchmark.py",
                "kinetic_structure.py",
            )
        },
        "predictions": rows,
        "prospective_status": "UNVERIFIED_REQUIRES_PRE_OUTCOME_PUBLICATION_AND_SOURCE_AUDIT",
    }
    return record | {"record_sha256": digest(record)}


def evaluate(record: dict, prefix_path: Path, endpoints_path: Path) -> dict:
    """Score exactly the registered bottles at the fixed horizon; never refit."""
    if set(record) != {
        "protocol",
        "protocol_sha256",
        "cohort",
        "prefix_sha256",
        "environment",
        "method_sha256",
        "predictions",
        "prospective_status",
        "record_sha256",
    }:
        raise ValueError("Incomplete or unexpected prediction record fields")
    payload = {k: v for k, v in record.items() if k != "record_sha256"}
    if record.get("record_sha256") != digest(payload):
        raise ValueError("Prediction record integrity failure")
    protocol = record["protocol"]
    validate_protocol(protocol)
    if record["protocol_sha256"] != digest(protocol):
        raise ValueError("Protocol hash mismatch")
    if file_hash(prefix_path) != record["prefix_sha256"]:
        raise ValueError("Prefix differs from the saved prediction input")
    validate_cohort(record["cohort"], protocol)
    if set(record["method_sha256"]) != {
        "prospective_forecast.py",
        "forecast_benchmark.py",
        "kinetic_structure.py",
    }:
        raise ValueError("Incomplete prediction method provenance")
    for name, expected in record["method_sha256"].items():
        if Path(name).name != name or file_hash(Path(__file__).parent / name) != expected:
            raise ValueError("Prediction code changed; evaluate in the original environment")
    endpoints = _table(
        pd.read_csv(endpoints_path, dtype={c: str for c in IDENTITY}), ENDPOINT_COLUMNS
    )
    if endpoints.duplicated(IDENTITY).any():
        raise ValueError("Exactly one endpoint per bottle required")
    if not np.isclose(endpoints["target_day"], protocol["target_day"], rtol=0, atol=1e-9).all():
        raise ValueError("Endpoint must be measured at the fixed target day")
    registered = {tuple(r[c] for c in IDENTITY) for r in record["predictions"]}
    if (
        len(registered) != len(record["predictions"])
        or len(registered) < protocol["minimum_bottles"]
    ):
        raise ValueError("Prediction roster contains duplicates or insufficient bottles")
    observed = {tuple(r) for r in endpoints[IDENTITY].itertuples(index=False, name=None)}
    if registered != observed:
        raise ValueError("Missing or extra bottles: all registered bottles must be scored")
    outcomes = endpoints.set_index(IDENTITY)["methane_yield"]
    scores = []
    for row in record["predictions"]:
        truth = float(outcomes.loc[tuple(row[c] for c in IDENTITY)])
        if set(row["predictions"]) != set(protocol["methods"]):
            raise ValueError("Prediction method set differs from protocol")
        for method in protocol["methods"]:
            value = row["predictions"][method]
            if not np.isfinite(value):
                raise ValueError("Nonfinite prediction")
            scores.append(
                {c: row[c] for c in IDENTITY}
                | {
                    "method": method,
                    "prediction": value,
                    "observed": truth,
                    "absolute_error": abs(value - truth),
                    "absolute_relative_error": abs(value - truth) / truth if truth > 0 else None,
                }
            )
    frame = pd.DataFrame(scores)
    all_positive = endpoints["methane_yield"].gt(0).all()
    methods = {}
    for method, part in frame.groupby("method", sort=True):
        methods[method] = {
            "mean_absolute_endpoint_error": float(part["absolute_error"].mean()),
            "mean_absolute_relative_endpoint_error": float(part["absolute_relative_error"].mean())
            if all_positive
            else None,
        }
    primary = methods[protocol["primary_method"]]["mean_absolute_endpoint_error"]
    comparator = methods[protocol["primary_comparator"]]["mean_absolute_endpoint_error"]
    report = {
        "status": "FIXED_PROTOCOL_DESCRIPTIVE_EVALUATION_PROSPECTIVE_STATUS_UNVERIFIED",
        "prediction_record_sha256": record["record_sha256"],
        "endpoints_sha256": file_hash(endpoints_path),
        "bottles": len(endpoints),
        "yield_unit": protocol["yield_unit"],
        "methods": methods,
        "primary_minus_comparator_absolute_error": primary - comparator,
        "secondary_metric_evaluable": bool(all_positive),
        "zero_endpoint_bottles": int(endpoints["methane_yield"].eq(0).sum()),
        "scores": scores,
        "limitations": [
            "Dates, units, new-batch identity and unseen outcomes are declarations, not independent verification.",
            "Hashes detect changes to saved artifacts; they do not prove pre-outcome timing.",
            "Publish protocol and predictions before outcomes; obtain independent source review.",
            "One batch has shared conditions; bottle means are descriptive, without population inference.",
            "No causal biochar benefit, cross-study validation or continuous-reactor claim.",
        ],
    }
    return report


def write_new(path: Path, value: dict) -> None:
    """Never overwrite a protocol, prediction or evaluation artifact."""
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
