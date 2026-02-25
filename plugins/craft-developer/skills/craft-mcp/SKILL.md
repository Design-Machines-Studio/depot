---
name: craft-mcp
description: How to effectively use the Craft CMS MCP server tools. Use when working with a Craft project that has the craft-mcp plugin installed. Covers tool selection, common workflows, and interpreting results.
---

# Craft MCP Server Guide

The Craft MCP plugin provides 50+ tools for direct access to your Craft installation. This guide helps you use them effectively.

## Tool Categories

### Content Tools
Access and manage content directly.

| Tool | Use For |
|------|---------|
| `list_entries` | Query entries with filtering |
| `get_entry` | Full entry details including custom fields |
| `create_entry` | Create new entries |
| `update_entry` | Modify existing entries |
| `list_assets` | Browse assets by volume/folder |
| `get_asset` | Asset details and metadata |
| `list_categories` | Query categories by group |
| `list_users` | Query users by group |
| `list_globals` | All global sets with values |

### Schema Tools
Understand the content architecture.

| Tool | Use For |
|------|---------|
| `list_sections` | All sections with entry types |
| `list_fields` | All fields with types and settings |
| `list_volumes` | Asset volume configurations |
| `list_entry_types` | Entry type configurations |
| `list_plugins` | Installed plugins and versions |

### System Tools
Configuration and system state.

| Tool | Use For |
|------|---------|
| `get_system_info` | Craft/PHP versions, environment |
| `get_config` | Configuration values |
| `read_logs` | Application log entries |
| `get_last_error` | Most recent error |
| `clear_caches` | Clear specific or all caches |
| `list_routes` | Registered routes |

### Database Tools
Direct database access.

| Tool | Use For |
|------|---------|
| `get_database_info` | Connection details |
| `get_database_schema` | Full schema inspection |
| `get_table_counts` | Row counts for tables |
| `run_query` | Execute SELECT queries |
| `explain_query` | Query performance analysis |

### Debugging Tools
Diagnose issues.

| Tool | Use For |
|------|---------|
| `get_queue_jobs` | Queue job status |
| `get_project_config_diff` | Pending config changes |
| `get_deprecations` | Deprecated code warnings |
| `get_environment` | Environment info (safe) |
| `tinker` | Execute PHP code |

### GraphQL Tools
GraphQL API access.

| Tool | Use For |
|------|---------|
| `list_graphql_schemas` | Available schemas |
| `get_graphql_schema` | Schema details and SDL |
| `execute_graphql` | Run queries/mutations |

## Common Workflows

### Content Model Audit

Understand an existing Craft installation:

```
1. get_system_info → Craft version, environment
2. list_sections → Sections and entry types
3. list_fields → Field architecture
4. list_entry_types → Entry type details
5. list_volumes → Asset configuration
```

### Debugging an Issue

Systematic debugging workflow:

```
1. get_last_error → Most recent error
2. read_logs → Search for related errors
3. get_config → Verify configuration
4. get_deprecations → Check for deprecated code
5. run_query / explain_query → Test database queries
```

### Template Development

Understand structure for template queries:

```
1. list_sections → Find section handles
2. list_fields → Find field handles
3. list_entry_types → Understand entry types
4. get_entry → Inspect actual content
5. run_query → Test raw queries
```

### Migration Planning

Assess before migration:

```
1. get_system_info → Current versions
2. list_plugins → Plugin compatibility
3. get_deprecations → Code to update
4. get_database_schema → Schema complexity
5. get_project_config_diff → Pending changes
```

### Performance Analysis

Diagnose performance issues:

```
1. explain_query → Analyze slow queries
2. get_queue_jobs → Check queue backlog
3. get_table_counts → Database size
4. read_logs → Error patterns
```

## Tool Selection Guide

### "I need to understand the content model"

```
list_sections + list_fields + list_entry_types
```

### "Something is broken"

```
get_last_error + read_logs + get_deprecations
```

### "Query isn't returning expected results"

```
run_query + explain_query + list_fields
```

### "I need to verify configuration"

```
get_config + get_environment + list_plugins
```

### "I need to inspect specific content"

```
list_entries + get_entry + list_assets
```

### "I need to test a GraphQL query"

```
list_graphql_schemas + execute_graphql
```

## Interpreting Results

### Section Output

```json
{
  "handle": "blog",
  "type": "channel",
  "entryTypes": [
    { "handle": "article", "name": "Article" }
  ]
}
```

- `handle` — Use in queries: `.section('blog')`
- `type` — Determines behavior (single/channel/structure)
- `entryTypes` — Available entry types in this section

### Field Output

```json
{
  "handle": "featureImage",
  "type": "craft\\fields\\Assets",
  "settings": {
    "sources": ["volume:images"],
    "limit": 1
  }
}
```

- `handle` — Use in templates: `entry.featureImage`
- `type` — Field class, indicates capabilities
- `settings` — Configuration affecting behavior

### Entry Type Output

```json
{
  "handle": "article",
  "name": "Article",
  "fieldLayout": {
    "tabs": [
      {
        "name": "Content",
        "fields": ["body", "featureImage", "categories"]
      }
    ]
  }
}
```

- `handle` — Use in queries: `.type('article')`
- `fieldLayout` — Fields available in this entry type

## Best Practices

### Start Broad, Then Narrow

Begin with overview tools:
```
get_system_info → list_sections → list_fields
```

Then drill into specifics:
```
get_entry → specific content inspection
```

### Combine Tools for Context

Don't rely on single tools. Combine for full picture:
```
list_sections + list_entry_types = understand content architecture
get_last_error + read_logs = full error context
```

### Use run_query Carefully

`run_query` is powerful but:
- Only SELECT queries (read-only)
- Use for verification, not exploration
- Prefer Craft's API tools when possible

### Tinker for Advanced Debugging

`tinker` executes PHP in Craft context:
```php
Craft::$app->sections->getAllSections()
```

Powerful but use carefully. Good for:
- Testing Craft API calls
- Inspecting objects
- Quick fixes

## MCP in Agents and Commands

### Content Modeler Agent

Use MCP to understand current state before making recommendations:
```
list_sections → existing structure
list_fields → available fields
list_entry_types → current entry types
```

### Debugger Agent

Use MCP for systematic diagnosis:
```
get_last_error → start point
read_logs → context
get_config → verify settings
run_query → test fixes
```

### Template Builder Agent

Use MCP to understand what's available:
```
list_sections → query targets
list_fields → available data
get_entry → example content
```
