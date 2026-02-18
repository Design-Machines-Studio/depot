---
name: dataviz
description: "Design Machines data visualization and information graphics philosophy rooted in graphical integrity, data-ink efficiency, and editorial integration. Use when critiquing charts and graphs, advising on visualization choices, evaluating information graphics, or reviewing data presentations. Draws primarily on Dona M. Wong, Edward Tufte, and Francesco Franchi. Covers HTML/CSS, Figma, InDesign, Illustrator, and Affinity."
---

# Data Visualization

Above all else, show the data. Add as many layers of information as necessary to convey the key message, and not one bit more. Simplify, simplify, simplify.

Infographics are not decoration -- they are acts of journalism. A visualization is simultaneously design and narrative, representation and interpretation.

**You never generate designs. You inform, critique, and advise.**

---

## Three Governing Principles

### 1. Graphical Integrity (Tufte)

The representation of numbers, as physically measured on the surface of the graph, must be directly proportional to the numerical quantities represented. Show data variation, not design variation. Graphics must not quote data out of context.

### 2. Data-Ink Efficiency (Tufte)

Maximize the share of ink devoted to non-redundant display of data information. Erase non-data-ink. Erase redundant data-ink. Revise and edit.

**Data-ink ratio** = Data-ink / Total ink used

### 3. Journalistic Responsibility (Franchi)

Data visualization is a narrative language: representation plus interpretation to develop an idea. The designer shapes a view of the data with a particular goal. Design serves as content, and the designer works as a facilitator.

---

## Chart Type Selection (Wong)

| Chart Type | Use When | Rules |
|---|---|---|
| **Bar chart** | Comparing discrete categories; 5+ data points | Start Y-axis at zero; bar width = 2x spacing; max 5 bars ideal; shade left-to-right lightest-to-darkest |
| **Line chart** | Showing trends over time | Max 4 lines (never exceed 5); label directly on lines; Y-axis = 2/3 of chart area |
| **Pie chart** | Part-to-whole with 2--3 segments | Largest slice starts at 12 o'clock, clockwise; never exceed 5--7 segments; no 3D ever |
| **Table** | Small datasets under 20 values; precise lookup needed | Not for visual comparison |
| **Sparkline** | Inline trend context in text or tables | No axes, labels, or decoration; word-sized |
| **Small multiples** | Comparing many series across one variable | Consistent frame, consistent scale, let the eye detect patterns |

---

## The Lie Factor (Tufte)

**Lie Factor** = Size of effect shown in graphic / Size of effect in data

| Lie Factor | Meaning |
|---|---|
| **1.0** | Truthful |
| **> 1.05** | Substantial overstatement |
| **< 0.95** | Substantial understatement |

Any deviation from 1.0 distorts the reader's perception.

---

## Color Rules

| DO | DON'T |
|---|---|
| Use gray for grids, backgrounds, secondary elements | Use bright colors for structural elements |
| Assign color only when it encodes information | Use color for decoration or branding in data areas |
| Ensure legibility without color (B&W test) | Rely on color alone to differentiate data |
| Use muted, naturally blended backgrounds | Use fully saturated primaries for everything |
| Bright/saturated for primary data, muted for context | Give equal visual weight to all elements |
| Use the smallest effective difference between categories | Over-differentiate with excessive contrast |

**Gray is the most important color in information design** (Tufte). Use it for grids, backgrounds, and contextual elements so data colors stand out naturally.

---

## Typography in Charts (Wong)

- Use simple, legible typefaces -- no decorative or novelty fonts
- Never combine bold AND italic -- choose one
- No ALL CAPS in charts
- No angled or rotated text on axes -- rotate the chart instead
- Write full names in tables; use abbreviations on axes sparingly
- Align decimals with ".0" notation for whole numbers
- Limit text to title, subtitle, and annotations

---

## Labeling and Annotation (Wong + Tufte)

- Label data directly on the chart rather than in a separate legend
- Disclose missing data via footnote
- For bar charts with missing data: leave the space empty
- For line charts: draw through gaps if the broad trend is the message
- Always include: source, date, measurement units, and full context
- Annotations should explain the data story, not repeat what's visible

---

## Tufte's Six Principles of Analytic Design

1. **Comparisons**: Always answer "Compared to what?"
2. **Causality**: Show cause-and-effect, not just correlation
3. **Multivariate**: The world is multivariate; your displays should be too
4. **Integration**: Treat words, numbers, images, and diagrams as equals
5. **Documentation**: Thoroughly describe sources, scales, and provenance
6. **Content**: Analytical presentations stand or fall on content quality

---

## Scale and Axes (Wong)

- Use natural increments: 1, 2, 5, 10, 20, 50, 100
- Always start bar chart Y-axes at zero
- Draw the zero baseline thicker and heavier than other grid lines
- Adjust Y-axis scale to emphasize the intended comparison
- When comparing stocks or financial data, use percentage change, not absolute values
- Provide historical comparison data for context
- Standardize metrics across related charts

---

## Eliminating Chartjunk (Tufte)

Remove everything that does not represent data variation:

- Moire vibration patterns
- Heavy grid lines competing with data
- Self-promoting graphics showcasing the designer
- 3D effects and decorative dimensionality
- Unnecessary shading and gradients
- Redundant annotations restating what visuals show

**The 1+1=3 effect**: Two adjacent visual elements create an unintended third element. Manage through subtle spacing, muted colors, and the smallest effective difference.

---

## Editorial Integration (Franchi)

### Infographic Thinking

Not "how to make numbers and vectors look clever together" but a narrative language. The viewer is invited to join in the process of interpretation.

### The Hybrid System

Infographics combine verbal and visual communication systems. Words, images, and numbers together offer the greatest opportunity to increase communication effectiveness.

### Layered Communication

- Hide some elements and reintroduce them later
- Create overviews with key data points accompanied by drawings, illustrations, photos, and boxes
- Develop text, headlines, photography, and infographics together as a unified story

---

## Tool-Specific Guidance

### HTML + CSS
- Use SVG for charts (scalable, accessible, stylable)
- D3.js for complex, data-driven visualizations
- Implement Tufte's principles: light grid lines via `stroke-opacity`, direct labels, minimal decoration
- Use `<figure>` and `<figcaption>` for accessible chart markup
- Sparklines can be inline SVG within text

### Figma
- Use auto layout for systematic chart construction
- Create component variants for different chart types
- Use consistent color tokens for data encoding
- Test at actual display sizes

### Adobe InDesign
- Use anchored objects for charts that flow with text
- Set up graph styles for consistent treatment across a publication
- Use layers to separate data from annotation from grid

### Adobe Illustrator
- Best tool for custom infographics and chart refinement
- Use the graph tools as a starting point, then manually refine
- Strip chartjunk: remove default grid lines, box borders, 3D effects
- Apply Tufte's data-ink principle: delete everything you can without losing data

### Affinity Designer
- Use symbols for repeated chart elements (axis markers, grid lines)
- Export at multiple resolutions for print and screen
- Use constraints for responsive chart sizing

---

## Quick Evaluation Checklist

When critiquing a data visualization:

1. **Integrity**: Is the Lie Factor between 0.95 and 1.05? Are proportions truthful?
2. **Data-ink**: Could any ink be removed without losing data? Is the ratio maximized?
3. **Chart type**: Is this the right chart for this data? (Trends = line; comparison = bar; part-to-whole = pie)
4. **Color**: Does color encode information or just decorate? Does it pass the B&W test?
5. **Labels**: Are elements labeled directly? Is there a legend when direct labeling would work?
6. **Context**: Is the source disclosed? Are there comparison baselines? Is "Compared to what?" answered?
7. **Typography**: Simple fonts? No rotated text? No ALL CAPS? No bold-italic combos?
8. **Scale**: Does the Y-axis start at zero (for bar charts)? Are increments natural?
9. **Chartjunk**: Any 3D effects, moire patterns, heavy grids, or decorative elements?
10. **Narrative**: Does the visualization tell a story, or just display numbers?

---

## Domain Reference Guide

| Topic | File | When to Load |
|---|---|---|
| **Chart Rules** | `references/chart-rules.md` | Wong's detailed dos and don'ts for every chart type |
| **Tufte Principles** | `references/tufte-principles.md` | Full Tufte framework: data-ink, integrity, analytic design |
| **Editorial Dataviz** | `references/editorial-dataviz.md` | Franchi's integration of data visualization in editorial context |
