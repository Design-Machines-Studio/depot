---
name: dm-review
description: Full code review with all applicable agents including visual browser testing
argument-hint: "[optional: PR number, branch name, or file path]"
---

# Full Code Review

Run a comprehensive code review using all applicable agents for the current project stack.

## Read-only Promise

This command inspects and reports. It writes only immutable evidence and
derived projections beneath the declared review artifact root. It never edits
the review target, mutates Git state, creates tracking items, or changes
external provider state. Use `/dm-review-fix` or `/dm-review-loop` after
explicit approval for any mutation.

## Zero-Deferral Policy (default)

All dm-review commands default to zero-deferral: P1, P2, AND P3 findings MUST be fixed before the branch is considered ready to merge. P3s fix band-aid solutions and tech debt -- deferring them is how debt compounds silently. `/dm-review` surfaces findings; `/dm-review-fix` resolves them; `/dm-review-loop` automates fix-until-clean.

The merge recommendation reflects this policy:

- **Zero findings:** `CLEAN` -- safe to merge.
- **P3 only (no P1/P2):** `APPROVE WITH FIXES -- P3s mandatory under zero-deferral.` NOT clean. Run `/dm-review-fix` (or `/dm-review-loop`) to resolve before merging.
- **P2 present:** `APPROVE WITH FIXES`. Must fix.
- **P1 present:** `BLOCKS MERGE`. Must fix.

To explicitly opt out of zero-deferral for a specific run (rare -- e.g. a P3 genuinely belongs in a different branch), pass `--allow-defer-p3`. Each deferred P3 must carry a written justification and a tracking destination.

## Process

1. Load the review skill from `plugins/dm-review/skills/review/SKILL.md`
2. Execute in **Full** mode with the provided argument:
   - No argument: review uncommitted changes or current branch vs main
   - PR number or URL: review that pull request
   - Branch name: review that branch vs main
   - File path: review that specific file or directory
3. Output the unified review report with merge recommendation (per the zero-deferral policy above)

## Synthesis and Contribution Contract

Every raw reviewer finding is immediately persisted as a content-addressed
finding record with a bounded EventStore reference, and keeps a durable
`raw_ref`, source-scoped identity,
agent, provider, model, evidence, and severity. Consolidation derives stable
canonical finding IDs from the finding itself, never from display order or
provider preference. Agreement merges contributor IDs; disagreement is retained
in the synthesis decision ledger and changes the decision, not the finding's
identity. A summary never substitutes for missing raw evidence.

Before rendering, group source records by canonical ID and preserve every
source-scoped ID/ref, lane finding ref, provider attempt, source severity, and
decision. Reciprocal cross-ID disputes remain separate canonical findings.

After consolidation, emit contribution receipts that attribute retained,
superseded, duplicate, resolved, and disagreement outcomes to the contributing
attempts. These receipts are observation-only economics evidence: they cannot
select a provider, change routing, invent a finding, waive coverage, or alter
the zero-deferral recommendation. Missing raw evidence or any required lane or
browser case remains a reported coverage gap, never an implicit clean result.

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
```

Inline Python source is forbidden. `bind-prediction` atomically seals the pre-action source, translated events, event digest, and request context and appends its exact authority to the canonical lifecycle ledger before `run.started`. Observation and direct comparison require that ordered binding plus the matching artifact and never create or mutate either. Byte-identical predicted and authoritative receipts are valid only with this durable pre-start authority. Keep the source input, request, authoritative receipts, `review-shadow-observation.json`, and `review-shadow-prediction.json` through comparison. Delete the prediction source and bound artifact only after semantic `match`. Missing independent prediction evidence fails closed and preserves the review result. A parity gap cannot convert `CLEAN`, `APPROVE WITH FIXES`, `BLOCKS MERGE`, or `REVIEW INCOMPLETE`; it is proposal-only evidence. Never auto-delete `.workflow-kernel/repository-scope.json`. Parity match alone never deletes terminal run state; retain the run directory or a durable tombstone until fresh exact-scope Docker inventory proves zero exact-run objects and no uninspectable matches.

When a review request has no explicit `workflowClass`, translate it as `feature` with `workflow_class_defaulted=true`; never infer it from findings, diff kinds, or severity. Preserve requested/attempted/implemented-by/fallback/reason evidence for every provider lane.
