---
name: dm-review-quick
description: Quick code review with 5 core agents, plus ui-standards-reviewer when UI files changed -- no other conditional agents, no memory capture
argument-hint: "[optional: PR number, branch name, or file path]"
---

# Quick Code Review

Run a fast code review using the core agents plus ui-standards-reviewer for UI files.

## Diff-Size Scaling

Quick mode scales agent count by diff size:

- **< 100 lines (lightweight):** 3 agents — security-auditor, pattern-recognition-specialist, code-simplicity-reviewer. Skips architecture-reviewer and doc-sync-reviewer (small diffs rarely have architectural or doc-sync impact). With DeepSeek routing, this is 1 Claude + 2 DeepSeek agents.
- **100–500 lines (standard):** 5 core agents (all below).
- **> 500 lines (extended):** 5 core + applicable classification-aware agents.

## Core Agents (standard+ mode)

1. code-simplicity-reviewer
2. security-auditor
3. pattern-recognition-specialist
4. architecture-reviewer
5. doc-sync-reviewer

## Classification-Aware Agents (skip when not applicable)

Each agent has a file-type trigger. Do NOT dispatch an agent whose trigger is absent from the diff -- it wastes tokens and may emit confused findings.

- **go-build-verifier:** dispatch ONLY if `.go` files changed. Skip otherwise.
- **craft-reviewer:** dispatch ONLY if `.twig`, `.php`, or Craft module config files changed. Skip otherwise.
- **migration-validator:** dispatch ONLY if `.sql` files under a migrations directory changed. Skip otherwise.
- **ui-standards-reviewer:** dispatch when `.templ`, `.twig`, `.html`, or `.css` files changed. Evaluates rendered UI against Stripe/Notion/Linear quality bar with token discovery and Live Wires compliance.

Compute the trigger set from the diff before dispatching. Skipped agents are logged in the report's Agent Summary as `<agent>: skipped (no matching files in diff)` so the zero-deferral audit can confirm nothing was overlooked by accident.

## Zero-Deferral Policy (default)

Quick mode surfaces findings at the same P1/P2/P3 severities as full mode. The zero-deferral policy applies equally -- any P3 surfaced here is a mandatory fix before merge unless `--allow-defer-p3` is explicitly used (see `/dm-review`).

## Process

1. Load the review skill from `plugins/dm-review/skills/review/SKILL.md`
2. Compute the file-type trigger set from the diff (Go, Twig/PHP, SQL, UI)
3. Execute in **Quick** mode with the provided argument:
   - No argument: review uncommitted changes or current branch vs main
   - PR number or URL: review that pull request
   - Branch name: review that branch vs main
   - File path: review that specific file or directory
4. Dispatch core agents + any classification-aware agents whose triggers match the diff
5. Log skipped agents explicitly in the Agent Summary
6. Output the unified review report with merge recommendation (per zero-deferral)
