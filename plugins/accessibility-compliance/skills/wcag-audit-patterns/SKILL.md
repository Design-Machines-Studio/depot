---
name: wcag-audit-patterns
description: Conduct WCAG 2.2 accessibility audits with automated testing, manual verification, and remediation guidance for Live Wires, Go+Templ+Datastar, and Craft CMS projects. Use when auditing websites for accessibility, fixing WCAG violations, reviewing HTML templates for a11y compliance, checking color contrast, validating focus management, adding ARIA attributes, or preparing for EAA/ADA compliance. Also use when writing new Templ components, Twig templates, or Datastar-enhanced pages that need accessible markup patterns. Covers WCAG 2.2 Level AA, ARIA Authoring Practices, automated tooling, and stack-specific patterns.
argument-hint: "[url or file path to audit]"
---

# WCAG Audit Patterns

Accessibility is not a feature — it is a constraint that shapes every design decision. This skill provides the methodology, checklists, and stack-specific patterns for auditing and building accessible interfaces across all Design Machines projects.

## Philosophy

Accessibility compliance follows the same progressive refinement approach as Live Wires:

1. **Semantic HTML first** — correct elements, heading hierarchy, landmark regions
2. **Keyboard operability** — tab order, focus management, skip links
3. **ARIA enhancement** — only when native semantics are insufficient
4. **Visual compliance** — contrast, motion, spacing, reflow

If you get Step 1 right, most of the work is done. ARIA is a repair tool, not a construction material.

## WCAG 2.2 Level AA — The Compliance Target

All Design Machines projects target **WCAG 2.2 Level AA**. This is the legal baseline for ADA (US), EAA (EU, enforceable since June 2025), and Section 508 (US government).

### The Four Principles (POUR)

| Principle | Meaning | Key success criteria |
|-----------|---------|---------------------|
| **Perceivable** | Can users perceive the content? | Text alternatives, captions, contrast, resize |
| **Operable** | Can users operate the interface? | Keyboard, timing, seizures, navigation |
| **Understandable** | Can users understand the content? | Readable, predictable, input assistance |
| **Robust** | Does it work with assistive tech? | Valid markup, name/role/value, status messages |

### Critical Success Criteria

These are the criteria most commonly failed. Check these first:

| SC | Name | Level | What to check |
|----|------|-------|---------------|
| 1.1.1 | Non-text Content | A | Every `<img>` has `alt`, decorative images use `alt=""` |
| 1.3.1 | Info and Relationships | A | Headings, lists, tables, forms use correct elements |
| 1.4.3 | Contrast (Minimum) | AA | 4.5:1 body text, 3:1 large text (18px+ or 14px+ bold) |
| 1.4.11 | Non-text Contrast | AA | 3:1 for UI components and graphical objects |
| 2.1.1 | Keyboard | A | All functionality reachable via keyboard |
| 2.4.3 | Focus Order | A | Tab order matches visual reading order |
| 2.4.7 | Focus Visible | AA | Visible focus indicator on all interactive elements |
| 2.5.8 | Target Size (Minimum) | AA | 24x24px minimum. **Not auto-flagged** -- the SC has real-world exceptions (inline links, grouped targets, spaced targets, browser defaults, essential presentation) that automated checks routinely misfire on. Audit manually when touch-surface scrutiny is warranted. |
| 3.3.2 | Labels or Instructions | A | Every form input has a visible label |
| 4.1.2 | Name, Role, Value | A | Custom widgets expose name, role, state to AT |

### New in WCAG 2.2

| SC | Name | What it means |
|----|------|---------------|
| 2.4.11 | Focus Not Obscured (Minimum) | Focused element not fully hidden by sticky headers/modals |
| 2.4.13 | Focus Appearance | Focus indicator meets minimum area and contrast |
| 2.5.7 | Dragging Movements | Single-pointer alternative for drag operations |
| 2.5.8 | Target Size (Minimum) | 24x24px minimum for pointer targets. Auto-check removed (Apr 2026) due to WCAG exception complexity; manual audit only. |
| 3.2.6 | Consistent Help | Help mechanisms in same relative order across pages |
| 3.3.7 | Redundant Entry | Don't make users re-enter previously provided info |
| 3.3.8 | Accessible Authentication (Minimum) | No cognitive function tests for login |

## Audit Methodology

### Phase 1: Automated Scan

Run automated tools against rendered HTML. They catch ~30-40% of issues.

```bash
# Pa11y — quick scan of a single page
npx pa11y http://localhost:8080/page --standard WCAG2AA

# Pa11y-CI — scan multiple pages from a sitemap or list
npx pa11y-ci --config .pa11yci.json

# Lighthouse — broader audit including performance
npx lighthouse http://localhost:8080 --only-categories=accessibility --output=json
```

**Playwright with axe-core** (best for CI pipelines):

```javascript
const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

test('page has no a11y violations', async ({ page }) => {
  await page.goto('/page');
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag22aa'])
    .analyze();
  expect(results.violations).toEqual([]);
});
```

### Phase 2: Keyboard Audit

Test every page manually:

1. **Tab through** — Can you reach every interactive element?
2. **Activate** — Do Enter/Space trigger buttons and links?
3. **Escape** — Do modals, dropdowns, and dialogs close?
4. **Arrow keys** — Do composite widgets (tabs, menus, radio groups) support arrow navigation?
5. **Focus trap** — Is focus trapped inside modals when open?
6. **Skip links** — Does Tab from page top reveal a "Skip to main content" link?
7. **Focus visible** — Is there a clear focus indicator on every element?

### Phase 3: Screen Reader Testing

See the `screen-reader-testing` skill for detailed protocols. Quick checks:

1. **Landmarks** — Are `<header>`, `<nav>`, `<main>`, `<footer>` present?
2. **Headings** — Does the heading hierarchy make sense when read in sequence?
3. **Images** — Are alt texts meaningful (not "image.png" or "photo")?
4. **Forms** — Are labels announced when focusing inputs?
5. **Dynamic content** — Are live regions announcing updates?

### Phase 4: Visual Compliance

1. **Color contrast** — Test with browser DevTools or WebAIM Contrast Checker
2. **200% zoom** — Does the layout still work at 200% browser zoom?
3. **400% zoom** — Is content still usable at 400%?
4. **Reduced motion** — Enable `prefers-reduced-motion` and verify animations stop
5. **Forced colors** — Test in Windows High Contrast Mode (or emulate in DevTools)
6. **Text spacing** — Apply WCAG text spacing overrides and verify no content is clipped

## Stack-Specific Patterns

### Live Wires

Live Wires has built-in accessibility support. The framework provides:

- **Color tokens** that meet WCAG AA contrast ratios by default
- **`:focus-visible`** styles on all interactive elements
- **`prefers-reduced-motion`** respect in the reset layer
- **`.visually-hidden`** utility for screen-reader-only content
- **`.skip-link`** utility for skip navigation
- **44x44px touch targets** on form elements via `--touch-target-min`
- **Logical properties** for RTL support

See `${CLAUDE_SKILL_DIR}/references/live-wires-a11y.md` for the complete Live Wires accessibility reference.

**Common Live Wires mistakes:**
- Using `.hidden` when `.visually-hidden` is needed (removes from AT)
- Setting `outline: none` on focus without providing alternative
- Using color-only indicators (add text or icon alongside)
- Forgetting `aria-label` on icon-only buttons

### Go + Templ + Datastar

See `${CLAUDE_SKILL_DIR}/references/templ-datastar-a11y.md` for patterns. Key concerns:

- **Templ components** should enforce accessible props (require `alt` on image components, `label` on form components)
- **Datastar partial updates** need `aria-live` regions for dynamic content
- **SSE-driven morphing** can break focus — manage focus explicitly after DOM updates
- **`data-on-click`** must only be used on natively interactive elements (`<button>`, `<a>`)

### Craft CMS + Twig

See `${CLAUDE_SKILL_DIR}/references/craft-cms-a11y.md` for patterns. Key concerns:

- **Twig templates** must not bypass auto-escaping with `|raw` without sanitization
- **Rich text fields** output from Redactor/CKEditor needs heading hierarchy enforcement
- **Image transforms** must preserve alt text from the asset
- **Matrix blocks** need semantic wrapper elements, not generic `<div>` soup

## ARIA Patterns Quick Reference

See `${CLAUDE_SKILL_DIR}/references/aria-patterns.md` for the full APG pattern library. Essential patterns:

| Pattern | Key attributes | Keyboard |
|---------|---------------|----------|
| **Dialog (modal)** | `role="dialog"`, `aria-modal="true"`, `aria-labelledby` | Escape closes, focus trapped |
| **Tabs** | `role="tablist/tab/tabpanel"`, `aria-selected`, `aria-controls` | Arrows switch tabs |
| **Accordion** | `<button>` trigger, `aria-expanded`, `aria-controls` | Enter/Space toggle |
| **Menu** | `role="menu/menuitem"`, `aria-expanded` | Arrows navigate, Escape closes |
| **Combobox** | `role="combobox"`, `aria-expanded`, `aria-activedescendant` | Arrows + type-ahead |
| **Alert** | `role="alert"` or `aria-live="assertive"` | Announced immediately |
| **Status** | `role="status"` or `aria-live="polite"` | Announced at next pause |

### The First Rule of ARIA

> If you can use a native HTML element or attribute with the semantics and behavior you require already built in, instead of re-purposing an element and adding an ARIA role, state or property to make it accessible, then do so.

Use `<button>` not `<div role="button">`. Use `<nav>` not `<div role="navigation">`. Use `<dialog>` not `<div role="dialog">`.

## Automated Testing Configuration

### Pa11y-CI Configuration (`.pa11yci.json`)

```json
{
  "defaults": {
    "standard": "WCAG2AA",
    "timeout": 30000,
    "wait": 1000,
    "chromeLaunchConfig": {
      "args": ["--no-sandbox"]
    }
  },
  "urls": [
    "http://localhost:8080/",
    "http://localhost:8080/login",
    "http://localhost:8080/dashboard"
  ]
}
```

### axe-core Rule Tags

Use these tags to match your compliance target:

| Tag | Covers |
|-----|--------|
| `wcag2a` | WCAG 2.0 Level A |
| `wcag2aa` | WCAG 2.0 Level AA |
| `wcag21a` | WCAG 2.1 Level A |
| `wcag21aa` | WCAG 2.1 Level AA |
| `wcag22aa` | WCAG 2.2 Level AA |
| `best-practice` | Common best practices beyond WCAG |

## Remediation Priority

When an audit finds violations, fix in this order:

1. **Critical** — blocks access entirely (missing form labels, keyboard traps, zero-contrast text)
2. **Serious** — significant barriers (missing alt text, broken focus order, no skip links)
3. **Moderate** — degraded experience (low contrast on secondary text, missing landmarks)
4. **Minor** — polish items (redundant ARIA, suboptimal heading levels)

## Reference Files

| File | Contents |
|------|----------|
| [${CLAUDE_SKILL_DIR}/references/wcag-2.2-checklist.md](${CLAUDE_SKILL_DIR}/references/wcag-2.2-checklist.md) | Complete WCAG 2.2 AA success criteria checklist |
| [${CLAUDE_SKILL_DIR}/references/aria-patterns.md](${CLAUDE_SKILL_DIR}/references/aria-patterns.md) | ARIA Authoring Practices pattern library |
| [${CLAUDE_SKILL_DIR}/references/testing-tools.md](${CLAUDE_SKILL_DIR}/references/testing-tools.md) | Tool configuration and CI integration guides |
| [${CLAUDE_SKILL_DIR}/references/live-wires-a11y.md](${CLAUDE_SKILL_DIR}/references/live-wires-a11y.md) | Live Wires framework accessibility reference |
| [${CLAUDE_SKILL_DIR}/references/templ-datastar-a11y.md](${CLAUDE_SKILL_DIR}/references/templ-datastar-a11y.md) | Go + Templ + Datastar accessibility patterns |
| [${CLAUDE_SKILL_DIR}/references/craft-cms-a11y.md](${CLAUDE_SKILL_DIR}/references/craft-cms-a11y.md) | Craft CMS + Twig accessibility patterns |

## Ecosystem Integration

Official and third-party Claude Code plugins that complement this skill:

| Plugin | Tool | When to Use |
|--------|------|-------------|
| **accessibility-compliance (official)** | WCAG skills | General WCAG 2.2 rules and testing methodology |
| **compound-engineering** | a11y review agents | Automated HTML, CSS, and dynamic content a11y checks |
| **playwright** | Browser tools | Automated accessibility testing with axe-core |
| **superpowers** | `/verify` | Verify remediation after fixing a11y issues |

> **Note:** The official `accessibility-compliance` plugin provides general-purpose WCAG 2.2 auditing. This depot skill adds stack-specific patterns for Live Wires CSS, Go+Templ+Datastar, and Craft CMS. Use both together: the official plugin for rules, this skill for implementation patterns.
