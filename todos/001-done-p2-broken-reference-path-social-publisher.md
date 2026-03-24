# P2: Broken reference path in social-publisher agent

**Source:** doc-sync-reviewer
**File:** `plugins/ghostwriter/agents/workflow/social-publisher.md:30`
**Date:** 2026-03-24

## Problem

Path `skills/social-media/references/propaganda-strategy.md` is a bare relative path that won't resolve from the agent's context (`agents/workflow/`). Every other reference in the depot uses `${CLAUDE_SKILL_DIR}/references/filename.md`.

## Fix

Either use the `${CLAUDE_SKILL_DIR}` variable or instruct the agent to load the social-media skill (which already references the file correctly).
