---
name: dm-review-visual
description: Run visual browser testing on rendered pages -- responsive layouts, interactive states, and accessibility
argument-hint: "[optional: URL to test, --states, or --a11y]"
---

# Visual Browser Testing

Run the visual testing protocol on rendered web pages using Playwright browser tools.

## Zero-Deferral Policy (default)

Visual findings at any severity (P1/P2/P3) are mandatory fixes before merge. See `plugins/dm-review/skills/review/references/severity-mapping.md` for the policy and `--allow-defer-p3` opt-out.

## Process

1. Load the visual-test skill from `plugins/dm-review/skills/visual-test/SKILL.md`
2. Execute with the provided argument:
   - No argument: auto-detect dev server, test all pages
   - URL: test that specific URL
   - `--states`: focus on interactive state testing
   - `--a11y`: focus on runtime accessibility checks
3. Output the visual testing report

Materialize the validated standalone review request, including its explicit/defaulted `workflowClass`, at `.claude/ux-review/workflow-kernel/request.json`; maintain its cumulative ordered redacted receipts at `.claude/ux-review/workflow-kernel/authoritative-receipts.json`. Resolve `$WORKFLOW_KERNEL` -- the workflow-kernel launcher script -- once per run, following the fail-closed resolution contract in the workflow-kernel plugin's `references/runtime-resolution.md`. Initialize the run under `.workflow-kernel/runs/<run-id>`; the kernel derives and verifies the immutable repository scope from the state directory, and no caller-selected lease root is accepted. Before authoritative browser actions, seal the independent prediction:

```text
"$WORKFLOW_KERNEL" bind-prediction --type review --request .claude/ux-review/workflow-kernel/request.json --prediction-receipts .claude/ux-review/workflow-kernel/independent-prediction-receipts.json --state-dir .claude/ux-review/workflow-kernel
```

Use the complete project verification profile selected from configuration and `tests/ux/` task frontmatter: persona, scenario, concrete route, configured engine, viewport, authentication state, and expected evaluation. `not_declared` applies only when declarations are absent; a present but incomplete declaration or unresolved route binding is blocking. Execute the selected case set rather than a fixed persona sample.

On any missing required browser tool, dev server, authentication fixture, route binding, or verification profile prerequisite, preserve safe initial-attempt evidence, quit the primary browser process/engine session, launch a demonstrably fresh primary profile and retry once, then try a genuinely different configured engine. Record unavailable recovery actions rather than omitting them. If recovery cannot complete, emit blocked `human_help_required` with every attempt and exact missing case IDs, explicitly ask the user to restore the missing prerequisite, and stop. Never skip, defer, degrade, approve, or proceed without the required browser evidence. Curl and reachability are diagnostic only and never satisfy browser evidence. Application/assertion failures are findings and do not trigger browser restart.

After the authoritative visual report exists, append it to `.claude/ux-review/workflow-kernel/authoritative-receipts.json` and invoke exactly:

```text
"$WORKFLOW_KERNEL" observe-review --request .claude/ux-review/workflow-kernel/request.json --receipts .claude/ux-review/workflow-kernel/authoritative-receipts.json --state-dir .claude/ux-review/workflow-kernel
"$WORKFLOW_KERNEL" compare --state-dir .claude/ux-review/workflow-kernel --authoritative-receipts .claude/ux-review/workflow-kernel/authoritative-receipts.json --output .claude/ux-review/workflow-kernel/shadow-report.json
"$WORKFLOW_KERNEL" metrics --events .claude/ux-review/workflow-kernel/authoritative-receipts.json --output .claude/ux-review/workflow-kernel/metrics.json
"$WORKFLOW_KERNEL" emit-cost-summary --events .claude/ux-review/workflow-kernel/authoritative-receipts.json --output .claude/ux-review/workflow-kernel/run-cost-summary.json --receipt .claude/ux-review/workflow-kernel/run-receipt.md --repository-commit "$(git rev-parse HEAD)" $(test -n "$(git status --porcelain)" && echo --dirty-state) \
  || { s=$?; [ "$s" -eq 2 ] || [ "$s" -eq 6 ]; } || printf 'run-cost-summary: skipped (kernel-unresolvable)\n' >> .claude/ux-review/workflow-kernel/run-receipt.md
```

The `emit-cost-summary` command is one transaction: it owns the artifact path, clears any stale file left there by an earlier run, writes a schema-bound `run-cost-summary.json` beside that run's own `authoritative-receipts.json`, and appends exactly one inventory line to the run receipt naming what actually happened -- the artifact path on success, or `run-cost-summary: skipped (<reason>)` on any internal failure. It exits 0 for every measurement outcome, because the artifact is observation-only: it never gates, blocks, waives, or alters a review, lane, or phase outcome, and its absence never fails one. It exits 6 in exactly one case -- the receipt path was accepted but the write failed -- because a receipt naming neither an artifact nor a skip is the silence the failure-modes checklist forbids, and reporting that it could not report is the command's last obligation. A *refused* receipt path is the deliberate exception and still exits 0: exiting non-zero would fire the caller's `||` fallback, which appends through the very symlink the command just rejected, so the refusal is reported on stderr alone. Exit 2 is the other non-zero outcome and means the invocation was wrong -- bad flags, or `--output` and `--receipt` pointing at one path -- so nothing ran and nothing is recorded. The `||` fallback beside it must be gated on the status (`|| { s=$?; [ "$s" -eq 2 ] || [ "$s" -eq 6 ]; } || printf ...`), because a bare `||` fires on every non-zero exit: after an exit 6 whose receipt line was already written it appends a second, contradicting skip line, and after an exit 2 it blames a launcher that demonstrably ran. Gated, the fallback covers only what no process inside the kernel can report -- the launcher itself failing to run. Receipt paths are fixed for a given receipt directory, so two concurrent runs sharing one directory overwrite each other: serialize them, or give each run its own directory. The command refuses a symlinked artifact or receipt path, and when the *receipt* path is the one refused it records nothing rather than writing the refusal through the symlink it just rejected. Pass `--matrix plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json` so subscription-rail attempt usage receives a visibly imputed API-equivalent cost; an unreadable matrix emits one stderr line, skips imputation, and never fails this observation-only emission. It does not inspect the working tree: the caller passes `--dirty-state`, and that flag is the artifact's only source of that fact. Populate the events it reads: after each lane attempt, translate that attempt's OpenRouter wrapper receipt with `openrouter-usage`, or that lane's Codex/Claude input files with `lane-input-bytes`, passing `--append-to <authoritative-receipts.json> --run-id <id> --occurred-at <ISO-8601> --authoritative-receipt <path>` so the translator wraps the payload as an `attempt_usage` receipt and appends it under an exclusive lock in one validated step. Emit a row for every attempt including failed ones -- an attempt missing from the receipt stream is indistinguishable from one that never ran, and its spend disappears with it. A `lanes: 0` artifact after a run that executed lanes means this boundary is not wired; a structurally valid artifact with zero measured lanes proves the command ran, never that lanes were measured. Full command reference, when the workflow-kernel plugin is installed alongside this one: `plugins/workflow-kernel/skills/workflow-kernel/references/cli-measurement-commands.md`; if that path is not readable from this cache, the flags named above are the complete required set.

`bind-prediction` atomically seals the independent source and translated context as `review-shadow-prediction.json`; later authoritative observation requires it and never creates or overwrites it. Keep the prediction source and bound artifact through comparison, deleting them only after semantic `match`. Missing or source-reused prediction evidence fails closed and never converts the visual result. The repository-lifetime scope file is never auto-deleted, and parity match alone never deletes terminal run state; retain the run directory or a durable tombstone until fresh exact-scope Docker inventory proves zero exact-run objects and no uninspectable matches.
