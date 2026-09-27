"""Run the frozen Sanglier analysis exactly as pre-registered.

Stops unless the spec SHA-256 equals the hash recorded by the admission step and
the development comparator matches its frozen hash. Then computes, from admitted
bottles only:

- primary and sensitivity log response ratios (Welch interval, exact
  permutation p and its floor, verdict);
- S1 variance components, S2 plateau audit, S3 exploratory per-cycle Gompertz
  identifiability, S4 independent-unit count;
- a post-freeze check of the event statements about failing control bottles;
- an evidence-graded partition of reasons generalization is not established.
"""

from __future__ import annotations

import argparse
import io
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from biochar_ad_kinetics.baselines import BASELINES
from biochar_ad_kinetics.fit import _numerical_jacobian, parameter_covariance
from biochar_ad_kinetics.locked_effects import (
    balanced_variance_decomposition,
    exact_permutation_p,
    verdict,
    welch_log_ratio,
)
from biochar_ad_kinetics.validation_admission import file_sha256, load_spec

ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "results" / "validation"
SPEC = ROOT / "data" / "validation" / "sanglier_2022_validation_spec.json"
METHANE = ROOT / "results" / "intake" / "sanglier_2022_candidate.csv.gz"
TARGET = "methane_yield_nml_gvs"
PLATEAU_FRACTION = 0.01  # daily increment below 1% of cumulative (VDI 4630 stop rule)


def _norm(label: object) -> str:
    return str(label).replace(" ", "")


def verify_frozen_inputs(spec: dict) -> dict:
    report = json.loads((VALIDATION / "sanglier_2022_admission_report.json").read_text())
    spec_hash = file_sha256(SPEC)
    if spec_hash != report["spec_sha256"]:
        raise SystemExit("Spec changed after admission; locked evaluation refuses to run")
    comparator = spec["development_comparator"]
    if file_sha256(ROOT / comparator["path"]) != comparator["sha256"]:
        raise SystemExit("Development comparator changed after the spec was frozen")
    return report


def horizon_values(methane: pd.DataFrame, cycles: pd.DataFrame, horizon: float, tol: float):
    at_h = methane[(methane["within_batch_days"] - horizon).abs() <= tol]
    merged = cycles.merge(
        at_h[["lab", "batch_id", "bottle_id", TARGET, "source_amptshort_row"]],
        on=["lab", "batch_id", "bottle_id"],
        how="left",
        validate="1:1",
    )
    merged["evaluable"] = merged[TARGET].notna() & (merged[TARGET] > 0)
    merged["log_yield_h"] = np.where(merged["evaluable"], np.log(merged[TARGET]), np.nan)
    return merged


def bottle_summaries(values: pd.DataFrame, windows: dict) -> pd.DataFrame:
    rows = []
    for (lab, bottle), group in values.groupby(["lab", "bottle_id"], sort=True):
        start, end = windows[lab]
        batches = set(range(start, end + 1))
        ok = group[group["evaluable"]]
        rows.append(
            {
                "lab": lab,
                "bottle_id": bottle,
                "arm": _norm(group["source_condition_inoculation"].iloc[0]),
                "window": f"{start}-{end}",
                "batches_evaluable": len(ok),
                "complete": set(ok["batch_id"]) == batches,
                "mean_log_yield_h": float(ok["log_yield_h"].mean()) if len(ok) else np.nan,
                "geometric_mean_yield_h": float(np.exp(ok["log_yield_h"].mean()))
                if len(ok)
                else np.nan,
            }
        )
    return pd.DataFrame(rows)


def contrasts(
    summaries: pd.DataFrame, controls: dict, analysis: str, locked: bool = True
) -> list[dict]:
    rows = []
    for lab, group in summaries.groupby("lab", sort=True):
        complete = group[group["complete"]]
        control = complete.loc[
            complete["arm"] == _norm(controls[lab]), "mean_log_yield_h"
        ].to_numpy()
        for arm in sorted(group["arm"].unique()):
            if arm == _norm(controls[lab]):
                continue
            treat = complete.loc[complete["arm"] == arm, "mean_log_yield_h"].to_numpy()
            est = welch_log_ratio(treat, control)
            if len(treat) and len(control):
                perm = exact_permutation_p(treat, control)
            else:
                perm = {"permutation_p": np.nan, "permutation_p_floor": np.nan, "relabellings": 0}
            if not np.isfinite(est["log_response_ratio"]):
                est["log_response_ratio"] = np.nan
            rows.append(
                {
                    "analysis": analysis,
                    "locked": locked,
                    "lab": lab,
                    "arm": arm,
                    "control": _norm(controls[lab]),
                    **est,
                    "percent_change": 100 * math.expm1(est["log_response_ratio"])
                    if np.isfinite(est["log_response_ratio"])
                    else np.nan,
                    "percent_ci_low": 100 * math.expm1(est["ci_low"])
                    if np.isfinite(est["ci_low"])
                    else np.nan,
                    "percent_ci_high": 100 * math.expm1(est["ci_high"])
                    if np.isfinite(est["ci_high"])
                    else np.nan,
                    **perm,
                    "low_replication": min(len(treat), len(control)) < 3,
                    "verdict": verdict(est["ci_low"], est["ci_high"], len(treat), len(control)),
                }
            )
    return rows


def with_window(values: pd.DataFrame, lab: str, start: int, end: int) -> pd.DataFrame:
    keep = (values["lab"] != lab) | values["batch_id"].between(start, end)
    return values[keep]


def gompertz_cycle(cycle: pd.DataFrame) -> dict:
    spec = BASELINES["modified_gompertz"]
    data = cycle.dropna(subset=[TARGET]).sort_values("within_batch_days")
    time = data["within_batch_days"].to_numpy(float)
    observed = data[TARGET].to_numpy(float)
    from scipy.optimize import least_squares

    upper = np.array(spec.upper, dtype=float)
    lower = np.array(spec.lower, dtype=float)
    start = np.array([max(observed.max() * 1.2, 2.0), max(observed.max() / 3, 1.0), 0.2])
    start = np.clip(start, lower, upper)

    def residual(v):
        return spec.function(time, *v) - observed

    sol = least_squares(residual, start, bounds=(lower, upper))
    jac = _numerical_jacobian(residual, sol.x, lower, upper)
    cov = parameter_covariance(jac, residual(sol.x), len(observed))
    se = np.sqrt(np.clip(np.diag(cov), 0, None))
    with np.errstate(invalid="ignore", divide="ignore"):
        corr = cov[0, 1] / (se[0] * se[1]) if se[0] > 0 and se[1] > 0 else np.nan
    at_bound = bool(np.any(np.isclose(sol.x, upper, rtol=1e-6) | np.isclose(sol.x, lower)))
    return {
        "gompertz_potential": float(sol.x[0]),
        "gompertz_rate": float(sol.x[1]),
        "gompertz_lag": float(sol.x[2]),
        "potential_relative_se": float(se[0] / sol.x[0]),
        "potential_rate_correlation": float(corr),
        "parameter_at_bound": at_bound,
        "potential_over_last_observed": float(sol.x[0] / observed[-1]),
        "converged": bool(sol.success),
    }


def truncation_extrapolation(
    methane: pd.DataFrame, admitted: pd.DataFrame, cut: float
) -> pd.DataFrame:
    """Fit Gompertz to data up to ``cut`` days and predict the last observation.

    Only admitted cycles observed well beyond ``cut`` are used. This asks
    whether a typical short cycle identifies the asymptote a longer cycle reaches.
    """

    rows = []
    keys = admitted[["lab", "batch_id", "bottle_id"]]
    subset = methane.merge(keys, on=["lab", "batch_id", "bottle_id"])
    spec = BASELINES["modified_gompertz"]
    for (lab, batch, bottle), cycle in subset.groupby(["lab", "batch_id", "bottle_id"], sort=True):
        c = cycle.dropna(subset=[TARGET]).sort_values("within_batch_days")
        last_t = float(c["within_batch_days"].iloc[-1])
        if last_t < 2 * cut:
            continue
        early = c[c["within_batch_days"] <= cut + 1e-9]
        fit = gompertz_cycle(early)
        observed = float(c[TARGET].iloc[-1])
        predicted = float(
            spec.function(
                np.array([last_t]),
                fit["gompertz_potential"],
                fit["gompertz_rate"],
                fit["gompertz_lag"],
            )[0]
        )
        rows.append(
            {
                "lab": lab,
                "batch_id": int(batch),
                "bottle_id": bottle,
                "fit_until_days": cut,
                "predict_at_days": last_t,
                "observed_last_yield": observed,
                "predicted_last_yield": predicted,
                "relative_error": (predicted - observed) / observed,
                "early_fit_potential_relative_se": fit["potential_relative_se"],
            }
        )
    return pd.DataFrame(rows)


def cycle_kinetics(methane: pd.DataFrame, admitted: pd.DataFrame) -> pd.DataFrame:
    rows = []
    keys = admitted[["lab", "batch_id", "bottle_id"]]
    subset = methane.merge(keys, on=["lab", "batch_id", "bottle_id"])
    for (lab, batch, bottle), cycle in subset.groupby(["lab", "batch_id", "bottle_id"], sort=True):
        c = cycle.dropna(subset=[TARGET]).sort_values("within_batch_days")
        last_t = float(c["within_batch_days"].iloc[-1])
        last_y = float(c[TARGET].iloc[-1])
        prior = c[c["within_batch_days"] <= last_t - 1.0 + 1e-9]
        increment = last_y - float(prior[TARGET].iloc[-1]) if len(prior) else np.nan
        rows.append(
            {
                "lab": lab,
                "batch_id": int(batch),
                "bottle_id": bottle,
                "last_within_batch_days": last_t,
                "last_yield": last_y,
                "final_24h_increment_fraction": increment / last_y if last_y > 0 else np.nan,
                "plateau_reached": bool(last_y > 0 and increment / last_y < PLATEAU_FRACTION),
                **gompertz_cycle(c),
            }
        )
    return pd.DataFrame(rows)


def failure_partition(results: dict) -> pd.DataFrame:
    vc = results["variance_components"]
    kin = results["cycle_kinetics_summary"]
    units = results["independent_units"]
    lab_disagree = results["cross_lab_agreement"]
    rows = [
        (
            "biological_variability",
            "supported",
            (
                f"Persistent bottle-within-arm differences explain "
                f"{vc['BRL']['unit_within_arm_share']:.0%} (BRL) and "
                f"{vc['LBE']['unit_within_arm_share']:.0%} (LBE) of ln-yield variance; "
                "control bottle IV.3 failed while its replicates did not."
            ),
        ),
        (
            "missing_biochar_descriptors",
            "unknown_due_to_missing_data",
            (
                "No feedstock, pyrolysis temperature, surface area, conductivity or particle "
                "size for the Sanglier biochar is committed; one material only, so no "
                "descriptor effect is estimable inside the study."
            ),
        ),
        (
            "missing_operating_conditions",
            "supported",
            (
                "BRL reactor mass is not recorded; temperature is not a committed field; "
                "trace-element regimes differ by lab (High vs Low)."
            ),
        ),
        (
            "study_batch_heterogeneity",
            "supported",
            (
                f"Batch (substrate lot / cycle) explains {vc['BRL']['batch_share']:.0%} (BRL) and "
                f"{vc['LBE']['batch_share']:.0%} (LBE) of ln-yield variance versus "
                f"{vc['BRL']['arm_share']:.0%} and {vc['LBE']['arm_share']:.0%} for arm."
            ),
        ),
        (
            "kinetic_structural_inadequacy",
            "plausible_but_unproven",
            (
                f"Only {kin['plateau_share']:.1%} of admitted cycles meet the 1%/day stop rule "
                f"(median final-day increment {kin['median_final_24h_increment_fraction']:.0%} of "
                "cumulative), yet full-cycle Gompertz fits place the asymptote only "
                f"{kin['median_potential_over_last_observed'] - 1:.1%} above the last observation. "
                "A single-pool curve per cycle also ignores carry-over biomass and residual "
                "substrate. No alternative structure was tested, so this stays unproven."
            ),
        ),
        (
            "parameter_non_identifiability",
            "supported",
            (
                f"Gompertz fitted to the first 6.5 d of the {kin['truncation_test_cycles']} longer "
                f"cycles ({', '.join(kin['truncation_test_batches'])}) misses their final yield by "
                f"a median {kin['truncation_median_relative_error']:.0%} although the nominal "
                f"potential SE is small (median {kin['median_potential_relative_se']:.1%} on full "
                "cycles): 7-day cycles do not identify the asymptote and the Jacobian SE is "
                f"overconfident. Median |corr(potential, rate)| "
                f"{kin['median_abs_potential_rate_correlation']:.2f}; "
                f"{kin['share_parameter_at_bound']:.0%} of fits hit a bound."
            ),
        ),
        (
            "treatment_reconstruction_uncertainty",
            "supported",
            (
                f"{results['cycles_not_admitted']} of {results['cycles_total']} cycles are "
                "excluded by conflicts, carry-over, co-interventions or ambiguous labels."
            ),
        ),
        (
            "measurement_normalization_differences",
            "supported",
            (
                "13 of 14 chemistry units are unresolved; methane units are builder-asserted; "
                "only LBE applies a volume correction; TS/VS bases differ between labs."
            ),
        ),
        (
            "insufficient_independent_training_data",
            "supported",
            (
                f"{units['bottles']} admitted bottles in {units['arms']} arms, "
                f"{units['labs']} labs, {units['biochar_materials']} biochar material and "
                f"{units['committed_biochar_descriptors']} committed descriptors, against "
                f"{units['time_rows_in_admitted_cycles']} time rows; the smallest attainable "
                f"exact two-sided p for any contrast is {units['min_permutation_p_floor']:.2f}."
            ),
        ),
        (
            "batch_to_continuous_domain_shift",
            "unknown_due_to_missing_data",
            (
                "Sanglier is repeated batch with recirculation; no continuous-reactor methane "
                "data with matched biochar dosing are in the repository to test transfer."
            ),
        ),
        (
            "incorrect_assumptions",
            "supported",
            "Source records contradict three convenient assumptions: labels 1/2 are not "
            "one dose across labs (4/8 g vs 2.5/5 g initial biochar); FAN is derived from "
            "TAN and pH, not measured; the ammonium event's single-condition scope "
            "disagrees with Inoculation grams for every BRL bottle."
            + (" Direction verdicts differ between labs." if lab_disagree else ""),
        ),
    ]
    return pd.DataFrame(rows, columns=["failure_mode", "evidence_status", "evidence"])


def _write(frame: pd.DataFrame, path: Path, digits: int = 12) -> None:
    """Write CSV deterministically; iterative-fit outputs use fewer digits so that
    optimizer round-off across numpy/scipy builds cannot change the bytes."""

    buffer = io.StringIO()
    frame.to_csv(buffer, index=False, lineterminator="\n", float_format=f"%.{digits}g")
    path.write_text(buffer.getvalue(), encoding="utf-8")


def build(output: Path = VALIDATION) -> dict:
    spec = load_spec(SPEC)
    report = verify_frozen_inputs(spec)
    temporal = spec["temporal_definition"]
    horizon, tol = float(report["horizon_days"]), float(temporal["time_tolerance_days"])
    windows = {lab: tuple(v) for lab, v in report["windows"].items()}
    controls = spec["allowable_treatments"]["controls"]

    admission = pd.read_csv(VALIDATION / "sanglier_2022_admission.csv")
    methane = pd.read_csv(METHANE)

    # Primary population
    primary_cycles = admission[admission["admitted_primary"]]
    values = horizon_values(methane, primary_cycles, horizon, tol)
    summaries = bottle_summaries(values, windows)
    rows = contrasts(summaries, controls, "primary")

    # SA1: LBE '+' arms as separate arms (their cycles are admissible except for arm rule)
    plus = admission[
        (admission["lab"] == "LBE")
        & admission["in_window"]
        & (admission["exclusion_reason"] == "arm_not_allowable")
    ]
    sa1_values = horizon_values(
        methane, pd.concat([primary_cycles, plus]).drop_duplicates(), horizon, tol
    )
    rows += contrasts(bottle_summaries(sa1_values, windows), controls, "SA1_include_plus_arms")

    # SA2: drop failing control IV.3
    sa2 = summaries[summaries["bottle_id"] != "IV.3"]
    rows += contrasts(sa2, controls, "SA2_exclude_IV.3")

    # SA3: IV.5 / IV.8 excluded only in batch 1: LBE window 2-8
    sa3_cycles = admission[
        admission["in_window"]
        & (
            admission["admitted_primary"]
            | (
                admission["bottle_id"].isin(["IV.5", "IV.8"])
                & (admission["exclusion_reason"] == "bottle_class_excluded")
                & (admission["batch_id"] >= 2)
            )
        )
    ]
    sa3_cycles = with_window(sa3_cycles, "LBE", 2, 8)
    sa3_values = horizon_values(methane, sa3_cycles, horizon, tol)
    sa3_windows = {**windows, "LBE": (2, 8)}
    rows += contrasts(bottle_summaries(sa3_values, sa3_windows), controls, "SA3_LBE_batches_2_8")
    # D1 (post-hoc deviation, not locked): the frozen horizon rule used each
    # cycle's last observed time, but BRL batch 6 ends at 5.46/5.51 d with no
    # 5.5 d grid point. The corrected rule takes the largest 0.5 d multiple at
    # which every admitted cycle has an observation.
    grid = methane.merge(primary_cycles[["lab", "batch_id", "bottle_id"]])
    per_cycle = grid.groupby(["lab", "batch_id", "bottle_id"])["within_batch_days"].apply(set)
    candidates = [h / 2 for h in range(int(horizon * 2), 0, -1)]
    corrected = next(
        h for h in candidates if all(any(abs(t - h) <= tol for t in ts) for ts in per_cycle)
    )
    d1_values = horizon_values(methane, primary_cycles, corrected, tol)
    d1_summaries = bottle_summaries(d1_values, windows)
    rows += contrasts(d1_summaries, controls, f"D1_posthoc_horizon_{corrected:g}d", locked=False)
    rows += contrasts(
        d1_summaries[d1_summaries["bottle_id"] != "IV.3"],
        controls,
        f"D1_posthoc_horizon_{corrected:g}d_exclude_IV.3",
        locked=False,
    )
    effects = pd.DataFrame(rows)

    # Cross-lab agreement on nominal labels 1 and 2 (primary only)
    primary = effects[effects["analysis"] == "primary"].set_index(["lab", "arm"])["verdict"]
    agreement = {}
    for label, brl, lbe in (("1", "MBE[1]", "[1]"), ("2", "MBE[2]", "[2]")):
        a, b = primary.get(("BRL", brl)), primary.get(("LBE", lbe))
        agreement[f"label_{label}"] = {
            "BRL": a,
            "LBE": b,
            "agree": bool(a == b and a not in ("inconclusive", "not_evaluable")),
        }
    decisive = [v for v in primary if v in ("increase", "decrease")]
    lab_disagree = any({v["BRL"], v["LBE"]} == {"increase", "decrease"} for v in agreement.values())

    d1 = effects[effects["analysis"] == f"D1_posthoc_horizon_{corrected:g}d"].set_index(
        ["lab", "arm"]
    )["verdict"]
    agreement_d1 = {}
    for label, brl, lbe in (("1", "MBE[1]", "[1]"), ("2", "MBE[2]", "[2]")):
        a, b = d1.get(("BRL", brl)), d1.get(("LBE", lbe))
        agreement_d1[f"label_{label}"] = {
            "BRL": a,
            "LBE": b,
            "agree": bool(a == b and a not in ("inconclusive", "not_evaluable")),
        }
    lab_disagree = lab_disagree or any(
        {v["BRL"], v["LBE"]} == {"increase", "decrease"} for v in agreement_d1.values()
    )

    # S1 variance components at the corrected horizon (all window batches)
    ev = d1_values[d1_values["evaluable"]].assign(
        arm=lambda d: d["source_condition_inoculation"].map(_norm)
    )
    variance = {
        lab: balanced_variance_decomposition(g, "log_yield_h", "batch_id", "arm", "bottle_id")
        for lab, g in ev.groupby("lab", sort=True)
    }
    variance_frame = pd.DataFrame([{"lab": k, **v} for k, v in variance.items()])

    # S2 + S3 per-cycle kinetics (exploratory, within-study)
    kinetics = cycle_kinetics(methane, primary_cycles)
    truncation = truncation_extrapolation(methane, primary_cycles, cut=6.5)
    kin_summary = {
        "truncation_test_cycles": len(truncation),
        "truncation_median_relative_error": float(truncation["relative_error"].median())
        if len(truncation)
        else float("nan"),
        "truncation_test_batches": sorted(
            {f"{r.lab} batch {r.batch_id}" for r in truncation.itertuples()}
        ),
        "cycles": len(kinetics),
        "plateau_share": float(kinetics["plateau_reached"].mean()),
        "median_final_24h_increment_fraction": float(
            kinetics["final_24h_increment_fraction"].median()
        ),
        "median_potential_relative_se": float(kinetics["potential_relative_se"].median()),
        "median_abs_potential_rate_correlation": float(
            kinetics["potential_rate_correlation"].abs().median()
        ),
        "share_parameter_at_bound": float(kinetics["parameter_at_bound"].mean()),
        "median_potential_over_last_observed": float(
            kinetics["potential_over_last_observed"].median()
        ),
        "category": "exploratory_within_study_not_validation",
    }
    kin_summary = {
        k: float(f"{v:.6g}") if isinstance(v, float) else v for k, v in kin_summary.items()
    }

    # S4 independent units
    admitted_bottles = primary_cycles.assign(
        arm=lambda d: d["source_condition_inoculation"].map(_norm)
    ).drop_duplicates(["lab", "bottle_id"])
    floors = effects.loc[
        effects["analysis"].isin(["primary", f"D1_posthoc_horizon_{corrected:g}d"]),
        "permutation_p_floor",
    ].dropna()
    units = {
        "bottles": len(admitted_bottles),
        "bottles_by_lab": admitted_bottles.groupby("lab").size().to_dict(),
        "arms": int(admitted_bottles[["lab", "arm"]].drop_duplicates().shape[0]),
        "labs": int(admitted_bottles["lab"].nunique()),
        "biochar_materials": 1,
        "committed_biochar_descriptors": 0,
        "admitted_cycles": len(primary_cycles),
        "time_rows_in_admitted_cycles": int(
            methane.merge(primary_cycles[["lab", "batch_id", "bottle_id"]]).shape[0]
        ),
        "min_permutation_p_floor": float(floors.min()),
        "ml_defensible": False,
        "reason": "Rows are repeated measures of a few bottles; one material means no "
        "descriptor variation; arm-level units are fewer than model parameters.",
    }

    # Post-freeze check of Events!6/7 (outcome events, not exclusions): each LBE
    # control's yield relative to the median admitted biochar bottle, per batch.
    lbe = values[(values["lab"] == "LBE") & values["evaluable"]]
    is_ctrl = lbe["source_condition_inoculation"].map(_norm) == "[0]"
    reference = lbe[~is_ctrl].groupby("batch_id")[TARGET].median()
    event_check = {}
    for bottle in ("IV.1", "IV.2", "IV.3"):
        own = lbe[lbe["bottle_id"] == bottle].set_index("batch_id")[TARGET]
        event_check[bottle] = {
            int(b): round(float(own[b] / reference[b]), 3) for b in own.index if b in reference
        }

    # Development comparator (context only, non-commensurate)
    comp = spec["development_comparator"]
    dev = pd.read_csv(ROOT / comp["path"])
    dev = dev[(dev["study_id"] == comp["study_id"]) & (dev["treatment"] == comp["treatment"])]
    comparator = {}
    for response in comp["responses"]:
        r = dev[dev["response"] == response].iloc[0]
        comparator[response] = {
            "log_response_ratio": float(r["log_response_ratio"]),
            "ci95": [
                float(r["log_response_ratio_ci95_low"]),
                float(r["log_response_ratio_ci95_high"]),
            ],
        }
    for row in effects[effects["analysis"] == "primary"].itertuples():
        for response, c in comparator.items():
            overlap = np.isfinite(row.ci_low) and not (
                row.ci_high < c["ci95"][0] or row.ci_low > c["ci95"][1]
            )
            c.setdefault("interval_overlap_by_arm", {})[f"{row.lab} {row.arm}"] = bool(overlap)
    comparator["commensurate"] = False

    results = {
        "status": "LOCKED_EVALUATION_COMPLETE",
        "category": "exploratory (preregistered, within-study question A)",
        "not_external_validation": True,
        "spec_sha256": report["spec_sha256"],
        "horizon_days": horizon,
        "windows": report["windows"],
        "primary_verdicts": {f"{lab} {arm}": v for (lab, arm), v in primary.items()},
        "primary_not_evaluable": {
            "BRL": "Frozen rule required a 5.5 d observation in every window batch; BRL "
            "batch 6 ends at 5.51 d without one, so every BRL bottle lost a window batch."
        }
        if summaries.loc[summaries["lab"] == "BRL", "complete"].eq(False).all()
        else {},
        "protocol_deviations": [
            {
                "id": "D1",
                "locked": False,
                "discovered_after_freeze": True,
                "description": "Horizon recomputed as the largest 0.5 d multiple observed in "
                f"every admitted cycle ({corrected:g} d) instead of flooring the shortest "
                "last-observed time. Reported beside, never instead of, the locked result.",
            }
        ],
        "deviation_verdicts": {f"{lab} {arm}": v for (lab, arm), v in d1.items()},
        "cross_lab_agreement_deviation": agreement_d1,
        "decisive_primary_contrasts": len(decisive),
        "cross_lab_agreement": agreement,
        "variance_components": variance,
        "cycle_kinetics_summary": kin_summary,
        "independent_units": units,
        "cycles_total": len(admission),
        "cycles_not_admitted": int((~admission["admitted_primary"]).sum()),
        "event_check_control_yield_over_other_controls": event_check,
        "development_comparator": comparator,
        "incomplete_bottles_primary": summaries.loc[~summaries["complete"], "bottle_id"].tolist(),
    }
    partition = failure_partition({**results, "cross_lab_agreement": lab_disagree})

    output.mkdir(parents=True, exist_ok=True)
    _write(effects, output / "sanglier_2022_locked_effects.csv")
    _write(summaries, output / "sanglier_2022_bottle_summaries.csv")
    _write(variance_frame, output / "sanglier_2022_variance_components.csv")
    _write(kinetics, output / "sanglier_2022_cycle_kinetics.csv", digits=6)
    _write(truncation, output / "sanglier_2022_truncation_extrapolation.csv", digits=6)
    _write(partition, output / "sanglier_2022_generalization_failure_partition.csv")
    (output / "sanglier_2022_locked_evaluation.json").write_text(
        json.dumps(results, indent=2, sort_keys=True, default=float) + "\n", encoding="utf-8"
    )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=VALIDATION)
    results = build(parser.parse_args().output_dir)
    print(json.dumps({k: results[k] for k in ("primary_verdicts", "deviation_verdicts")}, indent=2))


if __name__ == "__main__":
    main()
