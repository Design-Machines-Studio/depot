# Theming Live Wires

Transform Live Wires to match an existing website, PDF, or design artifact by editing design tokens systematically.

---

## The Golden Rule

> **Only edit the tokens folder for theming.** The cascade handles everything else.

All theming happens in `src/css/1_tokens/`. Never edit component CSS or other layers for color/typography changes.

---

## Phase 1: Analyze the Source

Before writing any CSS, extract the visual DNA from your source design.

### Colors

1. **Identify the primary brand color** — The dominant color used for key UI elements
2. **Find the secondary palette** — Supporting colors for accents, CTAs, backgrounds
3. **Note background/foreground pairs** — Light and dark combinations used
4. **Capture specific hex values** — Use browser dev tools, color picker, or PDF inspector

### Typography

1. **Font family** — Identify the typeface(s) used (check Google Fonts, Adobe Fonts)
2. **Weights in use** — Note which weights appear (light, regular, bold, etc.)
3. **Heading sizes** — Observe the visual hierarchy (h1 vs h2 vs body)
4. **Body text size** — The base reading size

### Other Visual Details

1. **Border radius** — Sharp corners, subtle rounding, or pill shapes
2. **Spacing patterns** — Tight, comfortable, or generous whitespace
3. **Shadows** — Flat, subtle elevation, or dramatic shadows

---

## Phase 2: Build Your Color Palette

### Use Existing Color Variables

Don't invent new color names. Update the existing scales in `color.css`:

```css
/* Update existing greens, blues, oranges, etc. */
--color-green-100: #...;
--color-green-200: #...;
--color-green-500: #...;  /* Primary anchor */
--color-green-700: #...;
--color-green-900: #...;
```

### The 500 Anchor Rule

Position your primary brand color at the **500** level. This gives you:

- **100-400** — Lighter shades for backgrounds, hover states, subtle accents
- **600-900** — Darker shades for text, borders, dark mode, depth

### Brand Positioning

Some brands naturally sit in different parts of the scale:

- **Light brands** (pastels, bright colors) — Anchor at 300-400
- **Standard brands** — Anchor at 500
- **Dark brands** (forest greens, navy blues) — Anchor at 600-700

This is fine. Just ensure you have headroom above and below.

### Smooth Interpolation

Avoid jarring jumps between adjacent values:

```css
/* BAD — Jumps from light to dark */
--color-green-300: #88CEBA;  /* Light mint */
--color-green-400: #2A7A5E;  /* Suddenly dark! */

/* GOOD — Smooth progression */
--color-green-300: #88CEBA;
--color-green-400: #5FB89E;
--color-green-500: #3D9A7E;
--color-green-600: #2A7A5E;
```

---

## Phase 3: Update Design Tokens

### Files to Edit

| File | Purpose |
|------|---------|
| `src/css/1_tokens/color.css` | Color palette, semantic colors, schemes |
| `src/css/1_tokens/typography-base.css` | Font stacks, weights |
| `src/css/1_tokens/typography-scale-auto.css` | Base size, scale ratio |
| `src/css/1_tokens/borders.css` | Border radius values |

### Semantic Color Mapping

Map your scale to semantic tokens in `:root`:

```css
:root {
  --color-bg: var(--color-white);
  --color-fg: var(--color-green-700);      /* Body text */
  --color-accent: var(--color-green-600);  /* Links, interactive */
  --color-muted: var(--color-green-500);   /* Secondary text */
  --color-border: var(--color-green-700);  /* Borders */
  --color-subtle: var(--color-green-100);  /* Subtle backgrounds */
}
```

### Typography Setup

In `typography-base.css`, update font stacks:

```css
--font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
--font-serif: 'Merriweather', Georgia, serif;
--font-mono: 'Fira Code', monospace;

--font-body: var(--font-sans);
--font-heading: var(--font-sans);
```

### Font Weight Mapping

Map CSS weight keywords to your font's available weights:

```css
/* If your font only has 400 and 700 */
--font-light: 400;      /* Map light to regular */
--font-normal: 400;
--font-medium: 400;     /* Map medium to regular */
--font-semibold: 700;   /* Map semibold to bold */
--font-bold: 700;
```

### Font Loading

**For Google Fonts / Adobe Fonts (embeds):**

Add to `public/_includes/head.html`:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
```

**For self-hosted fonts:**

Add to `typography-base.css`:

```css
@import url('/fonts/your-font.css');
```

---

## Phase 4: Create Color Schemes

Schemes override semantic colors for specific sections.

### Scheme Naming

- **`.scheme-{color}`** — Primary variant (e.g., `.scheme-green`)
- **`.scheme-{color}-light`** — Light background variant
- **`.scheme-{color}-dark`** — Dark background variant
- **`.scheme-subtle`** — Subtle/muted variant

### Light-on-Dark Schemes

```css
.scheme-forest {
  --color-bg: var(--color-green-700);
  --color-fg: var(--color-white);
  --color-accent: var(--color-green-300);  /* Use LIGHT accent */
  --color-muted: var(--color-green-200);
  --color-border: var(--color-green-300);
  --color-subtle: var(--color-green-800);
  --vf-grad: -50;  /* Reduce font weight on dark */
}
```

### Dark-on-Light Schemes

```css
.scheme-mint {
  --color-bg: var(--color-green-100);
  --color-fg: var(--color-green-700);
  --color-accent: var(--color-green-600);  /* Use DARK accent */
  --color-muted: var(--color-green-500);
  --color-border: var(--color-green-500);
  --color-subtle: var(--color-green-200);
  --vf-grad: 0;
}
```

### The `--vf-grad` Variable

Controls variable font grade for optical adjustment:

- `0` for light backgrounds
- `-25` to `-50` for dark backgrounds (reduces perceived heaviness)

### Dark Mode Comes Free

When you properly update the schemes and the `:root` semantic colors, dark mode works automatically via:

1. The `@media (prefers-color-scheme: dark)` query in `color.css`
2. The `.dark-mode` class for manual override

No need to create separate dark mode rules.

---

## Phase 4b: Update Heading Hierarchy

Match source heading sizes using existing `text-*` variables.

### Edit `src/css/4_elements/typography.css`

```css
h1 { font-size: var(--text-4xl); }  /* Was 5xl, source uses smaller */
h2 { font-size: var(--text-2xl); }
h3 { font-size: var(--text-xl); }
h4 { font-size: var(--text-lg); }
h5 { font-size: var(--text-base); }
h6 { font-size: var(--text-sm); }
```

### Available Size Variables

```
text-xs, text-sm, text-base, text-lg, text-xl,
text-2xl, text-3xl, text-4xl, text-5xl, text-6xl,
text-7xl, text-8xl, text-9xl
```

Only use these. Don't create new size variables.

---

## Phase 5: Verify Accessibility

### WCAG Contrast Requirements

| Element | Minimum Ratio |
|---------|---------------|
| Body text | 4.5:1 |
| Large text (18px+ or 14px+ bold) | 3:1 |
| UI components | 3:1 |

### Contrast Quick Check

| Background | Minimum Foreground |
|------------|-------------------|
| 100-200 (very light) | 700+ or black |
| 300-400 (medium-light) | 800+ or black |
| 500 (medium) | white or 100 |
| 600-700 (medium-dark) | white or 100-200 |
| 800-900 (dark) | white or 100-300 |

### Testing

1. Use browser DevTools (Chrome/Firefox have built-in contrast checking)
2. [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)
3. [Accessible Colors](https://accessible-colors.com/)

### Common Mistake: Muted Text

Muted/secondary text often fails contrast. Check `--color-muted` carefully:

```css
/* BAD — ~2.2:1 on medium background */
.scheme-green {
  --color-bg: var(--color-green-400);
  --color-muted: var(--color-green-600);
}

/* GOOD — ~5.5:1 on medium background */
.scheme-green {
  --color-bg: var(--color-green-400);
  --color-muted: var(--color-green-800);
}
```

---

## Phase 6: Review and Clean Up Manual

After updating tokens, review and update the Manual documentation.

### Pages to Check

| Page | Action |
|------|--------|
| `/manual/brand/colors.html` | Update swatches to reflect new palette |
| `/manual/components/schemes.html` | Remove unused schemes, document new ones |
| `/manual/brand/fonts.html` | Update font samples |

### Delete Legacy Schemes

If your theme uses greens, remove unused color schemes from:

1. `src/css/1_tokens/color.css` — Delete the scheme definitions
2. `/manual/components/schemes.html` — Remove the examples

Keep the codebase clean. Don't ship unused CSS.

---

## Anti-Patterns

### Never Edit Component CSS

```css
/* WRONG — Don't do this */
.button { background: #17362D; }

/* RIGHT — Use semantic tokens */
.button { background: var(--color-accent); }
```

### Never Hardcode Colors

All colors should reference `var(--color-*)` tokens.

### Never Skip Scale Interpolation

Every scale needs smooth progression from 100-900.

### Never Invent New Color Names

Update existing greens, blues, oranges. Don't create `--color-forest` or `--color-mint` as new base colors.

### Never Create Separate Dark Mode Rules

Dark mode works automatically when you properly update the schemes and `:root` semantic colors in `color.css`.

---

## Quick Reference

### Files to Edit

| Purpose | File |
|---------|------|
| Colors & Schemes | `src/css/1_tokens/color.css` |
| Font Family | `src/css/1_tokens/typography-base.css` |
| Font Sizes | `src/css/1_tokens/typography-scale-auto.css` |
| Border Radius | `src/css/1_tokens/borders.css` |
| Heading Hierarchy | `src/css/4_elements/typography.css` |
| Web Fonts (embeds) | `public/_includes/head.html` |

### Scheme Template

```css
.scheme-{name} {
  --color-bg: var(--color-{hue}-{shade});
  --color-fg: var(--color-{contrast});
  --color-accent: var(--color-{hue}-{accent-shade});
  --color-muted: var(--color-{hue}-{muted-shade});
  --color-border: var(--color-{hue}-{border-shade});
  --color-subtle: var(--color-{hue}-{subtle-shade});
  --vf-grad: {0 for light, -50 for dark};
}
```

### Theming Checklist

```
□ Extract colors and fonts from source
□ Update color scale (use existing variable names)
□ Map semantic colors in :root
□ Create color schemes
□ Update heading hierarchy
□ Verify contrast ratios (4.5:1 body, 3:1 large)
□ Test dark mode toggle
□ Update Manual pages (colors, schemes, fonts)
□ Remove unused schemes from CSS and Manual
□ Complete visual verification (see Phase 7)
```

---

## Phase 7: Visual Verification

**This phase is critical.** Theming isn't complete until you've visually compared every page type.

### ⚠️ Do Not Skip This

The most common theming failure: applying colors to the homepage and calling it done. The source design likely has multiple page types with different scheme applications. You must audit all of them.

### Step 1: Inventory All Source Pages

Before verifying, catalog every distinct page type in the source:

```
Source Page Types:
□ Homepage / Landing
□ Article / Content page
□ Listing / Index page
□ Detail / Show page
□ Form / Input page
□ Dashboard / Admin
□ Error pages (404, 500)
□ Header (across all pages)
□ Footer (across all pages)
□ Sidebar (if present)
□ Navigation states
```

For each page type, note:
- What schemes are applied where
- Which sections have dark backgrounds vs light
- How the header/footer treatment changes (if at all)
- Button and link styling in different contexts

### Step 2: Screenshot Comparison

For each page type:

1. **Take a screenshot of the source** (or reference the original PDF/design)
2. **Take a screenshot of your prototype** at the same viewport width
3. **Compare side by side** looking for differences in:
   - Background colors for each section
   - Text colors (headings, body, muted text)
   - Link colors (default, hover if visible)
   - Button styling
   - Border colors and treatments
   - Card/callout backgrounds

### Step 3: Section-by-Section Scheme Audit

Walk through each page and verify schemes are applied correctly:

```
Page: [page name]
□ Header: scheme matches source (e.g., scheme-dark, scheme-default)
□ Hero/Banner: scheme matches source
□ Content area: scheme matches source
□ Sidebar: scheme matches source (often darker than main)
□ Callouts/Cards: scheme matches source
□ Footer: scheme matches source
```

### Step 4: Component Visual Check

Verify each UI component matches the source styling:

**Buttons**
```
□ Default button background color
□ Default button text color
□ Hover state color change
□ Focus ring color and style
□ Disabled state appearance
□ Button variants (if source has multiple)
```

**Links**
```
□ Default link color
□ Visited link color (if distinct in source)
□ Hover state (underline, color change)
□ Links on dark backgrounds (should use light accent)
□ Links on light backgrounds (should use dark accent)
```

**Forms**
```
□ Input border color
□ Input focus ring color
□ Label color
□ Placeholder text color
□ Error state styling
□ Submit button styling
```

**Cards/Callouts**
```
□ Background color
□ Border (if any)
□ Heading color within card
□ Text color within card
□ Link color within card
```

**Tables (if present)**
```
□ Header row background
□ Header text color
□ Row striping (if source uses it)
□ Border colors
```

### Step 5: State Verification

Check interactive states match the source:

```
□ Hover states on buttons
□ Hover states on links
□ Focus rings on all interactive elements
□ Active/pressed states
□ Selected/current navigation state
□ Disabled element appearance
```

### Step 6: Dark Mode Verification

If the source has dark mode:

1. Toggle dark mode in both source and prototype
2. Compare each page type in dark mode
3. Verify all schemes invert appropriately
4. Check that `--vf-grad` is reducing font weight on dark backgrounds

### Step 7: Responsive Spot Check

At minimum, verify theming at:

```
□ 320px (mobile)
□ 768px (tablet)
□ 1024px (small desktop)
□ 1440px (large desktop)
```

Look for:
- Scheme breaks at different viewports
- Colors that don't apply correctly at smaller sizes
- Navigation scheme changes on mobile

---

## Visual Verification Shortcodes

Use these when documenting issues:

```
THEME-MISMATCH   — Section scheme doesn't match source
THEME-MISSING    — Section has no scheme applied (should have one)
THEME-WRONG      — Wrong scheme applied (e.g., dark instead of light)
THEME-CONTRAST   — Contrast fails after theming
THEME-STATE      — Interactive state doesn't match source
THEME-COMPONENT  — Component styling doesn't match source
THEME-DARK       — Dark mode doesn't match source dark mode
THEME-HEADER     — Header scheme incorrect
THEME-FOOTER     — Footer scheme incorrect
THEME-SIDEBAR    — Sidebar scheme incorrect
```

---

## The Visual Verification Loop

After finding issues:

1. **Document the discrepancy** with screenshots if possible
2. **Identify which token or scheme** needs adjustment
3. **Make the fix** in the tokens folder
4. **Re-verify** the specific area
5. **Check for side effects** on other pages using the same token

Repeat until all page types match the source.

---

## Final Theming Sign-Off

Before considering theming complete:

```
□ All source page types have been compared
□ All sections have correct scheme applied
□ All components match source styling
□ All interactive states verified
□ Dark mode verified (if applicable)
□ Contrast ratios pass WCAG AA
□ Manual documentation updated
□ Unused schemes removed
□ No side effects on other pages
```
