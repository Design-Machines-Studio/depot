# QA Testing a Live Wires Prototype

Use this system to audit prototypes for consistency, accessibility, and Live Wires compliance.

## ⚠️ CRITICAL: Test ALL Pages

**Do not skip subpages.** A common failure mode is testing top-level pages and missing nested pages entirely.

Before starting QA:

1. **Discover all HTML files** in the prototype (exclude `/docs/`, `/example/`, `/manual/`)
2. **Create a complete page list** including ALL subdirectories
3. **Test every single page** - no exceptions

```bash
# Find all prototype pages to test
find public -name "*.html" | grep -v -E "(docs|example|manual)" | sort
```

Example of what to test:

```
✓ /index.html
✓ /about.html
✓ /users/index.html      ← Don't skip!
✓ /users/show.html       ← Don't skip!
✓ /users/edit.html       ← Don't skip!
✓ /articles/index.html   ← Don't skip!
✓ /articles/show.html    ← Don't skip!
✓ /dashboard/index.html  ← Don't skip!
✓ /dashboard/settings.html ← Don't skip!
```

**Excluded directories** (framework docs, not prototype):

- `/docs/` - Live Wires documentation
- `/example/` - Example implementation
- `/manual/` - Brand manual/component library

---

## Core Testing Objectives

### ⚠️ THOROUGH Link Testing (Every Link, Every Page)

**Test EVERY link on EVERY page**, not just navigation. This includes:

- Navigation links (header, footer, sidebar)
- In-content links (within paragraphs, lists, cards)
- Button links (`<a>` styled as buttons)
- Image links (clickable images/figures)
- Icon links (social icons, action icons)
- Breadcrumb links
- Pagination links
- "Read more" / "View all" links
- Footer links (legal, sitemap, etc.)

**For each link, verify:**

- Internal links resolve to existing prototype pages (no 404s)
- Anchor links (`#section`) scroll to the correct section
- External links open in new tab with `target="_blank" rel="noopener noreferrer"`
- No empty `href=""` or `href="#"` placeholder links
- No dead-end pages (pages with no way to navigate away)

### JavaScript Console Audit

**Check browser console on EVERY page for:**

- JavaScript errors (red) — must fix
- JavaScript warnings (yellow) — should review
- Failed network requests (404s for scripts, styles, images)
- Web component initialization errors
- Uncaught exceptions or promise rejections

**Common JS issues to catch:**

- Web components not registering (check custom element definitions)
- Missing dependencies or imports
- Event listeners on non-existent elements
- Incorrect paths to JS modules

### Form Testing

**For every form in the prototype:**

- `action` attribute points to an existing page (e.g., `action="/users/show.html"`)
- `method` attribute is set appropriately (`GET` or `POST`)
- Required fields have `required` attribute
- Form inputs have associated `<label>` elements (for/id match)
- Submit buttons are inside the form or use `form="formId"`
- Form validation states render correctly (`:invalid`, `:valid`)

**Test form flows:**

- Submit the form and verify it lands on the correct page
- Check that "Cancel" buttons navigate back appropriately
- Verify edit forms and create forms share templates where logical

### Image and Media Audit

- No broken images (check for 404s in Network tab)
- All `<img>` elements have `alt` attributes (can be empty for decorative)
- Images load at appropriate sizes (not oversized)
- Placeholder images use consistent service (placehold.co)
- Video embeds render correctly (if any)

### Interactive Element Verification

- Test all buttons for hover, focus, and active states
- Verify every clickable element has a visible focus indicator
- Test keyboard navigation (Tab through entire page)
- Check web components render and function correctly
- Dialog/modal open and close correctly
- Dropdowns and toggles work as expected

### Layout and Responsive Behavior

- Compare header/footer appearance across all pages
- Verify spacing and alignment is consistent page-to-page
- Check responsive behavior at 320px, 768px, 1024px, and 1440px
- Flag layout breaks, overflow, or unexpected scrollbars
- Test horizontal scroll (should only exist intentionally, e.g., `.reel`)

### Typography Audit

- Check heading hierarchy: each page has exactly ONE `<h1>`, headings follow h1→h2→h3 order
- Verify font weights and families are consistent per heading level
- Flag excessive utility class usage for typography that should be handled by defaults
- No orphaned text (text outside proper containers)

### Live Wires Compliance Audit

- No inline styles: Flag any `style="..."` attributes
- No invented classes: Only use existing Live Wires classes
- Correct naming: Layouts use single-dash, components use double-dash
- State handling: Uses `data-*` attributes, not state classes
- Semantic HTML: Proper landmarks (`<header>`, `<nav>`, `<main>`, `<footer>`, `<aside>`)

---

## Quick Checklists

### Navigation

| Check | Pass |
| ----- | ---- |
| All nav links resolve to valid pages | ☐ |
| Active state uses `data-state="active"` or `[data-active]` | ☐ |
| Focus states visible on all links | ☐ |
| Keyboard accessible | ☐ |

### Headlines

| Check | Pass |
| ----- | ---- |
| Each page has exactly ONE `<h1>` | ☐ |
| Headings follow logical order (no skipping levels) | ☐ |
| h1-h6 styled at element level (minimal utility classes) | ☐ |
| Consistent sizing/weight per level across pages | ☐ |

### Buttons

| Check | Pass |
| ----- | ---- |
| Visible hover state | ☐ |
| Visible focus state (critical for a11y) | ☐ |
| Disabled buttons use `[data-state="disabled"]` | ☐ |
| Variants use `--` syntax (`.button--red`) | ☐ |

### Layout Primitives

| Check | Pass |
| ----- | ---- |
| Layout variants use single-dash (`.stack-compact`) | ☐ |
| No inline styles for layout adjustments | ☐ |
| Primitives handle structure, not visual styling | ☐ |

### Links (per page)

| Check | Pass |
| ----- | ---- |
| All internal links resolve to existing pages | ☐ |
| No empty `href=""` or `href="#"` placeholders | ☐ |
| Anchor links scroll to correct sections | ☐ |
| External links have `target="_blank" rel="noopener noreferrer"` | ☐ |
| No dead-end pages (every page has navigation out) | ☐ |

### Forms

| Check | Pass |
| ----- | ---- |
| Form `action` points to existing page | ☐ |
| Form has appropriate `method` attribute | ☐ |
| All inputs have associated `<label>` elements | ☐ |
| Required fields have `required` attribute | ☐ |
| Submit button is inside form or uses `form` attribute | ☐ |
| Form submission lands on correct page | ☐ |

### Console (per page)

| Check | Pass |
| ----- | ---- |
| No JavaScript errors (red) | ☐ |
| No failed network requests (404s) | ☐ |
| Web components initialize correctly | ☐ |
| No uncaught exceptions | ☐ |

### Images

| Check | Pass |
| ----- | ---- |
| No broken images (404s) | ☐ |
| All images have `alt` attributes | ☐ |
| Placeholder images use placehold.co | ☐ |

---

## Live Wires Compliance Criteria

### Naming Conventions

| Layer | Pattern | Examples |
| ----- | ------- | -------- |
| Utility | `.{abbrev}-{value}` | `.mt-4`, `.text-center`, `.scheme-warm` |
| Layout | `.{layout}` or `.{layout}-{variant}` | `.stack`, `.stack-compact` |
| Component | `.{component}--{variant}` | `.button--red`, `.table--bordered` |
| State | `[data-state="{state}"]` | `[data-state="active"]`, `[data-open]` |

### Key Rules

- NO BEM `__` syntax for child elements—use CSS nesting
- NO class prefixes like `.c-`, `.m-`, `.u-`
- NO invented class names—use existing primitives
- NO inline styles—use utility classes
- State uses `data-*` attributes, not classes

**Class Order in HTML** (general to specific):

1. Layout/composition (`.stack`, `.grid`)
2. Block/component (`.callout`, `.button`)
3. Variant modifiers (`.button--red`)
4. Utility classes (`.mt-4`, `.scheme-warm`)

---

## Common Issue Shortcodes

Use these for efficient documentation:

```
LINK-BROKEN   — Link leads to 404 or non-existent page
LINK-EMPTY    — Empty href="" or href="#" placeholder
LINK-ANCHOR   — Anchor link doesn't scroll to target
LINK-EXTERNAL — External link missing target/rel attributes
NAV-DEADEND   — Page has no outbound navigation

FORM-ACTION   — Form action points to non-existent page
FORM-LABEL    — Input missing associated label
FORM-METHOD   — Form missing method attribute
FORM-SUBMIT   — Submit button outside form without form attribute

JS-ERROR      — JavaScript error in console
JS-NETWORK    — Failed network request (404 for asset)
JS-COMPONENT  — Web component failed to initialize

IMG-BROKEN    — Image returns 404
IMG-ALT       — Image missing alt attribute

TYP-HIERARCHY — Heading level skipped (h1→h3)
TYP-DUPLICATE — Multiple h1 elements on page
TYP-UTILITY   — Excessive utility classes for typography

A11Y-FOCUS    — Missing visible focus state
A11Y-KEYBOARD — Element not keyboard accessible
A11Y-LABEL    — Interactive element missing accessible name

LW-INLINE     — Inline style attribute
LW-INVENTED   — Invented class name (not in Live Wires)
LW-BEM        — BEM syntax used (should use CSS nesting)
LW-STATE      — State class used (should use data-*)
LW-VARIANT    — Wrong variant syntax (single vs double dash)

LAYOUT-BREAK  — Layout breaks at specific viewport
LAYOUT-SCROLL — Unexpected horizontal scroll
```

---

## QA Testing Procedure

**For each page in the prototype:**

1. **Open browser DevTools** before navigating to the page
2. **Check Console tab** — note any errors or warnings
3. **Check Network tab** — note any failed requests (404s)
4. **Click every link** on the page — verify destination exists
5. **Test every form** — submit and verify action page exists
6. **Tab through the page** — verify focus states and keyboard access
7. **Resize viewport** — check 320px, 768px, 1024px, 1440px
8. **Inspect the HTML** — check for compliance issues

**Do not move to the next page until current page passes all checks.**

---

## The Three Questions for Every Element

1. **Is this semantic HTML styled by default?** If adding typography utilities to `<p>`, `<h1-h6>`, `<ul>`, `<blockquote>`—that's likely a violation.

2. **Are inline styles used?** Any `style="..."` should be replaced with existing utility classes.

3. **Is this an invented class?** Every class should exist in Live Wires. If you need a new class, reconsider the approach.

---

## The Sculpture Test

Disable CSS temporarily. Does the HTML structure still communicate hierarchy and meaning? If the page becomes incomprehensible, the HTML isn't semantic enough.
