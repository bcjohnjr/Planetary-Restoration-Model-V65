#!/usr/bin/env python3
"""Apply the already-green V63 2183-horizon patch to the pinned V62.2 Hector runner."""
from __future__ import annotations

import argparse
import re
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    args = ap.parse_args()

    src = Path(args.input)
    dst = Path(args.output)
    text = src.read_text(encoding="utf-8")

    extension_pattern = re.compile(
        r"""
        \n
        \s*last\s*<-\s*x\[nrow\(x\),\s*\]
        \s*
        if\s*\(\s*max\(x\$year\)\s*<\s*2300\s*\)
        \s*\{
        .*?
        \n\s*\}
        \s*
        (?=yrs\s*<-\s*as\.numeric\(x\$year\))
        """,
        re.VERBOSE | re.DOTALL,
    )
    text, n_extension = extension_pattern.subn("\n", text, count=1)
    if n_extension != 1:
        raise SystemExit(f"Expected exactly one V62 2183-to-2300 extension block; found {n_extension}")

    text, n_year_check = re.subn(
        r"as\.numeric\(\s*2026\s*:\s*2300\s*\)",
        "as.numeric(2026:2183)",
        text,
        count=1,
    )
    if n_year_check != 1:
        raise SystemExit("Failed to patch 2026:2300 Hector year check")

    text, n_match = re.subn(
        r"match_years\s*<-\s*2027\s*:\s*2300",
        "match_years <- 2027:2183",
        text,
        count=1,
    )
    if n_match != 1:
        raise SystemExit("Failed to patch Hector match_years")

    run_pattern = re.compile(r"run\s*\(\s*core\s*,\s*2300\s*\)", re.VERBOSE)
    text, n_run = run_pattern.subn("run(\n      core,\n      2183\n    )", text, count=1)
    if n_run != 1:
        raise SystemExit("Failed to patch Hector run horizon")

    milestone_pattern = re.compile(
        r"""
        yy\s+in\s+c\s*\(
        \s*2040\s*,\s*2100\s*,\s*2156\s*,
        \s*2184\s*,\s*2200\s*,\s*2300\s*\)
        """,
        re.VERBOSE,
    )
    replacement = """yy in c(
        2040,
        2100,
        2156,
        2183
      )"""
    text, n_milestones = milestone_pattern.subn(replacement, text, count=1)
    if n_milestones != 1:
        raise SystemExit("Failed to patch Hector milestone years")

    text = text.replace("2026-2300", "2026-2183")
    text = text.replace("2027-2300", "2027-2183")
    text = text.replace("through 2300", "through 2183")
    text = text.replace(
        "V62 removal-ON/OFF with FaIR-derived harmonized",
        "V65 schedule-matrix removal-ON/OFF with FaIR-derived harmonized",
    )

    remaining = [line for line in text.splitlines() if "2300" in line]
    if remaining:
        raise SystemExit("Unexpected 2300 references remain after patch:\n" + "\n".join(remaining))

    dst.write_text(text, encoding="utf-8")
    print(f"Patched Hector runner written to {dst}")


if __name__ == "__main__":
    main()
