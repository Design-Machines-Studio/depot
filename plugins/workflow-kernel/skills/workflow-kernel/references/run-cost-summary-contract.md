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
The `emit-cost-summary` command is one transaction: it owns the artifact path, clears any stale file left there by an earlier run, writes a schema-bound `run-cost-summary.json` beside that run's own `authoritative-receipts.json`, and appends exactly one inventory line to the run receipt naming what actually happened -- the artifact path on success, or `run-cost-summary: skipped (<reason>)` on any internal failure. It exits 0 for every measurement outcome, because the artifact is observation-only: it never gates, blocks, waives, or alters a review, lane, or phase outcome, and its absence never fails one. It exits 6 in exactly one case -- the receipt path was accepted but the write failed -- because a receipt naming neither an artifact nor a skip is the silence the failure-modes checklist forbids, and reporting that it could not report is the command's last obligation. A *refused* receipt path is the deliberate exception and still exits 0: exiting non-zero would fire the caller's `||` fallback, which appends through the very symlink the command just rejected, so the refusal is reported on stderr alone. Exit 2 is the other non-zero outcome and means the invocation was wrong -- bad flags, or `--output` and `--receipt` pointing at one path -- so nothing ran and nothing is recorded. The `||` fallback beside it must be status-aware: exit 6 triggers one final append of `skipped (receipt-write-failed)`, exit 2 is explicitly propagated as an invalid invocation, and every other non-zero status appends `skipped (kernel-unresolvable)`. If the final append also fails, its non-zero status remains visible instead of being erased. Receipt paths are fixed for a given receipt directory, so two concurrent runs sharing one directory overwrite each other: serialize them, or give each run its own directory. The command refuses a symlinked artifact or receipt path, and when the *receipt* path is the one refused it records nothing rather than writing the refusal through the symlink it just rejected. The caller resolves a coherent installed-plugin bundle and passes its model-matrix asset as `--matrix "$MODEL_MATRIX_ASSET"`; the kernel validates both bundle containment and matrix structure without owning a provider dependency. An unreadable or invalid matrix emits one stderr line, skips imputation, and never fails this observation-only emission. It does not inspect the working tree: the caller passes `--dirty-state`, and that flag is the artifact's only source of that fact. Populate the events it reads through `record-attempt` as each lane settles; that one atomic call appends the lane outcome and exactly one `attempt_usage` row under the same lock. Pass the OpenRouter wrapper receipt when present, otherwise pass the exact Codex/Claude input files for deterministic byte measurement; when neither exists, the paired row explicitly records `attempt_unmeasured`. Do not also call a standalone translator with `--append-to` for that attempt, because doing both double-counts it. A `lanes: 0` artifact after a run that executed lanes means this boundary is not wired; a structurally valid artifact with zero measured lanes proves the command ran, never that lanes were measured. Full command reference, when the workflow-kernel plugin is installed alongside this one: `plugins/workflow-kernel/skills/workflow-kernel/references/cli-measurement-commands.md`; if that path is not readable from this cache, the flags named above are the complete required set.
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
