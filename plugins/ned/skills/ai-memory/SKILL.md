---
name: ai-memory
description: Access Travis Gertz's personal knowledge graph with 5,800+ entities tracking projects, people, finances, health, and relationships. Use when the user asks about their memory, wants to search for people/projects/companies, needs to add observations, or references remembering something.
---

# AI Memory System

Personal knowledge graph interface for Travis Gertz. Accessed via native MCP tools from the `ai-memory` server. Provides search, entity management, and relationship tracking across 5,800+ entities.

## MCP Tools

| Tool | Description |
|------|-------------|
| `search_entities(query, limit?)` | Search across names, types, and observations |
| `get_entity(name)` | Full entity details by exact name |
| `add_observation(entity_name, content)` | Add timestamped observation (auto-saves) |
| `delete_observation(entity_name, content_match)` | Delete observations matching substring (auto-saves) |
| `edit_observation(entity_name, index_pos, new_content)` | Edit observation at index position (auto-saves) |
| `add_entity(name, entity_type, observations?)` | Create new entity (auto-saves) |
| `add_relationship(from_entity, to_entity, relationship_type)` | Link two entities (auto-saves) |
| `rename_entity(old_name, new_name)` | Rename entity and update all references (auto-saves) |
| `get_relationships(entity_name)` | Outgoing and incoming relationships |
| `list_entity_types()` | All entity types with counts |
| `get_stats()` | System overview and entity counts |
| `save()` | Explicit save (rarely needed, writes auto-save) |

## Usage Pattern

1. **Search first**: `search_entities("query")` to discover entities
2. **Drill in**: `get_entity("exact name")` for full details
3. **Write**: `add_observation`, `add_entity`, `add_relationship` as needed
4. All writes auto-save -- no manual save step required

## Excluded Entities

These are excluded from search results (too large): Recent Updates, Current Priorities, Search Keywords. Use `get_entity("Recent Updates")` directly if needed.

## Entity Types

**Core types**: Person, Company, Project, Location, Financial, Health, Document, Event, Recipe, Tool, Workflow, Strategy, Relationship

**See**: [REFERENCE.md](REFERENCE.md) for complete type list and memory structure.

## Important Rules

1. **Search before creating** - Check if an entity exists before adding a new one
2. **Use exact names** - `get_entity` requires exact name match (case-insensitive)
3. **Prefix observations with dates** - e.g., `[Feb 2026] New development...`
4. **Never create new scripts** - Use MCP tools only. If something fails, report to user.

## Additional Documentation

- **Reference**: [REFERENCE.md](REFERENCE.md) - Entity types, memory structure, error handling
- **Relationships**: [RELATIONSHIPS.md](RELATIONSHIPS.md) - Relationship types and patterns
- **Examples**: [EXAMPLES.md](EXAMPLES.md) - Common workflows

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Search returns 0 results | Try different search terms, check spelling |
| Entity not found | Use `search_entities` first to find correct name |
| MCP tools not available | Check `.mcp.json` config and server status |
