# Code Style Guidelines

## CUBE CSS Layer Mapping

Live Wires uses [CUBE CSS](https://cube.fyi/) by Andy Bell. Every class and rule belongs in a specific layer:

| CUBE Layer | Live Wires Layer | Directory | Naming Pattern |
|------------|-----------------|-----------|----------------|
| -- | `tokens` | `1_tokens/` | CSS custom properties |
| -- | `reset` | `3_generic/` | Browser normalization |
| -- | `base` | `4_elements/` | Semantic element defaults |
| Composition | `layouts` | `5_layouts/` | `.{layout}` / `.{layout}-{variant}` (single-dash) |
| Block | `components` | `6_components/` | `.{component}` / `.{component}--{variant}` (double-dash) |
| Utility | `utilities` | `7_utilities/` | `.{abbrev}-{value}` |
| Exception | *(inline via `data-*`)* | -- | `[data-state="value"]` / `[data-attr]` |

Most styling is handled by defaults and utilities. Components should be minimal.

## State with Data Attributes

State changes use `data-*` attributes, NOT CSS classes. This is the Exception layer in CUBE CSS.

```css
/* WRONG: state as CSS classes */
.nav-link.active { }
.nav-link.is-active { }
.button.disabled { }

/* RIGHT: data attributes with CSS nesting */
.nav-link {
  &[data-state="active"] {
    color: var(--color-accent);
  }
}
.button {
  &[data-state="disabled"] {
    opacity: 0.5;
    pointer-events: none;
  }
}
```

**Named states** (multi-value): `[data-state="active"]`, `[data-state="loading"]`, `[data-state="error"]`

**Boolean states** (on/off): `[data-open]`, `[data-active]`, `[data-expanded]`

```html
<nav class="offcanvas" data-open>...</nav>
<a href="/" class="nav-link" data-state="active">Home</a>
```

**JavaScript:** Use `element.dataset.state = 'active'` or `element.toggleAttribute('data-open')`.

## Class Order

Order classes from general to specific:

1. Layout/composition classes
2. Block/component classes
3. Variant modifiers
4. Utility classes

```html
<!-- Layout -> Block -> Variant -> Utilities -->
<section class="stack box callout callout--featured scheme-warm mt-4">
```

## HTML Attribute Order

For consistency, order attributes as:

1. `class`
2. `id`
3. `data-*`
4. `src`, `href`, `for`
5. `type`, `name`, `value`
6. `aria-*`, `role`

```html
<button class="button button--red" id="delete-btn" data-state="disabled" type="button" aria-label="Delete item">
  Delete
</button>
```

## Avoid Inline Styles

Always check if a utility class exists before adding inline styles. Live Wires has comprehensive utilities:

```html
<!-- BAD: inline styles -->
<div style="display: flex; align-items: center; justify-content: center;">

<!-- GOOD: utility classes -->
<div class="flex items-center justify-center">
```

## Use Scheme Classes Over bg-* + text-*

Scheme classes set both background AND text color together:

```html
<!-- BAD: separate bg and text classes -->
<div class="bg-black text-white">
<div class="bg-grey-200 text-black">

<!-- GOOD: scheme handles both -->
<div class="scheme-black">
<div class="scheme-grey-200">
<div class="scheme-subtle">
<div class="scheme-dark">
<div class="scheme-white">
<div class="scheme-accent">
```

## Use Box Classes for Padding

When you need consistent box padding, use `box` variants instead of `p-*` utilities:

```html
<!-- BAD: manual padding -->
<div class="p-4">

<!-- GOOD: semantic box padding -->
<div class="box">           <!-- Default padding -->
<div class="box box-tight"> <!-- Smaller padding -->
<div class="box box-loose"> <!-- Larger padding -->
```

## Keep Markup Minimal

Avoid unnecessary wrapper divs. Let layout primitives and utilities do the work:

```html
<!-- BAD: too many wrappers -->
<div class="box bg-subtle">
  <figure class="py-4">
    <div class="bg-white p-4" style="display: flex; align-items: center;">
      <div>
        <img src="..." />
      </div>
    </div>
  </figure>
</div>

<!-- GOOD: minimal, clean markup -->
<figure class="box scheme-white border">
  <img src="..." />
</figure>
```

## Simplify Before Adding

Before adding classes or elements, ask:

- Does a layout primitive already handle this?
- Can I combine classes instead of nesting divs?
- Is this wrapper actually necessary?
- Would a scheme class replace multiple color classes?

## Placeholder Images

Use placehold.co for all placeholder images:

```html
<!-- Basic placeholder -->
<img src="https://placehold.co/800x600" alt="Placeholder" />

<!-- With custom colors (background/text) -->
<img src="https://placehold.co/600x400/e5e5e5/888888?text=Logo" alt="Logo placeholder" />

<!-- Common patterns -->
<img src="https://placehold.co/800x800/e5e5e5/888888?text=Logomark" />  <!-- Square -->
<img src="https://placehold.co/600x200/e5e5e5/1a1a1a?text=Logo" />      <!-- Horizontal -->
<img src="https://placehold.co/120x120/1a1a1a/ffffff?text=Logo" />      <!-- Avatar dark -->
<img src="https://placehold.co/120x120/f5f5f5/1a1a1a?text=Logo" />      <!-- Avatar light -->
<img src="https://placehold.co/1920x1080" />                             <!-- Hero/full-width -->
```

Format: `https://placehold.co/{width}x{height}/{bg-color}/{text-color}?text={label}`

## Typography Triplet

When setting `font-size` with a `--text-*` token in CSS, always include the matching line-height and tracking:

```css
.component-title {
  font-size: var(--text-2xl);
  line-height: var(--line-height-2xl);
  letter-spacing: var(--tracking-2xl);
}
```

The suffixes match across all three scales (`xs` through `9xl`). If you only need to set font size in HTML, use the `.text-*` utility class instead -- it bundles all three properties.

## Prefer Token Variables Over Custom Properties

Use existing token variables directly in component CSS:

```css
/* BAD: unnecessary intermediary variables */
.card {
  --card-bg: var(--color-subtle);
  --card-text: var(--color-fg);
  background: var(--card-bg);
  color: var(--card-text);
}

/* GOOD: use tokens directly */
.card {
  background: var(--color-subtle);
  color: var(--color-fg);
}
```

Create component custom properties only when needed for scheme overrides or external theming.

## Development Tools

Body classes for prototyping and QA:

- `show-baseline` — baseline grid overlay (vertical rhythm check)
- `show-columns-2`, `show-columns-3`, `show-columns-4` — column grid overlays
- `redact` — placeholder text rendering (shows type hierarchy without readable content)
- `dark-mode` — forces dark mode regardless of system preference

**Design toolbar:** Press `T` to show/hide. All settings persist in localStorage across page loads and navigation. Source: `src/js/prototyping.js`.

## Adding New Features

All new CSS must live inside the correct `@layer` block and be imported in `src/css/main.css`.

| Feature type | Directory | Layer wrapper |
|---|---|---|
| Utility class | `src/css/7_utilities/` | `@layer utilities { }` |
| Layout primitive | `src/css/5_layouts/` | `@layer layouts { }` |
| Component | `src/css/6_components/` | `@layer components { }` |

Rules:
- Use `--line-*` tokens for all spacing (never arbitrary pixel values)
- Use logical properties (`margin-block-start`, not `margin-top`)
- Use custom properties for configuration and theming
- Use container queries for responsive component behavior
