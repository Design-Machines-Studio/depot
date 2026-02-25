# CKEditor Patterns

Common patterns for configuring and using CKEditor in Craft CMS.

## Configuration Approach

### Multiple Configurations

Create different configs for different contexts:

**Simple**
- Bold, italic, links
- Lists (bulleted, numbered)
- Basic for short content fields

**Full**
- Everything in Simple, plus:
- Headings (H2, H3, H4)
- Block quotes
- Horizontal rules
- Tables
- Entry embeds

**Minimal**
- Bold, italic, links only
- For single-line formatted text

### Toolbar Groups

Organize buttons logically:
```
Bold, Italic | Link | BulletedList, NumberedList | Heading | BlockQuote
```

Use separators (`|`) to group related functions.

## Embedding Entry Types

### How It Works

1. Create entry types for embeddable content (Image block, Quote block, etc.)
2. In CKEditor config, enable "Create entries" and select allowed entry types
3. Authors insert via "+ " button or toolbar

### Good Embed Candidates

- Image with caption
- Code snippet
- Pull quote
- Call to action
- Video embed
- Info box / callout

### Poor Embed Candidates

- Section containers
- Navigation elements
- Complex nested structures

## CKEditor vs Matrix Decision

### Use CKEditor When

**Document-style content**
```
Paragraph
Paragraph
[Embedded quote]
Paragraph
[Embedded image]
Paragraph
```

**Flowing narrative**
Authors think in documents, not blocks.

**Inline positioning matters**
Embed sits exactly where cursor is placed.

**Simpler sites**
CKEditor + embeds may be sufficient without Matrix.

### Use Matrix When

**Layout-driven content**
```
[Section: Hero]
[Section: Features Grid]
  [Feature Card]
  [Feature Card]
  [Feature Card]
[Section: Testimonials]
```

**Visual page structure**
Authors drag and arrange distinct regions.

**Tight design control**
Each block has specific templates.

### Use Both When

**Hybrid approach:**
- Matrix for page structure (Section blocks)
- CKEditor inside Content blocks for flowing text

```
[Section block]
  [Content block] ← CKEditor with embeds here
  [Image block]
[Section block]
  [Content block] ← CKEditor with embeds here
```

## Style Presets

### Built-in Styles

Define reusable formatting in CKEditor config:

```json
{
  "styles": [
    { "name": "Lead paragraph", "element": "p", "classes": ["lead"] },
    { "name": "Highlight", "element": "span", "classes": ["highlight"] },
    { "name": "Caption", "element": "p", "classes": ["caption"] }
  ]
}
```

Authors select from dropdown, classes applied automatically.

### When to Use Styles

- Consistent design-system formatting
- Variations that don't warrant separate blocks
- Semantic markup needs

## Template Rendering

### Basic Output

```twig
{{ entry.body }}
```

CKEditor outputs HTML, so no additional processing needed.

### With Markdown Fields

If using Markdown instead:
```twig
{{ entry.body|md }}
```

### Embedded Entries

Embedded entries render automatically, but you can customize:

```twig
{# In your CKEditor field's "Entry Template" setting #}
{% switch entry.type.handle %}
  {% case 'imageBlock' %}
    <figure>
      {{ entry.image.one().getImg() }}
      <figcaption>{{ entry.caption }}</figcaption>
    </figure>
  {% case 'quoteBlock' %}
    <blockquote>
      {{ entry.quote }}
      <cite>{{ entry.source }}</cite>
    </blockquote>
{% endswitch %}
```

## Performance Considerations

### Eager Loading Embedded Entries

CKEditor embedded entries need eager loading:

```twig
{% set entry = craft.entries()
  .section('blog')
  .slug('my-post')
  .with([
    'body', {# The CKEditor field #}
  ])
  .one() %}
```

Note: Craft automatically eager loads embedded entries when you access the CKEditor field.

### Large Content Fields

For very long content, consider:
- Pagination or "read more" patterns
- Lazy loading images
- Content chunking in templates

## Common Issues

### Embedded Entry Not Rendering

1. Check entry type is enabled in CKEditor config
2. Verify entry is published (not draft/disabled)
3. Check template handles embedded entry type

### Styles Not Applying

1. Verify style classes exist in your CSS
2. Check style definition in CKEditor config
3. Clear Craft caches

### Toolbar Button Missing

1. Check button is in toolbar config
2. Verify required plugin is installed
3. Some buttons need specific config options enabled
