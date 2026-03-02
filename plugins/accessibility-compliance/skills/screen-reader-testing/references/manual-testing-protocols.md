# Manual Testing Protocols

Cross-browser testing procedures, NVDA reference, and regression testing protocols.

---

## Testing Priority Matrix

### Browser + Screen Reader Combinations

| Priority | Combination | Coverage |
|----------|-------------|----------|
| **Primary** | VoiceOver + Safari (macOS) | Development team's main environment |
| **Secondary** | NVDA + Chrome (Windows) | Most common AT combination globally |
| **Tertiary** | NVDA + Firefox (Windows) | Strong ARIA support |
| **Stretch** | JAWS + Chrome (Windows) | Enterprise/corporate users |

For Design Machines projects, VoiceOver + Safari is the primary test environment. Test in NVDA when possible (use a VM or BrowserStack).

---

## NVDA Quick Reference

NVDA is the most widely used free screen reader on Windows. Use it for cross-platform validation.

### Install

Download from https://www.nvaccess.org/download/

### Key Commands

NVDA uses the Insert key as its modifier (or Caps Lock if configured).

| Action | Keys | Notes |
|--------|------|-------|
| Next element | Down Arrow | In browse mode |
| Previous element | Up Arrow | |
| Next heading | H | |
| Previous heading | Shift + H |  |
| Next landmark | D | |
| Next link | K | |
| Next form control | F | |
| Activate | Enter | |
| Toggle browse/focus mode | NVDA + Space | Browse mode for reading, focus mode for forms |
| Elements list | NVDA + F7 | Like VoiceOver's rotor |
| Read from cursor | NVDA + Down Arrow | |
| Stop reading | Control | |

### Browse Mode vs Focus Mode

NVDA has two modes:
- **Browse mode:** Arrow keys navigate through content (headings, links, text). Used for reading.
- **Focus mode:** Arrow keys are passed to the focused element. Used inside form fields, widgets.

NVDA switches automatically when you Tab into a form field. This is important for testing — if arrow keys don't navigate content, you're in focus mode.

---

## Keyboard-Only Testing Protocol

This does NOT require a screen reader. Test with the screen reader OFF to verify keyboard operability independently.

### Checklist

1. **Start from the address bar** — press Tab to enter the page
2. **Tab through the entire page** — note every element that receives focus
3. **Verify tab order** matches visual reading order (left-to-right, top-to-bottom)
4. **Check skip links** — first Tab should reveal "Skip to main content"
5. **Test interactive elements:**

| Element | Expected Keyboard Behavior |
|---------|--------------------------|
| Link | Enter activates |
| Button | Enter or Space activates |
| Checkbox | Space toggles |
| Radio | Arrow keys select within group |
| Select | Arrow keys change value, Enter confirms |
| Tabs | Arrow keys switch tabs |
| Menu | Arrow keys navigate, Escape closes |
| Dialog | Tab cycles within, Escape closes |
| Accordion | Enter/Space toggles, Arrows move between headers |

6. **Check for keyboard traps** — can focus always escape every element?
7. **Check focus visibility** — is there a clear indicator on every focused element?
8. **Test without mouse** — can you complete every task using only keyboard?

---

## Color and Visual Testing

### Contrast Testing

**Browser DevTools approach:**
1. Open DevTools (Cmd + Option + I)
2. Select element with color
3. Click the color swatch in the Styles panel
4. DevTools shows contrast ratio and AA/AAA compliance

**Automated approach:**
```bash
npx pa11y http://localhost:8080/ --standard WCAG2AA --reporter cli | grep "color-contrast"
```

### Reduced Motion Testing

**macOS:**
1. System Settings > Accessibility > Display
2. Enable "Reduce motion"
3. Reload the page
4. Verify all animations are stopped or reduced

**Chrome DevTools:**
1. Open DevTools > Rendering tab
2. Check "Emulate CSS media feature prefers-reduced-motion: reduce"

### Forced Colors / High Contrast

**Chrome DevTools:**
1. Open DevTools > Rendering tab
2. Check "Emulate CSS media feature forced-colors: active"
3. Verify UI elements are still distinguishable (borders, focus indicators)

**Windows:**
1. Settings > Accessibility > Contrast themes
2. Select a high contrast theme
3. Verify all content is visible and interactive elements are distinguishable

### Color Blindness Simulation

**Chrome DevTools:**
1. Open DevTools > Rendering tab
2. Select vision deficiency: Protanopia, Deuteranopia, Tritanopia, Achromatopsia
3. Verify information is not conveyed by color alone

---

## Zoom Testing

### 200% Zoom (WCAG 1.4.4)

1. Set browser zoom to 200% (Cmd + Plus)
2. Verify:
   - [ ] No content is clipped or hidden
   - [ ] No horizontal scrolling (at 1280px viewport = 640px effective)
   - [ ] Text is readable and not overlapping
   - [ ] Interactive elements are still usable

### 400% Zoom (WCAG 1.4.10 Reflow)

1. Set browser zoom to 400%
2. Or set viewport to 320px width
3. Verify:
   - [ ] Content reflows to single column
   - [ ] No horizontal scrolling for text content
   - [ ] Navigation is still accessible
   - [ ] Forms are still usable

### Text Spacing Override (WCAG 1.4.12)

Apply these CSS overrides and verify no content is clipped:

```css
* {
  line-height: 1.5 !important;
  letter-spacing: 0.12em !important;
  word-spacing: 0.16em !important;
}
p {
  margin-bottom: 2em !important;
}
```

Use the bookmarklet:
```javascript
javascript:void(function(){var s=document.createElement('style');s.textContent='*{line-height:1.5!important;letter-spacing:0.12em!important;word-spacing:0.16em!important}p{margin-bottom:2em!important}';document.head.appendChild(s)})()
```

---

## Regression Testing Protocol

### When to Run

Run the full manual accessibility test suite:
- **Before every release** (all tests)
- **After template changes** (affected page + navigation)
- **After CSS changes** (visual compliance tests)
- **After Datastar/JS changes** (keyboard + screen reader tests for dynamic content)

### Regression Test Template

```markdown
## Accessibility Regression Test

**Date:** YYYY-MM-DD
**Tester:** Name
**Environment:** VoiceOver X.X + Safari X.X on macOS X.X
**Pages tested:** [list]

### Results

| Page | Auto scan | Keyboard | Screen reader | Visual | Status |
|------|-----------|----------|---------------|--------|--------|
| Homepage | Pass | Pass | Pass | Pass | OK |
| Login | Pass | Pass | 1 issue | Pass | Fix needed |
| Dashboard | 2 issues | Pass | Pass | 1 issue | Fix needed |

### Issues Found

1. **Login page:** Error message not announced by screen reader
   - Location: #login-form error container
   - Missing: `role="alert"` on error message div
   - Severity: Serious
   - SC: 4.1.3 Status Messages

2. **Dashboard:** Low contrast on muted text in sidebar
   - Location: .sidebar .text-muted
   - Current: 3.2:1 (needs 4.5:1 for body text)
   - Severity: Moderate
   - SC: 1.4.3 Contrast (Minimum)

### Sign-off

- [ ] All Critical issues resolved
- [ ] All Serious issues resolved or tracked
- [ ] Moderate issues tracked for next sprint
```

---

## Integration with CI/CD

Manual testing supplements automated testing. The recommended workflow:

1. **Every PR:** Automated Pa11y-CI + Playwright axe scan (catches ~40% of issues)
2. **Every sprint:** Full manual keyboard + screen reader audit of changed pages
3. **Every release:** Complete manual audit of all pages using the regression template
4. **Annually:** Third-party accessibility audit for compliance documentation

### Automated Baseline

Keep a `.pa11yci.json` with all project URLs. Run on every PR that touches front-end files. This catches regressions in the automated category.

### Manual Coverage Tracking

Maintain a spreadsheet or Notion database tracking:
- Which pages have been manually tested
- Date of last test
- Known issues and their status
- WCAG criteria verified per page
