---
name: dm-review-quick
description: Quick code review with 5 core agents only — no conditional agents, no memory capture
argument-hint: "[optional: PR number, branch name, or file path]"
---

# Quick Code Review

Run a fast code review using only the 5 core agents (simplicity, security, patterns, architecture, docs).

## Process

1. Load the review skill from `plugins/dm-review/skills/review/SKILL.md`
2. Execute in **Quick** mode with the provided argument:
   - No argument: review uncommitted changes or current branch vs main
   - PR number or URL: review that pull request
   - Branch name: review that branch vs main
   - File path: review that specific file or directory
3. Output the unified review report with merge recommendation
