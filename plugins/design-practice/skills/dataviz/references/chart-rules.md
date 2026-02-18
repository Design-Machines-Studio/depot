# Chart Rules

Dona M. Wong's detailed rules for every chart type, from The Wall Street Journal Guide to Information Graphics.

---

## Bar Charts

### When to Use
- Comparing discrete categories
- When you have more than 5 data points
- When precise comparisons between values matter

### Construction Rules

| Rule | Requirement |
|---|---|
| **Y-axis** | Must start at zero (the zero baseline rule) |
| **Zero baseline** | Draw thicker and heavier than other grid lines |
| **Bar width** | Approximately 2x the spacing between bars |
| **Bar count** | Limit to 5 bars when possible |
| **Shading** | Left-to-right, lightest to darkest |
| **Legend order** | Match the order bars appear |
| **Horizontal bars** | Use for ranking/ordering and long category labels |

### Missing Data
- Leave the space empty
- Do not plot if more than 2 of 10 data points are missing

### Common Mistakes
- Starting Y-axis above zero (exaggerates differences)
- Bars too wide or too narrow relative to spacing
- Rotated axis labels (rotate the chart instead)
- 3D effects (distort perception of bar heights)

---

## Line Charts

### When to Use
- Showing trends over time (time-series data)
- When the relationship between sequential data points matters

### Construction Rules

| Rule | Requirement |
|---|---|
| **Maximum lines** | 4 (never exceed 5; use 3 if lines intersect heavily) |
| **Line differentiation** | Use weight and shading variation, not patterns |
| **Avoid** | Dotted and dashed lines |
| **Y-axis proportion** | Should occupy approximately 2/3 of the chart area |
| **Labels** | Place directly on lines, not in a separate legend |
| **Scale** | Steep lines = significant increase; flat lines = smaller changes |

### Missing Data
- Draw through gaps if the broad trend is the message
- Disclose gaps via footnote

### Common Mistakes
- Too many lines making the chart unreadable
- Using patterns (dots, dashes) instead of weight variation
- Legend separated from the data it describes
- Y-axis scale that makes minor fluctuations appear dramatic

---

## Pie Charts

### When to Use
- Part-to-whole comparisons with 2--3 segments
- When you want to show simple proportions

### Construction Rules

| Rule | Requirement |
|---|---|
| **Starting position** | Largest segment at 12 o'clock |
| **Direction** | Proceed clockwise |
| **Segment count** | Easiest with 2--3; never exceed 5--7 |
| **Missing data** | Never create pie charts with missing slices |
| **Nesting** | Never chain or nest pie charts |
| **3D** | Never. Distorts magnitude perception. |
| **Decoration** | None -- no extra visual elements |

### Common Mistakes
- Too many segments (use a bar chart instead)
- Starting anywhere other than 12 o'clock
- 3D rendering (makes front slices appear larger)
- Exploded slices (reduces comparison accuracy)
- Using a pie chart when a bar chart would serve better

---

## Tables

### When to Use
- Small datasets under 20 values
- When precise lookup is needed
- When exact values matter more than visual comparison

### Construction Rules
- Write full names (avoid abbreviations)
- Align decimals with ".0" notation for whole numbers
- Right-align numbers, left-align text
- Use light horizontal rules to aid scanning; avoid vertical rules
- Sort meaningfully (alphabetical, chronological, or by value)

---

## Sparklines

### When to Use
- Inline trend context in text or dashboards
- When space is limited but trend information is valuable

### Construction Rules
- Word-sized: fit within a line of text
- No axes, labels, or decoration
- Show trend, variation, and context at a glance
- High data density in minimal space

---

## Small Multiples

### When to Use
- Comparing many series across a shared variable
- When a single chart would have too many overlapping elements
- When you want the eye to detect patterns across consistent frames

### Construction Rules
- Each frame uses the same scale, axes, and format
- Vary only one dimension (time, category, geography)
- Arrange in a logical sequence (chronological, spatial, categorical)
- Keep individual frames simple -- the power is in comparison

---

## Scale and Axes

### Natural Increments
Always use: 1, 2, 5, 10, 20, 50, 100
Never use: 3, 7, 15, 25 (unnatural, harder to read)

### The Zero Baseline Rule
- Bar charts: Y-axis MUST start at zero
- Line charts: Starting above zero is acceptable when showing relative change
- The zero baseline should be drawn thicker than other grid lines

### Comparison Across Charts
- When comparing related data in adjacent charts, standardize:
  - The same axis scale
  - The same time period
  - The same units
  - The same color encoding

### Financial Data
- Use percentage change, not absolute values, for stock comparisons
- Adjust for inflation in time-series monetary data
- Explain the relative significance of percentages

---

## Color in Charts

### Wong's Rules

| DO | DON'T |
|---|---|
| Add color only if it conveys information | Use color for decoration |
| Use meaningful encoding (red = loss, green = gain) | Use arbitrary color choices |
| Ensure legibility in black and white | Rely on color alone to differentiate |
| Use different line weights when color unavailable | Use color for branding in data areas |
| Differentiate hierarchy with color, not just categories | Give equal visual weight to all elements |

---

## Typography in Charts

### Wong's Typography Rules

| DO | DON'T |
|---|---|
| Use simple, legible typefaces | Use decorative or novelty fonts |
| Use bold OR italic for emphasis | Combine bold AND italic |
| Keep all text horizontal | Angle or rotate axis labels |
| Write full names in tables | Over-abbreviate without explanation |
| Align decimals with ".0" for whole numbers | Mix alignment in numeric columns |
| Limit to title, subtitle, annotations | Crowd charts with text |

### Never
- ALL CAPS in charts
- Condensed fonts that sacrifice legibility
- Type that is too small to read comfortably
- Center-aligned text in data labels

---

## Statistical Awareness

When encountering data, know which statistical measure serves the communication goal:

| Measure | Best For | Watch Out For |
|---|---|---|
| **Mean** | Showing total impact | Skewed by outliers |
| **Median** | Rankings, typical values | Unaffected by extremes |
| **Mode** | Most likely outcomes | May not represent typical experience |
| **Weighted Average** | Emphasizing important data points | Requires transparent weighting |
| **Moving Average** | Revealing trends, smoothing volatility | Lags behind real-time data |
