# AI Memory Reference

Complete reference for the AI Memory system accessed via MCP tools.

## Entity Types

### Core Types (most common)

| Type | Count | Description |
|------|-------|-------------|
| Person | 54+ | Friends, family, professional contacts |
| Company | 10+ | Organizations and businesses |
| Project | 27+ | Personal, work, and creative projects |
| Location | 98+ | Cities, countries, travel destinations |
| Financial | 21+ | Financial tracking with temporal data |
| Health | 8+ | Medical records and wellness data |

### Supporting Types

| Type | Description |
|------|-------------|
| Document | Legal, technical, research, design docs |
| Event | Meetings, trips, milestones |
| Recipe | Cooking recipes |
| Tool | Technologies and tools |
| Workflow | Processes and workflows |
| Strategy | Business, content, financial strategies |
| Relationship | Relationship mappings and circles |

### Organizational Types (internal use)

| Type | Description |
|------|-------------|
| StatusSummary | CurrentPriorities, RecentUpdates (excluded from search) |
| MaterializedView | Dashboards |
| DomainIndex | Domain organization |
| SemanticCluster | Semantic groupings |
| IndexNode | Index structures |

Use `list_entity_types()` for the current complete list with counts.

## Memory Structure

Each entity follows this structure:

```json
{
  "name": "Entity Name",
  "entityType": "Person",
  "observations": [
    {
      "content": "Observation text",
      "timestamp": "2025-01-15T10:30:00Z",
      "source": "claude_desktop",
      "confidence": 0.9,
      "tags": ["tag1", "tag2"]
    }
  ],
  "relationships": [
    {
      "name": "Related Entity",
      "relationship": "relationship_type"
    }
  ],
  "metadata": {
    "temporal_series": true,
    "subtype": "tracking"
  }
}
```

## MCP Tool Parameters

### search_entities(query, limit=10)
Search for entities by name, type, or observation content.
- `query` (str): Search term
- `limit` (int): Maximum results (default: 10)
- Returns: List of entity summaries (5 most recent observations each)

### get_entity(name)
Get full entity details by exact name (case-insensitive).
- `name` (str): Exact entity name
- Returns: Full entity with all observations and relationships

### add_observation(entity_name, content)

Add timestamped observation to existing entity. Auto-saves.

- `entity_name` (str): Entity to update
- `content` (str): Observation text

### delete_observation(entity_name, content_match)

Delete observations matching content substring (case-insensitive). Auto-saves.

- `entity_name` (str): Entity to modify (case-insensitive lookup)
- `content_match` (str): Substring to match in observation content
- Returns: Success status, deleted count, and remaining count

**Example**: `delete_observation("Alex Johnson", "Circle 3")`

### edit_observation(entity_name, index_pos, new_content)

Edit observation at specific index position. Auto-saves.

- `entity_name` (str): Entity to modify (case-insensitive lookup)
- `index_pos` (int): Index of observation to edit (0-based)
- `new_content` (str): New observation content
- Returns: Success status, old/new content preview, and observation count

**Example**: `edit_observation("Alex Johnson", 2, "[February 2026] Circle 2 - Inner Circle")`

### add_entity(name, entity_type, observations=None)
Create new entity. Auto-saves and rebuilds search index.
- `name` (str): Entity name
- `entity_type` (str): Type (Person, Project, etc.)
- `observations` (list): Optional initial observations

### add_relationship(from_entity, to_entity, relationship_type)
Create directional relationship between two entities. Auto-saves.
- `from_entity` (str): Source entity name
- `to_entity` (str): Target entity name
- `relationship_type` (str): Relationship type

### rename_entity(old_name, new_name)

Rename entity and update all relationship references. Auto-saves.

- `old_name` (str): Current entity name (case-insensitive)
- `new_name` (str): Desired new name (must not exist)
- Returns: Success status and count of updated references

**Example**: `rename_entity("James Musilak", "James Musulak")`

### get_relationships(entity_name)
Get all outgoing and incoming relationships for an entity.
- `entity_name` (str): Entity name

### list_entity_types()
Get all entity types with counts, sorted by count descending.

### get_stats()
Get system overview: entity count, type distribution, recent observations.

### save()
Explicit save. Rarely needed since all write operations auto-save.

## Excluded Entities

These entities are excluded from search results (too many observations):
- Recent Updates (327+ observations)
- Current Priorities (300+ observations)
- Search Keywords

Access them directly with `get_entity("Recent Updates")`.

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "Entity not found" | Name doesn't match | Use `search_entities()` to find correct name |
| "Entity already exists" | Duplicate name | Use `add_observation()` instead |
| MCP tool not available | Server not running | Check `.mcp.json` and restart |

## Search Performance

| Search Type | Time |
|-------------|------|
| Exact match | 0.007ms |
| Partial match | 0.12ms |
| Type match | 0.1ms |
| Observation search | 0.12ms |

Index builds automatically on server startup (~200ms for 5,800+ entities).
