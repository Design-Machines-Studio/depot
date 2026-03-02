# Live Wires Accessibility Reference

Complete accessibility features built into the Live Wires CSS framework, plus patterns for maintaining compliance when extending the framework.

---

## Built-in Accessibility Features

Live Wires provides accessibility as a foundational principle. These features are active by default:

### 1. Color Contrast

Default color tokens meet WCAG AA standards:

| Context | Minimum ratio | Token pair example |
|---------|--------------|-------------------|
| Body text | 4.5:1 | `--color-fg` on `--color-bg` |
| Large text (18px+ or 14px+ bold) | 3:1 | `--color-muted` on `--color-bg` |
| UI components | 3:1 | `--color-border` on `--color-bg` |

**Quick contrast check by shade pairing:**

| Background shade | Minimum foreground shade |
|-----------------|------------------------|
| 100-200 (very light) | 700+ or black |
| 300-400 (medium-light) | 800+ or black |
| 500 (medium) | white or 100 |
| 600-700 (medium-dark) | white or 100-200 |
| 800-900 (dark) | white or 100-300 |

**When creating custom color schemes:**

```css
/* CORRECT: Verify contrast meets AA */
.scheme-forest {
  --color-bg: var(--color-green-700);
  --color-fg: var(--color-white);        /* 4.5:1+ ✓ */
  --color-accent: var(--color-green-300); /* 3:1+ for large text ✓ */
  --color-muted: var(--color-green-200);  /* Check this pair */
  --vf-grad: -50;  /* Reduce font weight on dark backgrounds */
}
```

### 2. Focus Indicators

Live Wires uses `:focus-visible` for keyboard-only focus styles:

```css
/* From elements/links.css, elements/forms.css, components/buttons.css */
.button:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}

input:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
  border-color: var(--color-accent);
}
```

**Rules for custom focus states:**
- Visible: clear visual change from unfocused state
- Sufficient contrast: 3:1 against adjacent colors
- Not color-only: use outline, border, or other indicators
- Never remove without replacement: avoid `outline: none` without alternative

### 3. Reduced Motion

From `generic/reset.css`:

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

**When adding custom animations:**

```css
/* CORRECT: Wrap in motion-safe query */
@media (prefers-reduced-motion: no-preference) {
  .fade-in {
    animation: fadeIn 0.3s ease-out;
  }
}

/* WRONG: Animation without motion check */
.fade-in {
  animation: fadeIn 0.3s ease-out;
}
```

### 4. Skip Links

From `utilities/display.css`:

```css
.skip-link {
  /* Positioned off-screen by default */
  /* Visible when focused */
}
```

**Usage:**

```html
<body>
  <a href="#main" class="skip-link">Skip to main content</a>
  <header>...</header>
  <main id="main">...</main>
</body>
```

### 5. Visually Hidden

From `utilities/display.css`:

```css
.visually-hidden {
  border: 0;
  clip-path: inset(50%);
  height: 1px;
  margin: 0;
  overflow: hidden;
  position: absolute;
  white-space: nowrap;
  width: 1px;
}
```

**Use for:**
- Icon-only button labels
- Skip link text (combined with `.skip-link`)
- Screen-reader-only descriptions
- Form field supplementary instructions

```html
<button>
  <svg aria-hidden="true"><!-- icon --></svg>
  <span class="visually-hidden">Close menu</span>
</button>
```

### 6. Touch Targets

From `elements/forms.css`:

```css
:root {
  --touch-target-min: 44px; /* WCAG 2.5.5 minimum */
}
```

All form elements (inputs, buttons, checkboxes, radios) meet the 44x44px minimum.

### 7. Logical Properties

Live Wires uses CSS logical properties throughout for RTL language support:
- `margin-block-start` instead of `margin-top`
- `padding-inline` instead of `padding-left`/`padding-right`
- `inset-inline-start` instead of `left`

---

## Accessibility Audit Points for Live Wires Projects

When reviewing HTML that uses Live Wires, check these common issues:

### Issue: Using `.hidden` instead of `.visually-hidden`

```html
<!-- WRONG: Removes from accessibility tree -->
<span class="hidden">Screen reader text</span>

<!-- RIGHT: Hidden visually, available to AT -->
<span class="visually-hidden">Screen reader text</span>
```

### Issue: Icon-Only Buttons Without Labels

```html
<!-- WRONG: No accessible name -->
<button class="button button--small">
  <svg><!-- trash icon --></svg>
</button>

<!-- RIGHT: Visually hidden label -->
<button class="button button--small">
  <svg aria-hidden="true"><!-- trash icon --></svg>
  <span class="visually-hidden">Delete proposal</span>
</button>

<!-- ALSO RIGHT: aria-label -->
<button class="button button--small" aria-label="Delete proposal">
  <svg aria-hidden="true"><!-- trash icon --></svg>
</button>
```

### Issue: Color-Only Status Indicators

```html
<!-- WRONG: Color is the only indicator -->
<span class="status-indicator bg-green-500"></span>

<!-- RIGHT: Include text (visually hidden if needed) -->
<span class="status-indicator bg-green-500" aria-label="Online">
  <span class="visually-hidden">Online</span>
</span>
```

### Issue: Color Scheme Without Contrast Verification

When using `.scheme-*` classes, verify that all text within the scheme meets contrast requirements. Dark schemes need `--vf-grad: -50` to reduce optical font weight.

### Issue: Reel Without Region Label

The horizontal scroll pattern needs context for screen readers:

```html
<!-- WRONG: Unlabeled scrollable region -->
<div class="reel">...</div>

<!-- RIGHT: Labeled region -->
<div class="reel" role="region" aria-label="Recent proposals" tabindex="0">...</div>
```

### Issue: Custom Checkbox/Radio Missing Native Input

Live Wires custom form controls hide the native input visually but keep it in the accessibility tree:

```html
<!-- CORRECT: Native input is visually hidden, not display:none -->
<label class="checkbox">
  <input type="checkbox" name="field" value="value">
  Label text
</label>
```

The CSS uses `:has(input:checked)` for styling, keeping the native input functional for AT.

---

## Checklist for Live Wires CSS Changes

When modifying or extending Live Wires CSS:

- [ ] New components have `:focus-visible` styles
- [ ] Animations respect `prefers-reduced-motion`
- [ ] Color pairs meet AA contrast (4.5:1 text, 3:1 large text, 3:1 UI)
- [ ] Interactive elements have 44x44px minimum touch targets
- [ ] No `outline: none` without alternative focus indicator
- [ ] Logical properties used (not physical direction properties)
- [ ] Decorative SVGs have `aria-hidden="true"`
- [ ] Functional SVGs have `role="img"` and `aria-label`
- [ ] `.visually-hidden` used instead of `.hidden` for AT content
- [ ] Custom form controls preserve native input accessibility
