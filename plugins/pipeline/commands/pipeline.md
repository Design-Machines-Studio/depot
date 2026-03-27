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

1. Decompose the plan into chunks
2. Extract context for each chunk from the Assessment and Research Briefs
3. Perform overlap analysis
4. Generate self-contained execution prompts
5. Generate the manifest
6. Save to `plans/<feature-slug>/manifest.json` and `plans/<feature-slug>/prompts/`

Present the manifest summary: chunk count, parallel groups, overlap risk.

### Phase 5: Adversarial Review

Launch the plan-adversary agent from `plugins/pipeline/agents/workflow/plan-adversary.md`.

1. Pass the plan, prompts, and manifest
2. Collect findings
3. If verdict is REVISE: apply revisions and re-submit (max 3 rounds)
4. If verdict is APPROVED: proceed

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

**If feedback given:** Re-enter the pipeline at Phase 3 or Phase 4 depending on the scope of feedback. Generate new prompts for the revisions and execute again on the same feature branch.
