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

<!-- CANONICAL-PARAGRAPH-START -->
The `emit-cost-summary` command is one transaction: it owns the artifact path, clears any stale file left there by an earlier run, writes a schema-bound `run-cost-summary.json` beside that run's own `authoritative-receipts.json`, and appends exactly one inventory line to the run receipt naming what actually happened -- the artifact path on success, or `run-cost-summary: skipped (<reason>)` on any internal failure. It always exits 0, because the artifact is observation-only: it never gates, blocks, waives, or alters a review, lane, or phase outcome, and its absence never fails one. The `||` fallback beside it covers the one case no process inside the kernel can report -- the launcher itself failing to run. Receipt paths are fixed for a given receipt directory, so two concurrent runs sharing one directory overwrite each other: serialize them, or give each run its own directory. The command refuses a symlinked artifact or receipt path and auto-detects a dirty working tree via `git status --porcelain`. Populate the events it reads: after each lane attempt, translate that attempt's OpenRouter wrapper receipt with `openrouter-usage`, or that lane's Codex/Claude input files with `lane-input-bytes`, passing `--append-to <authoritative-receipts.json> --run-id <id> --occurred-at <ISO-8601> --authoritative-receipt <path>` so the translator wraps the payload as an `attempt_usage` receipt and appends it under an exclusive lock in one validated step. Emit a row for every attempt including failed ones -- an attempt missing from the receipt stream is indistinguishable from one that never ran, and its spend disappears with it. A `lanes: 0` artifact after a run that executed lanes means this boundary is not wired; a structurally valid artifact with zero measured lanes proves the command ran, never that lanes were measured. Full command reference, when the workflow-kernel plugin is installed alongside this one: `plugins/workflow-kernel/skills/workflow-kernel/references/cli-measurement-commands.md`; if that path is not readable from this cache, the flags named above are the complete required set.
<!-- CANONICAL-PARAGRAPH-END -->

## Why the concurrency wording is what it is

An earlier draft claimed the artifact was "run-scoped ... so concurrent
instances never collide." That was false for every consumer: dm-review writes to
the fixed `.claude/ux-review/workflow-kernel/`, and pipeline writes to
`plans/<feature>/`, which is per-feature rather than per-run. Neither carries a
run identifier. The paragraph now states the real property and the real
operational requirement.

Making the paths genuinely run-scoped is a separate change: it moves
`authoritative-receipts.json`, the prediction and observation artifacts, the
contribution inputs, and the Docker node artifacts under a run directory, and it
touches every command that names one of those paths. Until that lands, the
contract must not promise isolation the layout does not provide.

## The consumers

Eleven files embed the paragraph. Seven are dm-review, four are pipeline:

| File | Receipt directory |
|------|-------------------|
| `plugins/dm-review/skills/review/SKILL.md` | `.claude/ux-review/workflow-kernel/` |
| `plugins/dm-review/commands/dm-review.md` | `.claude/ux-review/workflow-kernel/` |
| `plugins/dm-review/skills/dm-review/SKILL.md` | `.claude/ux-review/workflow-kernel/` |
| `plugins/dm-review/commands/dm-review-loop.md` | `.claude/ux-review/workflow-kernel/` |
| `plugins/dm-review/skills/dm-review-loop/SKILL.md` | `.claude/ux-review/workflow-kernel/` |
| `plugins/dm-review/commands/dm-review-visual.md` | `.claude/ux-review/workflow-kernel/` |
| `plugins/dm-review/skills/dm-review-visual/SKILL.md` | `.claude/ux-review/workflow-kernel/` |
| `plugins/pipeline/commands/pipeline.md` | `plans/<feature-slug>/` |
| `plugins/pipeline/skills/pipeline/SKILL.md` | `plans/<feature-slug>/` |
| `plugins/pipeline/commands/pipeline-run.md` | `plans/<feature>/` |
| `plugins/pipeline/skills/pipeline-run/SKILL.md` | `plans/<feature>/` |

The exact invocation above the paragraph is path-specific and is **not**
generated. Only the paragraph is.

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
