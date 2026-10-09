---
name: assess
description: Current codebase state and UX baseline before planning changes -- architecture, patterns, tech debt, and UX quality. Use when starting a feature, iterating on existing work, or needing a baseline understanding before making changes. Evaluates what EXISTS, not what CHANGED. Invoke with /pipeline-assess or as the first phase of /pipeline.
---

# Pre-Plan Assessment

Evaluate the current state of a codebase area before planning changes. Unlike dm-review which reviews a diff, this reviews what exists -- architecture, patterns, tech debt, UX quality, and known issues.

## Input

The user provides a feature idea, area description, or specific file paths. If vague, ask: "Which part of the codebase should I assess? Give me a feature area, directory, or file paths."

## Process

### Phase 0: Project Alignment

Before implementation-detail assessment, resolve the smallest relevant project
context in this order:

1. Resolve repository identity and current source state.
2. Read root `AGENTS.md`, `CLAUDE.md`, and only directly referenced instruction
   files applicable to the request.
3. Inspect relevant active repository plans, coordination documents,
   engineering principles, and `tasks/lessons.md` when present.
4. Inspect a supplied or safely discoverable native Issue or PR.
5. Consult a coordination Project only when the repository or user declares
   one, and load only relevant installed company, product, or domain strategy
   skills.
6. Identify the current project goal, ownership boundary, and why the proposed
   work is appropriate now.

Keep authority boundaries explicit. Native Issues and PRs own live status,
ownership, dependencies, reviews, checks, and linkage. Repository instructions
and tracked documents own architecture, product scope, project goals,
implementation policy, and durable lessons. A declared coordination Project
owns only its current projection. Old plans, receipts, comments, or remembered
state are not evidence of current GitHub status.

Do not require GitHub Projects, an Assembly-specific layout, one planning
document shape, or a project-management plugin. Do not copy a roadmap. Carry a
compact rendered `Project Alignment` record in the existing assessment:

- Current project goal
- Evidence/source
- How the request advances it
- Relevant constraints and decisions
- Explicit non-goals
- Dependencies or ownership conflicts
- Stale or unknown context

### Phase 1: Scope Detection

Determine what to assess based on the user's input:

1. If specific paths given, use those
2. If a feature area described, identify the relevant directories and files
3. If a project name given, use the project root

Inspect only the files needed to resolve behavior, acceptance, design,
consequence/reversibility, coordination, patterns and verification. Existing
acceptance can serve as the plan for settled low-impact work. Name the question
another research/review stage would resolve; otherwise do not add that stage.
Use the Pipeline command’s direct/lean/full selection, not file count, language,
UI or integration labels. The current agent can perform a bounded assessment;
no mandatory assessment roster or separate planning agent is implied.

For rendered work, resolve declared prototype authority before target UX
evaluation. Load `plugins/pipeline/references/prototype-authority.md` when its
conditional trigger applies. Read the exact prototype templates/components
first and produce only the affected-surface `prototypeReference` and
`prototypeParity` map defined there. Conflicting or unresolved repository,
commit, route, or authority declarations stop UI implementation with
`human_help_required`; a source-proven missing counterpart is recorded and
falls back to existing production patterns.

### Phase 2: Proportional Assessment

The current agent assesses bounded settled work directly. Add a separate
assessment specialist only for a named affected concern or independent work
with a concrete advantage. Parallelize only genuinely independent scopes;
a stage does not imply another participant.

**Executor routing:** Optional bounded evidence gathering requests
`research-fast` with only needed capabilities and normalized effort through
model-router. Conflicting or consequential judgment uses an appropriate
stronger role. Never select a native transport or inherit the driver’s model.
Workers receive relevant source, scope and the question to resolve.

Resolve the coherent installed Pipeline bundle with `--plugin pipeline
--minimum-version 1.36.1 --required-asset
references/openrouter-authorization-contract.md --active-host <claude|codex>`
and read the current-mode contract from that selected root. Never use a
target-repository copy.

**Agent 1: Code Assessment**

Use this summary. Load `references/code-assessment-protocol.md` only if the
area is unfamiliar or the first pass cannot name architecture, dependents, and
current debt:

- Architecture: How is the code organized? What patterns are used?
- Dependencies: What does this area depend on? What depends on it?
- Tech debt: Band-aids, TODOs, complexity hotspots, dead code
- Patterns: Naming conventions, error handling, testing approach
- Known issues: Inspect repository history. If callable, ai-memory may enrich project history; otherwise omit it silently.

Produce a **Current State Report** covering:
- Architecture summary (1-2 paragraphs)
- Key files and their roles
- Patterns in use (good and bad)
- Tech debt inventory
- Dependencies (internal and external)
- Known issues from project history

**Agent 2: UX Assessment** (conditional -- UI-touching feature)

**Skip rule (token budget):** if the feature's scope is entirely backend/logic -- none of the planned work touches templates, CSS, JS modules, or rendered pages -- skip the UX assessment. Log one line: `UX assessment: skipped (no UI/Integration surface detected).`

Resolve uncertain rendered applicability with targeted source inspection.
Required UX/browser/prototype coverage remains required; an integration label
alone does not create a UI assessment or three-viewport screenshot pass.

Run discovery whenever source evidence establishes affected rendered behavior. Execute browser proof
when a dev server is detected or a URL is provided. Read
`references/ux-assessment-protocol.md` for the full protocol. In summary:

- Use host Playwright via dm-review’s shared formal transport contract; T3
  supports operator handoff and verified target context
- Evaluate: visual hierarchy, spacing, typography, interaction states, responsiveness
- Apply the same UX principles as dm-review's ux-quality-reviewer
- Check at 3 viewports: mobile (375px), tablet (768px), desktop (1440px)

When a declared counterpart exists, capture prototype and target evidence at
matching routes, states, and viewports. Source inspection and browser evidence
are complementary; neither a target-only screenshot nor matching class names
completes parity. Capture matched parity through host Playwright.

Produce a **Current UX Report** covering:
- Screenshots at each viewport
- Visual hierarchy assessment
- Spacing and rhythm evaluation
- Interaction state inventory (hover, focus, active, disabled, empty, error)
- Accessibility quick-check (color contrast, focus indicators, semantic structure)
- UX debt inventory

If no dev server or supplied URL is available, discovery may continue, but the
required UI/integration target is unavailable. Record a blocked
`human_help_required` outcome and ask the user to start/provide the target; never
mark required browser proof skipped or replace it with curl reachability.

#### Baseline Screenshot Persistence

When the project has a rendered surface and a reachable dev server, load
`plugins/pipeline/references/assess-baseline-screenshots.md` and follow it.
With no rendered surface, do not load it.

#### Fixture Discovery

When the project ships fixtures, dev-time auth bypasses or persona-switching
helpers, or a `tests/ux/` verification declaration, load
`plugins/pipeline/references/assess-fixture-discovery.md` and follow it.
Record auth field names only; never copy cookie, bearer, password, username, or
fixture-secret values into assessment HTML or its data islands. A project with
none of those does not load that file.

#### Prior Lessons Check

When the repository carries prior run postmortems or codified lessons, load
`plugins/pipeline/references/assess-prior-lessons.md` and apply it. With none
present, record that and do not load it.

### Phase 3: Consolidation

Combine both reports into a single **Assessment Brief**. When running as part of `/pipeline`, preserve the original prompt verbatim and distinguish in the existing assessment prose:

- desired outcomes;
- hard constraints and explicit approved decisions;
- implementation mechanisms proposed by the user or an upstream prompt; and
- future or conditional ideas.

Never silently discard an explicit request. Proposed mechanisms do not override authorized outcomes. Carry unresolved
scope choices to discovery; preserve explicit upstream decisions. Persist the
actual authority in Scope Intake, Project Alignment and `keyRequirements`;
only unresolved scope stays provisional. Selected research proceeds without
another approval pause.

The brief is written as **HTML with a JSON data island**, not markdown -- assemble `templates/base.html` + `templates/sections/assessment.html` per `${CLAUDE_PLUGIN_ROOT}/plugins/pipeline/skills/promptcraft/references/templates/README.md`. The content outline below maps to the section's slots; the `keyRequirements`, `testPersonas`, `recentLessons`, and `baselineScreenshots` arrays also populate the `#pipeline-data` island so later phases read them with `extract-json-island.sh` instead of grepping prose. When prototype authority applies, add the compact optional `prototypeReference` object and affected-surface `prototypeParity` collection from `prototype-authority.md`; do not add a separate artifact or durable schema.

```markdown
# Assessment: [Area Name]

## Scope Intake
- Desired outcomes: [...]
- Hard constraints and approved decisions: [...]
- Proposed mechanisms: [...]
- Future or conditional ideas: [...]
- Smallest adequate alternative and any user decision needed: [...]

## Project Alignment
- Current project goal: [...]
- Evidence/source: [...]
- How the request advances it: [...]
- Relevant constraints and decisions: [...]
- Explicit non-goals: [...]
- Dependencies or ownership conflicts: [...]
- Stale or unknown context: [...]

## Key Requirements (record scope authority; unresolved entries stay provisional)
1. [Requirement 1 verbatim]
2. [Requirement 2 verbatim]
3. [Requirement N verbatim]

## Code State
[From Code Assessment agent]

## UX State
[From UX Assessment agent; use "Skipped" only for no UI/integration surface.
For an unavailable required target, record blocked `human_help_required`.]

## Prototype Parity
[Source-first parity map for affected counterparts, including matched browser
evidence and intentional differences; otherwise "No prototype counterpart"
with inspected evidence, or "No declared prototype".]

## Test Personas
[From Fixture Discovery, or "No dev-mode auth bypass detected."]

## Recent Lessons That May Apply
[From Prior Lessons Check, or "No lessons file."]

## Baseline Screenshots
[Show an actual image gallery using linked images and route/state/viewport
captions, not filename lists. Show desktop 1440 per route; preserve mobile
375/320 files in `baselineScreenshots`. Follow the saved-baseline reference for
markup. Required target unavailable: blocked `human_help_required`; no rendered
surface: assessment not applicable.]

## Key Findings
- [Top 3-5 findings that should inform planning]

## Recommendations
- [What to address in the upcoming work]
- [What to leave alone]
```

Save the brief to `plans/<feature-slug>/assessment.html` in the target project (detect host CSS first; on `FALLBACK` inline `templates/baseline.css`). When running standalone via `/pipeline-assess`, the slug may be the area name instead of a feature slug.

### Phase 4: Handoff

If running as part of `/pipeline`, pass relevant assessment/alignment to the
next selected stage; research only for named unanswered questions. If running standalone via `/pipeline-assess`, present it and stop.

## Companion Skills

- **ai-memory** (from ned, optional) -- When its tools appear in the callable-tool inventory or tool search, it may enrich repository-backed project history. Do not invoke it merely to probe availability.
- **Domain skills** (assembly, live-wires, craft-developer) -- Loaded based on project type detection for pattern evaluation

## Graceful Degradation

- No browser transport: when no supported Playwright transport is available
  after the shared recovery ladder,
  discovery may continue but required UI/integration browser coverage is
  blocked. Return `human_help_required`; never mark required proof skipped or
  curl-verified. Missing Playwright blocks required browser proof; T3 does not replace it.
- Optional personal sources: detect them only from callable-tool inventory or
  tool search. If ai-memory is not callable, omit the lookup and any mention of
  its absence; repository history still supplies the project-history evidence.
  Do not ask the user to install or configure incidental enrichment. Only an
  explicit user-requested personal-memory operation may report that its named
  capability is unavailable.
- No domain plugins: Use general patterns only, note which plugins would have helped
