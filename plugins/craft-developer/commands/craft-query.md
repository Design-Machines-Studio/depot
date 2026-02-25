---
name: craft-query
description: Build complex Craft CMS element queries
---

# Query Builder

Help construct Craft CMS element queries for entries, assets, categories, users, and Matrix content.

## Process

1. **Understand the goal** — What data does the user need?
2. **Choose the element type** — Entries, assets, categories, users?
3. **Build the query** — Add parameters step by step
4. **Optimize** — Add eager loading, consider caching
5. **Test** — Verify the query returns expected results

## Query Building Blocks

### Basic Structure
```twig
{% set results = craft.entries()
  .section('blog')
  .orderBy('postDate DESC')
  .limit(10)
  .all() %}
```

### Execution Methods
- `.all()` — Array of all results
- `.one()` — Single element or null
- `.exists()` — Boolean check
- `.count()` — Integer count
- `.ids()` — Array of IDs only

### Common Parameters
- `.section()` / `.volume()` / `.group()` — Filter by container
- `.type()` — Filter by entry type
- `.status()` — Include drafts, disabled, etc.
- `.site()` — Multi-site queries
- `.relatedTo()` — Relational queries
- `.search()` — Full-text search
- `.orderBy()` — Sort results
- `.limit()` / `.offset()` — Pagination

### Relational Queries
```twig
{# Find entries related to a category #}
{% set posts = craft.entries()
  .section('blog')
  .relatedTo(category)
  .all() %}

{# Direction matters for some queries #}
{% set products = craft.entries()
  .relatedTo({
    targetElement: category,
    field: 'productCategories'
  })
  .all() %}
```

### Eager Loading
```twig
{% set posts = craft.entries()
  .section('blog')
  .with([
    'featureImage',
    'author',
    'contentBlocks.image',
  ])
  .all() %}
```

## MCP Integration

If the Craft MCP server is available:

- `list_sections` — See available sections
- `list_fields` — Understand field structure
- `run_query` — Test raw SQL queries
- `explain_query` — Analyze performance

## Output

Provide working Twig code with explanations. Include performance considerations and alternatives where relevant.
