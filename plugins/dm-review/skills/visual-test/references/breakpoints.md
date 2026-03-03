# Responsive Breakpoints

Canonical breakpoints for visual browser testing, aligned with Live Wires framework conventions.

## Default Breakpoints

| Width | Name | Rationale |
|-------|------|-----------|
| 320px | Mobile (small) | Narrowest supported viewport. WCAG 1.4.10 requires reflow at 400% zoom of 1280px = 320px effective width |
| 768px | Tablet | Common tablet portrait width. First major layout shift for most designs |
| 1024px | Desktop (small) | Typical laptop viewport. Default testing baseline for all pages |
| 1440px | Desktop (large) | Common external monitor width. Verifies wide layout behavior |

## When to Test All Four Breakpoints

Always test all four when:

- CSS files changed (any `.css` modification)
- Template layout structure changed (new sections, grid changes, sidebar additions)
- Layout primitives added or modified (`.stack`, `.grid`, `.sidebar`, `.cluster`, `.switcher`)
- New pages created
- Responsive utility classes added or changed

## When to Test Desktop + Mobile Only

Test 320px + 1024px minimum when:

- Only content text changed (verify reflow)
- Form fields added (verify mobile usability)
- Images or media added (verify responsive sizing)
- Minor component changes (button text, icon swaps)

## Breakpoint Heights

When taking screenshots, use these heights with `browser_resize`:

| Breakpoint | Width | Height |
|-----------|-------|--------|
| Mobile | 320 | 568 |
| Tablet | 768 | 1024 |
| Desktop (small) | 1024 | 768 |
| Desktop (large) | 1440 | 900 |

Always also take a `fullPage: true` screenshot to capture below-the-fold content.

## Live Wires Container Query Context

Live Wires uses container queries rather than media queries for component-level responsive behavior. The breakpoints above are **viewport widths** for `browser_resize`, but the actual CSS breakpoints are container-based:

- `@container (min-width: 40rem)` — mapped via `@md` suffix
- `@container (min-width: 60rem)` — mapped via `@lg` suffix

At viewport width 320px, most containers will be below 40rem, triggering the narrowest layout. At 1024px+, containers in the main content area will typically exceed 60rem.

## Overflow Detection

At each breakpoint, check for horizontal overflow by running:

```javascript
// browser_evaluate — check for horizontal overflow
document.documentElement.scrollWidth > document.documentElement.clientWidth
```

If true, flag as P2: "Horizontal overflow detected at [width]px viewport."
