---
name: a11y-audit
description: Run automated accessibility audit on a page or template
argument-hint: "[URL, file path, or 'all' for full site scan]"
---

# Accessibility Audit

Quick WCAG 2.2 AA audit of a page, template, or site.

## Process

### 1. Determine Target

- **URL provided**: Audit the live page
- **File path provided**: Audit the template file
- **"all" or no argument**: Scan all template files in the project

### 2. Load Checklist

Read the WCAG audit skill for the full checklist:
- `plugins/accessibility-compliance/skills/wcag-audit-patterns/references/wcag-2.2-checklist.md`

### 3. Run Audit

**For template files (.templ, .twig, .html):**

Launch the a11y-html-reviewer agent to check:
- Landmark regions (header, nav, main, footer)
- Heading hierarchy (h1 → h2 → h3, no skips)
- Form labeling (every input has a label)
- Image alt text (meaningful, not decorative defaults)
- Link text quality (no "click here" or "read more")
- ARIA attributes (valid roles, required properties)

**For CSS files:**

Launch the a11y-css-reviewer agent to check:
- Color contrast ratios (4.5:1 text, 3:1 large text)
- Focus indicator visibility
- Reduced motion support (prefers-reduced-motion)
- Text spacing resilience
- Reflow at 320px viewport (400% zoom)

Touch target size (WCAG 2.5.8) is documented for manual audit but not automatically flagged -- the SC has real-world exceptions (inline links, grouped targets, browser defaults, essential presentation) that automated checks misfire on. Audit manually when touch surfaces are a known concern.

**For live URLs (if browser tools available):**

Navigate to the URL and check:
- Page title exists and is descriptive
- Skip navigation link present
- Keyboard navigation works (Tab through interactive elements)
- No content visible only on hover

### 4. Report

```
Accessibility Audit — [target] — [date]

Violations: X
Warnings: Y

VIOLATIONS:
- [file:line] Missing alt text on <img> — WCAG 1.1.1
- [file:line] Form input without label — WCAG 1.3.1

WARNINGS:
- [file:line] Generic link text "Learn more" — WCAG 2.4.4
- [file:line] Heading level skipped (h2 → h4) — WCAG 1.3.1

PASSED:
- Landmark regions present
- Focus indicators visible
- Color contrast adequate
```
