---
name: pipeline-run
description: Execute generated prompts in worktrees with review-fix loops
argument-hint: "[path to manifest.json or prompts directory]"
---

# Pipeline Run

Execute a set of generated prompts autonomously in worktrees with review-fix loops. This is the execution engine -- it creates branches, runs subagents, reviews, fixes, merges, and delivers a clean feature branch.

## Input

<manifest_path> #$ARGUMENTS </manifest_path>

If the path above is empty, check for `manifest.json` files matching `plans/*/manifest.json`. If found, ask which manifest to execute. If none found, ask: "Provide a path to manifest.json, or run `/pipeline-prompts` first to generate one."

If a directory was provided instead of a manifest file, look for `manifest.json` inside it.

## Pre-Flight Checks

Before executing, verify:

1. **Manifest exists and is valid JSON**
2. **All prompt files referenced in manifest exist and resolve within `plans/`** -- reject any path that escapes the project's `plans/<feature>/prompts/` directory after canonical resolution
3. **Branch names are safe** -- `featureBranch` and all chunk IDs match `^[a-z0-9][a-z0-9\-\/]*$`
4. **Git working tree is clean** (`git status --porcelain` is empty)
5. **On the base branch** (usually main) with latest changes
6. **Bypass permissions active** -- If not, warn: "Autonomous execution requires bypass permissions mode. Enable it and re-run."

If any check fails, report the issue and stop.

## Process

1. Read the manifest
2. Launch the execution-orchestrator agent from `plugins/pipeline/agents/workflow/execution-orchestrator.md`
3. Pass the manifest path, prompts directory, and feature branch name
4. The orchestrator handles everything autonomously:
   - Branch creation
   - Worktree creation per chunk
   - Subagent dispatch with inlined prompt content
   - dm-review-loop after each chunk (quick mode, zero-deferral)
   - Merge back to feature branch
   - Final full dm-review
   - ai-memory session recording
5. Present the execution summary

## After Execution

Present the summary report from the orchestrator, then ask:

"Feature branch `<branch>` is ready. Options:
1. Review the branch (`git log main..<branch>`)
2. Create a PR (`gh pr create`)
3. Give feedback for another iteration
4. Run another full review (`/dm-review <branch>`)
5. Done"

If feedback given, suggest re-running `/pipeline-prompts` with the feedback to generate revision prompts, then `/pipeline-run` again on the same feature branch.
