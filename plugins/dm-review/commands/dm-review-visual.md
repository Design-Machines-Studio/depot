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

Materialize the validated standalone review request, including its explicit/defaulted `workflowClass`, at `.claude/ux-review/workflow-kernel/request.json`; maintain its cumulative ordered redacted receipts at `.claude/ux-review/workflow-kernel/authoritative-receipts.json`.

Use the complete project verification profile selected from configuration and `tests/ux/` task frontmatter: persona, scenario, concrete route, configured engine, viewport, authentication state, and expected evaluation. `not_declared` applies only when declarations are absent; a present but incomplete declaration or unresolved route binding is blocking. Execute the selected case set rather than a fixed persona sample.

On any missing required browser tool, dev server, authentication fixture, route binding, or verification profile prerequisite, preserve safe initial-attempt evidence, quit the primary browser process/engine session, launch a demonstrably fresh primary profile and retry once, then try a genuinely different configured engine. Record unavailable recovery actions rather than omitting them. If recovery cannot complete, emit blocked `human_help_required` with every attempt and exact missing case IDs, explicitly ask the user to restore the missing prerequisite, and stop. Never skip, defer, degrade, approve, or proceed without the required browser evidence. Curl and reachability are diagnostic only and never satisfy browser evidence. Application/assertion failures are findings and do not trigger browser restart.

After the authoritative visual report exists, append it to `.claude/ux-review/workflow-kernel/authoritative-receipts.json` and invoke exactly:

```text
python3 -m workflow_kernel observe-review --request .claude/ux-review/workflow-kernel/request.json --receipts .claude/ux-review/workflow-kernel/authoritative-receipts.json --state-dir .claude/ux-review/workflow-kernel
python3 -m workflow_kernel compare --state-dir .claude/ux-review/workflow-kernel --authoritative-receipts .claude/ux-review/workflow-kernel/authoritative-receipts.json --output .claude/ux-review/workflow-kernel/shadow-report.json
python3 -m workflow_kernel metrics --events .claude/ux-review/workflow-kernel/authoritative-receipts.json --output .claude/ux-review/workflow-kernel/metrics.json
```

Keep the request, receipt array, and generated `review-shadow-observation.json` snapshot until all three commands complete. Shadow unavailability or parity gaps remain evidence only and never convert the visual result.
