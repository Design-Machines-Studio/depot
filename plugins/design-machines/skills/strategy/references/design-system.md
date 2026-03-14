# Design Machines Design System

The visual identity system for Design Machines and its product family. Built in OKLCH, exported as sRGB hex.

---

## Typeface: GT Standard

**Primary typeface** for all Design Machines properties: GT Standard by Grilli Type.

| Weight/Style | Use |
|---|---|
| **GT Standard VF** (variable) | Body text, UI, headings — full weight axis from Thin to Black |
| **GT Standard Mono VF** (variable) | Code, data, catalog codes (DM-003), technical UI |

**Font files:** Variable WOFF2 format (`GT-Standard-VF.woff2`, `GT-Standard-Mono-VF.woff2`).

### CSS implementation

```css
@font-face {
  font-family: 'GT Standard';
  src: url('/fonts/GT-Standard-VF.woff2') format('woff2-variations');
  font-weight: 100 900;
  font-display: swap;
}
@font-face {
  font-family: 'GT Standard Mono';
  src: url('/fonts/GT-Standard-Mono-VF.woff2') format('woff2-variations');
  font-weight: 100 900;
  font-display: swap;
}
```

### Fallback stack

```css
--font-body: 'GT Standard', system-ui, -apple-system, sans-serif;
--font-mono: 'GT Standard Mono', ui-monospace, 'SF Mono', monospace;
```

### Character

GT Standard is a neo-grotesque sans-serif with warm, humanist details — systematic and precise without feeling cold or clinical. Opinionated tools built with care, not sterile corporate infrastructure.

**Do:** Use the full weight axis for typographic contrast. Pair light weights at display size with medium/bold at body size. Use the mono cut for all code, data tables, and catalog codes.

**Don't:** Use decorative or script typefaces for any DM property. Don't pair GT Standard with another sans-serif — use weight contrast within the family instead.

---

## Color Palette

Seven color families, each with 11 steps (50 through 950). Every step has defined hex, RGB, CMYK, and approximate Pantone values.

### Families and Roles

| Family | Role | Anchor Step | Anchor Hex | Character |
|---|---|---|---|---|
| **Purple** | Brand primary | 800 | `#220d46` | Deep, authoritative, distinctive |
| **Red** | Danger, urgent, agitprop | 500 | `#ed1d26` | Warm red, not cold crimson |
| **Orange** | Warning, action needed | 500/600 | `#fc7f4f`/`#e94c00` | Coral at 500, International Orange at 600 |
| **Gold** | Accent, highlight, energy | 400 | `#ffcb09` | Bright yellow-gold, drifts amber in darks |
| **Green** | Success, approved, healthy | 500 | `#4aa342` | Natural leaf green |
| **Blue** | Info, interactive, links | 500 | `#3d6fd9` | Cornflower, drifts warm-violet in darks |
| **Iron** | Warm neutral | 100 | `#f9f5f0` | Warm gray with yellow undertone, compressed light end with cliff at 500-600 |

### Primitive Ramps

Primitives are the raw color values. **Never use primitives directly in markup or component CSS.** Always reference them through semantic tokens or scheme classes.

#### Purple
| Step | Hex |
|---|---|
| 50 | `#f7f5fe` |
| 100 | `#f0eefb` |
| 200 | `#e8e5f9` |
| 300 | `#ada4d2` |
| 400 | `#917ecd` |
| 500 | `#774ece` |
| 600 | `#5a2ea7` |
| 700 | `#3d1679` |
| 800 | `#220d46` |
| 900 | `#0f0128` |
| 950 | `#050013` |

#### Red
| Step | Hex |
|---|---|
| 50 | `#fff4f2` |
| 100 | `#ffebe8` |
| 200 | `#ffddd9` |
| 300 | `#ffc3bc` |
| 400 | `#ff7f73` |
| 500 | `#ed1d26` |
| 600 | `#ba1e20` |
| 700 | `#891817` |
| 800 | `#5f1210` |
| 900 | `#3d0b09` |
| 950 | `#250504` |

#### Orange
| Step | Hex |
|---|---|
| 50 | `#fff4f1` |
| 100 | `#ffebe5` |
| 200 | `#ffe0d6` |
| 300 | `#ffd0c1` |
| 400 | `#ffaf93` |
| 500 | `#fc7f4f` |
| 600 | `#e94c00` |
| 700 | `#ae390c` |
| 800 | `#7c2d18` |
| 900 | `#552519` |
| 950 | `#3b1d16` |

#### Gold
| Step | Hex |
|---|---|
| 50 | `#fff7f0` |
| 100 | `#fff3e7` |
| 200 | `#ffedda` |
| 300 | `#ffe5c5` |
| 400 | `#ffcb09` |
| 500 | `#ea9434` |
| 600 | `#c1783c` |
| 700 | `#985f39` |
| 800 | `#71462e` |
| 900 | `#543425` |
| 950 | `#41281d` |

#### Green
| Step | Hex |
|---|---|
| 50 | `#edfbef` |
| 100 | `#dff8e3` |
| 200 | `#caf3ce` |
| 300 | `#a2e9a7` |
| 400 | `#68cb69` |
| 500 | `#4aa342` |
| 600 | `#397e28` |
| 700 | `#305d1e` |
| 800 | `#264018` |
| 900 | `#1a2910` |
| 950 | `#0f1909` |

#### Blue
| Step | Hex |
|---|---|
| 50 | `#f3f7fe` |
| 100 | `#eaf0fd` |
| 200 | `#dde8fd` |
| 300 | `#a0b5dc` |
| 400 | `#6b93e2` |
| 500 | `#3d6fd9` |
| 600 | `#1b3bdb` |
| 700 | `#1e2993` |
| 800 | `#181858` |
| 900 | `#0d0b2f` |
| 950 | `#05031a` |

#### Iron
| Step | Hex |
|---|---|
| 50 | `#fdf9f4` |
| 100 | `#f9f5f0` |
| 200 | `#f3efea` |
| 300 | `#e9e4dd` |
| 400 | `#d9d3cc` |
| 500 | `#bcb6ae` |
| 600 | `#6c665d` |
| 700 | `#4e4941` |
| 800 | `#34302b` |
| 900 | `#201d18` |
| 950 | `#14100c` |

---

## Token Architecture

Three layers. Each builds on the one below. **Claude should work at the semantic and scheme layers, never at the primitive layer.**

### Layer 1: Primitives

CSS custom properties on `:root`. Named `--color-{family}-{step}`.

```css
--color-purple-800: #220d46;
--color-iron-50: #fdf9f4;
```

### Layer 2: Semantic Tokens

Map primitives to functional roles. These are what component CSS references.

#### Light Mode (default)

| Token | Maps To | Purpose |
|---|---|---|
| `--color-bg-page` | iron-50 | Primary page background |
| `--color-bg-surface` | iron-100 | Card and panel surfaces |
| `--color-bg-recessed` | iron-200 | Inset or recessed areas |
| `--color-bg-elevated` | iron-300 | Elevated surfaces and borders |
| `--color-bg-muted` | iron-400 | Muted feature surfaces |
| `--color-text-primary` | iron-900 | Body text |
| `--color-text-heading` | purple-800 | Headings and titles |
| `--color-text-secondary` | iron-600 | Supporting text |
| `--color-text-tertiary` | iron-500 | Placeholder/decorative (not AA for body) |
| `--color-brand` | purple-800 | Primary brand color |
| `--color-brand-accent` | gold-400 | Brand highlight |
| `--color-brand-bold` | red-500 | Agitprop red accent |
| `--color-link` | blue-500 | Default links |
| `--color-focus` | blue-400 | Focus ring |
| `--color-success` | green-500 | Success state |
| `--color-warning` | orange-600 | Warning state |
| `--color-danger` | red-500 | Error/danger state |
| `--color-info` | blue-500 | Informational state |

#### Dark Mode

Applied via `[data-theme="dark"]` or `.scheme-dark`.

| Token | Maps To | Notes |
|---|---|---|
| `--color-bg-page` | purple-900 | Purple-tinted dark, not neutral black |
| `--color-bg-surface` | purple-800 | Brand-infused surfaces |
| `--color-text-primary` | iron-100 | Light text on dark |
| `--color-text-heading` | iron-50 | Near-white headings |
| `--color-link` | blue-400 | Lighter link for contrast |

### Layer 3: Color Schemes

Self-applying utility classes following Live Wires convention. Each scheme sets `--color-bg`, `--color-fg`, `--color-accent` plus `background-color` and `color`.

| Scheme | Background | Foreground | Accent | Character |
|---|---|---|---|---|
| `.scheme-dark` | purple-800 | iron-100 | gold-400 | Brand dark |
| `.scheme-light` | iron-50 | iron-900 | purple-800 | Default light |
| `.scheme-subtle` | iron-200 | iron-800 | purple-600 | Recessed light |
| `.scheme-bold` | red-500 | iron-50 | iron-50 | Agitprop |
| `.scheme-black` | iron-950 | iron-100 | gold-400 | True dark |
| `.scheme-purple` | purple-800 | iron-100 | gold-400 | Brand hero |
| `.scheme-purple-light` | purple-50 | purple-800 | purple-600 | Soft brand |
| `.scheme-red` | red-500 | iron-50 | iron-50 | Urgent/bold |
| `.scheme-red-light` | red-50 | red-800 | red-600 | Soft danger |
| `.scheme-orange` | orange-600 | iron-50 | iron-50 | Warning |
| `.scheme-orange-light` | orange-50 | orange-800 | orange-700 | Soft warning |
| `.scheme-gold` | gold-400 | gold-950 | gold-950 | Highlight |
| `.scheme-gold-light` | gold-50 | gold-800 | gold-700 | Soft highlight |
| `.scheme-green` | green-600 | iron-50 | green-200 | Success |
| `.scheme-green-light` | green-50 | green-800 | green-700 | Soft success |
| `.scheme-blue` | blue-800 | iron-100 | blue-400 | Info |
| `.scheme-blue-light` | blue-50 | blue-800 | blue-600 | Soft info |
| `.scheme-iron-dark` | iron-900 | iron-100 | gold-400 | Neutral dark |
| `.scheme-iron-mid` | iron-700 | iron-100 | gold-400 | Neutral mid |
| `.scheme-iron-light` | iron-300 | iron-900 | purple-800 | Neutral light |

---

## Product Color Assignments

Each DM product has a primary color treatment derived from the shared palette.

### Design Machines (parent brand)

- **Hero scheme:** `.scheme-purple` (purple-800 bg, iron-100 text, gold-400 accent)
- **Primary color:** Purple-800 `#220d46`
- **Accent:** Gold-400 `#ffcb09`
- **Bold accent:** Red-500 `#ed1d26` (for agitprop/editorial emphasis)
- **Light mode:** Iron-50 page, purple-800 headings, iron-900 body
- **Dark mode:** Purple-900 page, iron-50 headings, gold-400 brand accent

### Assembly (DM-005)

- **Hero scheme:** `.scheme-purple` or `.scheme-dark` (governance = authority)
- **Primary surfaces:** Purple-800 for navigation and brand areas
- **Data/feedback:** Full spectrum — green (approved), red (danger), orange (warning), blue (info)
- **Neutral UI:** Iron ramp for tables, forms, card surfaces
- **Gold accent:** For highlights, active states, and member equity indicators

### Live Wires (DM-003)

- **Uses the full DM palette** as its token foundation
- **Hero scheme:** `.scheme-bold` (red-500) or `.scheme-purple` depending on context
- **Documentation:** `.scheme-light` with purple-800 headings
- **All color schemes** are defined by Live Wires and consumed by DM sites

### The Local (Matrix network)

- **Hero scheme:** `.scheme-blue` (blue-800 bg) — communication/infrastructure
- **Primary accent:** Blue-500 for links and interactive elements
- **Neutral surfaces:** Iron ramp
- **Shares the same palette** but emphasizes blue family

---

## Accessibility

### AA-Compliant Text Colors on Iron-50 (Light Backgrounds)

**Body text (4.5:1 minimum):** purple-600, purple-800, red-600, gold-800, green-600, blue-600, iron-600, iron-700

**Large text only (3:1 minimum):** red-500, blue-500, green-500, orange-600. Use their 600+ variants for body text.

### Text on Dark Backgrounds (Purple-800)

**Body text:** iron-100, iron-50

**Accent text (AA-compliant on purple-800):** gold-400, green-300, orange-400, red-400, blue-400

### Iron Ramp Cliff

The iron ramp has a deliberate lightness cliff between 500 and 600 (compressed light end). This means:
- iron-50 through iron-400: closely spaced light values (backgrounds, subtle distinctions)
- iron-500: mid-tone boundary
- iron-600 through iron-950: darker values with larger spacing (text, borders, dark modes)

This distribution is intentional — it gives more nuance in the light surface range where most reading happens.

---

## Source Files

Color palette source files are stored in iCloud:
`~/Library/Mobile Documents/com~apple~CloudDocs/Design Machines/Design/Identity/Colours/`

| File | Format | Purpose |
|---|---|---|
| `dm-color-reference.txt` | Plain text | Full ramp reference with hex, RGB, CMYK, Pantone |
| `dm-color-tokens.css` | CSS | Copy-ready CSS custom properties and scheme classes |
| `dm-color-tokens.json` | JSON | Compact token format for tooling |
| `dm-color-tokens.tokens.json` | DTCG | Design Tokens Community Group format for Figma/Style Dictionary |
| `dm-colors.ase` | ASE | Adobe swatch exchange for Illustrator/InDesign/Photoshop |
| `dm-figma-variables.csv` | CSV | Figma variable import format |
| `dm-livewires-claude-code-prompt.md` | Markdown | Implementation prompt for applying palette to Live Wires |
