# WCAG 2.2 Level AA Checklist

Complete success criteria checklist for WCAG 2.2 Level AA compliance. Organized by principle with testing methods.

---

## 1. Perceivable

### 1.1 Text Alternatives

| SC | Name | Level | Test |
|----|------|-------|------|
| 1.1.1 | Non-text Content | A | Every `<img>` has `alt`. Decorative images use `alt=""`. Form image buttons have descriptive `alt`. CAPTCHAs provide alternatives. |

### 1.2 Time-Based Media

| SC | Name | Level | Test |
|----|------|-------|------|
| 1.2.1 | Audio-only and Video-only | A | Audio has transcript. Video has transcript or audio description. |
| 1.2.2 | Captions (Prerecorded) | A | Video has synchronized captions. |
| 1.2.3 | Audio Description or Media Alternative | A | Video has audio description or full text alternative. |
| 1.2.5 | Audio Description (Prerecorded) | AA | Video has audio description track. |

### 1.3 Adaptable

| SC | Name | Level | Test |
|----|------|-------|------|
| 1.3.1 | Info and Relationships | A | Headings use `<h1>`-`<h6>`. Lists use `<ul>`/`<ol>`/`<dl>`. Tables use `<th>`, `scope`, `<caption>`. Forms use `<label>`, `<fieldset>`, `<legend>`. |
| 1.3.2 | Meaningful Sequence | A | DOM order matches visual reading order. CSS does not create misleading reordering. |
| 1.3.3 | Sensory Characteristics | A | Instructions don't rely solely on shape, size, position, or sound. |
| 1.3.4 | Orientation | AA | Content works in both portrait and landscape. |
| 1.3.5 | Identify Input Purpose | AA | Input fields use appropriate `autocomplete` attributes for personal data. |

### 1.4 Distinguishable

| SC | Name | Level | Test |
|----|------|-------|------|
| 1.4.1 | Use of Color | A | Color is not the only visual means of conveying info. |
| 1.4.2 | Audio Control | A | Auto-playing audio (>3 sec) can be paused/stopped/volume controlled. |
| 1.4.3 | Contrast (Minimum) | AA | Text: 4.5:1. Large text (18px+ or 14px+ bold): 3:1. |
| 1.4.4 | Resize Text | AA | Text resizable to 200% without loss of content or function. |
| 1.4.5 | Images of Text | AA | Real text used instead of images of text (except logos). |
| 1.4.10 | Reflow | AA | Content works at 320px width without horizontal scrolling. |
| 1.4.11 | Non-text Contrast | AA | UI components and graphics: 3:1 contrast against adjacent colors. |
| 1.4.12 | Text Spacing | AA | No content loss when: line-height 1.5x, paragraph spacing 2x, letter spacing 0.12em, word spacing 0.16em. |
| 1.4.13 | Content on Hover or Focus | AA | Dismissible (Escape), hoverable (mouse can move to tooltip), persistent (stays until dismissed). |

---

## 2. Operable

### 2.1 Keyboard Accessible

| SC | Name | Level | Test |
|----|------|-------|------|
| 2.1.1 | Keyboard | A | All functionality available via keyboard. |
| 2.1.2 | No Keyboard Trap | A | Focus can always be moved away from any component. |
| 2.1.4 | Character Key Shortcuts | A | Single-character shortcuts can be remapped or disabled. |

### 2.4 Navigable

| SC | Name | Level | Test |
|----|------|-------|------|
| 2.4.1 | Bypass Blocks | A | Skip navigation link or ARIA landmarks. |
| 2.4.2 | Page Titled | A | Descriptive `<title>` element. |
| 2.4.3 | Focus Order | A | Tab order follows logical reading sequence. |
| 2.4.4 | Link Purpose (In Context) | A | Link text + context identifies destination. |
| 2.4.5 | Multiple Ways | AA | Two+ ways to find pages (nav, search, sitemap). |
| 2.4.6 | Headings and Labels | AA | Headings and labels describe topic or purpose. |
| 2.4.7 | Focus Visible | AA | Keyboard focus indicator visible on all elements. |
| 2.4.11 | Focus Not Obscured (Minimum) | AA | Focused element not fully hidden by other content. |
| 2.4.13 | Focus Appearance | AAA (recommended) | Focus indicator meets minimum area and contrast. |

### 2.5 Input Modalities

| SC | Name | Level | Test |
|----|------|-------|------|
| 2.5.1 | Pointer Gestures | A | Multi-point/path gestures have single-pointer alternative. |
| 2.5.2 | Pointer Cancellation | A | Down-event doesn't trigger action (use click/up-event). |
| 2.5.3 | Label in Name | A | Accessible name contains visible label text. |
| 2.5.4 | Motion Actuation | A | Motion-triggered functions have UI alternative and can be disabled. |
| 2.5.7 | Dragging Movements | AA | Drag operations have single-pointer alternative. |
| 2.5.8 | Target Size (Minimum) | AA | Targets at least 24x24px (with spacing exceptions). |

---

## 3. Understandable

### 3.1 Readable

| SC | Name | Level | Test |
|----|------|-------|------|
| 3.1.1 | Language of Page | A | `<html lang="en">` (or appropriate language code). |
| 3.1.2 | Language of Parts | AA | Content in other languages marked with `lang` attribute. |

### 3.2 Predictable

| SC | Name | Level | Test |
|----|------|-------|------|
| 3.2.1 | On Focus | A | Focus doesn't trigger unexpected context changes. |
| 3.2.2 | On Input | A | Changing input value doesn't auto-submit or navigate. |
| 3.2.3 | Consistent Navigation | AA | Navigation in same order across pages. |
| 3.2.4 | Consistent Identification | AA | Same functions have same labels across pages. |
| 3.2.6 | Consistent Help | A | Help mechanisms in same relative location across pages. |

### 3.3 Input Assistance

| SC | Name | Level | Test |
|----|------|-------|------|
| 3.3.1 | Error Identification | A | Errors described in text (not just color). |
| 3.3.2 | Labels or Instructions | A | Input fields have visible labels or instructions. |
| 3.3.3 | Error Suggestion | AA | Error messages suggest how to fix the problem. |
| 3.3.4 | Error Prevention (Legal, Financial, Data) | AA | Submissions reversible, checked, or confirmed. |
| 3.3.7 | Redundant Entry | A | Previously entered info auto-populated or selectable. |
| 3.3.8 | Accessible Authentication (Minimum) | AA | No cognitive function tests for login (or alternatives provided). |

---

## 4. Robust

### 4.1 Compatible

| SC | Name | Level | Test |
|----|------|-------|------|
| 4.1.2 | Name, Role, Value | A | Custom components expose accessible name, role, and state. |
| 4.1.3 | Status Messages | AA | Status messages announced by screen readers without focus change. |

---

## Quick Audit Shortlist

For a rapid audit, check these 10 criteria first (they account for ~80% of real-world failures):

1. **1.1.1** — Image alt text
2. **1.3.1** — Heading structure and form labels
3. **1.4.3** — Color contrast
4. **2.1.1** — Keyboard operability
5. **2.4.3** — Focus order
6. **2.4.7** — Focus visible
7. **2.5.8** — Target size
8. **3.3.2** — Form labels
9. **4.1.2** — Custom widget accessibility
10. **4.1.3** — Status messages (live regions)
