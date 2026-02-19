# Grid Systems

Deep reference on grid theory and construction from Müller-Brockmann, Gerstner, and Lupton.

---

## Müller-Brockmann's Grid Theory

### The Purpose of the Grid

A grid creates "a sense of compact planning, intelligibility and clarity, and suggests orderliness of design." Information presented through grids is read more quickly, understood more easily, and retained in memory longer.

### Construction Method

1. **Define the page format** -- the outer boundary
2. **Set margins** -- wider outside than gutter; bottom wider than top (traditional proportions)
3. **Divide into columns** -- based on content requirements and reading comfort
4. **Establish horizontal modules** -- using the baseline grid as the vertical unit
5. **Define gutters** -- consistent horizontal and vertical spacing between modules
6. **Create a field matrix** -- the intersection of columns and rows produces modules

### Grid Configurations

| Fields | Use Case |
|---|---|
| **4 fields** (2x2) | Simple layouts, title pages |
| **6 fields** (2x3 or 3x2) | Brochures, simple editorial |
| **8 fields** (2x4 or 4x2) | Moderate editorial complexity |
| **12 fields** (3x4 or 4x3) | Flexible editorial, catalogues |
| **20 fields** (4x5 or 5x4) | Complex publications |
| **32 fields** (4x8 or 8x4) | Maximum flexibility, newspapers |

### Müller-Brockmann's Rules

- Vertical distance between fields: one, two, or more lines of text
- Horizontal spacing depends on type character size and illustration size
- Elements are placed precisely within the framework -- never arbitrarily
- Typography is treated as spatial material, not ornament
- Aligning type to a grid achieves clarity, legibility, and coherence without sacrificing expressiveness
- 7--10 words per line for text of any length
- The grid is an aid, not a guarantee -- it requires practice to use well

---

## Gerstner's Mobile Grid

### The Capital Magazine System

For Capital magazine (1962), Gerstner designed a "mobile grid" based on 58 modules. Starting from a single module, he divided recursively to allow for multiple column configurations within the same system.

### Recursive Division

From the base module, the grid supports:
- 1 column (full width)
- 2 columns
- 3 columns
- 4 columns
- 5 columns
- 6 columns

All within the same page format, with the same baseline grid, using the same proportional relationships.

### Why It Matters

Capital's content was unpredictable -- varying article lengths, image sizes, data tables, advertisements. The mobile grid accommodated any content rapidly, creatively, and without restrictions, while maintaining visual coherence across issues.

### The Programme Principle Applied

The grid is "a proportional regulator for composition, tables, pictures, etc. It is a formal programme to accommodate x unknown items." This is Gerstner's central insight: design the system, not the page. The system then generates pages.

---

## Lupton's Grid Framework

### Grid as Flexible Structure

For Ellen Lupton, a grid breaks space into regular units. It can be simple or complex, tightly defined or loosely interpreted. Typographic grids are about control -- establishing a system for arranging content.

**An effective grid is not a rigid formula but a flexible and resilient structure.**

### Types of Grids

| Grid Type | Structure | Use Case |
|---|---|---|
| **Single column** | One text column with margins | Long-form reading, books |
| **Multi-column** | 2--6 equal or unequal columns | Magazines, newspapers, websites |
| **Modular** | Columns intersected by horizontal rows | Complex publications, dashboards |
| **Hierarchical** | Irregular divisions based on content priority | Websites, landing pages, posters |
| **Compound** | Multiple grid systems overlaid | Complex editorial with varied content types |

### Scale as Relative Force

Scale is always relative. The same 12-point type appears vastly different on a 32-inch monitor versus a printed page. Designers leverage scale variations to establish visual hierarchy, create movement, and express content priorities.

---

## Baseline Grid Construction

### The Fitbaseline Principle

The baseline grid must divide the **full page height** evenly -- not just the text block. This is the medieval scribe's approach: the grid covers the entire page, margins snap to grid lines, and the text block is simply the region where content is permitted.

Most designers make the error of choosing a round leading value (e.g., 14pt) and hoping it works out. It almost never does. If the baseline doesn't divide the page height into a whole number of rows, the grid accumulates error and overshoots the bottom margin.

### The Calculation

1. **Start with the page height** in points or millimeters
2. **Choose a target leading** based on body text requirements (e.g., 14pt for 10pt body)
3. **Divide page height by target leading** -- this will almost certainly not be a whole number
4. **Round to the nearest whole number of rows** that produces a fitted baseline close to your target
5. **The fitted baseline = page height ÷ whole rows** -- this is the exact increment
6. **Verify the deviation** from your target is acceptable (under 0.5pt is imperceptible)

Example for A4 (297mm = 841.89pt), targeting 14pt leading:

| Rows | Fitted Baseline | Deviation from 14pt |
|---|---|---|
| 58 | 14.515pt | +0.515pt |
| 59 | 14.269pt | +0.269pt |
| **60** | **14.031pt** | **+0.031pt** ← optimal |
| 61 | 13.801pt | -0.199pt |
| 62 | 13.579pt | -0.421pt |

60 rows produces 14.031pt -- a 0.22% deviation from 14pt, visually identical to 10/14 body text.

### Margins Snap to Baselines

Once the fitted baseline is established, margins are whole multiples of baselines, not round millimeters:

- **Top margin**: N baselines (e.g., 5 × 4.95mm = 24.75mm, not 25mm)
- **Bottom margin**: M baselines (e.g., 8 × 4.95mm = 39.60mm, not 40mm)
- **Text block height**: Total rows − top − bottom (e.g., 60 − 5 − 8 = 47 rows)

The sub-millimeter differences from round numbers are imperceptible but ensure mathematical perfection. The grid starts at Y=0 (page top) and ends exactly at the page bottom.

### Connection to Gerstner's Mobile Fields

Gerstner's field divisions work within the fitted baseline system. Given a text block of N rows and 1-baseline gutters between fields:

- **2 fields**: (N−1) ÷ 2 rows each, if the result is whole
- **3 fields**: (N−2) ÷ 3 rows each
- **4 fields**: (N−3) ÷ 4 rows each
- **6 fields**: (N−5) ÷ 6 rows each

Fields that share gutter positions with other divisions create a nested system -- 6-field gutters contain all 2-field and 3-field gutters. This nesting is what gives the mobile grid its flexibility: elements aligned to any division are also aligned to compatible divisions.

Not all text block heights support all divisions. Choose a text block row count that divides cleanly into the configurations you need (2, 3, 4, and 6 are the most useful -- 5 rarely divides evenly).

### Type Scale and Baseline Integration

The type scale and baseline grid are interdependent systems, not separate decisions.

**Leading values must be baseline multiples.** Body text sits on single baselines. Headings occupy 2, 3, or 4 baselines. If a heading's natural leading doesn't land on a baseline multiple, adjust the type size or leading until it does. The baseline is non-negotiable; the type scale bends to serve it.

**Heading spacing uses asymmetric baseline multiples.** Space above a heading (2--3 baselines) is larger than space below (0--1 baselines). This binds headings to their following content while maintaining vertical rhythm.

**The classical typographic scale and the baseline grid share mathematical roots.** The classical scale (6, 7, 8, 9, 10, 12, 14, 16, 18, 21, 24...) can be expressed as a three-property system analogous to a musical scale: initial term (a), octave ratio (r=2), and number of notes per octave (n=5). This pentatonic structure naturally produces sizes whose leading values fall on baseline multiples when the baseline itself is derived from the body text leading.

### Vertical vs Horizontal: Different Rules

**Vertical dimension must lock to the baseline.** That is the entire purpose of a baseline grid -- horizontal lines at precise intervals governing all vertical spacing.

**Horizontal dimension needs clean column math.** Baseline multiples for gutters and margins are nice-to-have, not essential. Round numbers (e.g., 5mm gutters, 175mm text block) produce cleaner column widths than forcing baseline alignment horizontally.

---

## CSS Grid as Modern Grid System

CSS Grid is the closest digital equivalent to Müller-Brockmann's grid systems:

```css
/* Müller-Brockmann-style 12-column grid */
.editorial-grid {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: var(--gutter);
  padding: var(--margin-top) var(--margin-outside) var(--margin-bottom) var(--margin-inside);
}

/* Gerstner-style mobile grid -- multiple column configs from one system */
.content-block--full { grid-column: 1 / -1; }
.content-block--half { grid-column: span 6; }
.content-block--third { grid-column: span 4; }
.content-block--quarter { grid-column: span 3; }
.content-block--two-thirds { grid-column: span 8; }

/* Baseline grid alignment */
:root {
  --baseline: 1.5rem; /* 24px at 16px base */
}

* {
  margin-top: 0;
  margin-bottom: 0;
}

* + * {
  margin-top: var(--baseline);
}
```

### Subgrid for Nested Alignment

```css
/* Child elements align to parent grid */
.editorial-grid > .nested-content {
  display: grid;
  grid-template-columns: subgrid;
}
```

---

## Figma Grid Implementation

### Setting Up an Editorial Grid

1. **Frame**: Set to your target viewport or page size
2. **Layout Grid**: Add a column grid
   - Columns: 12 (or your chosen count)
   - Type: Stretch
   - Margin: Match your outside margins
   - Gutter: Match your gutter width
3. **Baseline Grid**: Add a row grid
   - Type: Top (starting from top of frame, not top of content)
   - Count: Frame height ÷ fitted baseline unit
   - Height: Your fitted baseline unit
   - The baseline grid must tile the entire frame evenly
4. **Multiple grid configs**: Use variants or component sets for different column arrangements

### Design at Actual Sizes

- Desktop: 1440px or 1280px frame width
- Tablet: 768px frame width
- Mobile: 375px frame width
- Test content reflow across all three

---

## InDesign Grid Implementation

### Master Page Grid Setup

1. **Layout > Margins and Columns**: Set margins and column count
2. **Preferences > Grids**: Set baseline grid
   - Start: 0mm (Relative To: **Top of Page**, not top margin)
   - Increment Every: Your fitted baseline unit (calculated from page height ÷ whole rows)
   - View Threshold: 75%
   - The grid must cover the entire page. Starting from the top margin is a common error that breaks field division alignment.
3. **Multiple Master Pages**: Create variants for different section types
   - "A-Feature" -- 3 columns with wide margins
   - "B-Standard" -- 4 columns
   - "C-Data" -- 6 columns for tables and charts

### Liquid Layouts for Multi-Format

Use liquid layout rules to adapt a single grid system across page sizes:
- Guide-based: Columns and guides reposition proportionally
- Object-based: Elements resize and reposition within rules
