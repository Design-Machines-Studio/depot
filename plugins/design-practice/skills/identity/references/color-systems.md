# Color Systems Reference

Guidance on color space selection, palette construction, and systematic color usage for identity and UI design.

---

## OKLCH Color Space

For new identity and palette work, recommend OKLCH over HSL or hex.

### Why OKLCH

- **Perceptually uniform:** Equal numeric steps produce equal perceived differences. HSL's lightness channel is misleading -- `hsl(60, 100%, 50%)` (yellow) and `hsl(240, 100%, 50%)` (blue) have the same L value but vastly different perceived brightness.
- **Predictable contrast:** The L (lightness) channel maps directly to perceived brightness, making contrast ratio estimation possible without external tools.
- **Better palette generation:** Adjusting C (chroma) and H (hue) at a fixed L produces colors that feel equally bright -- essential for accessible palettes.
- **CSS-native:** `oklch()` is supported in all modern browsers. No polyfill needed.

### OKLCH Anatomy

```
oklch(L C H)
L = lightness (0% = black, 100% = white)
C = chroma (0 = gray, ~0.4 = maximum saturation)
H = hue (0-360 degrees, same as HSL)
```

Key insight: chroma is absolute, not relative. `C = 0.15` produces a saturated color regardless of hue. This is unlike HSL where `S = 100%` produces wildly different visual saturation depending on the hue.

---

## Tinted Neutrals

The single most effective technique for creating palette cohesion. Instead of pure grays (`oklch(95% 0 0)`), add the brand's hue at very low chroma:

```css
/* Pure gray -- flat, lifeless, no brand connection */
--color-surface: oklch(95% 0 0);

/* Tinted neutral -- warm, cohesive, brand-connected */
--color-surface: oklch(95% 0.01 290);  /* purple-tinted for DM */
```

### Chroma Guidelines for Neutrals

| Context | Chroma Range | Effect |
|---------|-------------|--------|
| Backgrounds | 0.005-0.015 | Barely perceptible warmth, strong cohesion |
| Borders/dividers | 0.01-0.02 | Subtle brand presence in structural elements |
| Muted text | 0.015-0.03 | Secondary text feels part of the palette, not generic |

Vignelli would approve: this is systematic (one hue variable) and disciplined (chroma stays minimal). The tinting is felt, not seen.

---

## Palette Construction with OKLCH

### Step 1: Define the Brand Hue

Every brand color has a dominant hue angle. Find it by converting the primary brand color to OKLCH:

```
DM Purple-800 (#220d46) -> oklch(18% 0.12 290)
Brand hue = 290 (purple)
```

### Step 2: Build the Lightness Scale

Keep hue and chroma constant. Vary only lightness to create a scale:

```css
--color-purple-50:  oklch(97% 0.03 290);
--color-purple-100: oklch(93% 0.06 290);
--color-purple-200: oklch(85% 0.08 290);
--color-purple-300: oklch(73% 0.10 290);
--color-purple-400: oklch(60% 0.12 290);
--color-purple-500: oklch(48% 0.12 290);
--color-purple-600: oklch(38% 0.12 290);
--color-purple-700: oklch(28% 0.12 290);
--color-purple-800: oklch(18% 0.12 290);  /* primary */
--color-purple-900: oklch(12% 0.10 290);
```

Chroma may need slight reduction at extremes (very light, very dark) to prevent oversaturation.

### Step 3: Tint the Neutrals

Apply the brand hue at minimal chroma to all neutral values:

```css
--color-gray-50:  oklch(97% 0.01 290);
--color-gray-100: oklch(93% 0.01 290);
--color-gray-200: oklch(85% 0.01 290);
/* ... etc */
--color-gray-900: oklch(15% 0.015 290);
```

### Step 4: Derive Semantic Colors

Status colors (success, warning, error, info) use their own hues but share the lightness scale logic:

```css
--color-success: oklch(55% 0.15 145);  /* green */
--color-warning: oklch(75% 0.15 85);   /* amber */
--color-error:   oklch(55% 0.18 25);   /* red */
--color-info:    oklch(55% 0.12 250);  /* blue */
```

### Step 5: Verify Contrast

Because OKLCH's L channel is perceptually accurate, contrast checking is more intuitive:
- L difference of ~50+ between text and background generally meets WCAG AA (4.5:1)
- L difference of ~60+ generally meets AAA (7:1)
- Always verify with a proper contrast checker, but OKLCH makes initial palette design much more predictable

---

## DM Color System in OKLCH

Design Machines' core palette expressed in OKLCH:

| Token | Hex | OKLCH (approx) | Usage |
|-------|-----|----------------|-------|
| Purple-800 | #220d46 | oklch(18% 0.12 290) | Primary brand, `.scheme-purple` |
| Gold-400 | #ffcb09 | oklch(87% 0.18 90) | Accent, warmth, `.scheme-gold` |
| Red-500 | #ed1d26 | oklch(52% 0.22 27) | Agitprop, urgency, `.scheme-red` |
| Neutral tint | -- | oklch(L% 0.01 290) | All grays tinted toward purple |

---

## Integration with Live Wires

Live Wires color tokens are defined as CSS custom properties. OKLCH values work directly:

```css
:root {
  --color-purple-800: oklch(18% 0.12 290);
  --color-bg: oklch(97% 0.01 290);        /* tinted white */
  --color-fg: oklch(15% 0.015 290);       /* tinted near-black */
}
```

Scheme classes inherit and propagate these values correctly regardless of color space. The cascade handles OKLCH the same as hex or HSL.

When reviewing color in Live Wires projects, check for:
- Raw hex values that should be tokens
- Pure grays (`#808080`, `#ccc`, `#666`) that should be tinted neutrals
- Inconsistent hue tinting across the neutral scale
