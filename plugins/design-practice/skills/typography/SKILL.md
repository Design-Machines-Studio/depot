---
name: typography
description: Design Machines typography philosophy rooted in Swiss modernism, systematic thinking, and web-native practice. Use when critiquing typographic decisions, advising on typeface selection, evaluating rhythm and hierarchy, or reviewing typography in HTML/CSS, Figma, InDesign, Illustrator, or Affinity. Draws on Müller-Brockmann, Gerstner, Bringhurst, Vignelli, Spiekermann, Santa Maria, Brown, Rutter, Latin, and Craig.
---

# Typography

Typography exists to honor content. Every typographic decision must serve the text, not the designer's ego. Structure always comes first -- the grid, the hierarchy, the relationships between elements. The specific typeface is secondary.

On the web, typographers no longer decide; they suggest. They prepare and instruct text to make choices for itself.

**You never generate designs. You inform, critique, and advise.**

---

## The Five Foundations

### 1. Structure Before Typeface (Vignelli)

The typographic structure -- grid, hierarchy, spacing relationships -- is more important than any typeface selection. "What matters is the typographical structure, not the typeface." Choose font size in relation to column width. Stick to no more than 2 type sizes on a printed page. Play off small type with large type.

### 2. Design as Programme (Gerstner)

Typographic decisions should emerge from defined systems and criteria, not arbitrary feeling. "The more exact and complete these criteria are, the more creative the work becomes." Define your parameters, then select within them. Maximum conformity with maximum freedom.

### 3. Measure and Rhythm (Bringhurst)

All typographic decisions are interdependent. Adjust in this order: typeface first, then font size, then measure (line length), then line spacing. Each depends on the preceding.

### 4. Body Text as Anchor (Brown)

Body text acts as an anchor that makes other design decisions easier. Everything else scales in relation to it. Start with body text, then derive the entire system.

### 5. Invite, Then Disappear (Rutter)

Typography must draw the reader in, then get out of the way. The reader should scan, find information, and enter a reading flow without the typography calling attention to itself.

---

## Measure (Line Length)

| Context | Characters per line | Source |
|---|---|---|
| **Ideal single column** | 66 | Bringhurst |
| **Comfortable range** | 45--75 | Bringhurst |
| **Multiple columns** | 40--50 | Bringhurst |
| **Words per line** | 7--10 | Müller-Brockmann |

Font size relates to column width. If the measure is wrong, nothing else matters.

---

## Vertical Rhythm and Leading

Line-height is the fundamental rhythmic unit. All vertical measurements should be multiples of the base line-height.

| Property | Value | Source |
|---|---|---|
| **Body line-height** | 1.45--1.5 | Latin, Live Wires |
| **Heading line-height** | 1.2--1.3 | Live Wires |
| **Display line-height** | 1.0--1.1 | Live Wires |
| **Leading depends on** | Typeface, size, measure | Bringhurst, Brown |
| **Sans-serif needs** | More leading than serif | Bringhurst |
| **Wider measures need** | More leading | Bringhurst |

**Heading margins**: Larger top margin (2--3x base unit), smaller bottom margin (0--1x base unit). This visually binds headings to following content.

**Spacing rule**: Add and delete vertical space in measured intervals. Never break the rhythm with arbitrary spacing.

---

## Horizontal Spacing

| Rule | Guidance | Source |
|---|---|---|
| **Lowercase body text** | Never letterspace | Bringhurst, Latin, Goudy |
| **Capitals and small caps** | Increase spacing 5--10% | Bringhurst, Latin |
| **Headings** | Reduce letter-spacing 3--5% | Latin |
| **Sentence spacing** | Single word space only | Bringhurst |
| **Word space** | Suit the font's natural letterfit | Bringhurst |

---

## Typographic Scale

Use a modular scale -- a sequence of numbers that relate to one another meaningfully. Start with body text size, multiply by a ratio:

| Ratio | Name | Character |
|---|---|---|
| 1.067 | Minor Second | Subtle |
| 1.125 | Major Second | Restrained |
| 1.200 | Minor Third | Balanced |
| 1.250 | Major Third | Confident |
| 1.333 | Perfect Fourth | Authoritative |
| 1.414 | Augmented Fourth | Dramatic |
| 1.500 | Perfect Fifth | Bold |
| 1.618 | Golden Ratio | Classical |

**The classical typographic scale** (Bringhurst): 6, 7, 8, 9, 10, 11, 12, 14, 16, 18, 21, 24, 36, 48, 60, 72.

Vignelli's rule: No more than 2 type sizes on a page. Play off small with large (2x ratio).

---

## Typeface Selection

### Constraints

- **Maximum two typefaces** (Santa Maria). A single family in multiple weights often suffices.
- **Limited palette** (Vignelli): You need only a few basic typefaces. His six: Garamond, Bodoni, Century Expanded, Futura, Times, Helvetica.
- **Context determines everything** (Spiekermann): What is being said, to whom, in what medium, what response is desired?

### Classification Framework (Craig)

Understand the five families and why each exists:

| Family | Stress | Stroke Contrast | Serifs | Example |
|---|---|---|---|---|
| **Old Style** | Diagonal | Moderate | Heavy, bracketed | Garamond |
| **Transitional** | More vertical | Greater | Sharper | Baskerville |
| **Modern** | Vertical | Extreme | Hairline, 90° | Bodoni |
| **Slab Serif** | Vertical | Low | Heavy slab | Rockwell |
| **Sans Serif** | None | Uniform | None | Helvetica |

### Evaluation Method (Santa Maria)

1. Identify the context (audience, medium, purpose)
2. Classify the typeface (family, construction)
3. Evaluate the letterforms (physical characteristics, emotional register)
4. Test screen rendering, hinting, format support (Rutter)

---

## Web-Specific Typography

### Fluid Type with clamp() (Live Wires)

Use CSS `clamp()` for responsive type that smoothly scales between min and max sizes. Complete type packages where one utility class applies font-size, line-height, and letter-spacing together.

### Modern CSS

- `text-wrap: balance` for headings
- `text-wrap: pretty` for paragraphs
- OpenType features via `font-feature-settings` or `font-variant`
- Tabular vs. proportional numerals as context demands
- Ligatures, small caps, oldstyle figures available in CSS

### Responsive Considerations (Brown, Rutter)

- Typography must adapt to fluid viewports
- Font size, measure, and line spacing all change together
- Typographic pressure: recognize when text blocks feel wrong and diagnose the issue
- Suggestion over decision -- prepare ranges and boundaries, not fixed values

---

## The Morphological Box (Gerstner)

For systematic evaluation, list all typographic parameters and their possible treatments:

| Parameter | Options |
|---|---|
| **Typeface** | Serif, sans-serif, slab, monospace |
| **Size** | Scale positions (body, small, large, display) |
| **Weight** | Light, regular, medium, bold, black |
| **Width** | Condensed, normal, extended |
| **Style** | Roman, italic, oblique |
| **Spacing** | Tight, normal, loose |
| **Alignment** | Left, center, right, justified |
| **Color** | Primary text, secondary, accent, muted |
| **Case** | Lowercase, uppercase, small caps, title case |

Select across rows to generate systematic variations. This clears the mind to focus on the design problem itself.

---

## Tool-Specific Guidance

### HTML + CSS
- Set body text first, derive everything from it
- Use `rem` for type sizes, `em` for related spacing
- Use CSS custom properties for scale values
- Avoid justified text on the web (Latin) -- left-aligned preferred
- `p + p { text-indent: 1em; }` for paragraph indentation (never indent first paragraph)

### Figma
- Set up type styles that mirror the modular scale
- Use auto layout with spacing matching the baseline unit
- Create text style variants (body, heading, caption, display)
- Test at multiple viewport widths

### Adobe InDesign
- Set up baseline grid matching your leading unit
- Use paragraph styles with "Align to Baseline Grid" enabled
- Define character and paragraph styles before placing text
- Use optical margin alignment for hanging punctuation

### Adobe Illustrator
- Use area type (not point type) for body text
- Set up character and paragraph styles
- Check type at actual output size, not just screen zoom

### Affinity Publisher/Designer
- Set up baseline grid in document settings
- Use text styles hierarchy matching your scale
- Enable baseline grid snapping for body text

---

## Quick Evaluation Checklist

When critiquing typography, ask:

1. Does the typography honor the content? (Bringhurst)
2. Is there a visible system, or are decisions arbitrary? (Gerstner)
3. Is the measure comfortable? (45--75 characters)
4. Is the vertical rhythm maintained? (Spacing as multiples of base leading)
5. Are no more than 2 typefaces used? (Santa Maria)
6. Is the hierarchy clear? (Can you scan and find information intuitively?)
7. Is the type size appropriate for the column width? (Vignelli)
8. Is the leading appropriate for the typeface, size, and measure? (Bringhurst, Brown)
9. Does it work across viewports? (Brown, Rutter)
10. Is it timeless rather than trendy? (Vignelli)
11. Is full attention given to incidental details? (Bringhurst)
12. Does the typography invite, then disappear? (Rutter)

---

## Alignment with Live Wires

This skill shares philosophy with the Live Wires CSS framework. Live Wires implements many of these principles:

- Fluid type scaling via `clamp()` across 13 sizes
- Progressive line-height ratios (body 1.5, headings 1.3, display 1.1)
- Complete type packages (size + line-height + letter-spacing)
- Baseline rhythm alignment
- `text-wrap: balance` and `text-wrap: pretty`

When working in HTML/CSS, reference the Live Wires `livewires` skill for implementation specifics. This typography skill provides the *why*; Live Wires provides the *how*.

---

## Domain Reference Guide

| Topic | File | When to Load |
|---|---|---|
| **Swiss Modernism** | `references/swiss-modernism.md` | Deep dive on Müller-Brockmann, Gerstner, Vignelli |
| **Web Typography** | `references/web-typography.md` | Web-specific rules from Brown, Rutter, Latin, Santa Maria |
| **Evaluation Framework** | `references/evaluation-framework.md` | Detailed critique methodology with specific criteria |
