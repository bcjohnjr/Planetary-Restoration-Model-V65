#!/usr/bin/env python3
"""Generate the seven predeclared V65 CDR schedule-generalization trajectories.

All non-CDR source terms are held exactly equal to the pinned V62.2 canonical
trajectory. Only cdr_gtco2 changes. Every output spans 2026-2183 and satisfies
net = gross + permafrost + stored-carbon reversal - CDR exactly to floating
precision.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

REQUIRED = [
    "year",
    "gross_co2_gtco2",
    "permafrost_co2_gtco2",
    "stored_carbon_reversal_gtco2",
    "cdr_gtco2",
    "net_co2_gtco2",
]

ORDER = [
    "canonical_peak15p2",
    "scaled_peak5p0",
    "scaled_peak10p0",
    "scaled_peak20p0",
    "same_total_uniform",
    "same_total_peak20_early",
    "same_total_peak20_late",
]


def validate(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise RuntimeError(f"Missing trajectory columns: {missing}")
    x = df.sort_values("year").reset_index(drop=True).copy()
    expected = np.arange(2026, 2184, dtype=int)
    years = x["year"].to_numpy(dtype=int)
    if len(x) != len(expected) or not np.array_equal(years, expected):
        raise RuntimeError("Expected exactly one row for every year 2026-2183")
    ident = (
        x["gross_co2_gtco2"]
        + x["permafrost_co2_gtco2"]
        + x["stored_carbon_reversal_gtco2"]
        - x["cdr_gtco2"]
    )
    err = float(np.max(np.abs(ident - x["net_co2_gtco2"])))
    if err > 1e-9:
        raise RuntimeError(f"Canonical mass-balance error: {err}")
    if not np.isfinite(x[REQUIRED].to_numpy(dtype=float)).all():
        raise RuntimeError("Non-finite canonical trajectory value")
    if (x["cdr_gtco2"] < -1e-12).any():
        raise RuntimeError("Negative canonical CDR")
    return x


def pulse_schedule(years: np.ndarray, total: float, peak: float, late: bool) -> np.ndarray:
    """Exact-total rectangular pulse, excluding 2026, with at most one fractional year."""
    out = np.zeros(len(years), dtype=float)
    eligible = np.where(years >= 2027)[0]
    n_full = int(total // peak)
    rem = float(total - n_full * peak)
    n_needed = n_full + (1 if rem > 1e-12 else 0)
    if n_needed > len(eligible):
        raise RuntimeError("Pulse cannot fit inside 2027-2183")
    chosen = eligible[-n_needed:] if late else eligible[:n_needed]
    if late:
        if rem > 1e-12:
            out[chosen[0]] = rem
            out[chosen[1:]] = peak
        else:
            out[chosen] = peak
    else:
        out[chosen[:n_full]] = peak
        if rem > 1e-12:
            out[chosen[n_full]] = rem
    return out


def finalize(base: pd.DataFrame, cdr: np.ndarray) -> pd.DataFrame:
    out = base[REQUIRED].copy()
    out["cdr_gtco2"] = np.asarray(cdr, dtype=float)
    out["net_co2_gtco2"] = (
        out["gross_co2_gtco2"]
        + out["permafrost_co2_gtco2"]
        + out["stored_carbon_reversal_gtco2"]
        - out["cdr_gtco2"]
    )
    validate(out)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="external_validation_net_co2_trajectory.csv")
    ap.add_argument("--outdir", default="trajectories")
    args = ap.parse_args()

    source = Path(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    base = validate(pd.read_csv(source))
    years = base["year"].to_numpy(dtype=int)
    canonical = base["cdr_gtco2"].to_numpy(dtype=float)
    canonical_total = float(canonical.sum())
    canonical_peak = float(canonical.max())

    if abs(canonical_total - 2013.8807318595145) > 1e-6:
        raise RuntimeError(f"Unexpected pinned canonical total: {canonical_total}")
    if abs(canonical_peak - 15.2) > 1e-9:
        raise RuntimeError(f"Unexpected pinned canonical peak: {canonical_peak}")
    if abs(float(canonical[0])) > 1e-12:
        raise RuntimeError("2026 CDR must be zero for the predeclared experiment")

    variants: dict[str, tuple[np.ndarray, str, str]] = {}
    variants["canonical_peak15p2"] = (
        canonical.copy(),
        "canonical",
        "Exact pinned canonical pathway; reference case.",
    )
    for peak in (5.0, 10.0, 20.0):
        name = f"scaled_peak{str(peak).replace('.', 'p')}"
        variants[name] = (
            canonical * (peak / canonical_peak),
            "dose_rate",
            f"Canonical time-shape scaled to peak {peak:g} GtCO2/yr.",
        )

    active = years >= 2027
    uniform = np.zeros(len(years), dtype=float)
    uniform[active] = canonical_total / int(active.sum())
    variants["same_total_uniform"] = (
        uniform,
        "timing_fixed_total",
        "Canonical cumulative CDR distributed uniformly over 2027-2183.",
    )
    variants["same_total_peak20_early"] = (
        pulse_schedule(years, canonical_total, 20.0, late=False),
        "timing_fixed_total",
        "Canonical cumulative CDR delivered as early as possible at <=20 GtCO2/yr.",
    )
    variants["same_total_peak20_late"] = (
        pulse_schedule(years, canonical_total, 20.0, late=True),
        "timing_fixed_total",
        "Canonical cumulative CDR delivered as late as possible at <=20 GtCO2/yr.",
    )

    if list(variants) != ORDER:
        raise RuntimeError("Internal case ordering changed")

    manifest_rows = []
    for name in ORDER:
        cdr, family, purpose = variants[name]
        out = finalize(base, cdr)
        path = outdir / f"{name}.csv"
        out.to_csv(path, index=False)
        pos = out.loc[out["cdr_gtco2"] > 1e-12, "year"]
        row = {
            "case": name,
            "family": family,
            "purpose": purpose,
            "file": path.name,
            "cumulative_cdr_gtco2": float(out["cdr_gtco2"].sum()),
            "peak_cdr_gtco2_per_year": float(out["cdr_gtco2"].max()),
            "first_positive_cdr_year": int(pos.min()),
            "last_positive_cdr_year": int(pos.max()),
        }
        manifest_rows.append(row)

    fixed = [
        r["cumulative_cdr_gtco2"]
        for r in manifest_rows
        if r["case"] in {
            "canonical_peak15p2",
            "same_total_uniform",
            "same_total_peak20_early",
            "same_total_peak20_late",
        }
    ]
    spread = float(max(fixed) - min(fixed))
    if spread >= 1e-6:
        raise RuntimeError(f"Fixed-total design failed: spread={spread}")

    manifest = {
        "experiment": "V65 seven-schedule three-model CDR generality and mechanism matrix",
        "years": [2026, 2183],
        "source": source.name,
        "canonical_total_cdr_gtco2": canonical_total,
        "canonical_peak_cdr_gtco2_per_year": canonical_peak,
        "fixed_total_spread_gtco2": spread,
        "held_constant": [
            "gross_co2_gtco2",
            "permafrost_co2_gtco2",
            "stored_carbon_reversal_gtco2",
        ],
        "cases": manifest_rows,
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    pd.DataFrame(manifest_rows).to_csv(outdir / "manifest.csv", index=False)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
