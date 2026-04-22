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

**Agent 2: UX Assessment** (conditional -- dev server AND UI-touching feature)

**Skip rule (token budget):** if the feature's scope is entirely backend/logic -- none of the planned work touches templates, CSS, JS modules, or rendered pages -- skip the UX assessment. Log one line: `UX assessment: skipped (no UI/Integration surface detected).`

Heuristic (applied on the user's feature description since the chunk classification does not yet exist in Phase 1):

- UI-touching if the description mentions: route, page, form, button, modal, dialog, screen, visual, layout, styling, accessibility, template, component, or any filename ending in `.templ`, `.twig`, `.html`, `.css`, `.jsx`, `.tsx`.
- Backend-only if the description mentions only: handler, service, migration, schema, API, endpoint, background job, database, SQL, ETL, without any UI verbs above.

When in doubt, run the UX assessment -- false positives are cheaper than missing a regression. But a strict backend-only assessment (e.g. "add a new migration column for vote_count") should NOT trigger 3-viewport screenshots.

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

#### Baseline Screenshot Persistence

Save all screenshots taken during the UX assessment to disk for later comparison:

1. Create directory: `plans/<feature-slug>/baselines/`
2. Save each screenshot with a descriptive name: `baselines/<route-slug>-<viewport>.png`
   - Example: `baselines/governance-proposals-desktop-1440.png`
   - Example: `baselines/governance-proposals-mobile-375.png`
3. Record the screenshot manifest in the Assessment Brief under a `## Baseline Screenshots` section listing every saved file and its route/viewport.

These baselines serve as the "before" state for visual diff comparisons after implementation. The execution-orchestrator's visual verification protocol compares post-implementation screenshots against these baselines to detect regressions. Expected changes (the feature being built) are fine; unexpected visual differences are findings.

Note: Baseline screenshots are ephemeral -- useful within a pipeline run but not committed to git. Add `plans/*/baselines/*.png` to `.gitignore` if not already ignored.

#### Fixture Discovery

Many codebases ship with dev-time auth bypasses or persona-switching helpers. Discovering these up-front saves the prompt-writer from having to re-derive them from handler code.

Protocol:

1. **Auth middleware scan:** grep the project's auth middleware (common locations: `internal/handlers/middleware.go`, `backend/auth/*.go`, `app/Http/Middleware/*.php`, `config/authentication.*`) for keywords: `cookie`, `X-Test-User`, `Bearer`, `session`, `impersonate`. **Extract the header/cookie NAME only. Redact values.** If a matched line contains `=<literal>`, `: "<literal>"`, `Bearer <literal>`, or any hardcoded token, flag the file for manual review and record only the field name in the Assessment Brief. Never copy raw matched lines into `plans/<feature-slug>/assessment.md` -- dev-mode middleware sometimes hardcodes bearer tokens or session secrets that must not propagate downstream.
2. **Seed data scan:** grep seed files (`seeds/`, `fixtures/`, `db/seed.*`, `internal/fixtures/*/seed.go`) for user/member IDs and role names. Collect 2-3 representative personas per role.
3. **Test helper scan:** grep `tests/`, `_test.go`, `spec/` for patterns like `loginAs(`, `asUser(`, `setCurrentUser(` to find helper functions that scripts/tests use to switch identity.

Report findings in the Assessment Brief under a `## Test Personas` heading:

```markdown
## Test Personas

**Auth-switching mechanism:** `coop_member` cookie (fake auth middleware at internal/handlers/middleware.go:42)

| Persona | ID | Role | Use for |
|---------|-----|------|---------|
| Aisha Williams | mem_005 | Member, no position | Verify empty-state and unprivileged views |
| David Chen | mem_012 | Member with position | Verify authored-content views |
| Maria Rodriguez | mem_001 | Director | Verify privileged actions and approvals |

To switch identity: set `coop_member=<id>` cookie before navigating.
```

The prompt-writer reuses this instead of re-discovering the mechanism per chunk.

If no auth-bypass mechanism is found, log `fixture discovery: no dev-mode auth bypass detected` and continue.

#### Prior Lessons Check

If `tasks/lessons.md` exists in the project root (created by prior pipeline runs via `execution-orchestrator`), surface recent entries that may apply to this feature:

1. Run `test -f tasks/lessons.md && grep -A 3 "^## " tasks/lessons.md | head -60` to list the most recent lesson headings plus their first three lines.
2. Filter to entries modified in the last 60 days (use `git log --format=%ad --date=short tasks/lessons.md | head -5` to estimate recency if file-level mtime is unreliable).
3. Keyword-match lesson headings against the original prompt's key nouns -- if the lesson mentions any of those nouns, it is potentially relevant.
4. Record matches in the Assessment Brief under a `## Recent Lessons That May Apply` heading. Include the lesson heading and a one-line excerpt.

If no `tasks/lessons.md` exists, log `prior lessons check: no lessons file -- skipping` and continue.

### Phase 3: Consolidation

Combine both reports into a single **Assessment Brief**. When running as part of `/pipeline`, the Assessment Brief also serves as the cached source of truth for the Key Requirements list (extracted from `original-prompt.md` once, referenced many times across phases).

```markdown
# Assessment: [Area Name]

## Key Requirements (cached from original-prompt.md)
1. [Requirement 1 verbatim]
2. [Requirement 2 verbatim]
3. [Requirement N verbatim]

## Code State
[From Code Assessment agent]

## UX State
[From UX Assessment agent, or "Skipped" if no dev server or no UI surface]

## Test Personas
[From Fixture Discovery, or "No dev-mode auth bypass detected."]

## Recent Lessons That May Apply
[From Prior Lessons Check, or "No lessons file."]

## Baseline Screenshots
[Manifest of saved baselines, or "No baselines -- skipped UX assessment."]

## Key Findings
- [Top 3-5 findings that should inform planning]

## Recommendations
- [What to address in the upcoming work]
- [What to leave alone]
```

Save the brief to `plans/<feature-slug>/assessment.md` in the target project. When running standalone via `/pipeline-assess`, the slug may be the area name instead of a feature slug.

### Phase 4: Handoff

Present the Assessment Brief to the user. If running as part of `/pipeline`, pass it forward to the research phase. If running standalone via `/pipeline-assess`, present it and stop.

## Companion Skills

- **ai-memory** (from ned) -- Loaded during code assessment to check project history
- **Domain skills** (assembly, live-wires, craft-developer) -- Loaded based on project type detection for pattern evaluation

## Graceful Degradation

- No Playwright MCP: Skip UX assessment, note in report. Playwright is intentionally not declared in `mcpDependencies` because the UX assessment is optional -- the skill functions without it.
- No ai-memory MCP: Skip project history check, note in report
- No domain plugins: Use general patterns only, note which plugins would have helped
