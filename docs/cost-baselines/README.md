# Cost Baselines

This directory holds committed cost baselines. Some of them bound a phase exit
gate. Others record that a run's measurement was unavailable or unwired, and
bound nothing -- they are kept because the absence is itself evidence, not
because a gate can use them. Read the Honesty Rule below before treating any
file here as a reference for a comparison.

## Naming

Baseline files follow the pattern `<date>-<run_id>.json`, where `<date>` is the
date the baseline was **captured** in `YYYY-MM-DD` form and `<run_id>` is the
run identifier. The date a baseline was captured is often later than the date
the run executed -- a backfilled baseline is normal. The run's first recorded
event time lives at `invocation.first_event_at`; use its calendar date for the
run date, never the filename's capture date.

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

The baseline and candidate must describe comparable work: the same workflow
boundary, logical lanes, measurement unit, and accounting method. In particular,
implementation-chunk input bytes are not a baseline for selective review-loop
passes. Compare a full `dm-review-loop` pass with a later selective pass from
the same loop contract.

The former `2026-08-08-r1-review-burn-cuts.json` was removed from `*.json`
baseline discovery because it was unusable for this comparison. It was
byte-identical to `plans/r1-review-burn-cuts/run4/run-cost-summary.json` and is
reproducible from run4's receipts: Codex implemented chunks 01-05, chunk 06 was
not started, and 5/5 coverage is correct for that attempt. The observation-only
independent prediction forecast a separate six-chunk attempt using Claude Opus;
it is not execution evidence for run4, even though both artifacts reuse the same
run ID. The deleted baseline is excluded solely because implementation-chunk
input bytes are not comparable to `dm-review-loop` lane input bytes. See the
adjacent `.unusable.md` notice and do not use the removed rows or total for the
R1 input-reduction gate.

## Honesty Rule

Baselines carry `measurement_source` provenance for every row. A baseline
consisting entirely of `unavailable` rows is structurally valid, but it is
**not** evidence that measurement ran. A run that never invoked
`openrouter-usage` or `lane-input-bytes` produces exactly the same artifact as
a run that invoked them and found nothing.

An **empty** `lanes[]` says even less. All-`unavailable` rows at least name the
attempts that ran; zero rows name nothing at all, and the artifact cannot bound
any gate because there is no per-lane cost to compare a candidate against.
`2026-08-07-adaptive-fusion-verification.json` is such a file: it is the
committed example of an unwired emission boundary, not a gate reference.

Two different things are easy to confuse here, so name them:

- **Infrastructure evidence** -- the emission command ran and wrote an
  artifact. An all-`unavailable` baseline proves this and nothing more.
- **Lane usage evidence** -- the attempts that executed are accounted for.
  Only populated `lanes[]` rows prove this.

Before recording an all-`unavailable` baseline, confirm from the run's own
receipt stream that lanes executed and the translators were called. If they
were not, the baseline records an unwired emission boundary, not an honest
absence.

When a run mixes measurement sources, readers must read `lanes[]`, not
`totals`. `lanes` is an array of per-lane rows; `totals` is a single object
that is always present and is never null as a whole. Each of its usage fields
is null unless every expected attempt contributed that field **and** all
contributing rows agree on `measurement_source`; `usage_provenance` and
`cost_provenance` record which rule applied. Under mixed sources those fields
read null, so the per-lane breakdown in `lanes[]` is the authoritative
reading.

Units differ by source, so rows are not interchangeable even inside `lanes[]`.
A row with `measurement_source: "openrouter_api_receipt"` reports provider
tokens in `input_usage_count`; a row with
`measurement_source: "estimated_input_bytes"` reports bytes in `input_bytes`.
Never compare or add the two.
