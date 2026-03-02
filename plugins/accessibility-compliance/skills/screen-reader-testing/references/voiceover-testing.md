# VoiceOver Testing Guide

Detailed VoiceOver commands, Safari integration, and macOS configuration for accessibility testing.

---

## Setup

### Enable VoiceOver

- **Toggle:** Cmd + F5
- **Touch Bar Macs:** Triple-press Touch ID
- **Settings:** System Settings > Accessibility > VoiceOver

### Configure for Testing

1. Open VoiceOver Utility (VO + F8)
2. Set verbosity to "High" for thorough testing
3. Enable "Web > Automatically speak the web page" (for initial load testing)
4. Set Navigation > "Group items when navigating" to understand grouping

### Test in Safari

Always test VoiceOver in Safari first — it has the best integration on macOS. Then verify in Chrome and Firefox for cross-browser issues.

---

## Command Reference

VO = Control + Option (the "VoiceOver keys")

### Navigation

| Action | Keys | Notes |
|--------|------|-------|
| Next element | VO + Right Arrow | Steps through every element |
| Previous element | VO + Left Arrow | |
| Next heading | VO + Cmd + H | Navigate by heading |
| Previous heading | VO + Cmd + Shift + H | |
| Next landmark | VO + Cmd + L | Navigate by ARIA landmark |
| Next link | VO + Cmd + J | |
| Next form control | VO + Cmd + Shift + J | |
| Next table | VO + Cmd + T | |
| Next list | VO + Cmd + X | |

### Interaction

| Action | Keys | Notes |
|--------|------|-------|
| Activate (click) | VO + Space | Press the focused element |
| Start interaction | VO + Shift + Down Arrow | Enter a group/element (table, toolbar) |
| Stop interaction | VO + Shift + Up Arrow | Exit a group/element |
| Read from cursor | VO + A | Read everything from current position |
| Stop reading | Control | |
| Read current element | VO + F3 | |

### Web Rotor

| Action | Keys | Notes |
|--------|------|-------|
| Open rotor | VO + U | Master navigation menu |
| Switch rotor lists | Left/Right arrows | Headings, links, landmarks, forms, etc. |
| Navigate rotor list | Up/Down arrows | Move through items |
| Go to item | Enter | Jump to selected item |
| Close rotor | Escape | |

### Information

| Action | Keys | Notes |
|--------|------|-------|
| Read title | VO + F2 | Current page/window title |
| Read URL | VO + F7 | Current URL |
| Read element description | VO + F3 | Full description of current element |
| Item count in group | VO + F3, F3 | Number of items in current group |

---

## Testing Workflows

### Workflow 1: Page Structure Audit

1. **Open the page** in Safari
2. **Enable VoiceOver** (Cmd + F5)
3. **Open Rotor** (VO + U)
4. **Navigate to Landmarks** (Left/Right arrows until "Landmarks" list)
5. **Verify expected landmarks:**
   - banner (header)
   - navigation (nav — check aria-label if multiple)
   - main
   - contentinfo (footer)
   - complementary (sidebar, if applicable)
6. **Switch to Headings** in the Rotor
7. **Verify heading hierarchy:**
   - One h1
   - No skipped levels
   - Headings describe content accurately

**Record findings for each landmark and heading.**

### Workflow 2: Form Testing

1. **Tab to the first form field**
2. **For each field, note what VoiceOver announces:**
   - Field label (what it's for)
   - Field type (text field, checkbox, etc.)
   - Required state
   - Current value
   - Help text / description
3. **Submit the form with invalid data**
4. **Verify error handling:**
   - Are errors announced immediately? (role="alert")
   - Does focus move to the first error?
   - Is each error associated with its field?
5. **Submit with valid data**
6. **Verify success message** is announced (role="status")

### Workflow 3: Interactive Widget Testing

For each custom widget (tabs, accordions, dialogs, menus):

1. **Tab to the widget trigger**
2. **Note the announced role** (tab, button, etc.)
3. **Activate** (Enter/Space)
4. **Use expected keyboard controls** (arrows for tabs/menus, Escape for dialogs)
5. **Verify state announcements** (expanded/collapsed, selected, checked)
6. **Close/deactivate and verify focus returns** to trigger

### Workflow 4: Dynamic Content (SSE/Datastar)

1. **Position VoiceOver on or near the dynamic area**
2. **Trigger the update** (click button, submit form)
3. **Listen for announcement** — does VoiceOver speak the new content?
4. **Check the live region:**
   - `aria-live="polite"` for non-urgent updates
   - `aria-live="assertive"` for errors/alerts
5. **Verify focus** — where is focus after the update?

---

## Common VoiceOver + Safari Issues

### Issue: Links Announced as "Link, Link"

Safari sometimes double-announces link text. This is a Safari/VoiceOver quirk, not a code issue. Verify the `<a>` element has proper text content or `aria-label`.

### Issue: `role="region"` Not Announced

VoiceOver only announces `role="region"` if it has an `aria-label` or `aria-labelledby`. Regions without labels are ignored.

```html
<!-- Not announced -->
<div role="region">...</div>

<!-- Announced as "Recent proposals, region" -->
<div role="region" aria-label="Recent proposals">...</div>
```

### Issue: Live Regions Not Firing

Common causes:
1. The `aria-live` element was added to the DOM at the same time as its content — it must exist BEFORE content is injected
2. The element was replaced entirely (including the `aria-live` attribute) — keep the live region wrapper stable
3. Content was updated via `innerHTML` on the live region itself — update a child element instead

### Issue: `<dialog>` Focus Not Trapped

Safari + VoiceOver may allow VO navigation outside a `<dialog>`. The `inert` attribute on background content helps:

```html
<main id="main" inert>...</main>
<dialog open>...</dialog>
```

Native `<dialog>` with `showModal()` handles this automatically in most cases.

### Issue: SVG Not Announced

```html
<!-- Not announced (treated as decorative) -->
<svg>...</svg>

<!-- Announced correctly -->
<svg role="img" aria-label="Company logo">...</svg>

<!-- Hidden from AT (correct for decorative) -->
<svg aria-hidden="true">...</svg>
```

---

## Safari Accessibility Preferences

For thorough testing, enable these in Safari:

1. **Safari > Settings > Advanced > Show Develop menu**
2. **Develop > Experimental Features** — check for accessibility-related flags
3. **Safari > Settings > Advanced > Accessibility** — "Press Tab to highlight each item on a webpage" (this enables Tab key for links, not just form controls)

Without step 3, Safari only tabs to form controls by default, which can give a false impression of keyboard accessibility.

---

## Testing Matrix

For each page, fill in this matrix:

| Test | Pass | Fail | Notes |
|------|------|------|-------|
| Skip link works | | | |
| All landmarks present | | | |
| Heading hierarchy correct | | | |
| All images have alt text | | | |
| All links are descriptive | | | |
| All form fields labeled | | | |
| Tab order logical | | | |
| Focus visible on all elements | | | |
| Keyboard can reach everything | | | |
| No keyboard traps | | | |
| Dynamic updates announced | | | |
| Error messages announced | | | |
| Success messages announced | | | |
| Dialogs trap focus | | | |
| Escape closes overlays | | | |
