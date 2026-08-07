# Cost Baselines

This directory holds committed cost baselines used by phase exit gates.

## Naming

Baseline files follow the pattern `<date>-<run_id>.json`, where `<date>` is the
date the baseline was **captured** in `YYYY-MM-DD` form and `<run_id>` is the
run identifier. The date a baseline was captured is often later than the date
the run executed -- a backfilled baseline is normal. The run's own date lives in
the artifact's `run_identity` block; read it there, never from the filename.

Example: `2026-08-07-adaptive-fusion-verification.json` is the
`adaptive-fusion-verification` run (executed 2026-07-22) captured as a baseline
on 2026-08-07.

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
`totals`. `lanes` is an array of per-lane rows; `totals` is a single object. In
kernel 0.9.0, `totals` is deliberately null when measurement sources are mixed,
so it carries no useful signal in that case. The per-lane breakdown in `lanes[]`
is authoritative.

Units differ by source, so rows are not interchangeable even inside `lanes[]`.
A row with `measurement_source: "openrouter_api_receipt"` reports provider
tokens in `input_usage_count`; a row with
`measurement_source: "estimated_input_bytes"` reports bytes in `input_bytes`.
Never compare or add the two.
