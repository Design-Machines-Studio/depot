---
name: dm-review-visual
description: Run visual browser testing on rendered pages — responsive layouts, interactive states, and accessibility
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
