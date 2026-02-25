---
name: craft-5-migration
description: Patterns and breaking changes for Craft CMS 4 to 5 migrations. Use when upgrading Craft versions, fixing Craft 5 compatibility issues, or updating code for Craft 5 patterns. Covers Matrix changes, empty array behavior, GraphQL updates, and entrification.
---

# Craft 4 to 5 Migration Guide

Key changes, breaking patterns, and migration strategies for Craft 5.

## Major Conceptual Changes

### Matrix: Blocks → Entries

Matrix fields no longer contain "blocks." They contain nested entries.

**Terminology:**
- Craft 4: Matrix blocks, block types
- Craft 5: Nested entries, entry types

**Architecture:**
- Entry types exist independently (global pool)
- Same entry type can be used in multiple Matrix fields
- Entry types can be used in sections OR Matrix fields

**New capability:** Nesting blocks inside other blocks.

### Entrification

Everything is becoming entries:

- Matrix blocks → Nested entries
- Categories → Entry types in sections (recommended)
- Tags → Entry types in sections (recommended)
- Globals → Singles (recommended)

This simplifies the system: one pattern for everything.

## Breaking Changes

### Empty Array Behavior

**Critical change:**

```twig
{# Craft 4: Empty array returns ALL results #}
{% set entries = craft.entries()
  .relatedTo([])
  .all() %}

{# Craft 5: Empty array returns NO results #}
```

**Fix:**
```twig
{% set entries = craft.entries()
  .relatedTo(categoryIds|length ? categoryIds : null)
  .all() %}
```

This is the most common migration bug.

### GraphQL Type Names

**Craft 4:**
```graphql
... on news_article_Entry { }
```

**Craft 5:**
```graphql
... on article_Entry { }
```

Section prefix removed from entry type names.

### GraphQL Matrix Mutations

**Craft 4:**
```graphql
ingredients: {
  blocks: [...]
}
```

**Craft 5:**
```graphql
ingredients: {
  entries: [...]
}
```

### Element Query Caching

Query caching behavior changed. Review uses of:
- `.cache()`
- `{% cache %}` tags with queries inside

## Template Updates

### Matrix Loop

**Craft 4:**
```twig
{% for block in entry.contentBuilder.all() %}
  {% switch block.type %}
    {% case 'text' %}
```

**Craft 5:**
```twig
{% for block in entry.contentBuilder.all() %}
  {% switch block.type.handle %}
    {% case 'text' %}
```

Note: `block.type` is now an object. Use `block.type.handle` for comparisons.

### Eager Loading

**Craft 4:**
```twig
{% set entries = craft.entries()
  .with(['contentBuilder'])
  .all() %}
```

**Craft 5:** Same, but new lazy eager loading option:
```twig
{% for entry in entries %}
  {% set image = entry.featureImage.eagerly().one() %}
{% endfor %}
```

### Relational Queries

**Check empty arrays:**
```twig
{# Before passing to relatedTo #}
{% if categoryIds|length %}
  {% set entries = craft.entries()
    .relatedTo(categoryIds)
    .all() %}
{% else %}
  {% set entries = craft.entries().all() %}
{% endif %}
```

## Migration Checklist

### Before Migration

- [ ] Backup database
- [ ] Document current content model
- [ ] Check plugin compatibility
- [ ] Review deprecation warnings
- [ ] Test in staging environment

### Code Updates

- [ ] Fix empty array relatedTo calls
- [ ] Update `block.type` to `block.type.handle`
- [ ] Update GraphQL type names
- [ ] Update GraphQL Matrix mutations
- [ ] Review query caching

### After Migration

- [ ] Run all database migrations
- [ ] Apply project config
- [ ] Clear all caches
- [ ] Test all templates
- [ ] Verify GraphQL queries
- [ ] Check control panel functionality

## Plugin Compatibility

### Check Before Migration

Use MCP if available:
```
list_plugins → versions and status
```

Or check manually:
- Plugin has Craft 5 compatible version
- Plugin uses correct namespaces
- Plugin follows Craft 5 patterns

### Common Plugin Issues

- Matrix-related plugins may need updates
- GraphQL plugins may have type name changes
- Field type plugins may need migration

## Entrification Strategy

### Categories → Entries

**Create replacement:**
1. Create a Structure section "Categories"
2. Create "Category" entry type
3. Add necessary fields
4. Create Entries field limited to Categories section

**Migrate content:**
1. Export categories
2. Import as entries
3. Update relational fields
4. Update templates

### Tags → Entries

**Create replacement:**
1. Create a Channel section "Tags"
2. Create "Tag" entry type
3. Create Entries field limited to Tags section

### Globals → Singles

**Create replacement:**
1. Create Singles for each global set
2. Move field configurations
3. Update templates: `globalSet.field` → `entry.field`

## MCP Migration Tools

If Craft MCP is installed:

### Assessment
```
get_system_info → Current versions
list_plugins → Plugin compatibility
get_deprecations → Code to update
```

### Verification
```
list_sections → Verify structure
list_fields → Verify fields migrated
list_entry_types → Verify entry types
```

### Debugging
```
get_last_error → Migration errors
read_logs → Full error context
run_query → Verify data integrity
```

## Common Migration Issues

### "Entry type not found"

- Check entry type handle in template matches actual handle
- Remember: GraphQL types changed naming

### "Related entries returning nothing"

- Check for empty array being passed to relatedTo
- Add length check before passing arrays

### "Matrix content missing"

- Blocks migrated to entries automatically
- Check eager loading includes Matrix field
- Verify entry type handles match template

### "GraphQL query fails"

- Update type names (remove section prefix)
- Update mutations (blocks → entries)
- Check schema permissions

## Performance Improvements

Craft 5 offers performance opportunities:

### Lazy Eager Loading

```twig
{% for post in posts %}
  {% set image = post.featureImage.eagerly().one() %}
{% endfor %}
```

Cleaner than upfront `.with()` for complex cases.

### Improved Query Caching

Review and optimize cache strategies with new caching behavior.

### Entry Type Independence

Entry types in global pool means:
- Less duplication — define once, use in multiple sections and Matrix fields
- Better organization — entry types are first-class objects, not buried in section config
- Easier maintenance — change an entry type's fields and it updates everywhere
- Cross-pollination — a "Quote" block in Matrix can also be a standalone entry in a section

### Conditional Field Layouts

Craft 5 supports showing/hiding field layout tabs and fields based on conditions:
- Reduces the need for many specialized entry types
- One entry type with conditional fields replaces several similar types
- Conditions can check custom field values, user group, status, and more

### Matrix Entry Type Groups (5.8+)

The Matrix field's "Add" button can organize entry types into groups:
- Helps authors find the right block type quickly
- Groups are configured in the Matrix field settings
- Useful when a content builder has 10+ entry types
