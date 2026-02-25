---
name: craft-migrate
description: Plan and execute Craft CMS migrations (especially Craft 4 to 5)
---

# Migration Planner

Help plan and execute Craft CMS migrations, especially Craft 4 to Craft 5 upgrades.

## Migration Types

### Craft 4 → Craft 5

Major changes to understand:

**Matrix Fields**
- "Blocks" are now "nested entries"
- Entry types exist independently
- Nesting is now possible
- GraphQL types changed

**Empty Array Behavior**
- Craft 4: Empty `relatedTo` arrays return all results
- Craft 5: Empty arrays return NO results
- Fix: Check array length before passing

**GraphQL Type Names**
- Craft 4: `news_article_Entry`
- Craft 5: `article_Entry` (section prefix removed)

**Categories/Tags/Globals**
- Being phased out in favor of entries
- Build as entry types in sections instead

### Content Model Changes

When restructuring an existing content model:

1. **Audit current state** — Document sections, fields, entry types
2. **Identify changes** — What's being added, removed, restructured?
3. **Plan data migration** — How will existing content transform?
4. **Test in staging** — Never migrate production first
5. **Execute with backups** — Always have a rollback plan

## MCP Integration

If the Craft MCP server is available:

- `get_system_info` — Check Craft/PHP versions
- `list_sections` — Audit current sections
- `list_fields` — Audit current fields
- `list_plugins` — Check plugin compatibility
- `get_deprecations` — Find deprecated code
- `get_project_config_diff` — See pending changes
- `create_backup` — Backup before changes
- `list_backups` — Verify backups exist

## Process

1. **Assess** — Understand current state and target state
2. **Document** — Create migration checklist
3. **Test** — Run migration in development/staging
4. **Fix** — Address issues found in testing
5. **Execute** — Run migration on production
6. **Verify** — Confirm everything works

## Output

Provide clear migration plans with step-by-step instructions. Highlight breaking changes and required code updates. Include rollback strategies.
