---
name: dm-review-quick
description: Quick code review with two core judgment lanes plus applicable UI, build, and domain verification
argument-hint: "[optional: PR number, branch name, or file path]"
---

# Quick Code Review

Run a fast applicability-driven code review. Security-sensitive changes escalate to full mode.

## Core Lanes

Ordinary quick review always selects exactly:

1. `pattern-recognition-specialist`
2. `code-simplicity-reviewer`

Diff size never widens this roster by itself.

## Classification-Aware Agents (skip when not applicable)

Each agent has a file-type trigger. Do NOT dispatch an agent whose trigger is absent from the diff -- it wastes tokens and may emit confused findings.

- **go-build-verifier:** dispatch ONLY if `.go` or `.templ` files changed and the project has `go.mod` + `docker-compose.yml`. Skip otherwise.
- **craft-reviewer:** dispatch ONLY if `.twig`, `.php`, or Craft module config files changed and the project has `craft/` or `.ddev/`. Skip otherwise.
- **ui-standards-reviewer:** dispatch when `.templ`, `.twig`, `.html`, or `.css` files changed. Evaluates rendered UI against Stripe/Notion/Linear quality bar with token discovery and Live Wires compliance.

Compute the trigger set from the diff before dispatching. Log applicable selected lanes and any triggered lane that was meaningfully unavailable. Do not manufacture skip rows for every agent in the plugin.

## Security Escalation

If the diff touches the bounded security-sensitive path set named by the review
skill, do not use this ordinary roster as a substitute for security review.
Escalate to full mode, which retains the mandatory full-diff security
sign-off, authorized external security lens, and full-only second perspective.
Do not infer extra security triggers from generic handlers, shell scripts,
dependency manifests, or configuration files. Quick review is early feedback;
the one final full pre-merge review remains the complete security boundary.

## Zero-Deferral Finding Policy

Quick mode follows the full policy: every retained P1, P2, and P3 finding
enters the fix queue and must be resolved before `CLEAN`. Reject invalid or
scope-expanding reviewer suggestions during consolidation; do not retain them
as optional P3 debt.

## Process

1. Load the review skill from `plugins/dm-review/skills/review/SKILL.md` with
   `terminalModelReportOwner: dm-review` unless an enclosing Pipeline or
   dm-review-loop invocation explicitly supplies its own owner
2. Check security-sensitive paths first; escalate to Full mode if any match
3. Compute the file-type trigger set from the diff (Go, Twig/PHP, UI)
4. Execute in **Quick** mode with the provided argument:
   - No argument: review uncommitted changes or current branch vs main
   - PR number or URL: review that pull request
   - Branch name: review that branch vs main
   - File path: review that specific file or directory
5. Dispatch the two core lanes plus applicable existing UI/build/domain verification lanes
6. Output the unified review report with the standard merge recommendation,
   followed by this invocation's one terminal operator report

Every pre-execution abort and terminal outcome uses the review skill's
exact-owned cleanup sequence; quick mode does not get a weaker cleanup path.
