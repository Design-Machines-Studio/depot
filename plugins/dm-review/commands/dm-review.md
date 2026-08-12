---
name: dm-review
description: Full code review with all applicable agents including visual browser testing
argument-hint: "[optional: PR number, branch name, or file path]"
---

# Full Code Review

Run a comprehensive code review using all applicable agents for the current project stack.

## Finding Policy

P1 blocks merge and P2 must be fixed before merge. P3 is advisory: retain its complete evidence, provenance, count, and detail, but do not create mandatory work, drive convergence, or prevent `CLEAN`. `/dm-review` surfaces all findings; `/dm-review-fix` resolves pending P1/P2 findings; `/dm-review-loop` automates fix-until-clean for required work.

The merge recommendation reflects this policy:

- **Zero findings:** `CLEAN` -- safe to merge.
- **P3 only (no P1/P2):** `CLEAN` -- retain every P3 as a visible advisory.
- **P2 present:** `APPROVE WITH FIXES`. Must fix.
- **P1 present:** `BLOCKS MERGE`. Must fix.

## Process

1. Load the review skill from `plugins/dm-review/skills/review/SKILL.md`
2. Execute in **Full** mode with the provided argument:
   - No argument: review uncommitted changes or current branch vs main
   - PR number or URL: review that pull request
   - Branch name: review that branch vs main
   - File path: review that specific file or directory
3. Output the unified review report with merge recommendation (per the finding policy above)

## Synthesis and Contribution Contract

Every raw reviewer finding keeps a durable `raw_ref`, source-scoped identity,
agent, provider, model, evidence, and severity. Consolidation derives stable
canonical finding IDs from the finding itself, never from display order or
provider preference. Agreement merges contributor IDs; disagreement is retained
in the synthesis decision ledger and changes the decision, not the finding's
identity. A summary never substitutes for missing raw evidence.

After consolidation, materialize `synthesis-decisions.json`, the sealed raw
finding inventory, literal required-lane receipts, and machine-readable raw
output for every requested lane using the review skill's
exact structured contracts. Then use only the trusted launcher command
`export-review-contributions` to append contribution receipts that attribute retained,
superseded, duplicate, resolved, and disagreement outcomes to the contributing
attempts. These receipts are observation-only economics evidence: they cannot
select a provider, change routing, invent a finding, waive coverage, or alter
the finding-policy recommendation. Missing raw evidence or any required lane or
browser case remains a reported coverage gap, never an implicit clean result.
The exporter rejects credential-shaped content and credential-bearing URIs
before hashing or persistence, descriptor-safely seals every raw output, and
emits a durable coverage receipt even when the raw inventory is empty.

## OpenRouter Availability Resolution

OpenRouter is available when one coherent installed OpenRouter bundle resolves
and either `OPENROUTER_API_KEY` or the validated `OPENROUTER_API_KEY_FILE` input
is configured. Eligible mechanical, bulk, and supplementary Kimi security lanes
then dispatch non-interactively with the existing automatic disclosure scan and
unchanged-byte check. No user approval, broker probe, FIDO interaction, or
redispatch is part of the path.

A missing or invalid key, unavailable bundle/provider, or automatically
declined payload falls back to Codex without prompting. Workflow Authority
presence, absence, readiness, or degradation does not change configured-key
availability. Receipts remain content-free and record provider, model, usage,
and request-envelope digest metadata. Recommend provider-side per-key spending
limits as the runaway-cost control.

## Shadow Workflow Kernel Lifecycle

The review skill, selected lanes, findings, coverage receipt, merge recommendation, and repository-cleanup report remain authoritative. Resolve `$WORKFLOW_KERNEL` -- the workflow-kernel launcher script -- once per run, following the single fail-closed resolution contract in the workflow-kernel plugin's `references/runtime-resolution.md` (launcher discovery snippet, repo-vs-cache trust boundaries, semver compatibility, and symlink/scope fail-closed rules all live there; do not restate them here).

Materialize the validated review request at `.claude/ux-review/workflow-kernel/request.json` and the cumulative ordered redacted authoritative receipt array at `.claude/ux-review/workflow-kernel/authoritative-receipts.json`. Initialize this run under `.workflow-kernel/runs/<run-id>`; the kernel derives the nearest real Git repository from the state directory and binds its canonical `.workflow-kernel` root to an immutable random scope ID plus repository/root device and inode. No caller-selected lease root is accepted, and symlink, cross-repository, scope-metadata, or run-directory mismatches fail closed. Produce independent prediction receipts before corresponding authoritative actions and seal them first:

```text
"$WORKFLOW_KERNEL" bind-prediction --type review --request .claude/ux-review/workflow-kernel/request.json --prediction-receipts .claude/ux-review/workflow-kernel/independent-prediction-receipts.json --state-dir .claude/ux-review/workflow-kernel
```

After the authoritative consolidated review and coverage receipt exist, run exactly:

```text
"$WORKFLOW_KERNEL" observe-review --request .claude/ux-review/workflow-kernel/request.json --receipts .claude/ux-review/workflow-kernel/authoritative-receipts.json --state-dir .claude/ux-review/workflow-kernel
```

After terminal cleanup receipts are appended, run exactly:

```text
"$WORKFLOW_KERNEL" observe-review --request .claude/ux-review/workflow-kernel/request.json --receipts .claude/ux-review/workflow-kernel/authoritative-receipts.json --state-dir .claude/ux-review/workflow-kernel
"$WORKFLOW_KERNEL" compare --state-dir .claude/ux-review/workflow-kernel --authoritative-receipts .claude/ux-review/workflow-kernel/authoritative-receipts.json --output .claude/ux-review/workflow-kernel/shadow-report.json
"$WORKFLOW_KERNEL" metrics --events .claude/ux-review/workflow-kernel/authoritative-receipts.json --output .claude/ux-review/workflow-kernel/metrics.json
if MODEL_MATRIX_ASSET=$("$WORKFLOW_KERNEL" resolve-plugin-asset --plugin openrouter --asset skills/openrouter-delegate/references/model-matrix.json --minimum-version 1.11.0); then :; else MODEL_MATRIX_ASSET=""; fi
"$WORKFLOW_KERNEL" emit-cost-summary --events .claude/ux-review/workflow-kernel/authoritative-receipts.json --output .claude/ux-review/workflow-kernel/run-cost-summary.json --receipt .claude/ux-review/workflow-kernel/run-receipt.md --matrix "$MODEL_MATRIX_ASSET" --repository-commit "$(git rev-parse HEAD)" $(test -n "$(git status --porcelain)" && echo --dirty-state) \
  || { s=$?; if [ "$s" -eq 6 ]; then printf 'run-cost-summary: skipped (receipt-write-failed)\n' >> .claude/ux-review/workflow-kernel/run-receipt.md; elif [ "$s" -eq 2 ]; then exit "$s"; else printf 'run-cost-summary: skipped (kernel-unresolvable)\n' >> .claude/ux-review/workflow-kernel/run-receipt.md; fi; }
```

The `emit-cost-summary` command is one transaction: it owns the artifact path, clears any stale file left there by an earlier run, writes a schema-bound `run-cost-summary.json` beside that run's own `authoritative-receipts.json`, and appends exactly one inventory line to the run receipt naming what actually happened -- the artifact path on success, or `run-cost-summary: skipped (<reason>)` on any internal failure. It exits 0 for every measurement outcome, because the artifact is observation-only: it never gates, blocks, waives, or alters a review, lane, or phase outcome, and its absence never fails one. It exits 6 in exactly one case -- the receipt path was accepted but the write failed -- because a receipt naming neither an artifact nor a skip is the silence the failure-modes checklist forbids, and reporting that it could not report is the command's last obligation. A *refused* receipt path is the deliberate exception and still exits 0: exiting non-zero would fire the caller's `||` fallback, which appends through the very symlink the command just rejected, so the refusal is reported on stderr alone. Exit 2 is the other non-zero outcome and means the invocation was wrong -- bad flags, or `--output` and `--receipt` pointing at one path -- so nothing ran and nothing is recorded. The `||` fallback beside it must be status-aware: exit 6 triggers one final append of `skipped (receipt-write-failed)`, exit 2 is explicitly propagated as an invalid invocation, and every other non-zero status appends `skipped (kernel-unresolvable)`. If the final append also fails, its non-zero status remains visible instead of being erased. Receipt paths are fixed for a given receipt directory, so two concurrent runs sharing one directory overwrite each other: serialize them, or give each run its own directory. The command refuses a symlinked artifact or receipt path, and when the *receipt* path is the one refused it records nothing rather than writing the refusal through the symlink it just rejected. The caller resolves a coherent installed-plugin bundle and passes its model-matrix asset as `--matrix "$MODEL_MATRIX_ASSET"`; the kernel validates both bundle containment and matrix structure without owning a provider dependency. An unreadable or invalid matrix emits one stderr line, skips imputation, and never fails this observation-only emission. It does not inspect the working tree: the caller passes `--dirty-state`, and that flag is the artifact's only source of that fact. Populate the events it reads through `record-attempt` as each lane settles; that one atomic call appends the lane outcome and exactly one `attempt_usage` row under the same lock. Pass the OpenRouter wrapper receipt when present, otherwise pass the exact Codex/Claude input files for deterministic byte measurement; when neither exists, the paired row explicitly records `attempt_unmeasured`. Do not also call a standalone translator with `--append-to` for that attempt, because doing both double-counts it. A `lanes: 0` artifact after a run that executed lanes means this boundary is not wired; a structurally valid artifact with zero measured lanes proves the command ran, never that lanes were measured. Full command reference, when the workflow-kernel plugin is installed alongside this one: `plugins/workflow-kernel/skills/workflow-kernel/references/cli-measurement-commands.md`; if that path is not readable from this cache, the flags named above are the complete required set.

Inline Python source is forbidden. `bind-prediction` atomically seals the pre-action source, translated events, event digest, and request context and appends its exact authority to the canonical lifecycle ledger before `run.started`. Observation and direct comparison require that ordered binding plus the matching artifact and never create or mutate either. Byte-identical predicted and authoritative receipts are valid only with this durable pre-start authority. Keep the source input, request, authoritative receipts, `review-shadow-observation.json`, and `review-shadow-prediction.json` through comparison. Delete the prediction source and bound artifact only after semantic `match`. Missing independent prediction evidence fails closed and preserves the review result. A parity gap cannot convert `CLEAN`, `APPROVE WITH FIXES`, `BLOCKS MERGE`, or `REVIEW INCOMPLETE`; it is proposal-only evidence. Never auto-delete `.workflow-kernel/repository-scope.json`. Parity match alone never deletes terminal run state; retain the run directory or a durable tombstone until fresh exact-scope Docker inventory proves zero exact-run objects and no uninspectable matches.

When a review request has no explicit `workflowClass`, translate it as `feature` with `workflow_class_defaulted=true`; never infer it from findings, diff kinds, or severity. Preserve requested/attempted/implemented-by/fallback/reason evidence for every provider lane.
