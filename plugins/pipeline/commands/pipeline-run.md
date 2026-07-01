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
4. **Git working tree has no blocking user-file changes** -- classify dirty paths as pipeline-owned artifacts (`plans/<feature>/`, generated prompts/manifests/receipts) versus unrelated user files. Commit/gitignore/force-add pipeline-owned artifacts as directed by the orchestrator; block only on unrelated user files.
5. **On the manifest base branch** with latest changes -- use `manifest.baseBranch` when present, defaulting to `main`. The base may be any existing ref, including an unmerged PR branch, stacked branch, or hotfix branch.
6. **Bypass permissions active** -- If not, warn: "Autonomous execution requires bypass permissions mode. Enable it and re-run."

If any check fails, report the issue and stop.

## Codex Native Execution Adapter

When this command runs in Codex and the session exposes `multi_agent_v1.spawn_agent`, use this adapter instead of stopping on Claude-only `Agent` or nested `Skill(...)` availability. This is the supported Codex execution path, not a manual workaround.

**Mode label:** Set `executionMode: codex_native` in the progress ledger, every chunk receipt, `plans/<feature>/receipt.md`, and the final summary.

**Protocol source:** Read `plugins/pipeline/agents/workflow/execution-orchestrator.md` as the execution contract. The current Codex agent acts as the orchestrator in-process because Codex does not expose Claude's generic agent runner. All orchestrator steps remain mandatory: worktree isolation or documented `sequential-on-branch` mode for container-mounted test harnesses, input guardrails, chunk dispatch, validation, evaluation gates, merge-back, final full review, memory capture, cleanup, and summary.

**Implementation dispatch:** For each chunk, create the worktree first, inline the full prompt content, then call `multi_agent_v1.spawn_agent` with `agent_type: "worker"`. The worker prompt MUST include:

- The worktree path as the only allowed write scope.
- The complete chunk prompt content, not a path to the prompt.
- The pipeline Fix Philosophy and ambiguity-trailer requirements.
- A reminder that other workers may be active and the worker must not revert unrelated changes.
- A requirement to commit its chunk changes before reporting completion.

Wait for the worker result before validating that chunk. Do not dispatch overlapping chunks in parallel unless the manifest level grouping and file ownership are disjoint.

**dm-review inline protocol:** Codex sessions do not expose a generic nested `Skill(skill="dm-review:review", ...)` callable. Replace those nested calls with an inline execution of `plugins/dm-review/skills/review/SKILL.md` in the current orchestrator context:

- For per-chunk gates, run the review skill's quick-mode protocol against the chunk worktree.
- For the final gate, run the review skill's full-mode protocol against the feature branch.
- Use `multi_agent_v1.spawn_agent` for the review agents selected by the dm-review protocol when available.
- Preserve zero-deferral: fix all P1, P2, and P3 findings or record an explicit deferred-finding justification after the documented convergence limits.
- Write/read the same `todos/*-pending-*.md` and `todos/*-done-*.md` receipts that dm-review uses.

Do not report "Skill tool unavailable" in Codex when this adapter can run. That message is only valid if the session lacks both nested skill invocation and enough local access to execute the dm-review inline protocol.

## Process

1. Read the manifest
2. If running in Codex with `multi_agent_v1.spawn_agent`, run the **Codex Native Execution Adapter** above
3. Otherwise, launch the execution-orchestrator agent from `plugins/pipeline/agents/workflow/execution-orchestrator.md`
4. Pass the manifest path, prompts directory, and feature branch name
5. The orchestrator handles everything autonomously:
   - Branch creation
   - Worktree creation per chunk
   - Subagent dispatch with inlined prompt content
   - dm-review-loop after each chunk (quick mode, zero-deferral)
   - Merge back to feature branch
   - Final full dm-review
   - ai-memory session recording
6. Present the execution summary

## After Execution

Present the summary report from the orchestrator, then ask:

"Feature branch `<branch>` is ready. Options:
1. Review the branch (`git log main..<branch>`)
2. Create a PR (`gh pr create`)
3. Give feedback for another iteration
4. Run another full review (`/dm-review <branch>`)
5. Done"

If feedback given, suggest re-running `/pipeline-prompts` with the feedback to generate revision prompts, then `/pipeline-run` again on the same feature branch.
