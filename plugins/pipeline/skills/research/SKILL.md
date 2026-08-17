---
name: research
description: Gathers repository context and enriches it from any available relevant sources for feature planning. Use when starting a feature and needing comprehensive background before planning. May dispatch research agents across repository evidence, domain plugins, web search, Context7, and optional personal sources when those capabilities are callable. Invoke with /pipeline (research phase) or load directly when planning any DM project feature.
---

# DM Research Orchestrator

Gather context from all available DM knowledge sources before planning a feature. Produces a Research Brief that informs plan creation and prompt generation.

## Input

Requires:
1. **Original request** -- The user's verbatim feature description
2. **Provisional Assessment Brief** -- Including its compact Project Alignment record
3. **Current repository evidence** -- Identity, source state, and relevant instructions/plans

The assessment's `keyRequirements` remain provisional during research. Do not
describe them as approved or use them to override a current authority.

## Process

### Phase 1: Source Detection

Determine which research sources are both available and relevant. Availability
alone is not a reason to query a source. Select the smallest source set that can
test current project alignment and implementation claims. Discover optional
personal-source capability only from the current callable-tool inventory or a
tool-search result; never invoke a tool merely to probe whether it exists.
Capability availability is the complete rule; never infer it from usernames,
environment variables, repository ownership, or other identity heuristics.

| Source | How to Check | Required |
|--------|-------------|----------|
| Repository evidence | Read relevant tracked files, instructions, history, issues, and PR context | Yes |
| ai-memory | Look for the required ai-memory tools in the callable-tool inventory or tool search | No -- optional personal enrichment |
| RAG | Look for `mcp__rag__rag_search` in the callable-tool inventory or tool search | No -- optional personal enrichment |
| Web search | WebSearch tool available | No -- graceful skip |
| Context7 | `mcp__plugin_context7_context7__resolve-library-id` available | No -- graceful skip |
| compound-engineering | Check if repo-research-analyst agent is available | No -- graceful skip |

When an optional personal source is callable, continue using it for relevant
enrichment. When it is absent during incidental Pipeline research, omit that
lookup silently: do not mention the source in the brief, receipts, coverage,
completion status, or user guidance. Never ask the user to install or configure
it. Only an explicit user request for an ai-memory or RAG operation makes an
unavailable personal source reportable.

Inspect the supplied or safely discoverable native Issue/PR when it is relevant.
Consult a coordination Project only when the repository or user declares one.
Do not perform a generic organization-wide GitHub survey for every run.

### Phase 2: Project Type Detection

Detect the project type to determine which domain plugins to load as companions. Use the same detection logic as dm-review:

| Marker | Project Type | Companion Skill |
|--------|-------------|-----------------|
| `go.mod` | Go+Templ+Datastar | assembly `development` |
| `craft/` or `config/` with `craft` | Craft CMS | craft-developer `craft-development` |
| CSS files in `src/css/` or Live Wires patterns | Live Wires CSS | live-wires `livewires` |
| Design/UX context in feature description | Design practice | design-practice skills |
| Cooperative governance context | Governance | council `governance` |

For Assembly-related work, preserve the real operating context: a two-person
development team, trusted first-party repositories, small self-hosted Go
applications, and roughly 4--50 users per installation. Apply YAGNI and
pragmatic DRY. Keep strong security at real credential, authorization,
release-integrity, and data-loss boundaries, but do not add enterprise
architecture without a demonstrated current consumer.

### Phase 3: Parallel Research Dispatch

Launch the selected applicable research agents simultaneously. Each gets the
original request, provisional assessment, compact Project Alignment record, and
current repository evidence. Do not query unrelated company/domain sources.

**Executor routing:** Default read-heavy research fan-out to Codex, with Claude
as the local fallback when Codex is unavailable. This phase remains native by
workload policy; configured-key availability does not broaden the bounded
OpenRouter execution workload.

Resolve the coherent installed Pipeline bundle with `--plugin pipeline
--minimum-version 1.36.1 --required-asset
references/openrouter-authorization-contract.md --active-host <claude|codex>`
and read the current-mode contract from that selected root. Never use a
target-repository copy.

**Agent 1: ai-memory Researcher** (only when callable and relevant)

Search the knowledge graph for everything related to the feature area:

1. Search for project entities related to the feature
2. Search for person entities (who has context on this?)
3. Search for decision or architecture entities
4. For each relevant entity, get full details with `get_entity`
5. Extract: prior decisions, known constraints, related work, key contacts

**Agent 2: RAG Researcher** (only when callable and relevant)

Search the personal knowledge library:

1. Search for the feature topic broadly
2. Search for related design patterns or principles
3. Search for relevant technical approaches
4. Extract: design references, methodology guidance, prior art

**Agent 3: Domain Plugin Researcher**

Load companion skills based on project type and extract relevant patterns:

1. If Go project: What assembly patterns apply? Handler conventions? DTO patterns?
2. If Craft project: What content modeling patterns? Query patterns? Template conventions?
3. If CSS work: What Live Wires primitives exist? Token conventions? Component patterns?
4. If governance: What BC Co-op Act requirements apply? Voting thresholds? Member lifecycle?

This agent reads the companion skill content and extracts the sections most relevant to the feature.

**Agent 4: Web + Context7 Researcher** (if available)

Search for current best practices:

1. If a framework/library is involved, use Context7 to get current docs
2. WebSearch for recent best practices articles
3. Search for common pitfalls or known issues
4. Extract: current documentation, community patterns, version-specific guidance

**Agent 5: Codebase Researcher** (if compound-engineering available)

Delegate to compound-engineering's research agents:

1. `repo-research-analyst` -- Repository structure and conventions
2. `best-practices-researcher` -- Industry best practices for the feature type
3. `framework-docs-researcher` -- Framework-specific documentation

If compound-engineering is not installed, perform basic codebase research directly:
- Grep for similar patterns in the codebase
- Read CLAUDE.md files for conventions
- Check git log for related recent changes

When a native Issue/PR or declared coordination Project is in scope, verify only
the named repository/ownership/dependency state needed for this request. Record
conflicts between live GitHub state and stale tracked prose without treating the
coordination projection as architectural authority.

**Agent 6: Web Search Researcher** (Claude-native grounding, if WebSearch available)

Use native web tools for current, cited results:

1. Formulate at most 2-3 focused queries only when current external technical
   evidence is needed, targeting the specific framework/API claim
2. Run `WebSearch` for each query. From the results, select the most authoritative sources (official docs, maintainer posts, recognized practitioners)
3. `WebFetch` the top sources to extract specifics and capture exact URLs for citation
4. Extract: authoritative sources with URLs, recent changes or deprecations, community consensus, version-specific guidance

**Relationship to Agent 4 (Web + Context7):** Agent 4 leans on Context7 for framework API docs; this agent leans on WebSearch + WebFetch for current best practices, recent changes, and community patterns with cited URLs. They complement each other. If WebSearch is unavailable, skip gracefully.

### Phase 3b: Verify-Don't-Trust Checks

After parallel research completes, run these mandatory verification steps. These prevent the most common pipeline failures:

**1. API Existence Verification**

If the research suggests using specific framework functions, APIs, or library features, verify they exist in the actual installed version:

```bash
# Go: check if a function exists in the module
docker compose exec app grep -r "func.*WithID" /go/pkg/mod/github.com/a-h/templ* 2>/dev/null

# Node: check exports
node -e "console.log(Object.keys(require('package-name')))"

# General: check go.mod/package.json for actual version installed
```

Do NOT propose using an API that hasn't been verified to exist in the installed version. Hallucinated APIs are the #1 cause of pipeline failures.

**0. Project Alignment Verification**

Before technical verification, test the proposal against the compact alignment
record and current sources:

- Does it advance the current project goal?
- Does another repository, active branch, or named owner already own it?
- Is any supporting plan, comment, receipt, or remembered state stale?
- Is the requested mechanism necessary, or does a smaller direct solution
  preserve the approved outcome?
- Does it add speculative scale, ceremony, or machinery without a current
  consumer?

Surface real authority conflicts for the combined discovery gate. Never let a
technically attractive approach silently override the repository's current
project goal.

**2. Codebase Pattern Verification**

When research finds framework patterns (e.g., Datastar attribute syntax), verify the EXACT syntax used in the CURRENT codebase, not documentation:

```bash
# Find actual Datastar modifier syntax in use
grep -r "data-on:" backend/internal/ --include="*.templ" | head -5
```

If the codebase uses `data-on:keydown__window` but docs say `data-on:keydown.window`, the CODEBASE wins. Document the actual patterns found.

**3. Build Tool Detection**

Read the actual build configuration -- don't assume:

```bash
cat package.json | python3 -c "import json,sys; d=json.load(sys.stdin); print('scripts:', json.dumps(d.get('scripts',{}), indent=2))"
```

**4. Exhaustive File Search**

When research finds a file matching a pattern, search for ALL matches -- don't stop at the first one:

```bash
# Find ALL template files for a given feature
find . -name "*.templ" -path "*/members/*" 2>/dev/null
```

Document every match. Duplicate files serving different routes is a common source of bugs.

### Phase 3b: Stable Anchor Recommendations

When research uncovers code-to-doc cross-references (e.g. a spec cites a specific handler, or code references a design doc), prefer stable anchors over line numbers in the Research Brief output.

Rules the Research Brief should follow:

- **Go / Python / TS functions:** reference by function name, not line number. `func SetPosition in internal/handler/position.go` beats `position.go:42`.
- **Templ components:** `templ PositionChangeDialog` beats `dialogs.templ:235`.
- **Markdown documents:** use heading slugs (`#voting-thresholds`) rather than `docs/governance.md:120`.
- **Migrations:** cite filename plus table/column (`003_add_votes.sql -> proposals.vote_count`) rather than SQL line numbers.

When the research agent generates citations, it should apply these rules to its own outputs. The prompt-writer (Phase 4) inherits these anchors and does not have to clean up brittle line-number references the research phase introduced.

Also loads (see Phase 4 handoff): the promptcraft skill's Phase 3e Stable Anchors Audit enforces the same rule downstream.

### Phase 4: Consolidation

Collect results from all agents and produce a **Research Brief**. Write it as **HTML with a JSON data island**, not markdown -- assemble `templates/base.html` + `templates/sections/research.html` per `${CLAUDE_PLUGIN_ROOT}/plugins/pipeline/skills/promptcraft/references/templates/README.md`. This is the synthesized brief; if research also produced facet notes (`research-codebase.md`, `research-context.md`, `research-design.md`), leave those as markdown supporting detail. The `findings` and `references` arrays populate the `#pipeline-data` island. The content outline below maps to the section's slots:

```markdown
# Research Brief: [Feature Name]

## Summary
[2-3 sentence summary of what was found]

## Project Context
[Current project goal, source-backed relevance now, ownership/dependency state,
and stale or conflicting context. Prior memory is supporting context only.]

## Domain Knowledge
[From domain plugins: applicable patterns, conventions, requirements]

## Design References
[From available relevant sources: design principles, methodology guidance]

## Technical References
[From web/Context7: current docs, best practices, version guidance]

## Codebase Patterns
[From codebase research: existing similar implementations, conventions to follow]

## Constraints and Risks
[Anything that could complicate implementation]

## Alignment Verdict
[Whether the work advances the current goal; smallest supported scope; explicit
non-goals; ownership conflicts; any owner choice that remains]

## Key Decisions Needed
[Only user-owned decisions to resolve at the combined discovery gate]
```

Save the brief to `plans/<feature-slug>/research.html` in the target project (detect host CSS first; on `FALLBACK` inline `templates/baseline.css`).

### Phase 5: Handoff

If running as part of `/pipeline`, pass the Research Brief and provisional
assessment to the combined discovery gate. Research does not have a separate
human approval pause. If running standalone, present it to the user.

## Graceful Degradation

Each research source operates independently. Minimum viable research is
repository evidence plus any other available relevant sources. Missing
optional personal sources do not make research partial or incomplete and
produce no brief, assessment, receipt, coverage, or delivery notice. If a
non-personal source is unavailable, continue with the remaining relevant
evidence and report it only when its absence materially limits a user-requested
outcome.

## Reference Loading Discipline

Reference files under `plugins/*/references/` (domain plugins, companion skills) are loaded ON DEMAND by research agents, not eagerly up front. The Research Brief is synthesized from targeted loads -- an agent reads a specific reference only when its research thread needs it.

- DO: load `live-wires:livewires/references/spacing.md` when the feature touches CSS spacing.
- DO: load `council:governance/references/bc-cooperative-act.md` when the feature involves voting thresholds.
- DON'T: bulk-load every reference from every companion plugin at the start of the research phase -- that burns tokens without adding focus.

When in doubt, load narrowly. Re-load only if the first pass missed necessary detail.
