# P2: strategic-guardrails.md missing from planner Reference Files table

**Source:** doc-sync-reviewer
**File:** `plugins/project-manager/skills/planner/SKILL.md:189-200`
**Date:** 2026-03-24

## Problem

The new reference file exists on disk and is mentioned in the Companion Skills table, but is not listed in the Reference Files table at the bottom of the SKILL.md.

## Fix

Add a row to the Reference Files table:
```
| Strategic guardrails | `${CLAUDE_SKILL_DIR}/references/strategic-guardrails.md` | Phase 8-9: loop alignment, archetype traps, runway check |
```
