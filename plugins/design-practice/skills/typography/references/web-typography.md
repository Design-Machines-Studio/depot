# Web Typography

Web-specific typographic principles from Tim Brown, Richard Rutter, Matej Latin, and Jason Santa Maria.

---

## Tim Brown -- Flexible Typesetting

### Typography as Conditional Logic

On the web, typographers no longer decide; they suggest. They prepare and instruct text to make choices for itself. Typography becomes conditional logic -- media query breakpoints, relative units, and `calc()` equations are tools for dealing with pressure.

### Typographic Pressure

Pressure is why typeset text sometimes feels awkward. The web puts constant pressure on text blocks, easily disrupting balance. Designers sense pressure every time they choose a new font or adjust a setting. The vocabulary for diagnosing pressure: tension, compression, imbalance, crowding.

### The Interdependence of Text Block Properties

Font size, measure (line length), and line spacing all work together. Adjust in this order:

1. **Typeface** -- its x-height, contrast, and proportions determine everything else
2. **Font size** -- establish the body text anchor
3. **Measure** -- depends on both typeface and font size
4. **Line spacing** -- depends on all three preceding factors

### Modular Scales and the Three-Property Framework

Brown's modular scale concept was an important step: a sequence of numbers that relate meaningfully, like a musical scale. The named ratios below remain useful shorthand, but they are incomplete descriptions -- each is a two-property scale that conflates hierarchy impact with palette density. The three-property framework (Mortensen, LGC/Désiré) extends Brown's concept by adding notes-per-interval (n) as an independent control.

| Ratio | Name | Use When |
|---|---|---|
| 1.067 | Minor Second | Subtle differentiation needed |
| 1.125 | Major Second | Restrained, professional context |
| 1.200 | Minor Third | General-purpose editorial |
| 1.250 | Major Third | Confident hierarchy |
| 1.333 | Perfect Fourth | Strong editorial voice |
| 1.414 | Augmented Fourth | Dramatic contrast |
| 1.500 | Perfect Fifth | Bold, opinionated design |
| 1.618 | Golden Ratio | Classical proportions |

These named ratios are actually n=1 cases of the three-property formula fᵢ = f₀ × r^(i/n). The Major Third (1.250), for instance, approximates a tritonic scale with r=2 and n=3 (actual step: ³√2 = 1.2599). The Augmented Fourth (1.414) is exactly a tetratonic r=2 scale (⁴√2). See the typography skill's Typographic Scale section for the full three-property framework, scale temperaments, and derivation method.

**Body text as anchor.** Everything scales in relation to body text. Set body first, derive the system. In the three-property framework, body size = f₀.

**Mathematics balanced with instinct.** Brown reminds us that we ultimately read with our eyes and lead with our instincts. The three-property framework gives better starting points, but you still use your eyes. Ratios are starting points, not absolutes.

---

## Richard Rutter -- Web Typography

### Everyone Using CSS Is a Typographer

Anyone designing websites or using CSS functions as a typographer, whether consciously or not. Typography's chief role: ensure legibility and readability.

### Typography Must Draw You In, Then Get Out of the Way

The reader should scan, find information, and enter a reading flow without the typography calling attention to itself. Get the basics right first: line length, consistent spacing, appropriate text size. Then establish visual hierarchy.

### Setting Type to Be Read

**Reading mechanics:** Readers don't read letter by letter. They recognize word shapes and scan across saccades (jumps). Typography must support this natural reading behavior.

**The em system:** Use `em` for related spacing (margins, padding, indentation relative to text). Use `rem` for systematic sizing (type scale, baseline grid).

**Paragraph design:**
- Line length: 45--75 characters (Bringhurst's rule, applied via `max-width` in `ch` units)
- Text size: 16px minimum for body text on screen
- Line spacing: 1.4--1.6 for body text, depending on typeface and measure

**Alignment and justification:**
- Left-aligned (ragged right) is preferred for web
- Justified text requires CSS `hyphens: auto` and language attributes to avoid rivers
- `text-wrap: pretty` prevents orphans and short last lines

### Typographic Detail in CSS

| Feature | CSS Property | Notes |
|---|---|---|
| **Kerning** | `font-kerning: normal` | Enable for all text |
| **Ligatures** | `font-variant-ligatures: common-ligatures` | Standard ligatures |
| **Numerals** | `font-variant-numeric: lining-nums` / `oldstyle-nums` | Context-dependent |
| **Tabular figures** | `font-variant-numeric: tabular-nums` | For tables and aligned numbers |
| **Small caps** | `font-variant-caps: small-caps` | True small caps from OpenType |
| **Superscript/subscript** | `font-variant-position: super` / `sub` | Proper optical sizing |
| **Fractions** | `font-variant-numeric: diagonal-fractions` | When font supports it |

### Responsive Typography

All typographic decisions must account for fluid viewports. Line length, text size, and line spacing must all adapt. Rutter recommends testing at actual device sizes, not just resizing a browser window.

---

## Matej Latin -- Better Web Type

### Rhythm Creates Readability

Like rhythm in music, a well-designed text with established rhythm is easier to read and more enjoyable. Order is more pleasurable than chaos.

### Horizontal Rhythm Rules

- **Never letterspace lowercase body text.** (Goudy: "A man who would letterspace lower case would steal sheep.")
- **Headings:** Reduce letter spacing by 3--5% for compactness
- **Uppercase/small caps:** Increase spacing by 5--10% for legibility
- **Avoid justified text on the web.** Poor browser algorithms create rivers of white
- **Paragraph indenting:** Apply only to paragraphs preceded by other paragraphs: `p + p { text-indent: 1em; }`. Never indent the first paragraph. Recommended: 1em (min 0.5em, max 3em).
- **Hanging punctuation:** Place quotation marks and bullets outside the text block to maintain visual flow

### Vertical Rhythm Rules

**Line-height as fundamental rhythmic unit.** All margins, padding, and line-heights should be multiples of the base line-height.

**Baseline grid calculation:** Base font size x line-height = leading unit. Example: 16px x 1.5 = 24px. All subsequent vertical measurements are multiples of 24px.

**Heading treatment:**
- Line-heights equal to 2x or more of the base unit
- Larger top margin (3x unit) than bottom margin (1x unit)
- This visually connects headings with following text

**Images and the grid.** Images may break the baseline grid. Use the grid as guide, not constraint. Images that break the grid do not necessarily disrupt overall rhythm.

---

## Jason Santa Maria -- On Web Typography

### Typography as the Atomic Unit of Web Design

Type is the smallest atomic unit -- the framework for everything communicated with boxes, grids, CSS properties, and other web elements.

### Hierarchy Through Three Levers

1. **Size** -- the most direct signal of importance
2. **Color** -- value contrast creates depth and priority
3. **Placement** -- position on the page signals sequence and importance

Contrast is essential for forming distinctions that aid navigation.

### Typeface Evaluation Method

1. Identify the context (audience, medium, purpose, tone)
2. Classify the typeface (family, construction, era)
3. Evaluate the letterforms (physical characteristics, emotional register)
4. Test at actual sizes in actual contexts

### Maximum Two Typefaces

"It's conventional to use a maximum of two typefaces, and often using typefaces within the same family or a single typeface in multiple styles gives you all the variety you need."

### Typography and Reading Behavior

Understanding how readers consume content must inform typographic decisions:
- **Scanning:** Headlines, subheads, bold text, captions
- **Skimming:** First sentences, bullet points, pull quotes
- **Deep reading:** Sustained body text engagement

Each mode has different typographic requirements. A well-designed page supports all three.

---

## CSS Implementation Quick Reference

```css
/* Body text anchor */
body {
  font-size: clamp(1rem, 0.95rem + 0.25vw, 1.125rem);
  line-height: 1.5;
  font-kerning: normal;
  font-variant-ligatures: common-ligatures;
}

/* Measure control */
.prose {
  max-width: 65ch;
}

/* Heading rhythm */
h2, h3, h4 {
  line-height: 1.3;
  margin-top: 3rem; /* 2x base leading */
  margin-bottom: 1.5rem; /* 1x base leading */
  letter-spacing: -0.02em;
}

/* Paragraph indentation */
p + p {
  text-indent: 1em;
}

/* Balanced headings */
h1, h2, h3 {
  text-wrap: balance;
}

/* Pretty paragraphs */
p {
  text-wrap: pretty;
}

/* Tabular numbers in tables */
td {
  font-variant-numeric: tabular-nums lining-nums;
}

/* Small caps for abbreviations */
abbr {
  font-variant-caps: all-small-caps;
  letter-spacing: 0.05em;
}
```
