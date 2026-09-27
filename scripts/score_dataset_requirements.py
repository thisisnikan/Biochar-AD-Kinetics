"""Score every repository dataset against the minimum-information items.

Curated statuses in data/requirements/dataset_evidence.csv are cross-checked
against committed data wherever an automatic check exists. A curated status more
optimistic than the automatic one stops the build; a more conservative one is
allowed (the data cannot reveal source conflicts) and listed in the report. Outputs (results/requirements/):
- dataset_scorecard.csv          one row per dataset
- dataset_item_matrix.csv        dataset x item statuses
- scorecard_report.json          auto-check agreement and headline counts
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path

import pandas as pd

from biochar_ad_kinetics.evidence_requirements import (
    build_scorecard,
    load_items,
    observation_checks,
    validate_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
ITEMS = ROOT / "data" / "requirements" / "minimum_information_items.json"
EVIDENCE = ROOT / "data" / "requirements" / "dataset_evidence.csv"
OUTPUT = ROOT / "results" / "requirements"
EXP = ROOT / "data" / "experimental"
OPTIMISM = {"yes": 3, "partial": 2, "unknown": 1, "no": 0, "not_applicable": 0}


def automatic_statuses() -> dict[tuple[str, str], str]:
    auto: dict[tuple[str, str], str] = {}
    koz = pd.read_csv(EXP / "kozlowski_2025_reactor_observations.csv.gz")
    for item, status in observation_checks(koz).items():
        auto[("kozlowski_2025", item)] = status

    val = pd.read_csv(EXP / "valentin_bialowiec_2024_parameters.csv")
    amended = val[val["dose_g_l"] > 0]
    auto[("valentin_bialowiec_2024", "dose_levels_ge3")] = (
        "yes" if amended["dose_g_l"].nunique() >= 3 else "no"
    )
    materials = amended[["biochar_feedstock", "biochar_pyrolysis_c"]].drop_duplicates()
    auto[("valentin_bialowiec_2024", "materials_ge2")] = "yes" if len(materials) >= 2 else "no"
    auto[("valentin_bialowiec_2024", "temperature_levels_ge2")] = (
        "yes" if val["temperature_c"].nunique() >= 2 else "no"
    )

    cdu = pd.read_csv(EXP / "cdu_wang_2026_pyrolysis_temperature.csv")
    auto[("cdu_wang_2026", "materials_ge2")] = "yes" if cdu["material_id"].nunique() >= 2 else "no"
    auto[("cdu_wang_2026", "reactor_level_trajectories")] = "no"

    gp = pd.read_csv(EXP / "garcia_prats_2024_treatment_design.csv")
    biochar = gp[gp["condition_type"] == "biochar_amended"]
    auto[("garcia_prats_2024", "dose_levels_ge3")] = (
        "yes" if biochar.groupby("biochar_id")["dose_pct_ts"].nunique().min() >= 3 else "no"
    )
    auto[("garcia_prats_2024", "materials_ge2")] = (
        "yes" if biochar["biochar_id"].nunique() >= 2 else "no"
    )
    auto[("garcia_prats_2024", "inoculum_blanks")] = (
        "yes" if (gp["condition_type"] == "inoculum_blank").any() else "no"
    )
    auto[("garcia_prats_2024", "zero_dose_substrate_control")] = (
        "yes" if (gp["condition_type"] == "unamended_control").any() else "no"
    )

    lengths = pd.read_csv(OUTPUT / "sanglier_2022_cycle_length_requirement.csv")
    share = lengths["days_to_1pct_per_day"].notna().mean()
    auto[("sanglier_2022", "run_to_plateau")] = (
        "yes" if share >= 0.8 else "partial" if share >= 0.5 else "no"
    )
    sang = pd.read_csv(ROOT / "results" / "intake" / "sanglier_2022_candidate.csv.gz")
    levels = sang.loc[sang["biochar_label_ampts"] > 0, "biochar_label_ampts"].nunique()
    auto[("sanglier_2022", "dose_levels_ge3")] = "yes" if levels >= 3 else "no"
    return auto


def _write(frame: pd.DataFrame, path: Path) -> None:
    buffer = io.StringIO()
    frame.to_csv(buffer, index=False, lineterminator="\n")
    path.write_text(buffer.getvalue(), encoding="utf-8")


def build(output: Path = OUTPUT) -> dict:
    items = load_items(ITEMS)
    evidence = pd.read_csv(EVIDENCE)
    validate_evidence(evidence, items)
    curated = {(r.dataset, r.item_id): r.status for r in evidence.itertuples()}
    auto = automatic_statuses()
    # Curated evidence may be more conservative than an automatic check (a source
    # conflict the data cannot reveal), but never more optimistic.
    contradictions = {
        f"{d}:{i}": {"curated": curated[(d, i)], "automatic": s}
        for (d, i), s in sorted(auto.items())
        if OPTIMISM[curated[(d, i)]] > OPTIMISM[s]
    }
    downgraded = {
        f"{d}:{i}": {"curated": curated[(d, i)], "automatic": s}
        for (d, i), s in sorted(auto.items())
        if OPTIMISM[curated[(d, i)]] < OPTIMISM[s]
    }
    if contradictions:
        raise SystemExit(f"Curated evidence contradicts committed data: {contradictions}")
    scorecard = build_scorecard(evidence, items)
    order = [item["id"] for item in items["items"]]
    matrix = (
        evidence.pivot(index="dataset", columns="item_id", values="status")[order]
        .reset_index()
        .sort_values("dataset")
    )
    item_counts = {
        item: {
            status: int((matrix[item] == status).sum())
            for status in ("yes", "partial", "no", "unknown", "not_applicable")
        }
        for item in order
    }
    report = {
        "datasets": len(scorecard),
        "items": len(order),
        "critical_items": sum(i["critical_for_cross_study"] for i in items["items"]),
        "automatic_checks": len(auto),
        "automatic_checks_agreeing": len(auto) - len(downgraded),
        "curated_more_conservative_than_automatic": downgraded,
        "datasets_ready_for_cross_study_use": scorecard.loc[
            scorecard["ready_for_cross_study_use"], "dataset"
        ].tolist(),
        "max_critical_yes": int(scorecard["critical_yes"].max()),
        "items_satisfied_by_no_dataset": [i for i in order if item_counts[i]["yes"] == 0],
        "item_status_counts": item_counts,
    }
    output.mkdir(parents=True, exist_ok=True)
    _write(scorecard, output / "dataset_scorecard.csv")
    _write(matrix, output / "dataset_item_matrix.csv")
    (output / "scorecard_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    report = build(parser.parse_args().output_dir)
    print(json.dumps({k: v for k, v in report.items() if k != "item_status_counts"}, indent=2))


if __name__ == "__main__":
    main()
