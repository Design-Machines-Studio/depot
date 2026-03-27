---
name: pipeline-assess
description: Pre-plan assessment of current codebase and UX state
argument-hint: "[area to assess or feature context]"
---

# Pipeline Assess

Standalone pre-plan assessment. Evaluates current codebase state and UX before planning changes.

## Input

<assess_input> #$ARGUMENTS </assess_input>

If the input above is empty, ask: "What area should I assess? Give me a feature area, directory path, or describe what you're planning to change."

## Process

1. Load the assess skill from `plugins/pipeline/skills/assess/SKILL.md`
2. Execute the full assessment protocol (code + UX in parallel)
3. Save the Assessment Brief to `plans/assessment-<area-slug>.md`
4. Present the brief to the user

## After Assessment

Ask: "Assessment saved to `plans/assessment-<slug>.md`. Want to run the full pipeline from here (`/pipeline`), or use this brief as context for your own planning?"
