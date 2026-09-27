"""Test curve-family structure and cycle-length requirements on long Sanglier cycles.

Exploratory and within-study. Treatment labels are not used: the question is
whether any curve family can (1) describe a whole cycle and (2) predict the end of
a cycle from its first days. Only cycles recorded for at least 13 days are used,
and cycles with a source technical-fault exclusion (rule R7) are dropped. Failed
bottles stay in; the median-based summaries are robust to them and a sensitivity
without failing controls IV.2/IV.3 is reported.

Outputs (results/requirements/):
- sanglier_2022_structure_by_cycle.csv
- sanglier_2022_structure_summary.csv
- sanglier_2022_cycle_length_requirement.csv
- sanglier_2022_structure_report.json
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd

from biochar_ad_kinetics.kinetic_structure import days_to_daily_increment_below, evaluate_cycle

ROOT = Path(__file__).resolve().parents[1]
METHANE = ROOT / "results" / "intake" / "sanglier_2022_candidate.csv.gz"
ADJUDICATION = ROOT / "results" / "validation" / "sanglier_2022_treatment_adjudication.csv"
OUTPUT = ROOT / "results" / "requirements"
TARGET = "methane_yield_nml_gvs"
MIN_LONG_CYCLE_DAYS = 13.0
CUTS = (6.5, 9.5, 12.5)
FAILING_CONTROLS = ("IV.2", "IV.3")
ACCURACY = 0.10


def _write(frame: pd.DataFrame, path: Path) -> None:
    buffer = io.StringIO()
    frame.to_csv(buffer, index=False, lineterminator="\n", float_format="%.6g")
    path.write_text(buffer.getvalue(), encoding="utf-8")


def long_cycles(methane: pd.DataFrame, adjudication: pd.DataFrame) -> pd.DataFrame:
    faults = adjudication[adjudication["rules"].fillna("").str.contains("R7_")]
    fault_keys = set(zip(faults["lab"], faults["batch_id"], faults["bottle_id"], strict=True))
    last = methane.groupby(["lab", "batch_id", "bottle_id"])["within_batch_days"].max()
    keys = [k for k, d in last.items() if d >= MIN_LONG_CYCLE_DAYS and k not in fault_keys]
    return pd.DataFrame(keys, columns=["lab", "batch_id", "bottle_id"])


def summarize(by_cycle: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (population, family, cut), g in by_cycle.groupby(
        ["population", "family", "cut_days"], sort=True
    ):
        err = g["final_relative_error"].abs()
        rows.append(
            {
                "population": population,
                "family": family,
                "cut_days": cut,
                "cycles": len(g),
                "median_full_rmse_relative": float(g["full_rmse_relative_to_final"].median()),
                "median_signed_final_error": float(g["final_relative_error"].median()),
                "median_abs_final_error": float(err.median()),
                "share_final_within_10pct": float((err <= ACCURACY).mean()),
                "share_short_fit_at_bound": float(g["short_at_bound"].mean()),
                "best_aicc_share": float(g["best_aicc"].mean()),
            }
        )
    return pd.DataFrame(rows)


def build(output: Path = OUTPUT) -> dict:
    methane = pd.read_csv(METHANE)
    adjudication = pd.read_csv(ADJUDICATION)
    keys = long_cycles(methane, adjudication)
    subset = methane.merge(keys, on=["lab", "batch_id", "bottle_id"])
    rows = []
    for (lab, batch, bottle), cycle in subset.groupby(["lab", "batch_id", "bottle_id"], sort=True):
        c = cycle.dropna(subset=[TARGET]).sort_values("within_batch_days")
        t = c["within_batch_days"].to_numpy(float)
        y = c[TARGET].to_numpy(float)
        for cut in CUTS:
            if t[-1] < cut + 1.0:
                continue
            for r in evaluate_cycle(t, y, cut):
                rows.append(
                    {
                        "lab": lab,
                        "batch_id": int(batch),
                        "bottle_id": bottle,
                        "last_day": t[-1],
                        **r,
                    }
                )
    by_cycle = pd.DataFrame(rows)
    # Which family has the lowest full-cycle AICc for each cycle (once per cycle).
    full = by_cycle[by_cycle["cut_days"] == CUTS[0]]
    winners = full.loc[full.groupby(["lab", "batch_id", "bottle_id"])["full_aicc"].idxmin()]
    win_keys = set(
        zip(
            winners["lab"],
            winners["batch_id"],
            winners["bottle_id"],
            winners["family"],
            strict=True,
        )
    )
    by_cycle["best_aicc"] = [
        (r.lab, r.batch_id, r.bottle_id, r.family) in win_keys for r in by_cycle.itertuples()
    ]
    healthy = by_cycle[~by_cycle["bottle_id"].isin(FAILING_CONTROLS)]
    summary = pd.concat(
        [
            summarize(by_cycle.assign(population="all_long_cycles")),
            summarize(healthy.assign(population="without_failing_controls")),
        ],
        ignore_index=True,
    )

    # Cycle-length requirement: when does a cycle meet the 1%/day stop rule?
    lengths = []
    for (lab, batch, bottle), cycle in methane.groupby(["lab", "batch_id", "bottle_id"], sort=True):
        c = cycle.dropna(subset=[TARGET]).sort_values("within_batch_days")
        t = c["within_batch_days"].to_numpy(float)
        y = c[TARGET].to_numpy(float)
        lengths.append(
            {
                "lab": lab,
                "batch_id": int(batch),
                "bottle_id": bottle,
                "last_day": float(t[-1]),
                "days_to_1pct_per_day": days_to_daily_increment_below(t, y, 0.01),
                "days_to_2pct_per_day": days_to_daily_increment_below(t, y, 0.02),
            }
        )
    length_frame = pd.DataFrame(lengths)
    long_len = length_frame[length_frame["last_day"] >= MIN_LONG_CYCLE_DAYS]
    reached = long_len["days_to_1pct_per_day"].dropna()

    headline = summary[
        (summary["population"] == "without_failing_controls") & (summary["cut_days"] == CUTS[0])
    ].set_index("family")
    best_family = headline["median_abs_final_error"].idxmin()
    sweep = summary[
        (summary["population"] == "without_failing_controls") & (summary["family"] == best_family)
    ][["cut_days", "cycles", "median_abs_final_error", "share_final_within_10pct"]]
    report = {
        "status": "EXPLORATORY_WITHIN_STUDY_STRUCTURE_TEST",
        "cycles_used": len(keys),
        "lab_batches_used": sorted({f"{k.lab} batch {k.batch_id}" for k in keys.itertuples()}),
        "cuts_days": list(CUTS),
        "headline_cut_6_5_days": {
            fam: {
                "median_abs_final_error": round(float(r["median_abs_final_error"]), 4),
                "median_signed_final_error": round(float(r["median_signed_final_error"]), 4),
                "median_full_rmse_relative": round(float(r["median_full_rmse_relative"]), 4),
                "best_aicc_share": round(float(r["best_aicc_share"]), 4),
            }
            for fam, r in headline.iterrows()
        },
        "best_extrapolating_family_at_6_5_days": best_family,
        "prefix_sweep_for_best_family": [
            {k: (round(float(v), 4) if isinstance(v, float) else v) for k, v in rec.items()}
            for rec in sweep.to_dict("records")
        ],
        "cycle_length_to_1pct_per_day": {
            "long_cycles": len(long_len),
            "reached": int(reached.size),
            "median_days": round(float(reached.median()), 2) if reached.size else None,
            "p90_days": round(float(reached.quantile(0.9)), 2) if reached.size else None,
            "all_cycles_reaching": int(length_frame["days_to_1pct_per_day"].notna().sum()),
            "all_cycles": len(length_frame),
        },
        "interpretation_rules": {
            "structure": "A family that cannot fit whole long cycles (high full RMSE) is "
            "structurally inadequate for them.",
            "identifiability": "A family that fits whole cycles but mispredicts their end from "
            "the first days shows the short record, not the equation, is limiting.",
        },
    }
    output.mkdir(parents=True, exist_ok=True)
    _write(by_cycle, output / "sanglier_2022_structure_by_cycle.csv")
    _write(summary, output / "sanglier_2022_structure_summary.csv")
    _write(length_frame, output / "sanglier_2022_cycle_length_requirement.csv")
    (output / "sanglier_2022_structure_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    print(json.dumps(build(parser.parse_args().output_dir), indent=2))


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
