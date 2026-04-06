---
name: dm-review-quick
description: Quick code review with 5 core agents, plus ui-standards-reviewer when UI files changed -- no other conditional agents, no memory capture
argument-hint: "[optional: PR number, branch name, or file path]"
---

# Quick Code Review

Run a fast code review using the core agents plus ui-standards-reviewer for UI files.

## Core Agents (always run)

1. code-simplicity-reviewer
2. security-auditor
3. pattern-recognition-specialist
4. architecture-reviewer
5. doc-sync-reviewer

## UI Design Agent (run when .templ, .twig, .html, or .css files are in the diff)

6. ui-standards-reviewer -- evaluates rendered UI against Stripe/Notion/Linear quality bar with token discovery and Live Wires compliance

## Process

1. Load the review skill from `plugins/dm-review/skills/review/SKILL.md`
2. Execute in **Quick** mode with the provided argument:
   - No argument: review uncommitted changes or current branch vs main
   - PR number or URL: review that pull request
   - Branch name: review that branch vs main
   - File path: review that specific file or directory
3. If UI files are in the diff, include the ui-standards-reviewer agent
4. Output the unified review report with merge recommendation
