# Optional research sources

Loaded by the research phase only when the personal ai-memory or RAG tools are
callable in this session and relevant to the question. When neither is
callable, skip both silently -- no warning, coverage gap, or install request --
and do not load this file.

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
