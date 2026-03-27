# Research Source Registry

Maps research needs to the best available sources in the DM ecosystem.

## Source Capabilities

### ai-memory (ned plugin)

**What it knows:** Projects, people, companies, decisions, finances, relationships, architecture observations, prior review findings.

**Best for:**
- "What decisions have we made about X?"
- "Who has context on this area?"
- "What issues have we seen before?"
- "What's the project history?"

**MCP tools:**
- `mcp__ai-memory__search_entities` -- Full-text search across all entities
- `mcp__ai-memory__get_entity` -- Get full entity with all observations and relationships

**Search strategy:** Start broad (feature keywords), then narrow by entity type. Check relationships between entities for hidden context.

### RAG (global MCP)

**What it knows:** Personal knowledge library -- articles, books, design resources, saved references.

**Best for:**
- Design methodology and principles
- Typography, layout, and visual design references
- Industry analysis and business strategy
- Technical articles and tutorials

**MCP tools:**
- `mcp__rag__rag_search` -- Semantic search across the knowledge library

**Search strategy:** Use natural language queries. Try multiple phrasings if first search is sparse.

### Domain Plugins (depot)

**What they know:** Stack-specific patterns, conventions, and reference material.

| Plugin | Domain | Key Skill |
|--------|--------|-----------|
| assembly | Go+Templ+Datastar patterns | `development` |
| live-wires | CSS framework, layout primitives | `livewires` |
| craft-developer | Craft CMS queries, templates, content modeling | `craft-development` |
| design-practice | Typography, layout, data viz, identity | Various |
| council | BC Co-op Act, governance patterns | `governance` |
| ghostwriter | Writing voice, editorial style | `voice` |
| design-machines | Business strategy, catalog, partnerships | `strategy` |

**Best for:** "What's the right pattern for X in this stack?"

**Access:** Load as companion skills. Read their SKILL.md and references for applicable patterns.

### Web Search + Context7

**What they know:** Current documentation, community best practices, recent developments.

**Best for:**
- Framework version-specific docs
- Recent changes or deprecations
- Community-recommended approaches
- Third-party library documentation

**Tools:**
- `WebSearch` -- General web search
- `mcp__plugin_context7_context7__resolve-library-id` + `query-docs` -- Framework documentation

**Search strategy:** Start with Context7 for framework docs (more structured), fall back to WebSearch for broader queries.

### Codebase Research (compound-engineering or direct)

**What it knows:** Current repository structure, patterns in use, conventions.

**Best for:**
- "How do we do X in this codebase?"
- "What patterns exist for similar features?"
- "What conventions should I follow?"

**Agents (if compound-engineering installed):**
- `repo-research-analyst` -- Repository structure and patterns
- `best-practices-researcher` -- Industry practices
- `framework-docs-researcher` -- Framework docs

**Direct fallback:**
- Grep for similar patterns
- Read CLAUDE.md files
- Check git log for recent related changes

## Research Priority by Feature Type

### New Feature
1. ai-memory (prior decisions, constraints)
2. Domain plugins (stack patterns)
3. Codebase research (similar implementations)
4. Web/Context7 (framework docs)
5. RAG (design principles)

### Bug Fix / Iteration
1. ai-memory (known issues, history)
2. Codebase research (current implementation)
3. Domain plugins (correct patterns)
4. Web/Context7 (known issues, docs)

### Design / UX Work
1. RAG (design references)
2. Domain plugins (design-practice, live-wires)
3. ai-memory (prior design decisions)
4. Web/Context7 (current design trends)

### Governance Feature
1. Domain plugins (council governance skill)
2. ai-memory (co-op context, member data)
3. RAG (cooperative resources)
4. Web/Context7 (legal references)
