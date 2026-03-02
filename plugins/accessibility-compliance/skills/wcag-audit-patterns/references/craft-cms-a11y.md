# Craft CMS + Twig Accessibility Patterns

Accessibility patterns specific to Craft CMS projects with Twig templates.

---

## Twig Template Accessibility

### Page Layout

Every Craft CMS layout template should include landmarks and skip links:

```twig
{# _layouts/base.twig #}
<!DOCTYPE html>
<html lang="{{ currentSite.language }}">
<head>
  <title>{{ title ?? entry.title ?? siteName }} — {{ siteName }}</title>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body class="{{ bodyClass ?? '' }}">
  <a href="#main" class="skip-link">Skip to main content</a>

  <header>
    <nav aria-label="Primary">
      {% include '_partials/navigation' %}
    </nav>
  </header>

  <main id="main">
    {% block content %}{% endblock %}
  </main>

  <footer>
    {% include '_partials/footer' %}
  </footer>
</body>
</html>
```

### Dynamic Heading Levels

Craft Matrix blocks and entries are often nested at different depths. Pass the heading level:

```twig
{# _partials/content-blocks.twig #}
{% set headingLevel = headingLevel ?? 2 %}

{% for block in entry.contentBlocks.all() %}
  {% if block.type.handle == 'textBlock' %}
    <{{ 'h' ~ headingLevel }}>{{ block.heading }}</{{ 'h' ~ headingLevel }}>
    {{ block.body }}

  {% elseif block.type.handle == 'cardGrid' %}
    <{{ 'h' ~ headingLevel }}>{{ block.sectionTitle }}</{{ 'h' ~ headingLevel }}>
    <div class="grid">
      {% for card in block.cards.all() %}
        {% include '_partials/card' with {
          headingLevel: headingLevel + 1
        } %}
      {% endfor %}
    </div>
  {% endif %}
{% endfor %}
```

### Image Accessibility

Always use the asset's alt text field:

```twig
{# CORRECT: Uses CMS alt text #}
{% set image = entry.heroImage.one() %}
{% if image %}
  <img src="{{ image.url }}"
       alt="{{ image.alt ?? image.title }}"
       width="{{ image.width }}"
       height="{{ image.height }}"
       loading="lazy">
{% endif %}

{# CORRECT: Decorative image explicitly marked #}
{% set bgImage = entry.backgroundImage.one() %}
{% if bgImage %}
  <img src="{{ bgImage.url }}" alt="" role="presentation"
       width="{{ bgImage.width }}" height="{{ bgImage.height }}">
{% endif %}

{# WRONG: Missing alt or using filename #}
<img src="{{ image.url }}">
<img src="{{ image.url }}" alt="{{ image.filename }}">
```

**CMS configuration requirement:** The Image asset field should have an "Alternative Text" field in the asset volume's field layout. Make this field required for informative images.

### Image Transforms

When using Craft's image transforms, alt text is still available:

```twig
{% set transform = { width: 800, height: 450, mode: 'crop' } %}
{% set image = entry.heroImage.one() %}
{% if image %}
  <img src="{{ image.getUrl(transform) }}"
       alt="{{ image.alt ?? image.title }}"
       width="800" height="450"
       loading="lazy">
{% endif %}
```

### Navigation with Multiple Nav Elements

```twig
{# Primary navigation #}
<nav aria-label="Primary">
  <ul>
    {% nav node in craft.navigation.nodes('primaryNav').all() %}
      <li>
        <a href="{{ node.url }}"
           {% if node.isCurrent %} aria-current="page" {% endif %}>
          {{ node.title }}
        </a>
      </li>
    {% endnav %}
  </ul>
</nav>

{# Breadcrumb navigation #}
<nav aria-label="Breadcrumb">
  <ol class="breadcrumbs">
    <li><a href="/">Home</a></li>
    {% for crumb in breadcrumbs %}
      <li>
        {% if loop.last %}
          <span aria-current="page">{{ crumb.title }}</span>
        {% else %}
          <a href="{{ crumb.url }}">{{ crumb.title }}</a>
        {% endif %}
      </li>
    {% endfor %}
  </ol>
</nav>

{# Footer navigation #}
<nav aria-label="Footer">
  ...
</nav>
```

### Rich Text / Redactor / CKEditor Output

Rich text fields output HTML that may not follow heading hierarchy:

```twig
{# The body field might contain h2, h3 from the editor #}
{{ entry.body }}

{# Wrap in .prose for consistent styling #}
<div class="prose">
  {{ entry.body }}
</div>
```

**CMS configuration:** Configure the rich text editor to:
- Limit available heading levels based on context
- Require alt text when inserting images
- Disallow empty links

### Link Text from Entries

```twig
{# WRONG: Generic link text #}
{% for entry in craft.entries.section('news').limit(5).all() %}
  <div>
    <h3>{{ entry.title }}</h3>
    <p>{{ entry.summary }}</p>
    <a href="{{ entry.url }}">Read more</a>  {# Bad: "Read more" is meaningless #}
  </div>
{% endfor %}

{# RIGHT: Descriptive link text #}
{% for entry in craft.entries.section('news').limit(5).all() %}
  <article>
    <h3><a href="{{ entry.url }}">{{ entry.title }}</a></h3>
    <p>{{ entry.summary }}</p>
  </article>
{% endfor %}

{# ALSO RIGHT: Visually hidden context #}
{% for entry in craft.entries.section('news').limit(5).all() %}
  <div>
    <h3>{{ entry.title }}</h3>
    <p>{{ entry.summary }}</p>
    <a href="{{ entry.url }}">
      Read more<span class="visually-hidden"> about {{ entry.title }}</span>
    </a>
  </div>
{% endfor %}
```

---

## Craft CMS Configuration for Accessibility

### Asset Fields

1. **Add an "Alt Text" plain text field** to every image asset volume
2. **Make it required** for informative images
3. **Add instructions** in the field: "Describe the image content. Leave empty only for decorative images."

### Entry Types

1. **SEO/Meta fields** should include page title override for `<title>` element
2. **Content builder** blocks should accept heading level context

### Templates

1. **Set `lang` attribute** from `currentSite.language`
2. **Use `siteName`** in `<title>` for consistent naming
3. **Create a reusable `_partials/a11y-image.twig`** that handles alt text logic

```twig
{# _partials/a11y-image.twig #}
{# Expects: image (Asset), decorative (bool, default false), transform (optional) #}
{% set decorative = decorative ?? false %}
{% if image %}
  {% set src = transform is defined ? image.getUrl(transform) : image.url %}
  {% if decorative %}
    <img src="{{ src }}" alt="" role="presentation"
         width="{{ image.width }}" height="{{ image.height }}" loading="lazy">
  {% else %}
    <img src="{{ src }}" alt="{{ image.alt ?? image.title }}"
         width="{{ image.width }}" height="{{ image.height }}" loading="lazy">
  {% endif %}
{% endif %}
```

---

## Form Accessibility in Craft

### Freeform / Form Builder

When using Craft form plugins, verify:

- [ ] Every field has a visible `<label>`
- [ ] Required fields are marked with `aria-required="true"` and visual indicator
- [ ] Error messages are associated with fields via `aria-describedby`
- [ ] Success message uses `role="status"`
- [ ] Error summary uses `role="alert"`
- [ ] `<fieldset>` and `<legend>` group related fields (radio groups, checkbox groups)
- [ ] Submit button has descriptive text (not just "Submit")

### Guest Entries / Custom Forms

```twig
<form method="post">
  {{ csrfInput() }}
  {{ actionInput('guest-entries/save') }}

  <div class="stack">
    <div class="stack-compact">
      <label for="name">Full Name <span aria-hidden="true">*</span></label>
      <input type="text" id="name" name="fields[name]"
             required aria-required="true"
             {% if errors.name is defined %}
               aria-invalid="true"
               aria-describedby="name-error"
             {% endif %}>
      {% if errors.name is defined %}
        <p id="name-error" role="alert" class="text-sm text-red-600">
          {{ errors.name | first }}
        </p>
      {% endif %}
    </div>

    <button type="submit" class="button button--accent">
      Submit Entry
    </button>
  </div>
</form>
```

---

## Twig Accessibility Checklist

When writing or reviewing Twig templates:

- [ ] `<html lang="{{ currentSite.language }}">` is set
- [ ] `<title>` is descriptive and unique per page
- [ ] Skip link exists: `<a href="#main" class="skip-link">`
- [ ] `<main id="main">` landmark present
- [ ] Multiple `<nav>` elements have unique `aria-label`
- [ ] Heading hierarchy is logical (no skipped levels)
- [ ] Matrix blocks accept `headingLevel` parameter
- [ ] All `<img>` tags use asset alt text field
- [ ] Decorative images use `alt="" role="presentation"`
- [ ] Links have descriptive text (not "Read more" or "Click here")
- [ ] `aria-current="page"` on active navigation items
- [ ] Form fields have visible `<label>` elements
- [ ] Error messages use `role="alert"` and `aria-describedby`
- [ ] Rich text output is wrapped in `.prose` for consistent styling
- [ ] `|raw` filter is never used without prior sanitization
