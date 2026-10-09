---
name: research
description: Gathers repository context and enriches it from any available relevant sources for feature planning. Use when starting a feature and needing comprehensive background before planning. May dispatch research agents across repository evidence, domain plugins, web search, Context7, and optional personal sources when those capabilities are callable. Invoke with /pipeline (research phase) or load directly when planning any DM project feature.
---

# DM Research Orchestrator

Resolve named unanswered questions using the smallest relevant source set.
Settled work needs no research stage.

## Input

Requires:
1. **Original request** -- The user's verbatim feature description
2. **Provisional Assessment Brief** -- Including its compact Project Alignment record
3. **Current repository evidence** -- Identity, source state, and relevant instructions/plans

Preserve recorded scope authority. Unresolved `keyRequirements` remain
provisional; research cannot override approved decisions.

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

Use callable personal sources only for relevant enrichment. Incidental absence
is silent, never an installation request or coverage gap. Report unavailability
only for an explicitly requested personal-source operation.

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

### Phase 3: Focused Research

Research only named unanswered questions. The current agent can resolve a
bounded question directly. Add a specialist only for affected concerns and
parallelize only independent work with a concrete advantage. Workers receive
relevant request/assessment/source excerpts, owned scope and an answerable
question, not a full conversation. Do not query unrelated sources.

**Executor routing:** Request `research-fast` for bounded evidence gathering;
use a stronger judgment role for conflicting or consequential evidence. Concrete
selection, native service mode and fallback remain model-router-owned.

Resolve the coherent installed Pipeline bundle with `--plugin pipeline
--minimum-version 1.36.1 --required-asset
references/openrouter-authorization-contract.md --active-host <claude|codex>`
and read the current-mode contract from that selected root. Never use a
target-repository copy.

Determine ai-memory and RAG availability from the callable-tool inventory or
tool search, never by invoking either source as a probe. When either is callable
and relevant, load `plugins/pipeline/references/research-optional-sources.md`
for Agents 1 and 2. When neither is callable, skip them silently and do not load
that file.

These are source options, not a participant roster:

- Domain skills: extract only the applicable framework/governance patterns.
- Repository: inspect similar implementations, instructions and related history;
  verify named Issue/PR ownership or declared Project dependencies.
- Current external technical claims: use available Context7 or native web tools,
  at most 2–3 focused queries, and cite exact authoritative documentation URLs.
  Do not duplicate the same research through several agents or transports.
- Compound-engineering research is optional when it resolves the named question.

### Phase 3b: Verify-Don't-Trust Checks

Verify claims the research actually relies on; do not add unrelated checks.

**1. API Existence Verification**

Verify proposed APIs in the actual installed dependency/version before planning
implementation. Search dependency source or package exports; never rely on an
unverified model claim.

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

Verify the exact currently used framework syntax and version, including routes
with duplicate templates. Resolve any difference from documentation explicitly.

**3. Build Tool Detection**

Read actual package.json/Makefile/go.mod commands and versions before recommending
build or verification commands.

**4. Exhaustive File Search**

Search all relevant matches with `rg --files`; account for duplicate files serving
different routes rather than assuming the first match is the only consumer.

### Phase 3b: Stable Anchor Recommendations

Use function/component names, Markdown heading slugs and migration filenames
plus table/column when citing source. Avoid brittle line references. Promptcraft's
Phase 3e Stable Anchors Audit enforces the same rule downstream.

### Phase 4: Consolidation

Save material findings as **HTML with a JSON data island** using `templates/base.html`
+ `templates/sections/research.html` per
`${CLAUDE_PLUGIN_ROOT}/plugins/pipeline/skills/promptcraft/references/templates/README.md`.
Populate `findings` and `references`; supporting facet notes may stay Markdown.
Include only applicable sections from this outline:

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

Load references on demand for the named question; never bulk-load companion
plugins. Re-read only when changed facts or missing evidence require it.
