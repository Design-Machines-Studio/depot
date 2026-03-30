# UX Assessment Protocol

Browser-based evaluation of current UX state using Playwright MCP tools. Evaluates what exists now, not what changed.

## Prerequisites

- Playwright MCP tools available (primary: `mcp__plugin_compound-engineering_pw__browser_*`, fallback: `mcp__plugin_playwright_playwright__browser_*`)
- Dev server running and accessible

### Dev Server Detection

Check for a running dev server:
1. Try common ports: 8080, 3000, 4000, 5173, 1313
2. Check for `docker compose` services
3. Look for `Procfile`, `Makefile`, or scripts that start dev servers
4. If no server found, skip UX assessment with note

## Step 1: Navigate to Affected Area

1. Open the relevant page(s) in the browser
2. If the area has multiple pages, prioritize: index/list page, detail/show page, form/create page
3. Wait for full page load (no pending network requests)

## Step 2: Viewport Screenshots

Capture screenshots at three breakpoints:

1. **Mobile:** 375px wide (resize, wait 500ms, screenshot)
2. **Tablet:** 768px wide
3. **Desktop:** 1440px wide

For each viewport, take a full-page screenshot and note:
- Does the layout adapt properly?
- Is content readable at this size?
- Are touch targets adequate on mobile (min 44x44px)?

## Step 3: Visual Hierarchy Assessment

At desktop viewport:

1. **Heading hierarchy:** Is there a clear H1? Do headings follow logical order?
2. **Visual weight distribution:** Does the eye flow naturally through the content?
3. **Whitespace:** Is spacing consistent? Are elements properly grouped?
4. **Typography:** Is text readable? Proper line lengths (45-75 characters)?
5. **Color usage:** Is color used consistently for meaning (actions, states, emphasis)?

## Step 4: Interaction State Inventory

For each interactive element on the page:

1. **Buttons:** Hover state, focus state, active state, disabled state
2. **Links:** Hover, focus, visited (if applicable)
3. **Form inputs:** Empty, filled, focused, error, disabled
4. **Cards/list items:** Hover if clickable

Check using browser tools:
- Hover over elements to test hover states
- Tab through the page to test focus states
- Check if focus is visible and meets contrast requirements

## Step 5: Accessibility Quick-Check

Not a full WCAG audit -- just the visible basics:

1. **Focus indicators:** Are they visible when tabbing?
2. **Color contrast:** Do text elements appear readable against backgrounds?
3. **Semantic structure:** Use browser snapshot to check landmark regions and heading structure
4. **Form labels:** Are inputs visually associated with labels?
5. **Alt text:** Do images have visible alt text indicators?

## Step 6: UX Debt Inventory

Flag issues found:

- Missing interaction states (no hover, no focus indicator)
- Broken responsive behavior (overflow, overlap, tiny text)
- Inconsistent spacing or typography
- Missing empty states ("what does this look like with no data?")
- Missing error states
- Missing loading states
- Navigation issues (unclear where you are, how to go back)

## Step 6b: Persona-Driven Evaluation (Assembly projects only)

If the project has a `tests/ux/` directory with persona files, run an additional evaluation pass:

1. Read `tests/ux/personas/_index.md` to load the persona spectrum
2. Read `tests/ux/heuristics/governance-specific.md` for G1-G10 governance heuristics
3. For each page assessed, evaluate through the lens of at least 3 personas:
   - **Lowest tech comfort** (e.g., Aisha, reluctant board member): Does this work on mobile? Is it anxiety-free?
   - **Lowest governance knowledge** (e.g., David, casual member): Can the primary action be completed in under 15 seconds without jargon?
   - **Most restricted permissions** (e.g., Alex, new probationary): Are permission boundaries clear and non-frustrating?
4. Check relevant governance heuristics (G1-G10) against the assessed pages
5. Reference the coverage matrix (`tests/ux/coverage-matrix.md`) for expected outcomes per persona

Add a "Persona Evaluation" section to the UX report:

```markdown
## Persona Evaluation
| Persona | Page | Expected | Actual | Friction Points |
|---------|------|----------|--------|-----------------|
| casual-member | /proposals | SUCCESS | FRICTION | Position types unexplained |

## Governance Heuristics
| ID | Heuristic | Status | Notes |
|----|-----------|--------|-------|
| G1 | Permission Clarity | PASS/FAIL | |
| G2 | Lifecycle Comprehension | PASS/FAIL | |
```

## Step 7: Produce Report

Structure the Current UX Report as:

```markdown
## Screenshots
### Mobile (375px)
[Screenshot description or reference]

### Tablet (768px)
[Screenshot description or reference]

### Desktop (1440px)
[Screenshot description or reference]

## Visual Hierarchy
- [Assessment of heading structure, whitespace, typography]

## Interaction States
| Element | Hover | Focus | Active | Disabled | Notes |
|---------|-------|-------|--------|----------|-------|
| Primary button | yes | yes | no | n/a | Focus ring low contrast |

## Accessibility Quick-Check
- Focus indicators: [pass/fail/partial]
- Color contrast: [pass/fail/partial]
- Semantic structure: [pass/fail/partial]
- Form labels: [pass/fail/partial]

## UX Debt
- [Issue]: [Location] -- [Impact]
```
