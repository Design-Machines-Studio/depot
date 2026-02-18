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
   - Type: Top
   - Count: Height / baseline unit
   - Height: Your baseline unit (e.g., 24px)
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
   - Start: Match top margin
   - Increment Every: Your baseline unit
   - View Threshold: 75%
3. **Multiple Master Pages**: Create variants for different section types
   - "A-Feature" -- 3 columns with wide margins
   - "B-Standard" -- 4 columns
   - "C-Data" -- 6 columns for tables and charts

### Liquid Layouts for Multi-Format

Use liquid layout rules to adapt a single grid system across page sizes:
- Guide-based: Columns and guides reposition proportionally
- Object-based: Elements resize and reposition within rules
