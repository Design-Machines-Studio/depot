---
name: screen-reader-testing
description: Test web applications with screen readers including VoiceOver, NVDA, and JAWS for accessibility compliance. Use when validating screen reader compatibility, debugging accessibility issues, ensuring assistive technology support, writing ARIA markup, verifying live region announcements, or testing keyboard navigation with screen readers. Also use when a new interactive component is built and needs manual verification, when automated a11y tools report no issues but you suspect screen reader problems, or when reviewing Templ components, Twig templates, or Datastar-enhanced pages for screen reader compatibility. Covers VoiceOver (macOS), NVDA (Windows), testing protocols, and common failure patterns.
---

# Screen Reader Testing

Automated tools catch ~30-40% of accessibility issues. The rest requires manual testing with screen readers. This skill provides structured testing protocols, VoiceOver-first workflows (since DM projects are built on macOS), and patterns for the most common failures.

## Philosophy

Screen reader testing is not about making the screen reader say the right words. It is about verifying that the **information architecture** — headings, landmarks, labels, relationships — communicates the same meaning to a non-visual user as the visual design communicates to a sighted user.

The question is never "Does the screen reader read this?" but "Does a screen reader user understand the page structure, current state, and available actions?"

## VoiceOver Quick Start (macOS)

VoiceOver is the primary testing tool for Design Machines projects.

### Enable/Disable
- **Toggle:** Cmd + F5 (or Touch ID triple-press)
- **Settings:** System Settings > Accessibility > VoiceOver

### Essential Commands

| Action | Keys | Notes |
|--------|------|-------|
| **Next element** | VO + Right Arrow | VO = Control + Option |
| **Previous element** | VO + Left Arrow | |
| **Activate** | VO + Space | Click/press the focused element |
| **Read heading** | VO + Cmd + H | Next heading |
| **Read landmark** | VO + Cmd + L | Next landmark region |
| **Rotor** | VO + U | Navigate by type (headings, links, forms) |
| **Read from cursor** | VO + A | Read everything from current position |
| **Stop reading** | Control | |
| **Web rotor** | VO + U, then Left/Right arrows | Switch between heading/link/form/landmark lists |

### VoiceOver + Safari

Always test in Safari first — it has the best VoiceOver integration on macOS. Chrome and Firefox have quirks with certain ARIA patterns.

## Testing Protocol

### Test 1: Page Structure (Landmarks)

Open the VoiceOver Rotor (VO + U) and navigate to the Landmarks list.

**Expected landmarks for a typical page:**
- `banner` — site header
- `navigation` — primary nav (may have multiple, each labeled)
- `main` — primary content area
- `complementary` — sidebar content (if applicable)
- `contentinfo` — site footer

**Failures to catch:**
- Missing `<main>` element (most common)
- Multiple `<nav>` elements without `aria-label` to distinguish them
- Generic `<div>` where a landmark element should be used
- `<header>` and `<footer>` inside `<article>` creating unexpected nested landmarks

### Test 2: Heading Hierarchy

Open the Rotor and navigate to the Headings list.

**Check:**
- One `<h1>` per page (the page title)
- No skipped levels (h1 → h3 without h2)
- Headings create a meaningful outline
- Section headings accurately describe their content

**Common failures in Templ/Twig templates:**
- Hardcoded heading levels that break when components are composed
- Matrix blocks starting at `<h2>` when nested inside an `<h3>` context
- Decorative text styled as headings but not using heading elements

### Test 3: Link and Button Text

Navigate the Links list in the Rotor.

**Check:**
- Every link has descriptive text (not "click here", "read more", "learn more")
- Links that open new windows indicate this (`opens in new tab`)
- Buttons describe their action ("Delete proposal" not just "Delete")
- Icon-only buttons have accessible names via `aria-label` or `.visually-hidden` text

### Test 4: Forms

Tab through every form on the page.

**For each form field, verify VoiceOver announces:**
1. The label (what the field is for)
2. The input type (text field, checkbox, dropdown)
3. Required state (if applicable)
4. Error messages (when validation fails)
5. Help text (if using `aria-describedby`)

**Common failures:**
- Placeholder text used as the only label (disappears on input)
- Error messages not associated with the field via `aria-describedby`
- Radio groups without `<fieldset>` + `<legend>`
- Custom select/combobox widgets that don't announce selected value

### Test 5: Dynamic Content (Datastar / SSE)

For pages that update without full page reload:

1. **Trigger an update** (form submission, button click, SSE event)
2. **Listen for announcement** — Did VoiceOver announce the change?
3. **Check focus** — Is focus on a logical element after the update?

**Live region requirements:**
- Status messages: `role="status"` or `aria-live="polite"`
- Error messages: `role="alert"` or `aria-live="assertive"`
- Loading states: announce "Loading..." then announce completion

**Datastar-specific concerns:**
- `data-merge-morph` can destroy and recreate DOM nodes, losing focus
- After morph, explicitly set focus to the updated content or a logical target
- SSE-driven content needs a live region wrapper that persists across morphs

### Test 6: Interactive Widgets

For each custom widget (tabs, accordions, dialogs, menus):

| Widget | What to verify |
|--------|---------------|
| **Tabs** | Arrow keys switch tabs, VO announces "selected", panel content changes |
| **Accordion** | Enter/Space toggles, VO announces "expanded/collapsed" |
| **Dialog** | Focus moves into dialog, Escape closes, focus returns to trigger |
| **Dropdown menu** | Arrow keys navigate items, Escape closes, VO announces current item |
| **Toast/notification** | VO announces when it appears (live region) |
| **Loading spinner** | VO announces loading state and completion |

### Test 7: Images and Media

Navigate through images:

- **Informative images:** Alt text describes the content or function
- **Decorative images:** `alt=""` (empty alt, not missing alt)
- **Complex images (charts, diagrams):** Extended description via `aria-describedby` or adjacent text
- **SVG icons:** `role="img"` with `aria-label`, or `aria-hidden="true"` if decorative

## Common Failure Patterns by Stack

### Live Wires + Templ

| Pattern | Problem | Fix |
|---------|---------|-----|
| Icon-only button | No accessible name | Add `<span class="visually-hidden">Label</span>` |
| Color scheme toggle | State not announced | Add `aria-pressed` or `aria-checked` |
| Reel (horizontal scroll) | Not announced as scrollable | Add `role="region"` with `aria-label` |
| Status indicator | Color-only meaning | Add `.visually-hidden` text or `aria-label` |
| Custom checkbox | Native input hidden with `display:none` | Use `.visually-hidden` class instead |

### Datastar

| Pattern | Problem | Fix |
|---------|---------|-----|
| Partial page update | Content changes silently | Wrap target in `aria-live="polite"` |
| Form submission | Success/error not announced | Use `role="alert"` for errors, `role="status"` for success |
| Focus after morph | Focus lost to document body | Set focus explicitly with `data-on-load` or JS |
| Optimistic UI | Intermediate state confusing | Announce "Saving..." then "Saved" via live region |

### Craft CMS + Twig

| Pattern | Problem | Fix |
|---------|---------|-----|
| Matrix blocks | Heading levels wrong in context | Use dynamic heading level based on nesting depth |
| Rich text output | Missing alt on inline images | Enforce alt text in CMS field settings |
| Entry links | "Read more" everywhere | Use entry title as link text |
| Navigation | Multiple `<nav>` without labels | Add `aria-label` to each nav element |

## Testing Checklist Template

Use this for each page audit:

```markdown
## Screen Reader Audit: [Page Name]

**Tested with:** VoiceOver + Safari [version]
**Date:** YYYY-MM-DD

### Landmarks
- [ ] banner present
- [ ] navigation labeled (if multiple navs)
- [ ] main present
- [ ] contentinfo present

### Headings
- [ ] Single h1
- [ ] No skipped levels
- [ ] Meaningful outline

### Links & Buttons
- [ ] All links descriptive
- [ ] Buttons describe action
- [ ] Icon-only elements have accessible names

### Forms
- [ ] All inputs labeled
- [ ] Required fields announced
- [ ] Error messages associated
- [ ] Fieldsets group related inputs

### Dynamic Content
- [ ] Updates announced via live regions
- [ ] Focus managed after DOM changes
- [ ] Loading states communicated

### Images
- [ ] Informative images have meaningful alt
- [ ] Decorative images have empty alt
- [ ] Complex images have extended descriptions

### Keyboard
- [ ] All interactive elements reachable
- [ ] Focus order logical
- [ ] Focus visible on all elements
- [ ] Escape closes overlays
- [ ] No keyboard traps
```

## Reference Files

| File | Contents |
|------|----------|
| [${CLAUDE_SKILL_DIR}/references/voiceover-testing.md](${CLAUDE_SKILL_DIR}/references/voiceover-testing.md) | Detailed VoiceOver commands, Safari quirks, and macOS configuration |
| [${CLAUDE_SKILL_DIR}/references/manual-testing-protocols.md](${CLAUDE_SKILL_DIR}/references/manual-testing-protocols.md) | Cross-browser testing protocols, NVDA reference, and regression testing |
