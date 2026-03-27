---
name: pipeline-prompts
description: Generate execution prompts from an existing plan with overlap analysis
argument-hint: "[path to plan file]"
---

# Pipeline Prompts

Generate self-contained execution prompts from an existing plan. Standalone command for when you already have a plan and want to generate the execution chunks.

## Input

<plan_path> #$ARGUMENTS </plan_path>

If the plan path above is empty, check for plans in the current project:

```bash
ls plans/*.md 2>/dev/null
```

If plans found, ask: "Which plan should I generate prompts for?" and list them.
If no plans found, ask: "Provide a path to your plan file, or run `/pipeline` for the full workflow."

## Process

1. Read the plan file
2. Check for an Assessment Brief (`plans/assessment-*.md`) and Research Brief (`plans/research-*.md`) in the same directory
3. Load the promptcraft skill from `plugins/pipeline/skills/promptcraft/SKILL.md`
4. Generate execution prompts with overlap analysis
5. Save manifest and prompts to `plans/<feature-slug>/`

## After Generation

Present the manifest summary, then ask:

"Generated prompts at `plans/<feature-slug>/prompts/`. Options:
1. Review the prompts (I'll show each one)
2. Run adversarial review (plan-adversary agent)
3. Execute now (`/pipeline-run plans/<feature-slug>/manifest.json`)
4. Edit prompts manually first"
