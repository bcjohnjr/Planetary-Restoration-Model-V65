#!/usr/bin/env python3
"""Aggregate the seven V65 three-model schedule experiments into publication tables."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ORDER = [
    "canonical_peak15p2",
    "scaled_peak5p0",
    "scaled_peak10p0",
    "scaled_peak20p0",
    "same_total_uniform",
    "same_total_peak20_early",
    "same_total_peak20_late",
]
FIXED_TOTAL = [
    "canonical_peak15p2",
    "same_total_uniform",
    "same_total_peak20_early",
    "same_total_peak20_late",
]
DOSE_RATE = [
    "scaled_peak5p0",
    "scaled_peak10p0",
    "canonical_peak15p2",
    "scaled_peak20p0",
]


def load_summaries(root: Path) -> dict[str, dict]:
    found = {}
    for p in root.rglob("schedule_case_summary.json"):
        s = json.loads(p.read_text(encoding="utf-8"))
        case = s["case"]
        if case in found:
            raise RuntimeError(f"Duplicate summary for {case}")
        found[case] = s
    missing = [c for c in ORDER if c not in found]
    if missing:
        raise RuntimeError(f"Missing schedule cases: {missing}")
    return found


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="experiment_artifacts")
    ap.add_argument("--outdir", default="v65_results")
    args = ap.parse_args()

    root = Path(args.root)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    by_case = load_summaries(root)

    rows = []
    for case in ORDER:
        s = by_case[case]
        f = s["final_2183"]
        sh = s["oscar_reservoir_shares_2183"]
        rows.append({
            "case": case,
            "cumulative_cdr_gtco2": s["cumulative_cdr_gtco2"],
            "peak_cdr_gtco2_per_year": s["peak_cdr_gtco2_per_year"],
            "first_cdr_year": s["first_positive_cdr_year"],
            "last_cdr_year": s["last_positive_cdr_year"],
            "first_persistent_hector_outside_fair": s["first_5yr_persistent_hector_outside_fair_p05_p95"],
            "first_persistent_oscar_outside_fair": s["first_5yr_persistent_oscar_median_outside_fair_p05_p95"],
            "fair_delta_co2_2183_ppm": f["fair_delta_co2_p50_ppm"],
            "hector_delta_co2_2183_ppm": f["hector_delta_co2_ppm"],
            "oscar_delta_co2_2183_ppm": f["oscar_delta_co2_p50_ppm"],
            "fair_response_2183": f["fair_response_fraction_p50"],
            "hector_response_2183": f["hector_response_fraction"],
            "oscar_response_2183": f["oscar_response_fraction_p50"],
            "three_model_response_span_2183": f["three_model_response_span"],
            "oscar_atmospheric_share_2183": sh["atmospheric_benefit_fraction_of_cdr"],
            "oscar_land_compensation_share_2183": sh["land_compensation_fraction_of_cdr"],
            "oscar_ocean_compensation_share_2183": sh["ocean_compensation_fraction_of_cdr"],
            "oscar_budget_residual_share_2183": sh["budget_residual_fraction_of_cdr"],
        })

    table = pd.DataFrame(rows)
    table.to_csv(outdir / "v65_three_model_schedule_summary.csv", index=False)

    fixed = table[table["case"].isin(FIXED_TOTAL)].copy()
    fixed_total_spread = float(fixed["cumulative_cdr_gtco2"].max() - fixed["cumulative_cdr_gtco2"].min())
    if fixed_total_spread >= 1e-6:
        raise RuntimeError(f"Fixed-total design was not preserved: {fixed_total_spread}")

    dose = table[table["case"].isin(DOSE_RATE)].copy().sort_values("peak_cdr_gtco2_per_year")
    timing = table[table["case"].isin(FIXED_TOTAL)].copy()

    metrics = [
        "fair_response_2183",
        "hector_response_2183",
        "oscar_response_2183",
        "three_model_response_span_2183",
        "oscar_land_compensation_share_2183",
        "oscar_ocean_compensation_share_2183",
    ]

    dose_correlations = {}
    if len(dose) >= 3:
        x = dose["peak_cdr_gtco2_per_year"].to_numpy(float)
        for m in metrics:
            y = dose[m].to_numpy(float)
            if float(np.std(x)) == 0.0 or float(np.std(y)) == 0.0:
                dose_correlations[m] = None
            else:
                corr = float(np.corrcoef(x, y)[0, 1])
                dose_correlations[m] = corr if np.isfinite(corr) else None

    timing_ranges = {
        m: float(timing[m].max() - timing[m].min())
        for m in metrics
    }

    canonical = table.loc[table["case"] == "canonical_peak15p2"].iloc[0].to_dict()
    result = {
        "experiment": "V65 seven-schedule three-model CDR generality and mechanism matrix",
        "status": "PASS",
        "case_count": len(rows),
        "fixed_total_design": {
            "cases": FIXED_TOTAL,
            "max_minus_min_cumulative_cdr_gtco2": fixed_total_spread,
            "passes": fixed_total_spread < 1e-6,
            "timing_only_metric_ranges": timing_ranges,
        },
        "dose_rate_design": {
            "cases": DOSE_RATE,
            "pearson_correlations_with_peak_rate": dose_correlations,
            "note": "Four predeclared points are descriptive evidence, not a universal dose-response law.",
        },
        "canonical_2183": canonical,
        "predeclared_questions": [
            "Does long-horizon FaIR/Hector/OSCAR separation persist when CDR amplitude changes?",
            "At fixed cumulative CDR, how strongly does timing alter atmospheric response efficacy?",
            "Does OSCAR land/ocean compensation change systematically with rate or timing?",
            "Is three-model spread itself state- or pathway-dependent?",
        ],
        "claim_rule": (
            "A universal threshold is not claimed. Mechanistic interpretation requires schedule-robust behavior "
            "and reservoir compensation consistent with the direction of cross-model response changes."
        ),
        "cases": rows,
    }
    (outdir / "v65_three_model_schedule_summary.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )

    md = [
        "# V65 seven-schedule three-model results",
        "",
        "| Case | CDR total (GtCO2) | Peak | FaIR 2183 | Hector 2183 | OSCAR 2183 | 3-model span | OSCAR land comp. | OSCAR ocean comp. |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in table.iterrows():
        md.append(
            f"| {r['case']} | {r['cumulative_cdr_gtco2']:.3f} | {r['peak_cdr_gtco2_per_year']:.3f} | "
            f"{r['fair_response_2183']:.4f} | {r['hector_response_2183']:.4f} | {r['oscar_response_2183']:.4f} | "
            f"{r['three_model_response_span_2183']:.4f} | {r['oscar_land_compensation_share_2183']:.4f} | "
            f"{r['oscar_ocean_compensation_share_2183']:.4f} |"
        )
    md += [
        "",
        "The four fixed-total cases isolate timing/rate effects from cumulative removal.",
        "The scaled-shape cases test rate/dose sensitivity without changing the temporal shape.",
        "No universal threshold is inferred automatically from this matrix.",
    ]
    (outdir / "V65_THREE_MODEL_SCHEDULE_RESULTS.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
