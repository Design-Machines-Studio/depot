---
name: dm-review-visual
description: Run visual browser testing on rendered pages -- responsive layouts, interactive states, and accessibility
argument-hint: "[optional: URL to test, --states, --a11y, or --all]"
---

# Visual Browser Testing

Run the visual testing protocol on rendered web pages using Playwright browser tools.

## Zero-Deferral Policy (default)

Every retained visual P1, P2, and P3 finding requires a fix before `CLEAN`.
Reject preferences without an observable defect instead of recording optional
debt. See `plugins/dm-review/skills/review/references/severity-mapping.md` for
the policy.

## Process

1. Load the visual-test skill from `plugins/dm-review/skills/visual-test/SKILL.md`
2. Execute with the provided argument:
   - No argument: use an attached automation-capable T3 preview or optional
     tracked `.dm/ui-review.json`; never scan localhost ports
   - URL: test that specific URL
   - `--states`: focus on interactive state testing
   - `--a11y`: focus on runtime accessibility checks
   - `--all`: run the complete repository-declared browser matrix
3. Output the visual testing report

This command always requires rendered evidence. Run the shared readiness gate
with `--visual-required true`; if no target can be selected, return one `REVIEW
INCOMPLETE` coverage result and one next action.

Materialize the validated standalone review request, including its explicit/defaulted `workflowClass`, at `<exact-run-root>/review/request.json`; maintain its cumulative ordered redacted receipts at `<exact-run-root>/review/authoritative-receipts.json`. Resolve `$WORKFLOW_KERNEL` -- the workflow-kernel launcher script -- once per run, following the fail-closed resolution contract in the workflow-kernel plugin's `references/runtime-resolution.md`. Initialize the run under `.workflow-kernel/runs/<run-id>`; the kernel derives and verifies the immutable repository scope from the state directory, and no caller-selected lease root is accepted. Before authoritative browser actions, seal the independent prediction:

```text
"$WORKFLOW_KERNEL" bind-prediction --type review --request <exact-run-root>/review/request.json --prediction-receipts <exact-run-root>/review/independent-prediction-receipts.json --state-dir <exact-run-root>/review
```

Load `ui-case-selection.md`. By default select affected routes, prototype cases,
acceptance cases, directly affected dimensions, and at most one justified
baseline. `--all` selects the complete repository-declared matrix. Use the
project verification profile from configuration and `tests/ux/` task
frontmatter: persona, scenario, concrete route, configured engine, viewport,
authentication state, and expected evaluation. `not_declared` applies only
when declarations are absent; a present but incomplete declaration or
unresolved route binding is blocking. Supported viewport/engine lists alone do
not require every combination.

On any missing required browser tool, dev server, authentication fixture, route binding, or verification profile prerequisite, preserve safe initial-attempt evidence, quit the primary browser process/engine session, launch a demonstrably fresh primary profile and retry once, then try a genuinely different configured engine. Record unavailable recovery actions rather than omitting them. If recovery cannot complete, emit blocked `human_help_required` with every attempt and exact missing case IDs, explicitly ask the user to restore the missing prerequisite, and stop. Never skip, defer, degrade, approve, or proceed without the required browser evidence. Curl and reachability are diagnostic only and never satisfy browser evidence. Application/assertion failures are findings and do not trigger browser restart.

After the authoritative visual report exists, append it to `<exact-run-root>/review/authoritative-receipts.json` and invoke exactly:

```text
"$WORKFLOW_KERNEL" observe-review --request <exact-run-root>/review/request.json --receipts <exact-run-root>/review/authoritative-receipts.json --state-dir <exact-run-root>/review
"$WORKFLOW_KERNEL" compare --state-dir <exact-run-root>/review --authoritative-receipts <exact-run-root>/review/authoritative-receipts.json --output <exact-run-root>/review/shadow-report.json
"$WORKFLOW_KERNEL" metrics --events <exact-run-root>/review/authoritative-receipts.json --output <exact-run-root>/review/metrics.json
if MODEL_MATRIX_ASSET=$("$WORKFLOW_KERNEL" resolve-plugin-asset --plugin openrouter --asset skills/openrouter-delegate/references/model-matrix.json --minimum-version 1.11.0); then :; else MODEL_MATRIX_ASSET=""; fi
"$WORKFLOW_KERNEL" emit-cost-summary --events <exact-run-root>/review/authoritative-receipts.json --output <exact-run-root>/review/run-cost-summary.json --receipt <exact-run-root>/review/run-receipt.md --matrix "$MODEL_MATRIX_ASSET" --repository-commit "$(git rev-parse HEAD)" $(test -n "$(git status --porcelain)" && echo --dirty-state) \
  || { s=$?; if [ "$s" -eq 6 ]; then printf 'run-cost-summary: skipped (receipt-write-failed)\n' >> <exact-run-root>/review/run-receipt.md; elif [ "$s" -eq 2 ]; then exit "$s"; else printf 'run-cost-summary: skipped (kernel-unresolvable)\n' >> <exact-run-root>/review/run-receipt.md; fi; }
```

The `emit-cost-summary` command is one transaction: it owns the artifact path, clears any stale file, writes a schema-bound `run-cost-summary.json` beside that run's `authoritative-receipts.json`, and appends exactly one receipt line -- the artifact path, or `run-cost-summary: skipped (<reason>)` on any internal failure. It is observation-only: it exits 0 for every measurement outcome, never gates or alters a review, lane, or phase outcome, and its absence never fails one. Exit 6 (receipt write failed after acceptance) appends `skipped (receipt-write-failed)` through the status-aware `||` fallback; exit 2 is an invalid invocation and propagates; any other non-zero status appends `skipped (kernel-unresolvable)`, and a failing final append keeps its own status visible. A refused symlinked receipt path still exits 0 and reports on stderr alone -- a non-zero exit would append through the symlink just refused. Receipt paths are fixed per directory, so concurrent runs sharing one directory overwrite each other: use the invocation's exact-owned root or serialize callers that intentionally share a documented deliverable directory. Pass a coherent installed bundle's matrix asset as `--matrix "$MODEL_MATRIX_ASSET"`; an unreadable or invalid matrix emits one stderr line, skips imputation, and never fails the emission. Populate events with `record-attempt` as each lane settles -- a standalone `--append-to` translator double-counts the attempt, and `lanes: 0` after a run that executed lanes means this boundary is not wired. Full flags: `cli-measurement-commands.md`; otherwise the flags named here are the complete required set.

`bind-prediction` atomically seals the independent source and translated context as `review-shadow-prediction.json`; later authoritative observation requires it and never creates or overwrites it. Keep the prediction source and bound artifact through comparison, then preserve only compact durable evidence. Missing or source-reused prediction evidence fails closed and never converts the visual result. The repository-lifetime scope file is never auto-deleted. After fresh exact-scope Docker inventory proves zero exact-run objects, success removes terminal state and disposable roots; failure/interruption may retain one bounded diagnostic root with the four required terminal fields.
