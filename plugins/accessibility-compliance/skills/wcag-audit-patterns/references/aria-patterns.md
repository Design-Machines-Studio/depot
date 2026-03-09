# ARIA Authoring Practices Pattern Library

Accessible widget patterns following the WAI-ARIA Authoring Practices Guide (APG). Each pattern includes the required ARIA attributes, keyboard interactions, and implementation guidance for Live Wires + Templ projects.

## Contents
- [The First Rule of ARIA](#the-first-rule-of-aria) (line 7)
- [Dialog (Modal)](#dialog-modal) (line 22) — Structure, Templ component, keyboard
- [Tabs](#tabs) (line 71) — Structure, requirements, keyboard, activation modes
- [Accordion](#accordion) (line 125) — Structure, requirements, keyboard
- [Disclosure (Show/Hide)](#disclosure-showhide) (line 176)
- [Menu Button](#menu-button) (line 195) — Structure, requirements, keyboard
- [Combobox (Autocomplete)](#combobox-autocomplete) (line 234) — Structure, requirements, keyboard
- [Alert and Status Messages](#alert-and-status-messages) (line 273) — Alert (assertive), Status (polite), rules
- [Toast / Notification](#toast--notification) (line 314) — Requirements
- [Tooltip](#tooltip) (line 343) — Requirements
- [Loading / Progress](#loading--progress) (line 366) — Indeterminate, determinate, completion

---

## The First Rule of ARIA

Use native HTML elements whenever possible. ARIA is a repair tool for when native semantics are insufficient.

| Instead of | Use |
|------------|-----|
| `<div role="button">` | `<button>` |
| `<div role="navigation">` | `<nav>` |
| `<div role="dialog">` | `<dialog>` |
| `<span role="checkbox">` | `<input type="checkbox">` |
| `<div role="heading" aria-level="2">` | `<h2>` |
| `<div role="list"><div role="listitem">` | `<ul><li>` |

---

## Dialog (Modal)

### HTML Structure

```html
<dialog class="dialog" aria-labelledby="dialog-title">
  <h2 id="dialog-title">Confirm Action</h2>
  <p>Are you sure you want to delete this proposal?</p>
  <div class="cluster">
    <button type="button" class="button" data-action="cancel">Cancel</button>
    <button type="button" class="button button--danger" data-action="confirm">Delete</button>
  </div>
</dialog>
```

### Templ Component

```go
templ ConfirmDialog(id, title, message string) {
  <dialog id={id} class="dialog" aria-labelledby={id + "-title"}>
    <h2 id={id + "-title"}>{title}</h2>
    <p>{message}</p>
    <div class="cluster">
      <button type="button" class="button" value="cancel" formmethod="dialog">Cancel</button>
      { children... }
    </div>
  </dialog>
}
```

### Requirements

- `aria-labelledby` pointing to the dialog title
- Focus moves to first focusable element (or the dialog itself) on open
- Focus trapped inside dialog while open
- Escape key closes the dialog
- Focus returns to the triggering element on close
- Background content is inert (native `<dialog>` handles this)

### Keyboard

| Key | Action |
|-----|--------|
| Tab | Move focus between dialog controls |
| Escape | Close dialog |
| Enter | Activate focused button |

---

## Tabs

### HTML Structure

```html
<div class="tabs">
  <div role="tablist" aria-label="Project sections">
    <button role="tab" id="tab-overview" aria-selected="true" aria-controls="panel-overview">
      Overview
    </button>
    <button role="tab" id="tab-members" aria-selected="false" aria-controls="panel-members" tabindex="-1">
      Members
    </button>
    <button role="tab" id="tab-settings" aria-selected="false" aria-controls="panel-settings" tabindex="-1">
      Settings
    </button>
  </div>
  <div role="tabpanel" id="panel-overview" aria-labelledby="tab-overview">
    <!-- Overview content -->
  </div>
  <div role="tabpanel" id="panel-members" aria-labelledby="tab-members" hidden>
    <!-- Members content -->
  </div>
  <div role="tabpanel" id="panel-settings" aria-labelledby="tab-settings" hidden>
    <!-- Settings content -->
  </div>
</div>
```

### Requirements

- Tablist has `aria-label` describing the tab group
- Each tab has `role="tab"`, `aria-selected`, and `aria-controls`
- Each panel has `role="tabpanel"` and `aria-labelledby`
- Only the active tab is in tab order (`tabindex="0"`), others use `tabindex="-1"`
- Inactive panels are `hidden`

### Keyboard

| Key | Action |
|-----|--------|
| Arrow Left/Right | Move between tabs |
| Home | First tab |
| End | Last tab |
| Tab | Move focus from tab to panel content |

### Activation

Two approaches:
- **Automatic activation:** Arrow keys select and activate immediately (recommended for fast-loading content)
- **Manual activation:** Arrow keys move focus, Enter/Space activates (for slow-loading content)

---

## Accordion

### HTML Structure

```html
<div class="accordion stack">
  <div class="accordion-item">
    <h3>
      <button aria-expanded="true" aria-controls="panel-1">
        Section Title
        <svg aria-hidden="true"><!-- chevron icon --></svg>
      </button>
    </h3>
    <div id="panel-1" role="region" aria-labelledby="heading-1">
      <!-- Section content -->
    </div>
  </div>
  <div class="accordion-item">
    <h3>
      <button aria-expanded="false" aria-controls="panel-2">
        Another Section
        <svg aria-hidden="true"><!-- chevron icon --></svg>
      </button>
    </h3>
    <div id="panel-2" role="region" aria-labelledby="heading-2" hidden>
      <!-- Hidden content -->
    </div>
  </div>
</div>
```

### Requirements

- Trigger is a `<button>` inside the heading element
- `aria-expanded` reflects current state
- `aria-controls` links button to panel
- Panel has `role="region"` and `aria-labelledby` (for 6 or fewer sections)
- Icons are `aria-hidden="true"`

### Keyboard

| Key | Action |
|-----|--------|
| Enter / Space | Toggle section |
| Arrow Down | Next accordion header |
| Arrow Up | Previous accordion header |
| Home | First accordion header |
| End | Last accordion header |

---

## Disclosure (Show/Hide)

Simpler than accordion — a single toggle section.

```html
<div>
  <button aria-expanded="false" aria-controls="details-1">
    Show details
  </button>
  <div id="details-1" hidden>
    <!-- Hidden content -->
  </div>
</div>
```

Keyboard: Enter/Space toggles.

---

## Menu Button

### HTML Structure

```html
<div class="menu-container">
  <button aria-haspopup="true" aria-expanded="false" aria-controls="menu-1">
    Actions
    <svg aria-hidden="true"><!-- dropdown icon --></svg>
  </button>
  <ul role="menu" id="menu-1" hidden>
    <li role="menuitem"><button>Edit</button></li>
    <li role="menuitem"><button>Duplicate</button></li>
    <li role="separator"></li>
    <li role="menuitem"><button>Delete</button></li>
  </ul>
</div>
```

### Requirements

- Trigger button has `aria-haspopup="true"` and `aria-expanded`
- Menu has `role="menu"`, items have `role="menuitem"`
- Only one item in tab order at a time (roving tabindex)
- Focus moves to first item on open

### Keyboard

| Key | Action |
|-----|--------|
| Enter / Space | Open menu, focus first item |
| Arrow Down | Next menu item |
| Arrow Up | Previous menu item |
| Escape | Close menu, return focus to button |
| Home | First menu item |
| End | Last menu item |

---

## Combobox (Autocomplete)

### HTML Structure

```html
<div class="combobox-container">
  <label for="search-input">Search members</label>
  <div role="combobox" aria-expanded="false" aria-haspopup="listbox">
    <input id="search-input" type="text"
           aria-autocomplete="list"
           aria-controls="search-listbox"
           aria-activedescendant="">
  </div>
  <ul role="listbox" id="search-listbox" hidden>
    <li role="option" id="opt-1">Alice Johnson</li>
    <li role="option" id="opt-2">Bob Smith</li>
  </ul>
</div>
```

### Requirements

- Input has `aria-autocomplete="list"` (or `"both"` for inline completion)
- `aria-activedescendant` tracks the highlighted option
- Listbox appears below the input
- Selected option reflected in the input value

### Keyboard

| Key | Action |
|-----|--------|
| Arrow Down | Open listbox / next option |
| Arrow Up | Previous option |
| Enter | Select highlighted option |
| Escape | Close listbox |
| Type | Filter options |

---

## Alert and Status Messages

### Alert (Assertive — interrupts)

```html
<div role="alert">
  Error: Email address is required.
</div>
```

Or inject dynamically:

```html
<div aria-live="assertive" aria-atomic="true" id="error-container"></div>
```

### Status (Polite — waits for pause)

```html
<div role="status">
  3 results found.
</div>
```

Or for Datastar-updated content:

```html
<div aria-live="polite" aria-atomic="true" id="status-container">
  <!-- Datastar updates this content -->
</div>
```

### Rules

- Use `role="alert"` / `aria-live="assertive"` only for errors and urgent messages
- Use `role="status"` / `aria-live="polite"` for non-urgent updates (search results, save confirmations)
- The live region element must exist in the DOM before content is injected
- `aria-atomic="true"` announces the entire region, not just the changed part

---

## Toast / Notification

```html
<!-- Live region must be in DOM on page load (empty is fine) -->
<div class="toast-container" role="status" aria-live="polite" aria-atomic="true">
  <!-- Toasts injected here -->
</div>
```

When showing a toast:

```html
<div class="toast-container" role="status" aria-live="polite" aria-atomic="true">
  <div class="toast">
    Proposal saved successfully.
    <button aria-label="Dismiss notification">×</button>
  </div>
</div>
```

### Requirements

- Container is `role="status"` with `aria-live="polite"`
- Dismiss button has accessible label
- Auto-dismiss timing must be generous (5+ seconds) or dismissable
- Don't use `aria-live="assertive"` for success toasts (too intrusive)

---

## Tooltip

```html
<button aria-describedby="tooltip-1">
  <svg aria-hidden="true"><!-- info icon --></svg>
  <span class="visually-hidden">More info</span>
</button>
<div role="tooltip" id="tooltip-1" hidden>
  This action cannot be undone.
</div>
```

### Requirements

- Trigger has `aria-describedby` pointing to tooltip
- Tooltip has `role="tooltip"`
- Appears on hover AND focus
- Dismissible with Escape (WCAG 1.4.13)
- User can hover over tooltip content
- Persistent until dismissed or trigger loses focus/hover

---

## Loading / Progress

### Indeterminate (spinner)

```html
<div role="status" aria-live="polite">
  <span class="spinner" aria-hidden="true"></span>
  Loading proposals...
</div>
```

### Determinate (progress bar)

```html
<div role="progressbar" aria-valuenow="65" aria-valuemin="0" aria-valuemax="100" aria-label="Upload progress">
  <div class="progress-fill" style="width: 65%"></div>
</div>
```

### After loading completes

Update the live region:

```html
<div role="status" aria-live="polite">
  12 proposals loaded.
</div>
```
