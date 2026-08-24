# run-cost-summary emission contract

This is the canonical source for the `run-cost-summary` emission obligation that
every pipeline and dm-review consumer carries. Consumers embed the paragraph
below **verbatim** rather than linking to it: depot command and skill files must
stay self-contained because Claude Desktop caches each plugin independently and
resolves no cross-file references at read time.

Drift is prevented by generation, not by trust. `tools/sync-run-cost-summary-contract.sh`
rewrites every consumer from the block below, and `--check` mode fails when any
consumer has diverged. `tools/validate-workflow-contracts.sh` runs that check.

## The canonical paragraph

Everything between the two markers is the exact bytes each consumer must carry.
Edit it here and run the sync script; never edit a consumer copy by hand.

<!-- CANONICAL-INVOCATION-FLAG: --matrix "$MODEL_MATRIX_ASSET" -->
<!-- CANONICAL-MATRIX-RESOLUTION: if MODEL_MATRIX_ASSET=$("$WORKFLOW_KERNEL" resolve-plugin-asset --plugin openrouter --asset skills/openrouter-delegate/references/model-matrix.json --minimum-version 1.11.0); then :; else MODEL_MATRIX_ASSET=""; fi -->

<!-- CANONICAL-PARAGRAPH-START -->
The `emit-cost-summary` command is one transaction: it owns the artifact path, clears any stale file, writes a schema-bound `run-cost-summary.json` beside that run's `authoritative-receipts.json`, and appends exactly one receipt line -- the artifact path, or `run-cost-summary: skipped (<reason>)` on any internal failure. It is observation-only: it exits 0 for every measurement outcome, never gates or alters a review, lane, or phase outcome, and its absence never fails one. Exit 6 (receipt write failed after acceptance) appends `skipped (receipt-write-failed)` through the status-aware `||` fallback; exit 2 is an invalid invocation and propagates; any other non-zero status appends `skipped (kernel-unresolvable)`, and a failing final append keeps its own status visible. A refused symlinked receipt path still exits 0 and reports on stderr alone -- a non-zero exit would append through the symlink just refused. Receipt paths are fixed per directory, so concurrent runs sharing one directory overwrite each other: use the invocation's exact-owned root or serialize callers that intentionally share a documented deliverable directory. Pass a coherent installed bundle's matrix asset as `--matrix "$MODEL_MATRIX_ASSET"`; an unreadable or invalid matrix emits one stderr line, skips imputation, and never fails the emission. Populate events with `record-attempt` as each lane settles -- a standalone `--append-to` translator double-counts the attempt, and `lanes: 0` after a run that executed lanes means this boundary is not wired. Full flags: `cli-measurement-commands.md`; otherwise the flags named here are the complete required set.
<!-- CANONICAL-PARAGRAPH-END -->

## Why the concurrency wording is what it is

dm-review writes raw receipts beneath one unique exact-owned root, so those
invocations do not collide. Standalone Pipeline planning artifacts remain a
documented per-feature deliverable. Callers that intentionally target the same
feature directory must serialize; the exact-owned convention does not adopt or
delete that pre-existing deliverable directory.

## The consumers

Eleven files embed the paragraph. Seven are dm-review, four are pipeline:

| File | Receipt directory |
|------|-------------------|
| `plugins/dm-review/skills/review/SKILL.md` | `<exact-run-root>/review/` |
| `plugins/dm-review/commands/dm-review.md` | `<exact-run-root>/review/` |
| `plugins/dm-review/skills/dm-review/SKILL.md` | `<exact-run-root>/review/` |
| `plugins/dm-review/commands/dm-review-loop.md` | `<exact-run-root>/review/` |
| `plugins/dm-review/skills/dm-review-loop/SKILL.md` | `<exact-run-root>/review/` |
| `plugins/dm-review/commands/dm-review-visual.md` | `<exact-run-root>/review/` |
| `plugins/dm-review/skills/dm-review-visual/SKILL.md` | `<exact-run-root>/review/` |
| `plugins/pipeline/commands/pipeline.md` | `plans/<feature-slug>/` |
| `plugins/pipeline/skills/pipeline/SKILL.md` | `plans/<feature-slug>/` |
| `plugins/pipeline/commands/pipeline-run.md` | `plans/<feature>/` |
| `plugins/pipeline/skills/pipeline-run/SKILL.md` | `plans/<feature>/` |

The invocation's receipt and output paths are consumer-specific and
hand-maintained. Its canonical matrix-resolution line and `--matrix` flag are
generated and checked together with the paragraph.

## Producing the events the summary reads

`run-cost-summary` aggregates `attempt_usage` events already present in the
run's receipt stream. It invents nothing. A run that appends no usage events
gets an artifact whose rows are all `unavailable` -- structurally valid and
informationally empty.

Two kernel commands produce those events:

- `openrouter-usage` translates one schemaVersion-2 OpenRouter wrapper receipt
  into an attempt-scoped usage payload with real provider-reported token counts
  and cost.
- `lane-input-bytes` computes deterministic input-byte accounting for Codex and
  Claude lanes, which expose no usage receipt surface at all.

Both are documented in `cli-measurement-commands.md`. An orchestrator that runs
lanes but never invokes them will emit a structurally correct, permanently empty
cost summary.
