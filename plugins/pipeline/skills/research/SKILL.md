---
name: research
description: Gathers context from ai-memory, RAG, web search, and DM domain plugins for feature planning. Use when starting a feature and needing comprehensive background before planning. Dispatches parallel research agents across all DM knowledge sources -- ai-memory knowledge graph, personal RAG library, web search, Context7 framework docs, and compound-engineering research agents. Invoke with /pipeline (research phase) or load directly when planning any DM project feature.
---

# DM Research Orchestrator

Gather context from all available DM knowledge sources before planning a feature. Produces a Research Brief that informs plan creation and prompt generation.

## Input

Requires two things:
1. **Feature description** -- What the user wants to build or change
2. **Assessment Brief** (optional) -- Output from the assess skill, if available

## Process

### Phase 1: Source Detection

Determine which research sources are available. Check each and note availability:

| Source | How to Check | Required |
|--------|-------------|----------|
| ai-memory | Call `mcp__ai-memory__search_entities` with a test query | Yes (hard dep on ned) |
| RAG | Call `mcp__rag__rag_search` with a test query | No -- graceful skip |
| Web search | WebSearch tool available | No -- graceful skip |
| Context7 | `mcp__plugin_context7_context7__resolve-library-id` available | No -- graceful skip |
| compound-engineering | Check if repo-research-analyst agent is available | No -- graceful skip |
| Gemini CLI | Run `timeout 10 gemini -p "test" -m flash-lite --yolo --output-format json --raw-output 2>/dev/null` and check for valid JSON | No -- graceful skip |

### Phase 2: Project Type Detection

Detect the project type to determine which domain plugins to load as companions. Use the same detection logic as dm-review:

| Marker | Project Type | Companion Skill |
|--------|-------------|-----------------|
| `go.mod` | Go+Templ+Datastar | assembly `development` |
| `craft/` or `config/` with `craft` | Craft CMS | craft-developer `craft-development` |
| CSS files in `src/css/` or Live Wires patterns | Live Wires CSS | live-wires `livewires` |
| Design/UX context in feature description | Design practice | design-practice skills |
| Cooperative governance context | Governance | council `governance` |

### Phase 3: Parallel Research Dispatch

Launch all available research agents simultaneously. Each agent gets the feature description and assessment brief (if available).

**Agent 1: ai-memory Researcher**

Search the knowledge graph for everything related to the feature area:

1. Search for project entities related to the feature
2. Search for person entities (who has context on this?)
3. Search for decision or architecture entities
4. For each relevant entity, get full details with `get_entity`
5. Extract: prior decisions, known constraints, related work, key contacts

**Agent 2: RAG Researcher** (if available)

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

**Agent 6: Gemini Search Researcher** (if Gemini CLI available)

Search with Google grounding for current, cited results:

1. Formulate 2-3 search queries from the feature description targeting current best practices, recent framework changes, and community patterns
2. Resolve the gemini template and protocol paths via the plugin cache (pipeline runs in worktrees):
   ```bash
   TEMPLATES_PATH=""
   PROTOCOL_PATH=""
   for CACHE_ROOT in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
     TEMPLATES_PATH=$(ls -t "$CACHE_ROOT"/gemini/*/skills/gemini-delegate/references/prompt-templates.md 2>/dev/null | head -1)
     PROTOCOL_PATH=$(ls -t "$CACHE_ROOT"/gemini/*/skills/gemini-delegate/references/invocation-protocol.md 2>/dev/null | head -1)
     [ -n "$TEMPLATES_PATH" ] && [ -n "$PROTOCOL_PATH" ] && break
   done
   ```
   Load the **Search Grounding Template** from `$TEMPLATES_PATH`. Fill in the topic queries and project context, then invoke per `$PROTOCOL_PATH` (which itself resolves the gemini-wrapper.sh via the cache). Use `flash` model with 60s timeout.
3. Parse the `response` field from JSON output. Verify `stats.tools.byName.google_web_search` is present (confirms search grounding was used).
4. Extract: authoritative sources with URLs, recent changes or deprecations, community consensus, version-specific guidance

**Advantage over Agent 4 (Web + Context7):** Gemini's search grounding returns structured citations with URLs automatically. Context7 is better for framework API docs; Gemini is better for current best practices, recent changes, and community patterns. They complement each other.

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

Collect results from all agents and produce a **Research Brief**:

```markdown
# Research Brief: [Feature Name]

## Summary
[2-3 sentence summary of what was found]

## Project Context
[From ai-memory: prior decisions, known constraints, related work]

## Domain Knowledge
[From domain plugins: applicable patterns, conventions, requirements]

## Design References
[From RAG: relevant design principles, methodology guidance]

## Technical References
[From web/Context7: current docs, best practices, version guidance]

## Codebase Patterns
[From codebase research: existing similar implementations, conventions to follow]

## Constraints and Risks
[Anything that could complicate implementation]

## Key Decisions Needed
[Questions that planning will need to answer]
```

Save the brief to `plans/research-<feature-slug>.md` in the target project.

### Phase 5: Handoff

If running as part of `/pipeline`, pass the Research Brief forward to the planning phase. If running standalone, present it to the user.

## Graceful Degradation

Each research source operates independently. If a source is unavailable:
- Note it in the brief: "RAG search unavailable -- personal knowledge library not consulted"
- Continue with remaining sources
- The brief is still useful with partial research

Minimum viable research requires only ai-memory (hard dependency on ned).

## Reference Loading Discipline

Reference files under `plugins/*/references/` (domain plugins, companion skills) are loaded ON DEMAND by research agents, not eagerly up front. The Research Brief is synthesized from targeted loads -- an agent reads a specific reference only when its research thread needs it.

- DO: load `live-wires:livewires/references/spacing.md` when the feature touches CSS spacing.
- DO: load `council:governance/references/bc-cooperative-act.md` when the feature involves voting thresholds.
- DON'T: bulk-load every reference from every companion plugin at the start of the research phase -- that burns tokens without adding focus.

When in doubt, load narrowly. Re-load only if the first pass missed necessary detail.
