# V65 — Seven-Schedule Three-Model CDR Generality + Mechanism Experiment

This package is deliberately **flat**. Every supplied file is at the ZIP root.

## Scientific purpose

Run seven predeclared CDR schedules through the already-proven matched-forcing implementations of:

- FaIR 2.2.4 — 841 calibrated/constrained configurations
- Hector 3.5.0
- OSCAR v3.3 — 200-member ensemble

For every schedule, FaIR first derives the common future non-CO2 forcing trajectory. Hector and OSCAR are then matched to that same trajectory. OSCAR additionally reports land-sink compensation, ocean-sink compensation, atmospheric benefit, and carbon-budget residual.

The matrix tests whether long-horizon atmospheric CDR effectiveness and inter-model divergence depend on removal **rate, cumulative dose, and timing**.

## Seven schedules

1. `canonical_peak15p2`
2. `scaled_peak5p0`
3. `scaled_peak10p0`
4. `scaled_peak20p0`
5. `same_total_uniform`
6. `same_total_peak20_early`
7. `same_total_peak20_late`

The final four cases (`canonical`, `uniform`, `early`, `late`) have the same cumulative removal, isolating timing/rate effects. The scaled cases preserve the canonical temporal shape while changing amplitude.

## Upload / run

Upload all files to the root of a new V65 repository. Then move only:

`v65-seven-schedule-three-model.yml`

to:

`.github/workflows/v65-seven-schedule-three-model.yml`

Leave every Python file at repository root.

Then run:

**Actions → V65 Seven-Schedule Three-Model Generality → Run workflow**

The seven cases are parallelized up to four at a time. Each case runs OSCAR with 200 members, so this is intentionally compute-heavy. A single case may take well over an hour; the job timeout is 330 minutes.

## Reproducibility pins

- V62.2 validation base commit: `89a0f4ab18df25db3a05d4e39c6db06405456505`
- FaIR source commit: `ec46fefc8f8c6b560a8b78ab1f4a9a5e04537f79`
- OSCAR source commit: `3ce008400e06363564e5981a35cbc32377d41d86`
- Hector package version: `3.5.0`

## Interpretation boundary

This experiment does **not** automatically infer a universal CDR-efficiency threshold. Inter-model disagreement is retained as a result. A stronger mechanism claim requires schedule-robust behavior and reservoir compensation that changes consistently with the observed atmospheric response.

## Proven OSCAR runner

`run_oscar_matched_forcing_v63.py` is intentionally retained under its V63 filename because it is the exact runner that just passed the canonical matched-forcing OSCAR experiment. V65 reuses it unchanged for each schedule to avoid altering a now-proven implementation.
