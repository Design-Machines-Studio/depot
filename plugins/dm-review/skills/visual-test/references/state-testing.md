# Interactive State Testing Matrix

For each element type, test the listed states using the specified Playwright MCP tools. Use `browser_snapshot` to discover interactive elements by ARIA role — never hardcode selectors.

---

## Buttons

| State | How to trigger | What to verify |
|-------|---------------|----------------|
| Default | `browser_navigate` (initial render) | Visible, correctly styled, readable text |
| Hover | `browser_hover` on the button ref | Visual change (color, shadow, background shift) |
| Focus | `browser_press_key` Tab to reach it | Focus ring visible with 3:1 contrast (WCAG 2.4.7) |
| Active | `browser_click` the button | Visual feedback on press (color change, depression) |
| Disabled | Find `[disabled]` or `[aria-disabled="true"]` in snapshot | Visually distinct from enabled, not in tab order |
| Loading | `browser_click` action button, check during request | Spinner or text change visible, button disabled, `aria-busy` present |

---

## Links

| State | How to trigger | What to verify |
|-------|---------------|----------------|
| Default | Initial render | Identifiable as a link (underline, color, or both) |
| Hover | `browser_hover` on the link ref | Visual change (underline or color shift) |
| Focus | `browser_press_key` Tab to reach it | Focus ring visible, not clipped by overflow |

---

## Form Inputs

| State | How to trigger | What to verify |
|-------|---------------|----------------|
| Empty | Initial render | Label visible and associated, placeholder if present |
| Focused | `browser_press_key` Tab to reach input | Focus ring visible, label still visible (not replaced by placeholder) |
| Filled | `browser_fill_form` with test values | Value displays correctly, no overflow or clipping |
| Error | Submit with empty required field, or `browser_evaluate` to trigger validation | Error message visible, `aria-describedby` links error to input, error has `role="alert"` or `aria-live` |
| Disabled | Find `[disabled]` inputs in snapshot | Visually distinct, skipped by Tab navigation |

### Form-wide checks

- Submit the form empty to test all required field validations simultaneously
- Check that error summary (if present) links to each invalid field
- Verify tab order follows visual layout order

---

## Accordions / Disclosures

| State | How to trigger | What to verify |
|-------|---------------|----------------|
| Collapsed | Initial render | Trigger button visible, content hidden, `aria-expanded="false"` |
| Expanded | `browser_click` on trigger | Content visible and readable, `aria-expanded="true"` |
| Re-collapsed | `browser_click` trigger again | Content hidden, focus stays on trigger |
| Focus | `browser_press_key` Tab to trigger | Focus ring visible on the trigger button |

---

## Dialogs / Modals

| State | How to trigger | What to verify |
|-------|---------------|----------------|
| Closed | Initial render | Dialog not visible in viewport |
| Open | `browser_click` on dialog trigger | Dialog visible, backdrop present, focus moves inside dialog |
| Focus trap | `browser_press_key` Tab repeatedly inside open dialog | Focus cycles within dialog boundaries, never escapes to page behind |
| Dismiss via Escape | `browser_press_key` Escape | Dialog closes, focus returns to the trigger element |
| Dismiss via backdrop | `browser_click` outside dialog (if applicable) | Dialog closes, focus returns to trigger |

### Focus trap verification

1. Open the dialog
2. `browser_snapshot` to find all focusable elements inside
3. Tab through all elements — count matches
4. Tab one more time — focus should return to first focusable element inside dialog

---

## Tabs

| State | How to trigger | What to verify |
|-------|---------------|----------------|
| Default | Initial render | First tab selected (`aria-selected="true"`), first panel visible |
| Switch via click | `browser_click` on another tab | New panel visible, old panel hidden, `aria-selected` updates |
| Switch via keyboard | `browser_press_key` ArrowRight / ArrowLeft | Tab selection moves, panel content changes |
| Focus | `browser_press_key` Tab into tab list | Focus visible on the active tab |

---

## Dropdown / Select Menus

| State | How to trigger | What to verify |
|-------|---------------|----------------|
| Closed | Initial render | Selected value shown, dropdown menu hidden |
| Open | `browser_click` on trigger | Options list visible, not clipped by viewport |
| Navigate | `browser_press_key` ArrowDown / ArrowUp | Options highlight sequentially |
| Select | `browser_press_key` Enter on highlighted option | Option selected, menu closes, trigger shows new value |
| Dismiss | `browser_press_key` Escape | Menu closes without changing selection |

---

## Toast / Notification Messages

| State | How to trigger | What to verify |
|-------|---------------|----------------|
| Appear | Trigger the action that produces the toast | Toast visible, has `role="alert"` or `aria-live="polite"` |
| Auto-dismiss | `browser_wait_for` the toast text to disappear | Toast removes itself after timeout |
| Manual dismiss | `browser_click` close button (if present) | Toast removed, focus managed appropriately |

---

## Loading / Async States (Datastar SSE)

| State | How to trigger | What to verify |
|-------|---------------|----------------|
| Idle | Initial render | Normal content visible, no spinners |
| Loading | `browser_click` on action that triggers SSE/fetch | Loading indicator visible (spinner, skeleton, text), action button disabled or hidden, `aria-busy="true"` on updating region |
| Success | `browser_wait_for` completion text/element | Content updated, loading indicator removed, live region announces change |
| Error | Trigger error condition (if testable) | Error message visible, has `role="alert"`, retry option available |

### SSE-specific checks

After a Datastar morph:

1. `browser_snapshot` to verify DOM structure is intact
2. Check that focus was not lost (current focus element still exists)
3. Verify `aria-live` region announced the change

---

## General Rules

1. **Discover elements via `browser_snapshot`** — use ARIA roles (button, link, textbox, tab, dialog, etc.) to find elements, not CSS selectors
2. **Screenshot each state** — take a `browser_take_screenshot` after triggering each state for visual evidence
3. **Test keyboard before mouse** — if an element can't be reached via Tab, that's a P1 finding regardless of mouse behavior
4. **Reset between tests** — `browser_navigate` back to the page URL before testing a different component to ensure clean state
5. **Skip states that don't apply** — if there are no dialogs on the page, skip the dialog tests entirely
6. **Time-dependent states** — for loading and toast states, use `browser_wait_for` with reasonable timeouts (5 seconds default)
