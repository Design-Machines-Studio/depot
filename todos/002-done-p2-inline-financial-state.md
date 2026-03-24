# P2: Inline financial state violates ai-memory convention

**Source:** security-auditor, architecture-reviewer
**Files:**
- `plugins/design-machines/skills/strategy/SKILL.md:251`
- `plugins/project-manager/skills/planner/references/strategic-guardrails.md:43`
**Date:** 2026-03-24

## Problem

Specific savings balance (~$25K), burn rate (~$2-3K/mo), runway estimate, and named grant amount ($20K via Chris) are hardcoded in source-controlled files. The strategy skill's own Data Source Convention says dynamic financial state belongs in ai-memory.

## Fix

Remove inline figures from both files. Replace with `check ai-memory entity "Design Machines OÜ" for current runway`. Keep the structural framing (B1 loop exists, runway is a constraint) but not the numbers.
