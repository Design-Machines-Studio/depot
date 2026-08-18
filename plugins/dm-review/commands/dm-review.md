---
name: dm-review
description: Full code review with all applicable agents including visual browser testing
argument-hint: "[optional: PR number, branch name, or file path]"
---

# Full Code Review

## Zero-Deferral Finding Policy

Every retained P1, P2, and P3 finding is mandatory work: `/dm-review` tracks it, `/dm-review-fix` resolves it, `/dm-review-loop` repairs and rechecks until none remain; severity orders work but never makes it optional. Reject speculative, duplicate, disproved, or out-of-scope suggestions during consolidation; no deferral flag or clean-with-P3s outcome exists. Merge recommendation: zero findings -- `CLEAN` (safe to merge); **P3 only:** `APPROVE WITH FIXES`. Must fix. **P2 present:** `APPROVE WITH FIXES`. Must fix. **P1 present:** `BLOCKS MERGE`. Must fix.

## Process

Load `plugins/dm-review/skills/review/SKILL.md` and execute in **Full** mode on the argument: none -- uncommitted changes or current branch vs main; PR number or URL -- that pull request; branch name -- that branch vs main; file path -- that file or directory. Output the unified review report with that merge recommendation.

## Synthesis and Contribution Contract

Every raw reviewer finding keeps a durable `raw_ref`, source-scoped identity, agent, provider, model, evidence, and severity. Consolidation derives canonical finding IDs from the finding itself, never from display order or provider preference; agreement merges contributor IDs, disagreement is retained in the synthesis decision ledger, changing the decision, not the identity.

After consolidation, materialize `synthesis-decisions.json`, the sealed raw finding inventory, literal required-lane receipts, and machine-readable raw output for every requested lane per the review skill's exact structured contracts. Only the trusted launcher command `export-review-contributions` appends contribution receipts attributing retained, superseded, duplicate, resolved, and disagreement outcomes to the contributing attempts. They are observation-only economics evidence and cannot select a provider, change routing, invent a finding, waive coverage, or alter the finding-policy recommendation. Missing raw evidence or any required lane or browser case remains a reported coverage gap, never an implicit clean result.

## OpenRouter Availability Resolution

The review skill's routing contract governs OpenRouter availability, non-interactive dispatch after one disclosure scan, and Codex fallback. Receipts stay content-free, recording provider, model, usage, and request-envelope digest metadata.

## Shadow Workflow Kernel Lifecycle

The review skill, selected lanes, findings, coverage receipt, merge recommendation, and cleanup report remain authoritative. Resolve `$WORKFLOW_KERNEL` once per run per the fail-closed contract in the workflow-kernel plugin's `references/runtime-resolution.md`. Materialize the validated request at `.claude/ux-review/workflow-kernel/request.json` and the cumulative ordered redacted authoritative receipt array at `.claude/ux-review/workflow-kernel/authoritative-receipts.json`. Initialize the run under `.workflow-kernel/runs/<run-id>`; caller-selected lease roots and symlink, cross-repository, scope-metadata, or run-directory mismatches fail closed. Produce and seal independent prediction receipts before corresponding authoritative actions:

```text
"$WORKFLOW_KERNEL" bind-prediction --type review --request .claude/ux-review/workflow-kernel/request.json --prediction-receipts .claude/ux-review/workflow-kernel/independent-prediction-receipts.json --state-dir .claude/ux-review/workflow-kernel
```

After the consolidated review, coverage receipt, and terminal cleanup receipts exist, run exactly:

```text
"$WORKFLOW_KERNEL" observe-review --request .claude/ux-review/workflow-kernel/request.json --receipts .claude/ux-review/workflow-kernel/authoritative-receipts.json --state-dir .claude/ux-review/workflow-kernel
"$WORKFLOW_KERNEL" compare --state-dir .claude/ux-review/workflow-kernel --authoritative-receipts .claude/ux-review/workflow-kernel/authoritative-receipts.json --output .claude/ux-review/workflow-kernel/shadow-report.json
"$WORKFLOW_KERNEL" metrics --events .claude/ux-review/workflow-kernel/authoritative-receipts.json --output .claude/ux-review/workflow-kernel/metrics.json
if MODEL_MATRIX_ASSET=$("$WORKFLOW_KERNEL" resolve-plugin-asset --plugin openrouter --asset skills/openrouter-delegate/references/model-matrix.json --minimum-version 1.11.0); then :; else MODEL_MATRIX_ASSET=""; fi
"$WORKFLOW_KERNEL" emit-cost-summary --events .claude/ux-review/workflow-kernel/authoritative-receipts.json --output .claude/ux-review/workflow-kernel/run-cost-summary.json --receipt .claude/ux-review/workflow-kernel/run-receipt.md --matrix "$MODEL_MATRIX_ASSET" --repository-commit "$(git rev-parse HEAD)" $(test -n "$(git status --porcelain)" && echo --dirty-state) \
  || { s=$?; if [ "$s" -eq 6 ]; then printf 'run-cost-summary: skipped (receipt-write-failed)\n' >> .claude/ux-review/workflow-kernel/run-receipt.md; elif [ "$s" -eq 2 ]; then exit "$s"; else printf 'run-cost-summary: skipped (kernel-unresolvable)\n' >> .claude/ux-review/workflow-kernel/run-receipt.md; fi; }
```

The `emit-cost-summary` command is one transaction: it owns the artifact path, clears any stale file, writes a schema-bound `run-cost-summary.json` beside that run's `authoritative-receipts.json`, and appends exactly one receipt line -- the artifact path, or `run-cost-summary: skipped (<reason>)` on any internal failure. It is observation-only: it exits 0 for every measurement outcome, never gates or alters a review, lane, or phase outcome, and its absence never fails one. Exit 6 (receipt write failed after acceptance) appends `skipped (receipt-write-failed)` through the status-aware `||` fallback; exit 2 is an invalid invocation and propagates; any other non-zero status appends `skipped (kernel-unresolvable)`, and a failing final append keeps its own status visible. A refused symlinked receipt path still exits 0 and reports on stderr alone -- a non-zero exit would append through the symlink just refused. Receipt paths are fixed per directory, so concurrent runs sharing one directory overwrite each other: serialize them or give each its own. Pass a coherent installed bundle's matrix asset as `--matrix "$MODEL_MATRIX_ASSET"`; an unreadable or invalid matrix emits one stderr line, skips imputation, and never fails the emission. Populate events with `record-attempt` as each lane settles -- a standalone `--append-to` translator double-counts the attempt, and `lanes: 0` after a run that executed lanes means this boundary is not wired. Full flags: `cli-measurement-commands.md`; otherwise the flags named here are the complete required set.

Inline Python source is forbidden. `bind-prediction` atomically seals the pre-action source, translated events, event digest, and request context, appending its exact authority to the canonical lifecycle ledger before `run.started`; observation and direct comparison require that binding plus the matching artifact and never create or mutate either. Keep the source input, request, authoritative receipts, `review-shadow-observation.json`, and `review-shadow-prediction.json` through comparison; delete the prediction source and bound artifact only after semantic `match`. Missing prediction evidence fails closed and preserves the review result; a parity gap cannot convert `CLEAN`, `APPROVE WITH FIXES`, `BLOCKS MERGE`, or `REVIEW INCOMPLETE` -- it is proposal-only evidence. Never auto-delete `.workflow-kernel/repository-scope.json`; parity match alone never deletes terminal run state -- retain the run directory or a durable tombstone until fresh exact-scope Docker inventory proves zero exact-run objects and no uninspectable matches.

Translate a missing explicit `workflowClass` as `feature` with `workflow_class_defaulted=true`; never infer it from findings, diff kinds, or severity. Preserve requested/attempted/implemented-by/fallback/reason evidence for every provider lane.
