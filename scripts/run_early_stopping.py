"""Apply the frozen calibrated early-stopping protocol to the Sanglier long cycles.

Protocol: data/validation/early_stopping_v1.json (committed before this script ran).
Outputs: results/early-stopping/{pairs,stops,summary}.csv and report.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from biochar_ad_kinetics.early_stopping import (
    KEYS,
    TOLERANCE,
    bottle_mean,
    calibrate,
    evaluate,
    forecast_pairs,
    holliger_stop_day,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "data/validation/early_stopping_v1.json"
INPUTS = {
    "methane": ROOT / "results/intake/sanglier_2022_candidate.csv.gz",
    "structure": ROOT / "results/requirements/sanglier_2022_structure_by_cycle.csv",
    "spec": SPEC,
}
OUTPUT = ROOT / "results/early-stopping"
TARGET = "methane_yield_nml_gvs"
FAILING_CONTROLS = ("IV.2", "IV.3")


def load_trajectories() -> dict:
    methane = pd.read_csv(INPUTS["methane"])
    cycles = pd.read_csv(INPUTS["structure"]).drop_duplicates(KEYS)
    grouped = {key: c for key, c in methane.groupby(KEYS, sort=True)}
    out = {}
    for record in cycles.itertuples():
        key = (record.lab, record.batch_id, record.bottle_id)
        cycle = grouped[key].dropna(subset=[TARGET]).sort_values("within_batch_days")
        t = cycle["within_batch_days"].to_numpy(float)
        y = cycle[TARGET].to_numpy(float)
        if not np.isclose(t[-1], record.last_day):
            raise ValueError(f"cycle horizon differs from the structure audit: {key}")
        out[key] = (t, y)
    return out


def run_scheme(pairs, holliger, folds, scheme, population) -> tuple[list, pd.DataFrame]:
    bottle = pairs["lab"].astype(str) + "/" + pairs["bottle_id"].astype(str)
    stops_all, pair_rows = [], []
    for fold, test_mask in folds(pairs, bottle):
        model = calibrate(pairs[~test_mask], alpha=0.1)
        scored, stops = evaluate(pairs[test_mask], model, holliger)
        tag = {"scheme": scheme, "population": population, "fold": fold}
        stops_all.append(
            stops.assign(
                **tag,
                fixed_stop_day=model["fixed_stop_day"],
                normalised_quantile=model["normalised"],
            )
        )
        pair_rows.append(scored.assign(**tag))
    return pair_rows, pd.concat(stops_all, ignore_index=True)


def leave_one_bottle_out(pairs, bottle):
    for b in sorted(bottle.unique()):
        yield b, bottle == b


def leave_one_lab_out(pairs, bottle):
    for lab in sorted(pairs["lab"].unique()):
        yield f"test_{lab}", pairs["lab"] == lab


def summarise(pairs: pd.DataFrame, stops: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (scheme, population, fold_group), part in stops.assign(
        fold_group=np.where(stops["scheme"] == "leave_one_lab_out", stops["fold"], "all")
    ).groupby(["scheme", "population", "fold_group"]):
        p = pairs[
            (pairs["scheme"] == scheme)
            & (pairs["population"] == population)
            & ((pairs["fold"] == fold_group) | (fold_group == "all"))
        ]
        base = {
            "scheme": scheme,
            "population": population,
            "test_set": fold_group,
            "bottles": part["bottle_id"].nunique(),
            "cycles": len(part) // 4,
        }
        base["pair_coverage_fixed"] = bottle_mean(p, "covered_fixed")
        base["pair_coverage_normalised"] = bottle_mean(p, "covered_normalised")
        for rule, r in part.groupby("rule"):
            r = r.assign(
                days_saved=r["end_day"] - r["stop_day"],
                covered=r["covered"].astype(float),
                within_10pct=r["within_10pct"].astype(float),
                fired=r["fired"].astype(float),
            )
            fired = r[r["fired"] == 1]
            rows.append(
                base
                | {
                    "rule": rule,
                    "fired_share": bottle_mean(r, "fired"),
                    "coverage_at_stop": bottle_mean(r, "covered"),
                    "within_10pct_at_stop": bottle_mean(r, "within_10pct"),
                    "coverage_at_stop_fired_only": bottle_mean(fired, "covered")
                    if len(fired)
                    else np.nan,
                    "median_stop_day": float(r["stop_day"].median()),
                    "q1_stop_day": float(r["stop_day"].quantile(0.25)),
                    "q3_stop_day": float(r["stop_day"].quantile(0.75)),
                    "median_days_saved": float(r["days_saved"].median()),
                    "mean_days_saved": bottle_mean(r, "days_saved"),
                    "median_end_day": float(r["end_day"].median()),
                }
            )
    return pd.DataFrame(rows)


def criteria(summary: pd.DataFrame, stops: pd.DataFrame) -> dict:
    s = summary[summary["population"] == "all_long_cycles"]
    lobo = s[s["scheme"] == "leave_one_bottle_out"].set_index("rule")
    lolo = s[s["scheme"] == "leave_one_lab_out"]
    a = lobo.loc["adaptive"]
    fixed_days = stops[
        (stops.scheme == "leave_one_bottle_out")
        & (stops.population == "all_long_cycles")
        & (stops.rule == "adaptive")
    ]["fixed_stop_day"]
    adaptive = stops[
        (stops.scheme == "leave_one_bottle_out")
        & (stops.population == "all_long_cycles")
        & (stops.rule == "adaptive")
    ]
    c1 = all(0.85 <= a[k] <= 0.95 for k in ("pair_coverage_fixed", "pair_coverage_normalised"))
    transfer = lolo[lolo["rule"] == "adaptive"].set_index("test_set")["coverage_at_stop"]
    fixed_median = float(fixed_days.median()) if fixed_days.notna().all() else None
    return {
        "C1_calibration": {
            "pass": bool(c1),
            "pair_coverage_fixed": a["pair_coverage_fixed"],
            "pair_coverage_normalised": a["pair_coverage_normalised"],
        },
        "C2_coverage_at_stop": {
            "pass": bool(a["coverage_at_stop"] >= 0.85),
            "value": a["coverage_at_stop"],
        },
        "C3_time_saving": {
            "pass": bool(
                fixed_median is not None
                and a["median_stop_day"] < fixed_median
                and (adaptive["fired"]).mean() > 0.5
            ),
            "adaptive_median_stop_day": a["median_stop_day"],
            "fixed_day_rule_stop_day_median_over_folds": fixed_median,
            "adaptive_share_of_cycles_stopped_before_end": float(adaptive["fired"].mean()),
        },
        "C4_transfer": {
            "pass": bool((transfer >= 0.85).all()),
            "coverage_at_stop_by_test_lab": transfer.round(4).to_dict(),
        },
    }


def build(output: Path = OUTPUT) -> dict:
    trajectories = load_trajectories()
    holliger = {}
    for key, (t, y) in trajectories.items():
        fired = holliger_stop_day(t, y, t[-1])
        if fired is not None:
            holliger[key] = fired
    pairs = forecast_pairs(trajectories)
    populations = {
        "all_long_cycles": pairs,
        "without_failing_controls": pairs[~pairs["bottle_id"].isin(FAILING_CONTROLS)],
    }
    pair_frames, stop_frames = [], []
    for population, frame in populations.items():
        frame = frame.reset_index(drop=True)
        schemes = [("leave_one_bottle_out", leave_one_bottle_out)]
        if population == "all_long_cycles":
            schemes.append(("leave_one_lab_out", leave_one_lab_out))
        for scheme, folds in schemes:
            p, st = run_scheme(frame, holliger, folds, scheme, population)
            pair_frames += p
            stop_frames.append(st)
    scored = pd.concat(pair_frames, ignore_index=True)
    stops = pd.concat(stop_frames, ignore_index=True)
    summary = summarise(scored, stops)
    output.mkdir(parents=True, exist_ok=True)
    pairs.round(8).to_csv(output / "pairs.csv", index=False)
    stops.round(8).to_csv(output / "stops.csv", index=False)
    summary.round(6).to_csv(output / "summary.csv", index=False)
    report = {
        "spec_id": json.loads(SPEC.read_text())["spec_id"],
        "tolerance_log": TOLERANCE,
        "cycles": int(pairs.groupby(KEYS).ngroups),
        "bottles": int((pairs["lab"] + "/" + pairs["bottle_id"]).nunique()),
        "pairs": len(pairs),
        "holliger_fired_cycles": len(holliger),
        "criteria": criteria(summary, stops),
        "input_sha256": {k: hashlib.sha256(v.read_bytes()).hexdigest() for k, v in INPUTS.items()},
    }
    (output / "report.json").write_text(json.dumps(report, indent=2, default=float) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    print(json.dumps(build(parser.parse_args().output_dir), indent=2, default=float))


if __name__ == "__main__":
    main()
