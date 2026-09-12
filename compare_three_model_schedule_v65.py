#!/usr/bin/env python3
"""Summarize one V65 FaIR/Hector/OSCAR schedule experiment."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

GTCO2_PER_PPM = 2.124 * (44.009 / 12.011)
MILESTONES = (2040, 2100, 2156, 2183)


def nearest(df: pd.DataFrame, year: int) -> pd.Series:
    return df.iloc[int(np.argmin(np.abs(df["year"].to_numpy(float) - year)))]


def first_persistent(mask: np.ndarray, years: np.ndarray, n: int = 5):
    run = 0
    for i, flag in enumerate(mask):
        run = run + 1 if bool(flag) else 0
        if run >= n:
            return int(years[i - n + 1])
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--trajectory", required=True)
    ap.add_argument("--fair", required=True)
    ap.add_argument("--fair-summary", required=True)
    ap.add_argument("--hector", required=True)
    ap.add_argument("--hector-summary", required=True)
    ap.add_argument("--oscar", required=True)
    ap.add_argument("--oscar-summary", required=True)
    ap.add_argument("--oscar-reservoir", required=True)
    ap.add_argument("--output", default="schedule_case_summary.json")
    ap.add_argument("--milestones-output", default="schedule_case_milestones.csv")
    args = ap.parse_args()

    tr = pd.read_csv(args.trajectory).sort_values("year")
    f = pd.read_csv(args.fair).sort_values("year")
    h = pd.read_csv(args.hector).sort_values("year")
    o = pd.read_csv(args.oscar).sort_values("year")
    r = pd.read_csv(args.oscar_reservoir).sort_values("year")
    fs = json.loads(Path(args.fair_summary).read_text(encoding="utf-8"))
    hs = json.loads(Path(args.hector_summary).read_text(encoding="utf-8"))
    os_ = json.loads(Path(args.oscar_summary).read_text(encoding="utf-8"))

    expected = np.arange(2026, 2184)
    years = tr["year"].to_numpy(dtype=int)
    if len(tr) != 158 or not np.array_equal(years, expected):
        raise RuntimeError("Trajectory must be exact years 2026-2183")

    ident = (
        tr["gross_co2_gtco2"]
        + tr["permafrost_co2_gtco2"]
        + tr["stored_carbon_reversal_gtco2"]
        - tr["cdr_gtco2"]
    )
    if float(np.max(np.abs(ident - tr["net_co2_gtco2"]))) >= 1e-9:
        raise RuntimeError("Trajectory mass balance failed")

    cumulative = float(tr["cdr_gtco2"].sum())
    peak = float(tr["cdr_gtco2"].max())
    positive = tr.loc[tr["cdr_gtco2"] > 1e-12, "year"]

    if os_["status"] != "PASS" or not all(bool(v) for v in os_["gates"].values()):
        raise RuntimeError("OSCAR result did not pass its scientific gates")
    if abs(float(os_["canonical_cdr_2027_2183_gtco2"]) - cumulative) > 1e-6:
        raise RuntimeError("OSCAR cumulative CDR does not match the schedule trajectory")

    ff = f.copy()
    hh = h.copy()
    oo = o.copy()
    ff["iyear"] = np.rint(ff["year"].to_numpy(float)).astype(int)
    hh["iyear"] = np.rint(hh["year"].to_numpy(float)).astype(int)
    oo["iyear"] = np.rint(oo["year"].to_numpy(float)).astype(int)

    ff = ff[(ff.iyear >= 2027) & (ff.iyear <= 2183)].drop_duplicates("iyear")
    hh = hh[(hh.iyear >= 2027) & (hh.iyear <= 2183)].drop_duplicates("iyear")
    oo = oo[(oo.iyear >= 2027) & (oo.iyear <= 2183)].drop_duplicates("iyear")

    aligned = ff[[
        "iyear", "fraction_p05", "fraction_p50", "fraction_p95", "delta_co2_p50_ppm"
    ]].merge(
        hh[["iyear", "apparent_response_fraction", "delta_co2_ppm"]],
        on="iyear",
        how="inner",
    ).merge(
        oo[["iyear", "fraction_p05", "fraction_p50", "fraction_p95", "delta_co2_p50_ppm"]].rename(
            columns={
                "fraction_p05": "oscar_fraction_p05",
                "fraction_p50": "oscar_fraction_p50",
                "fraction_p95": "oscar_fraction_p95",
                "delta_co2_p50_ppm": "oscar_delta_co2_p50_ppm",
            }
        ),
        on="iyear",
        how="inner",
    )

    valid = aligned[
        np.isfinite(aligned["fraction_p50"])
        & np.isfinite(aligned["apparent_response_fraction"])
        & np.isfinite(aligned["oscar_fraction_p50"])
    ].copy()
    if len(valid) < 100:
        raise RuntimeError("Too few aligned finite model years")

    hector_outside_fair = (
        (valid["apparent_response_fraction"] < valid["fraction_p05"])
        | (valid["apparent_response_fraction"] > valid["fraction_p95"])
    ).to_numpy(bool)
    oscar_median_outside_fair = (
        (valid["oscar_fraction_p50"] < valid["fraction_p05"])
        | (valid["oscar_fraction_p50"] > valid["fraction_p95"])
    ).to_numpy(bool)

    milestones = []
    for y in MILESTONES:
        fr = nearest(f, y)
        hr = nearest(h, y)
        orow = nearest(o, y)
        rr = nearest(r, y)
        fair_p50 = float(fr["fraction_p50"])
        hector = float(hr["apparent_response_fraction"])
        oscar_p50 = float(orow["fraction_p50"])
        milestones.append({
            "year": y,
            "fair_delta_co2_p50_ppm": float(fr["delta_co2_p50_ppm"]),
            "hector_delta_co2_ppm": float(hr["delta_co2_ppm"]),
            "oscar_delta_co2_p50_ppm": float(orow["delta_co2_p50_ppm"]),
            "fair_response_fraction_p05": float(fr["fraction_p05"]),
            "fair_response_fraction_p50": fair_p50,
            "fair_response_fraction_p95": float(fr["fraction_p95"]),
            "hector_response_fraction": hector,
            "oscar_response_fraction_p05": float(orow["fraction_p05"]),
            "oscar_response_fraction_p50": oscar_p50,
            "oscar_response_fraction_p95": float(orow["fraction_p95"]),
            "hector_minus_fair": hector - fair_p50,
            "oscar_minus_fair": oscar_p50 - fair_p50,
            "oscar_minus_hector": oscar_p50 - hector,
            "three_model_response_span": max(fair_p50, hector, oscar_p50) - min(fair_p50, hector, oscar_p50),
            "oscar_atmospheric_benefit_p50_gtco2": float(rr["atmospheric_benefit_p50_gtco2"]),
            "oscar_land_compensation_p50_gtco2": float(rr["land_compensation_p50_gtco2"]),
            "oscar_ocean_compensation_p50_gtco2": float(rr["ocean_compensation_p50_gtco2"]),
            "oscar_budget_residual_p50_gtco2": float(rr["budget_residual_p50_gtco2"]),
        })

    final = milestones[-1]
    oscar_total = float(nearest(r, 2183)["cumulative_cdr_gtco2"])
    if oscar_total <= 0:
        raise RuntimeError("Final OSCAR cumulative CDR must be positive")

    final_reservoir_shares = {
        "atmospheric_benefit_fraction_of_cdr": final["oscar_atmospheric_benefit_p50_gtco2"] / oscar_total,
        "land_compensation_fraction_of_cdr": final["oscar_land_compensation_p50_gtco2"] / oscar_total,
        "ocean_compensation_fraction_of_cdr": final["oscar_ocean_compensation_p50_gtco2"] / oscar_total,
        "budget_residual_fraction_of_cdr": final["oscar_budget_residual_p50_gtco2"] / oscar_total,
    }

    summary = {
        "experiment": "V65 seven-schedule three-model CDR generality and mechanism matrix",
        "case": args.case,
        "trajectory_years": [2026, 2183],
        "cumulative_cdr_gtco2": cumulative,
        "peak_cdr_gtco2_per_year": peak,
        "first_positive_cdr_year": int(positive.min()),
        "last_positive_cdr_year": int(positive.max()),
        "first_5yr_persistent_hector_outside_fair_p05_p95": first_persistent(
            hector_outside_fair, valid["iyear"].to_numpy(dtype=int), 5
        ),
        "first_5yr_persistent_oscar_median_outside_fair_p05_p95": first_persistent(
            oscar_median_outside_fair, valid["iyear"].to_numpy(dtype=int), 5
        ),
        "milestones": milestones,
        "final_2183": final,
        "oscar_reservoir_shares_2183": final_reservoir_shares,
        "forcing_gates": {
            "fair_tolerance_wm2": float(fs["forcing_match_tolerance_wm2"]),
            "fair_on_max_abs_wm2": float(fs["forcing_match_max_abs_on_wm2"]),
            "fair_off_max_abs_wm2": float(fs["forcing_match_max_abs_off_wm2"]),
            "hector_tolerance_wm2": float(hs["forcing_match_tolerance_wm2"]),
            "hector_on_max_abs_wm2": float(hs["forcing_match_max_abs_on_wm2"]),
            "hector_off_max_abs_wm2": float(hs["forcing_match_max_abs_off_wm2"]),
            "oscar_tolerance_wm2": float(os_["forcing_protocol"]["tolerance_wm2"]),
            "oscar_on_max_abs_wm2": float(os_["forcing_protocol"]["on_max_abs_median_error_wm2"]),
            "oscar_off_max_abs_wm2": float(os_["forcing_protocol"]["off_max_abs_median_error_wm2"]),
        },
        "accounting_note": (
            "FaIR, Hector and OSCAR retain their native annual integration conventions. "
            "Compare delta-CO2 directly as the primary cross-model quantity; response fractions are also reported "
            "with each model's native cumulative-CDR accounting."
        ),
        "claim_boundary": (
            "This schedule experiment tests CDR timing/rate sensitivity while holding non-CDR source terms fixed. "
            "Model disagreement and reservoir compensation are results, not failure gates. No universal threshold is inferred automatically."
        ),
    }

    Path(args.output).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    pd.DataFrame(milestones).to_csv(args.milestones_output, index=False)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
