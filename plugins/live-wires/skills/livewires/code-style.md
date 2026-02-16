# Code Style Guidelines

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
