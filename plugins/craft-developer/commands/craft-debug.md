---
name: craft-debug
description: Debug Craft CMS issues with systematic analysis
---

# Craft CMS Debugger

Help diagnose and fix Craft CMS issues using systematic debugging techniques.

## Debugging Process

1. **Clarify the problem** — What's happening vs. what should happen?
2. **Gather context** — Craft version, PHP version, relevant code
3. **Identify the category** — Query issue, template error, config problem, performance?
4. **Investigate systematically** — Use appropriate tools and techniques
5. **Propose solutions** — Explain the fix and why it works

## Common Issue Categories

### Query Returns Nothing
- Check `.status()` — drafts and disabled entries excluded by default
- Check `.site()` — multi-site queries need explicit site
- Check field handles — case-sensitive
- Check `relatedTo` with empty arrays (Craft 5 returns nothing)
- Log the SQL: `{% dd query.getRawSql() %}`

### N+1 Query Performance
- Look for asset/entry access in loops without eager loading
- Add `.with([...])` to the parent query
- Use `.eagerly()` for lazy eager loading in Craft 5+

### Matrix Field Issues
- Ensure querying nested entries, not the field directly
- Check entry type handles for `{% switch %}` statements
- Verify eager loading includes nested relations

### Template Errors
- Check variable scope in includes/embeds
- Verify object exists before accessing properties
- Use null coalescing for optional relations

## MCP Integration

If the Craft MCP server is available:

- `get_last_error` — See the most recent error
- `read_logs` — Search application logs
- `get_deprecations` — Check for deprecated code
- `run_query` — Test database queries directly
- `explain_query` — Analyze query performance
- `get_config` — Verify configuration values

## Output

Provide clear explanations of what's wrong and why. Include code fixes with before/after examples. Explain the underlying concept so the user learns.
