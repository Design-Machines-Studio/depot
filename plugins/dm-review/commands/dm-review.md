---
name: dm-review
description: Full code review with all applicable agents including visual browser testing
argument-hint: "[optional: PR number, branch name, or file path]"
---

# Full Code Review

Run a comprehensive code review using all applicable agents for the current project stack.

## Process

1. Load the review skill from `plugins/dm-review/skills/review/SKILL.md`
2. Execute in **Full** mode with the provided argument:
   - No argument: review uncommitted changes or current branch vs main
   - PR number or URL: review that pull request
   - Branch name: review that branch vs main
   - File path: review that specific file or directory
3. Output the unified review report with merge recommendation
