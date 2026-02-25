# Matrix Field Patterns

Common patterns for configuring and using Matrix fields in Craft CMS 5+.

## Content Builder Pattern

A single Matrix field that handles all page content.

### Configuration

```
Field: Content builder (contentBuilder)
Entry Types:
  Structure:
    - Section block (sectionBlock) - contains nested contentBuilder
  Content:
    - Content block (contentBlock) - CKEditor rich text
    - Quote block (quoteBlock) - quote, source, link
    - Code block (codeBlock) - code snippet
    - Image block (imageBlock) - asset field
    - Video block (videoBlock) - embed code or asset
```

### Nesting Setup

1. Create the Content builder Matrix field with all entry types
2. Go to Section block entry type
3. Add Content builder field to its field layout
4. Now Section blocks can contain other blocks

### Template Rendering

```twig
{% for block in entry.contentBuilder.all() %}
  {% include "_blocks/#{block.type.handle}.twig" with {
    block: block
  } ignore missing %}
{% endfor %}
```

With eager loading:
```twig
{% set entry = craft.entries()
  .section('pages')
  .slug('about')
  .with([
    'contentBuilder',
    'contentBuilder.image:imageBlock',
    'contentBuilder.contentBuilder', {# nested blocks #}
  ])
  .one() %}
```

## Grid Pattern

A Grid block that contains only Grid Item children.

### Entry Types

```
Grid block (gridBlock)
  - Fields: columns (dropdown), gap (dropdown)
  - Contains: gridBuilder Matrix (only Grid Item entry type)

Grid Item block (gridItemBlock)
  - Fields: span (dropdown), content (CKEditor or nested Matrix)
```

### Template

```twig
{# _blocks/gridBlock.twig #}
<div class="grid grid-cols-{{ block.columns }}" style="gap: {{ block.gap }}">
  {% for item in block.gridBuilder.all() %}
    <div class="col-span-{{ item.span }}">
      {{ item.content }}
    </div>
  {% endfor %}
</div>
```

## Specialized Matrix Fields

Sometimes one Matrix isn't enough.

### Sidebar Content
Limited blocks for sidebar areas:
- Text block
- Image block
- Call to action block

### Hero Options
Specialized hero variations:
- Simple hero (heading, subhead, image)
- Video hero (heading, video embed)
- Carousel hero (multiple slides)

### Configuration

Create separate Matrix fields:
- `sidebarContent` — limited entry types
- `heroOptions` — specialized entry types

Same entry types can appear in multiple Matrix fields.

## View Mode Choices

### Inline-editable blocks (default)
Best for: Content builders, visual page composition
Authors see and arrange blocks in context.

### Cards
Best for: Complex blocks with many fields
Cleaner interface, opens in slideout for editing.

### Element index
Best for: Large datasets, structured data
Table view with sorting, searching, filtering.

## Common Pitfalls

### Infinite Nesting
If Section blocks can contain Section blocks recursively, set reasonable depth limits or authors will create chaos.

### Missing Eager Loading
Always eager load Matrix content and its nested relations:
```twig
.with([
  'contentBuilder',
  'contentBuilder.image:imageBlock',
  'contentBuilder.contentBuilder.image:imageBlock',
])
```

### Wrong Type Checking
```twig
{# WRONG - type is an object #}
{% if block.type == 'text' %}

{# CORRECT - compare handles #}
{% if block.type.handle == 'text' %}
```

### Empty Matrix Queries
```twig
{# Check for content #}
{% if entry.contentBuilder.exists() %}
  {% for block in entry.contentBuilder.all() %}
    ...
  {% endfor %}
{% endif %}
```
