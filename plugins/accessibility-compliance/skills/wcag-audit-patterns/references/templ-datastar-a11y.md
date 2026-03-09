# Go + Templ + Datastar Accessibility Patterns

Accessibility patterns specific to the Go + Templ + Datastar stack used in Assembly and similar projects.

## Contents
- [Templ Component Accessibility](#templ-component-accessibility) (line 14) -- Accessible props, headings, layouts, and forms
- [Datastar Accessibility](#datastar-accessibility) (line 139) -- Focus loss, live regions, and loading states
- [SSE Response Accessibility Patterns](#sse-response-accessibility-patterns) (line 249) -- Server-side feedback and error patterns
- [Go Handler Accessibility Checklist](#go-handler-accessibility-checklist) (line 303) -- Handler-level a11y verification items
- [Testing Datastar Interactions](#testing-datastar-interactions) (line 318) -- Manual and Playwright testing protocol

---

## Templ Component Accessibility

### Enforce Accessible Props

Design Templ components to require accessibility attributes by construction:

```go
// GOOD: alt is required
templ Image(src, alt string) {
  <img src={src} alt={alt} loading="lazy">
}

// GOOD: label is required for form fields
templ TextField(id, label string, required bool) {
  <div class="stack-compact">
    <label for={id}>{label}</label>
    <input
      type="text"
      id={id}
      name={id}
      if required {
        required
        aria-required="true"
      }
    >
  </div>
}

// GOOD: Decorative image explicitly marked
templ DecorativeImage(src string) {
  <img src={src} alt="" role="presentation">
}
```

### Heading Level Props

Allow dynamic heading levels so components can be nested correctly:

```go
// GOOD: Heading level is configurable
templ SectionCard(title string, headingLevel int) {
  <div class="box stack">
    switch headingLevel {
      case 2:
        <h2>{title}</h2>
      case 3:
        <h3>{title}</h3>
      case 4:
        <h4>{title}</h4>
      default:
        <h3>{title}</h3>
    }
    { children... }
  </div>
}

// BAD: Hardcoded heading level
templ SectionCard(title string) {
  <div class="box stack">
    <h2>{title}</h2>  // Breaks when nested inside an h2 context
    { children... }
  </div>
}
```

### Page Layout Template

Every page template should include landmarks and skip link:

```go
templ PageLayout(meta PageMeta) {
  <!DOCTYPE html>
  <html lang="en">
    <head>
      <title>{meta.Title} — {meta.SiteName}</title>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
    </head>
    <body class={meta.BodyClass}>
      <a href="#main" class="skip-link">Skip to main content</a>

      <header>
        <nav aria-label="Primary">
          { children... }
        </nav>
      </header>

      <main id="main">
        { children... }
      </main>

      <footer>
        { children... }
      </footer>
    </body>
  </html>
}
```

### Form Error Pattern

```go
templ FormField(id, label, errorMsg string) {
  <div class="stack-compact">
    <label for={id}>{label}</label>
    <input
      type="text"
      id={id}
      name={id}
      if errorMsg != "" {
        aria-invalid="true"
        aria-describedby={id + "-error"}
      }
    >
    if errorMsg != "" {
      <p id={id + "-error"} class="text-sm text-red-600" role="alert">
        {errorMsg}
      </p>
    }
  </div>
}
```

---

## Datastar Accessibility

Datastar uses server-sent events (SSE) and DOM morphing to update pages without full reloads. This creates specific accessibility challenges.

### Challenge 1: Focus Loss After Morph

When Datastar morphs the DOM, elements are replaced. If the focused element is inside the morphed region, focus jumps to the document body.

**Solution: Explicit focus management**

```html
<!-- Server response includes focus directive -->
<div id="proposal-form"
     data-on-load="document.getElementById('proposal-title').focus()">
  <input id="proposal-title" type="text" name="title">
  <!-- rest of form -->
</div>
```

Or use a Datastar action to restore focus:

```html
<form data-on-submit__prevent="$$post('/api/proposals')"
      data-on-load="this.querySelector('[autofocus]')?.focus()">
  <!-- form fields -->
</form>
```

### Challenge 2: Silent Content Updates

When SSE pushes content updates, screen readers don't announce them unless you use live regions.

**Solution: Live region wrappers**

```html
<!-- The live region wrapper MUST exist in the initial page HTML -->
<div aria-live="polite" aria-atomic="true" id="status-message">
  <!-- Datastar will merge content here -->
</div>

<!-- For lists that update -->
<div aria-live="polite" aria-relevant="additions removals">
  <ul id="proposal-list">
    <!-- SSE updates morph list items here -->
  </ul>
</div>
```

**Important:** The `aria-live` attribute must be on an element that EXISTS before the first update. Don't add `aria-live` to the morphed content — it needs to be on a stable parent.

### Challenge 3: Loading States

When a Datastar action triggers an SSE request, the user needs to know something is happening.

```html
<!-- Button with loading state -->
<button data-on-click="$$post('/api/proposals')"
        data-attr-disabled="$loading"
        data-attr-aria-busy="$loading">
  <span data-show="!$loading">Save Proposal</span>
  <span data-show="$loading" class="visually-hidden">Saving...</span>
  <span data-show="$loading" aria-hidden="true">
    <!-- spinner SVG -->
  </span>
</button>

<!-- Status announcement after completion -->
<div role="status" aria-live="polite" id="save-status">
  <!-- Server response: "Proposal saved successfully" -->
</div>
```

### Challenge 4: Interactive Attributes on Non-Interactive Elements

Datastar makes it easy to add `data-on-click` to any element. Only put click handlers on natively interactive elements.

```html
<!-- WRONG: div is not keyboard accessible -->
<div data-on-click="$$post('/api/toggle')">Toggle status</div>

<!-- RIGHT: button is natively keyboard accessible -->
<button data-on-click="$$post('/api/toggle')">Toggle status</button>

<!-- WRONG: span as link -->
<span data-on-click="window.location='/proposals'">View proposals</span>

<!-- RIGHT: actual link -->
<a href="/proposals">View proposals</a>
```

### Challenge 5: Conditional Rendering

Use `data-show` carefully — it sets `display: none` which removes elements from the accessibility tree.

```html
<!-- This is correct for truly hidden content -->
<div data-show="$showDetails" id="details-panel">
  Details content
</div>

<!-- But the trigger needs ARIA state -->
<button data-on-click="$showDetails = !$showDetails"
        data-attr-aria-expanded="$showDetails"
        aria-controls="details-panel">
  Toggle Details
</button>
```

---

## SSE Response Accessibility Patterns

### Pattern: Form Submission with Feedback

```go
// Handler sends back a success message in a live region
func handleProposalCreate(w http.ResponseWriter, r *http.Request) {
    // ... process form ...

    // Respond with morphed content + status
    sse.MergeFragments(w,
        `<div id="proposal-form">
            <!-- Reset form -->
        </div>`,
        `<div id="status-message" role="status">
            Proposal created successfully.
        </div>`,
    )
}
```

### Pattern: Error Response

```go
func handleProposalCreate(w http.ResponseWriter, r *http.Request) {
    // ... validation fails ...

    sse.MergeFragments(w,
        `<div id="title-error" role="alert">
            Title is required.
        </div>`,
    )
    // Also set aria-invalid on the field
}
```

### Pattern: List Update with Count

```go
func handleProposalDelete(w http.ResponseWriter, r *http.Request) {
    // ... delete proposal ...

    remaining := getProposalCount()
    sse.MergeFragments(w,
        fmt.Sprintf(`<ul id="proposal-list">%s</ul>`, renderProposals()),
        fmt.Sprintf(`<div id="status-message" role="status">
            Proposal deleted. %d proposals remaining.
        </div>`, remaining),
    )
}
```

---

## Go Handler Accessibility Checklist

When writing HTTP handlers that serve HTML:

- [ ] Response includes `lang` attribute on `<html>`
- [ ] Page has a descriptive `<title>`
- [ ] Error responses use `role="alert"` or `aria-live="assertive"`
- [ ] Success/status messages use `role="status"` or `aria-live="polite"`
- [ ] SSE morph responses preserve focus context
- [ ] Form validation errors are associated with fields via `aria-describedby`
- [ ] Loading states are communicated (not just visual spinners)
- [ ] Redirects after form submission go to a page with a clear status message

---

## Testing Datastar Interactions

Because Datastar operates via SSE and DOM morphing, automated tools may miss issues. Manual testing protocol:

1. **Tab to the interactive element** — is it reachable?
2. **Activate it** — does Enter/Space work?
3. **Wait for SSE response** — does the screen reader announce the change?
4. **Check focus** — is focus on a logical element after the morph?
5. **Check state** — are `aria-expanded`, `aria-selected`, etc. updated?

Use Playwright for automated checks of the rendered state:

```javascript
test('proposal creation announces success', async ({ page }) => {
  await page.goto('/proposals/new');
  await page.fill('#title', 'Test Proposal');
  await page.click('button[type="submit"]');

  // Wait for SSE morph to complete
  await page.waitForSelector('#status-message');

  // Check that the status message exists and is a live region
  const status = page.locator('#status-message');
  await expect(status).toHaveAttribute('role', 'status');
  await expect(status).toContainText('created successfully');
});
```
