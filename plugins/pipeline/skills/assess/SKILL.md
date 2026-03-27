---
name: assess
description: Reviews current codebase state and UX before planning changes, producing Current State and UX reports. Use when starting a feature, iterating on existing work, or needing a baseline understanding before making changes. Invoke with /pipeline-assess or as the first phase of /pipeline. Dispatches parallel code and UX assessment agents to evaluate what EXISTS, not what CHANGED.
---

# Pre-Plan Assessment

Evaluate the current state of a codebase area before planning changes. Unlike dm-review which reviews a diff, this reviews what exists -- architecture, patterns, tech debt, UX quality, and known issues.

## When to Use

- Before planning a new feature or iteration
- When inheriting unfamiliar code
- Before a major refactor
- When the user says "assess," "what's the current state," or "review before planning"

## Input

The user provides a feature idea, area description, or specific file paths. If vague, ask: "Which part of the codebase should I assess? Give me a feature area, directory, or file paths."

## Process

### Phase 1: Scope Detection

Determine what to assess based on the user's input:

1. If specific paths given, use those
2. If a feature area described, identify the relevant directories and files
3. If a project name given, use the project root

Produce a file list of 5-20 key files to examine. Prioritize:
- Entry points (handlers, controllers, routes)
- Core logic (services, models, domain)
- Templates/views
- Configuration
- Tests

### Phase 2: Parallel Assessment

Launch two agents simultaneously:

**Agent 1: Code Assessment**

Read the `references/code-assessment-protocol.md` for the full protocol. In summary:

- Architecture: How is the code organized? What patterns are used?
- Dependencies: What does this area depend on? What depends on it?
- Tech debt: Band-aids, TODOs, complexity hotspots, dead code
- Patterns: Naming conventions, error handling, testing approach
- Known issues: Check ai-memory for project history (load `ai-memory` skill from ned as companion)

Produce a **Current State Report** covering:
- Architecture summary (1-2 paragraphs)
- Key files and their roles
- Patterns in use (good and bad)
- Tech debt inventory
- Dependencies (internal and external)
- Known issues from project history

**Agent 2: UX Assessment** (conditional)

Only runs if a dev server is detected or a URL is provided. Read `references/ux-assessment-protocol.md` for the full protocol. In summary:

- Use Playwright MCP tools to navigate and screenshot the affected area
- Evaluate: visual hierarchy, spacing, typography, interaction states, responsiveness
- Apply the same UX principles as dm-review's ux-quality-reviewer
- Check at 3 viewports: mobile (375px), tablet (768px), desktop (1440px)

Produce a **Current UX Report** covering:
- Screenshots at each viewport
- Visual hierarchy assessment
- Spacing and rhythm evaluation
- Interaction state inventory (hover, focus, active, disabled, empty, error)
- Accessibility quick-check (color contrast, focus indicators, semantic structure)
- UX debt inventory

If no dev server is available, skip this agent and note: "UX assessment skipped -- no dev server detected."

### Phase 3: Consolidation

Combine both reports into a single **Assessment Brief**:

```markdown
# Assessment: [Area Name]

## Code State
[From Code Assessment agent]

## UX State
[From UX Assessment agent, or "Skipped" if no dev server]

## Key Findings
- [Top 3-5 findings that should inform planning]

## Recommendations
- [What to address in the upcoming work]
- [What to leave alone]
```

Save the brief to `plans/assessment-<area-slug>.md` in the target project.

### Phase 4: Handoff

Present the Assessment Brief to the user. If running as part of `/pipeline`, pass it forward to the research phase. If running standalone via `/pipeline-assess`, present it and stop.

## Companion Skills

- **ai-memory** (from ned) -- Loaded during code assessment to check project history
- **Domain skills** (assembly, live-wires, craft-developer) -- Loaded based on project type detection for pattern evaluation

## Graceful Degradation

- No Playwright MCP: Skip UX assessment, note in report. Playwright is intentionally not declared in `mcpDependencies` because the UX assessment is optional -- the skill functions without it.
- No ai-memory MCP: Skip project history check, note in report
- No domain plugins: Use general patterns only, note which plugins would have helped
