# Cost Baselines

This directory holds committed cost baselines used by phase exit gates.

## Naming

Baseline files follow the pattern `<date>-<run_id>.json`, where `<date>` is
the run date in `YYYY-MM-DD` form and `<run_id>` is the run identifier.
Example: `2026-08-07-adaptive-fusion-verification.json`

## Copy, Do Not Move

The run-cost-summary artifact lives beside its run's `authoritative-receipts.json`
in the run directory (for example, `plans/<feature-slug>/run-cost-summary.json`).
A baseline in this directory is a **copy** of that artifact, not a move. The
original stays with its run.

`plans/` is gitignored, so a baseline held there is invisible to another clone
or another developer. That is why this directory exists: baselines must be
verifiable from any clone.

## What Is Graded Against Baselines

Phase exit gates compare a later run's per-lane cost against a recorded
baseline. A gate checks whether the later run's lane costs are within the
baseline's recorded bounds. Baselines are the reference; the later run is the
candidate.

## Honesty Rule

Baselines carry `measurement_source` provenance for every row. A baseline
consisting entirely of `unavailable` rows is **valid evidence of absence**,
not a failed baseline. It proves the measurement wiring ran and found no usage
data -- that is honest evidence.

When a run mixes measurement sources, readers must read `lanes[]`, not
`totals[]`. In kernel 0.9.0, `totals` is deliberately null when measurement
sources are mixed, so `totals[]` carries no useful signal in that case. The
per-lane breakdown in `lanes[]` is authoritative.
