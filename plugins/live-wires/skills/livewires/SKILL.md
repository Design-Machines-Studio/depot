---
name: livewires
description: Live Wires CSS framework for editorial websites. Use when building HTML pages, writing CSS, or advising on layout and styling. Provides layout primitives (stack, grid, cluster, sidebar, center, section, cover, reel), utility classes, and design tokens based on a baseline rhythm system.
---

# Live Wires CSS Framework

## Philosophy

**Good defaults + additive art direction.** Semantic HTML looks good with zero classes. Utility classes provide precise control for art direction.

**Nothing gets thrown away.** The prototype becomes the product. Every step builds on the last.

---

## CRITICAL: Prototyping Mindset

### DO NOT Create New CSS Classes

Live Wires has comprehensive layout primitives and utilities. **Never invent new class names.** If you think you need a new class, you're probably:

- Missing an existing utility (check the reference files)
- Over-engineering the solution
- Not trusting the defaults

```html
<!-- WRONG: Inventing classes -->
<div class="hero-container">
<div class="article-meta-wrapper">
<p class="subtitle-text">

<!-- RIGHT: Use existing primitives -->
<div class="cover">
<div class="cluster">
<p class="lead">
```

### Minimal Styling During Prototyping

Prototyping is about **structure and content**, not visual polish. Resist the urge to over-style.

**Headlines:** Let the semantic HTML work. `<h1>` through `<h6>` have good defaults. Only add size utilities (`text-4xl`, etc.) when there's a specific design reason.

```html
<!-- WRONG: Over-styled headline -->
<h1 class="text-6xl font-bold text-center mb-4 leading-tight">Article Title</h1>

<!-- RIGHT: Trust the defaults -->
<h1>Article Title</h1>
```

**Spacing:** Layout primitives handle spacing. Don't manually add `mt-*`, `mb-*`, `py-*` everywhere.

```html
<!-- WRONG: Manual spacing chaos -->
<section class="py-6">
  <h2 class="mb-4">Section Title</h2>
  <p class="mb-2">Paragraph one.</p>
  <p class="mb-2">Paragraph two.</p>
</section>

<!-- RIGHT: Let stack handle it -->
<section class="section">
  <h2>Section Title</h2>
  <p>Paragraph one.</p>
  <p>Paragraph two.</p>
</section>
```

**Supporting text:** Use `.lead` for intro paragraphs. Otherwise, let paragraph defaults work.

```html
<!-- WRONG: Over-styled supporting text -->
<p class="text-lg text-muted font-light leading-relaxed">Introduction to the article.</p>

<!-- RIGHT: Semantic and minimal -->
<p class="lead">Introduction to the article.</p>
```

### Page Types, Not Individual Pages

Think like a rapid prototyper. Build **reusable page templates**, not a page for every piece of content.

**BAD approach:**

```
/users/john-profile.html
/users/jane-profile.html
/users/bob-profile.html
/articles/article-one.html
/articles/article-two.html
```

**GOOD approach:**

```
/users/show.html        ← User profile template
/users/edit.html        ← User edit template
/articles/show.html     ← Article template
/articles/index.html    ← Article listing template
```

When building a prototype:

1. **Identify the page types** (list, detail, form, dashboard, etc.)
2. **Build one template per type** with realistic placeholder content
3. **Reuse templates** - don't duplicate for each item
4. **Use the same edit page** for create and edit flows

### The Prototyping Test

Before adding any class, ask:

1. Does semantic HTML already handle this? → Use no class
2. Does a layout primitive handle this? → Use `.stack`, `.grid`, `.section`, etc.
3. Is this a scheme/theme concern? → Use `.scheme-*`
4. Is this specific art direction? → Only then use utilities

**Goal: The cleanest possible HTML that's ready for styling later.**

---

## The Design Process

Live Wires follows a sculptural approach—start with raw material, shape the form, refine the details, add expression.

### Step 1: Prototype in HTML

Build page templates using semantic HTML and layout primitives in the `public/` folder. Your prototype is instantly viewable in real browsers across devices.

### Step 2: Set Your Tokens

Adjust design tokens (colors, typography, spacing) in `src/css/1_tokens/`. Watch the Manual transform in real time.

### Step 3: Refine and Express

Expand your CSS. Add utility classes for art direction. Refine components. Each iteration takes you from coarse to detailed.

### Step 4: Apply to Production

Connect your templates to your CMS or framework. Your prototype becomes the product.

---

## Quick Reference

### Supporting Files

For detailed reference, see these files in the same directory:

- **[layouts.md](layouts.md)** — Stack, Grid, Cluster, Sidebar, Center, Section, Cover, Box, Reel, Imposter
- **[components.md](components.md)** — Dialogs, Popups, Status Indicators, Badges, Progress Bars
- **[utilities.md](utilities.md)** — Typography, Spacing, Color Schemes, Container Queries
- **[patterns.md](patterns.md)** — Article Structure, Hero, Statistics Grid, Responsive Picture
- **[theming.md](theming.md)** — Visual transformation workflow, color scales, typography, accessibility
- **[code-style.md](code-style.md)** — Avoid inline styles, use schemes, placeholder images
- **[qa-testing.md](qa-testing.md)** — QA testing system for prototypes

---

## The Sacred Baseline System

All spacing derives from `--line`. Use `--line-*` tokens for spacing:

```
--line-0, --line-025, --line-05, --line-075, --line-1, --line-15, --line-2, --line-3, --line-4, --line-5, --line-6, --line-7, --line-8, --line-1px
```

## CSS Cascade Layers

```css
@layer tokens, reset, base, layouts, components, utilities;
```

Utilities always win over components, components over layouts, etc.

## Modern CSS Features

Live Wires uses native CSS only — no preprocessors. Key features: cascade layers, native nesting (`&` syntax), container queries, logical properties (`margin-block-start` not `margin-top`), fluid typography via `clamp()`, and custom properties throughout. PostCSS config is autoprefixer only.

---

## Best Practices

1. Start with semantic HTML - it looks good with zero classes
2. Add layout primitives first: `.stack`, `.grid`, `.cluster`, `.center`
3. Add utilities for art direction
4. Use `--line-*` tokens - never arbitrary pixel values
5. Use container queries (`@md`, `@lg`) over viewport media queries
6. Use HTML entities: `&mdash;`, `&middot;`, `&pound;`

---

## Documentation Sync Requirement

**CRITICAL:** When modifying Live Wires CSS or adding new features, you MUST update documentation to stay in sync.

### After Any Code Change, Update:

| Change Type | Files to Update |
|-------------|-----------------|
| Layout primitives/variants | This file (SKILL.md), CLAUDE.md, manual/components/layout.html |
| Utility classes | This file (SKILL.md), CLAUDE.md |
| Tokens (`--line-*`, `--text-*`) | This file (SKILL.md), CLAUDE.md, README.md |
| Components | CLAUDE.md, relevant manual page |
| File structure | CLAUDE.md, README.md |

### Naming Conventions (MUST follow):

- Layout modifiers: **single-dash** (`stack-compact`, `box-tight`, `sidebar-reverse`)
- Component modifiers: **double-dash** (`button--red`, `badge--success`)
- Spacing tokens: `--line-*` pattern
- Typography: Tailwind-style (`text-xs`, `text-sm`, `text-lg`, `text-2xl`, etc.)
