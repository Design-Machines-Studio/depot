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

Use the complete project verification profile selected from configuration and `tests/ux/` task frontmatter: persona, scenario, concrete route, configured engine, viewport, authentication state, and expected evaluation. `not_declared` applies only when declarations are absent; a present but incomplete declaration or unresolved route binding is blocking. Execute the selected case set rather than a fixed persona sample.

On required browser-tooling failure, preserve safe attempt evidence, quit the primary browser process/engine session, launch a demonstrably fresh primary profile and retry once, then try a genuinely different configured engine. If recovery cannot complete, stop with `human_help_required`, all attempts, and exact missing case IDs. Curl and reachability are diagnostic only and never satisfy browser evidence. Application/assertion failures are findings and do not trigger browser restart.

After the authoritative visual report exists, feed it to `observe-review` when the trusted workflow-kernel runtime is available. Shadow unavailability or parity gaps remain evidence only and never convert the visual result.
