---
name: pipeline
description: Full autonomous pipeline -- assess, research, plan, prompt, review, execute, deliver
argument-hint: "[feature idea or feedback]"
---

# Pipeline

Full autonomous feature development pipeline. Takes an idea and delivers a clean feature branch.

## Feature Input

<feature_input> #$ARGUMENTS </feature_input>

If the feature input above is empty, ask: "What feature or change do you want to build? Describe the idea, feedback, or iteration."

Do not proceed without a clear feature description.

## Original Prompt Preservation

**Immediately** save the user's original input (verbatim) to `plans/<feature-slug>/original-prompt.md`. This is the ground truth for what the user asked for. Every subsequent phase must check back against this file to prevent context loss during compaction.

The file format:

```markdown
# Original Prompt

## User Input
[Exact user input, verbatim, including all bullet points, issues raised, and context]

## Date
[YYYY-MM-DD]

## Key Requirements Extracted
- [Requirement 1]
- [Requirement 2]
- [Requirement N]
```

Extract the key requirements as a numbered checklist. This checklist is used in Phases 4, 5, and 7 to verify nothing was dropped.

## Phases

Execute these phases in order. Each phase builds on the previous phase's output.

### Phase 1: Assess Current State

Load the assess skill from `plugins/pipeline/skills/assess/SKILL.md`.

1. Determine the codebase area affected by the feature
2. Run the pre-plan assessment (code + UX in parallel)
3. Save the Assessment Brief to `plans/assessment-<feature-slug>.md`
4. Present key findings to the user

**Pause for user input.** Ask: "Assessment complete. Any corrections or context to add before I research?"

### Phase 2: Research

Load the research skill from `plugins/pipeline/skills/research/SKILL.md`.

1. Pass the feature description and Assessment Brief to the research orchestrator
2. Dispatch parallel research agents across all available sources
3. Save the Research Brief to `plans/research-<feature-slug>.md`
4. Present the Research Brief summary to the user

**Pause for user input.** Ask: "Research complete. Ready to plan, or want to adjust the scope?"

### Phase 3: Plan

Create the implementation plan. Two options:

**Option A:** If compound-engineering `/workflows:plan` is available, invoke it with the feature description, Assessment Brief, and Research Brief as context.

**Option B:** If not available, create the plan directly:
1. Break the feature into logical implementation steps
2. Identify file paths, patterns, and dependencies
3. Write acceptance criteria for each step
4. Save to `plans/<feature-slug>.md`

**Pause for user input.** Ask: "Plan ready at `plans/<feature-slug>.md`. Review it and let me know when to generate execution prompts."

### Phase 4: Generate Execution Prompts

Load the promptcraft skill from `plugins/pipeline/skills/promptcraft/SKILL.md`.

1. Read `plans/<feature-slug>/original-prompt.md` to refresh the full original context
2. Decompose the plan into chunks
3. Extract context for each chunk from the Assessment and Research Briefs
4. Perform overlap analysis
5. Generate self-contained execution prompts
6. Generate the manifest
7. Save to `plans/<feature-slug>/manifest.json` and `plans/<feature-slug>/prompts/`

**Context-loss check:** After generating prompts, re-read the Key Requirements from `original-prompt.md`. For each requirement, verify at least one chunk's acceptance criteria covers it. If any requirement is unaddressed, add it to the appropriate chunk or create a new chunk. List the mapping in the manifest summary.

Present the manifest summary: chunk count, parallel groups, overlap risk, requirements coverage.

### Phase 5: Adversarial Review

Launch the plan-adversary agent from `plugins/pipeline/agents/workflow/plan-adversary.md`.

1. Pass the plan, prompts, manifest, AND `original-prompt.md`
2. The adversary checks prompts against the original requirements (see Perspective 2: Completeness)
3. Collect findings
4. If verdict is REVISE: apply revisions and re-submit (max 3 rounds)
5. If verdict is APPROVED: proceed

**Pause for user input.** Present the approved prompts and manifest. Ask: "Prompts reviewed and approved by adversary. Review the prompts in `plans/<feature-slug>/prompts/` and approve when ready to execute."

### Phase 6: Execute

**Pre-flight check:**
1. Confirm bypass permissions mode is active
2. Confirm git working tree is clean
3. Confirm on main branch with latest changes

Launch the execution-orchestrator agent from `plugins/pipeline/agents/workflow/execution-orchestrator.md`.

1. Pass the manifest path and prompts directory
2. The orchestrator handles: branch creation, worktree execution, review-fix loops, merging, final review, memory capture
3. Wait for completion

### Phase 7: Deliver

Present the execution summary from the orchestrator. The feature branch is ready for user review.

Ask: "Feature branch `<branch>` is ready. Review it with `git log main..<branch>`. Want to create a PR, give feedback for another iteration, or done?"

**Context-loss check:** Before delivering, re-read `original-prompt.md` and verify every Key Requirement was addressed in the final branch. If any requirement was missed, report it explicitly: "The following requirements from your original prompt were not addressed: [list]."

**If feedback given:** Append the new feedback to `original-prompt.md` as a new section (`## Iteration N Feedback`), extract new requirements, and re-enter at Phase 3 or Phase 4. This ensures feedback accumulates rather than replacing context.
