"""Industrial operating envelope from Heitkamp 2021 chemistry (process stability only).

Uses the committed source-cell table. The plant is the unit: repeated sampling
days describe one plant's trajectory and are never pooled as replicates. No
methane productivity is available in this source and none is inferred.

Cross-source comparison with Sanglier 2022 is limited to pH, the only variable
whose basis is resolved in both sources. Every other comparison is listed as
blocked with its reason.

Outputs (results/validation/):
- heitkamp_2021_plant_envelope.csv
- heitkamp_2021_envelope_report.json
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
HEITKAMP = ROOT / "results" / "intake" / "heitkamp_2021_chemistry.csv"
SANGLIER_CHEM = ROOT / "results" / "intake" / "sanglier_2022_chemistry.csv"
DICTIONARY = ROOT / "results" / "validation" / "sanglier_2022_variable_dictionary.csv"
OUTPUT = ROOT / "results" / "validation"

ANALYTES = ("pH", "NH4-N", "TVFA", "FOS TAC", "Acetic acid", "Propionic acid")
MIN_DAYS_FOR_CORRELATION = 8


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def numeric_long(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["value"] = pd.to_numeric(out["value_source"], errors="coerce")
    return out


def plant_envelope(long: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (plant, analyte), g in long[long["analyte"].isin(ANALYTES)].groupby(
        ["plant_id", "analyte"], sort=True
    ):
        v = g["value"].dropna()
        rows.append(
            {
                "plant_id": plant,
                "analyte": analyte,
                "unit_label": g["source_value_label"].iloc[0],
                "sampling_days": int(g["sampling_day"].nunique()),
                "numeric_values": int(v.size),
                "nonnumeric_tokens": int(g["value"].isna().sum()),
                "zeros": int((v == 0).sum()),
                "median": float(v.median()) if v.size else np.nan,
                "min": float(v.min()) if v.size else np.nan,
                "max": float(v.max()) if v.size else np.nan,
            }
        )
    wide = long.pivot_table(
        index=["plant_id", "sampling_day"], columns="analyte", values="value", aggfunc="first"
    )
    ratio = (wide["Propionic acid"] / wide["Acetic acid"]).replace([np.inf, -np.inf], np.nan)
    for plant, r in ratio.groupby(level=0):
        v = r.dropna()
        rows.append(
            {
                "plant_id": plant,
                "analyte": "propionic_over_acetic",
                "unit_label": "dimensionless (both mg/L of sludge)",
                "sampling_days": int(r.size),
                "numeric_values": int(v.size),
                "nonnumeric_tokens": int(r.isna().sum()),
                "zeros": int((v == 0).sum()),
                "median": float(v.median()) if v.size else np.nan,
                "min": float(v.min()) if v.size else np.nan,
                "max": float(v.max()) if v.size else np.nan,
            }
        )
    return pd.DataFrame(rows)


def ph_ammonium_association(long: pd.DataFrame) -> dict:
    wide = long.pivot_table(
        index=["plant_id", "sampling_day"], columns="analyte", values="value", aggfunc="first"
    )
    out = {}
    for plant, g in wide.groupby(level=0):
        g = g[["pH", "NH4-N"]].dropna()
        if len(g) < MIN_DAYS_FOR_CORRELATION:
            out[plant] = {"sampling_days": len(g), "spearman_rho": None, "note": "too few days"}
            continue
        rho = stats.spearmanr(g["pH"], g["NH4-N"]).statistic
        out[plant] = {"sampling_days": len(g), "spearman_rho": round(float(rho), 3)}
    return out


def build(output: Path = OUTPUT) -> dict:
    heitkamp = numeric_long(pd.read_csv(HEITKAMP))
    envelope = plant_envelope(heitkamp)
    ph = envelope[envelope["analyte"] == "pH"]
    plant_medians = ph["median"].to_numpy()

    dictionary = pd.read_csv(DICTIONARY).set_index("variable")
    if dictionary.loc["pH", "unit_status"] != "resolved_by_definition":
        raise SystemExit("Sanglier pH basis is no longer resolved; comparison refused")
    sanglier = pd.read_csv(SANGLIER_CHEM)
    sanglier_ph = {}
    for lab, g in sanglier.dropna(subset=["pH"]).groupby("Lab"):
        per_bottle = g.groupby("Bottle")["pH"].median()
        sanglier_ph[lab] = {
            "bottles": int(per_bottle.size),
            "samples": len(g),
            "bottle_median_range": [float(per_bottle.min()), float(per_bottle.max())],
            "sample_range": [float(g["pH"].min()), float(g["pH"].max())],
            "share_samples_within_industrial_plant_median_range": round(
                float(g["pH"].between(plant_medians.min(), plant_medians.max()).mean()), 3
            ),
            "share_samples_within_industrial_observed_range": round(
                float(g["pH"].between(ph["min"].min(), ph["max"].max()).mean()), 3
            ),
        }

    blocked = {}
    for variable in ("TAN", "C2", "C3", "TS", "VS", "sCOD"):
        blocked[variable] = (
            f"Sanglier {variable} unit_status={dictionary.loc[variable, 'unit_status']}; "
            f"admission_use={dictionary.loc[variable, 'admission_use']}."
        )
    blocked["C3/C2 vs propionic/acetic"] = (
        "Heitkamp ratio is mass/mass; Sanglier acid basis (molar, mass or COD) is "
        "unresolved, which changes the ratio by a species-specific factor."
    )
    blocked["VS (Heitkamp internal)"] = (
        "Workbook says % fresh biomass, article says % TS; conflict preserved."
    )

    wide = heitkamp.pivot_table(
        index=["plant_id", "sampling_day"], columns="analyte", values="value", aggfunc="first"
    )
    both = wide[["TVFA", "Acetic acid"]].dropna()
    tvfa_below_acetic = both[both["TVFA"] < both["Acetic acid"]]
    report = {
        "status": "PROCESS_STABILITY_CONTEXT_ONLY",
        "tvfa_internal_consistency": {
            "plant_days_with_tvfa_and_acetic": len(both),
            "plant_days_tvfa_below_acetic": len(tvfa_below_acetic),
            "plants_affected": sorted(tvfa_below_acetic.index.get_level_values(0).unique()),
            "note": "A total below one of its own components means TVFA is not a sum of "
            "the reported acids on one basis; the cause (method, sampling or "
            "transcription) is not documented. TVFA is kept as reported and not compared "
            "across sources.",
        },
        "forbidden_uses": [
            "methane_productivity_validation",
            "causal_biochar_effect",
            "treat_sampling_days_as_independent_replicates",
        ],
        "unit_of_analysis": "plant",
        "plants": int(heitkamp["plant_id"].nunique()),
        "sampling_days_by_plant": {
            p: int(n) for p, n in heitkamp.groupby("plant_id")["sampling_day"].nunique().items()
        },
        "industrial_pH_plant_median_range": [
            float(plant_medians.min()),
            float(plant_medians.max()),
        ],
        "industrial_pH_observed_range": [float(ph["min"].min()), float(ph["max"].max())],
        "sanglier_pH_by_lab": sanglier_ph,
        "within_heitkamp_pH_vs_NH4N_spearman_by_plant": ph_ammonium_association(heitkamp),
        "blocked_cross_source_comparisons": blocked,
        "input_sha256": {
            p.relative_to(ROOT).as_posix(): _sha(p) for p in (HEITKAMP, SANGLIER_CHEM, DICTIONARY)
        },
        "interpretation": (
            "The industrial plants operate in a narrow alkaline pH band. BRL samples sit "
            "mostly inside it; LBE samples extend well below it (acidifying bottles), so "
            "part of the LBE lab record lies outside the industrial operating envelope. "
            "pH overlap does not show kinetic or productivity transfer. Association of pH "
            "and NH4-N within a plant is descriptive and confounded by feed changes and time."
        ),
    }
    output.mkdir(parents=True, exist_ok=True)
    buffer = io.StringIO()
    envelope.to_csv(buffer, index=False, lineterminator="\n", float_format="%.12g")
    (output / "heitkamp_2021_plant_envelope.csv").write_text(buffer.getvalue(), encoding="utf-8")
    (output / "heitkamp_2021_envelope_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    report = build(parser.parse_args().output_dir)
    print(json.dumps(report["sanglier_pH_by_lab"], indent=2))


if __name__ == "__main__":
    main()
