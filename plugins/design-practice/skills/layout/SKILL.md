---
name: layout
description: "Design Machines editorial layout and art direction philosophy rooted in grid systems, reader-centered design, and visual storytelling. Use when critiquing page layouts, advising on grid construction, evaluating editorial spreads, or reviewing art direction decisions. Draws on Müller-Brockmann, Gerstner, Franchi, White, Lupton, Turley, Chimero, and Caldwell. Covers HTML/CSS, Figma, InDesign, Illustrator, and Affinity."
---

# Layout and Art Direction

Design your grid as a programme (Gerstner), build it on mathematical proportions (Müller-Brockmann), use it as a flexible structure for arranging type hierarchically (Lupton), then allow content to rupture it where editorial meaning demands (Turley).

**You never generate designs. You inform, critique, and advise.**

---

## The Four Positions

Every layout decision exists on a spectrum between four positions. The strongest editorial design draws on all of them simultaneously.

### 1. Rationalist Structure (Müller-Brockmann)

The grid divides space into consistent horizontal and vertical modules with uniform gutters. Mathematical proportions govern all relationships. Elements are placed precisely. The grid creates intelligibility, order, and faster comprehension. "The use of the grid system implies the will to systematize, clarify, penetrate to the essentials."

### 2. Systematic Flexibility (Gerstner)

The grid is a programme -- a rule set that accommodates unpredictable content. His 58-module mobile grid for Capital magazine allowed 2, 3, 4, 5, and 6 column configurations within a single system. "Instead of solutions for problems, programmes for solutions." Maximum conformity with maximum freedom.

### 3. Reader Service (White)

People don't want to read. They are lazy and in a hurry. They scan for 2.5 seconds before turning the page. Every layout decision must pass the WIIFM test (What's In It For Me?). Design as psychology (use curiosity), service (organize for ease), and interpretation (emphasis where deserved).

### 4. Expressive Disruption (Turley)

Learn the grid thoroughly, then break it deliberately. Photography, illustration, display type, and infographics sit free of the grid -- they disrupt to give energy and tone. "The design and type is quite formal and boring when you really look at it. What sits on top is multiple crazed levels of irony, sarcasm and visual spin."

---

## Grid Construction

### Module-Based Grids (Müller-Brockmann)

- Divide space into consistent horizontal and vertical units (modules)
- Vertical distance between fields: one, two, or more lines of text
- Horizontal spacing depends on type character size and illustrations
- Grid complexity scales from 8 to 32 fields depending on the publication
- Negative space is as active as positive space
- Sans-serif typography, generally lowercase, for maximum objectivity

### The Mobile Grid (Gerstner)

- Start from a single module, divide recursively
- Allow multiple column configurations within one system
- Text and pictures divided simultaneously
- Flexible enough for any content, consistent enough for every issue
- The grid is a "proportional regulator for composition, tables, pictures"

### Practical Grid Rules

| Principle | Guidance |
|---|---|
| **Margins** | Wider outside than gutter; bottom wider than top |
| **Columns** | 2--6 for editorial; single column for long-form reading |
| **Gutters** | Consistent; wide enough to prevent column bleed |
| **Baseline grid** | Match your leading unit; all text snaps to it |
| **Hanging elements** | Allow images, pull quotes, and display type to break the grid intentionally |

---

## Visual Hierarchy

### Hierarchy Through Type (Lupton)

Scale, weight, color, spacing, and placement create typographic hierarchy. Changes in scale express priorities. An effective grid is not a rigid formula but a flexible and resilient structure. "Think more, design less."

### The Three Modes of Editorial Design (White)

1. **Design as Psychology** -- use curiosity to keep readers engaged; let captions lead from pictures to text
2. **Design as Service** -- organize information for ease; think for the reader through lists and infographics
3. **Design as Interpreter** -- use type contrasts and color functionally to create emphasis where deserved

### Pacing and Rhythm

- **Micro-pacing**: arrangement within a single spread
- **Macro-pacing**: flow across the entire publication
- Alternate between dense, information-rich spreads and open, breathing ones
- Design in spreads, not individual pages -- readers see both sides together
- Section breaks let content breathe and orient the reader

---

## Art Direction Philosophy

### Purpose Before Craft (Chimero)

Before asking How (which grid? which typeface?), ask Why. What is the editorial intent? What should the reader feel, know, or do? "How enables, but Why motivates."

### Controlled Chaos (Turley)

Allow multiple design voices within the same publication. Let nervousness about an idea being "not quite right" signal creative risk worth taking. Hire hybrid talents who can cross disciplines.

### Integrated Storytelling (Franchi)

Develop text, headlines, photographs, and infographics together as a unified visual story. The art director is a journalist. Every visual element must advance the narrative. "A visual form that is as graphic as it is narrative, as entertaining as it is informative."

### Content Determines Form

- The grid serves content, not the reverse (Müller-Brockmann)
- Content is the variable the programme must accommodate (Gerstner)
- Consistent voice matters more than consistent style (Chimero)
- Both word people and design people have the same task: reveal the message plainly and compellingly (White)

---

## Digital Editorial Design (Chimero)

Every material has a grain. The web's grain favors fluidity, verticality, and assembly.

### Patterns That Honor the Web's Grain

- Flat colors and simple gradients
- Horizontal content stripes
- Large typography over atmospheric images
- Mosaic layouts
- Text as interface
- Build up from small elements, don't break down from large containers

### Edgelessness

- **Structural**: Infinite linking between content
- **Visual**: Fluid, unbounded canvases
- **Technical**: Spectrum of device sizes
- **Organizational**: Dissolved disciplinary boundaries

### The Key Distinction

Digital is not degraded print; it is a different material with its own grain. Print allows precise grid construction with fixed proportions. Digital requires fluid systems that compose rather than decompose.

---

## Tool-Specific Guidance

### HTML + CSS
- Use CSS Grid for editorial layouts -- it is the closest digital equivalent to Müller-Brockmann's grid systems
- Use `grid-template-columns` with `fr` units for proportional columns
- Use CSS `subgrid` for nested alignment to the parent grid
- Container queries for component-level responsiveness
- Reference Live Wires layout primitives (stack, grid, cluster, sidebar, switcher)

### Figma
- Set up a grid system with columns, gutters, and margins matching your programme
- Use auto layout for systematic spacing
- Create frame variants for different column configurations
- Design at actual output sizes, not arbitrary artboard dimensions
- Use constraints for responsive behavior testing

### Adobe InDesign
- Master pages define the grid programme
- Use multiple master pages for different column configurations (Gerstner's mobile grid)
- Parent-child relationships for systematic section handling
- Liquid layouts for multi-format adaptation
- Set baseline grid in document preferences

### Adobe Illustrator
- Use artboards as spread simulation
- Set up grid guides matching your module system
- Use symbols for repeated layout elements

### Affinity Publisher
- Master pages with multiple column configurations
- Baseline grid matching your leading unit
- Section-level master page assignment
- Spread-based design view

---

## Quick Evaluation Framework

When critiquing a layout, assess these eight dimensions:

1. **Structural Integrity** (Müller-Brockmann): Is there a visible, rational grid? Are proportions mathematically consistent?
2. **Systematic Coherence** (Gerstner): Does the layout follow from a programme? Could it handle entirely different content?
3. **Information Integration** (Franchi): Are text, images, and data developed as a unified story?
4. **Reader Service** (White): Does the reader grasp the story's value within 2.5 seconds? Is the WIIFM test passed?
5. **Typographic Clarity** (Lupton): Does the hierarchy communicate importance through scale, weight, and spacing?
6. **Art Direction Courage** (Turley): Does the layout take creative risks? Is there energy and personality?
7. **Purpose and Medium Fit** (Chimero): Has the designer asked Why before How? Does the layout work with the grain of its medium?
8. **Cross-Media Viability** (Caldwell): Does the design system translate across print and digital?

---

## Domain Reference Guide

| Topic | File | When to Load |
|---|---|---|
| **Grid Systems** | `references/grid-systems.md` | Deep dive on Müller-Brockmann and Gerstner grid theory |
| **Editorial Design** | `references/editorial-design.md` | White, Franchi, Turley, Caldwell editorial principles |
| **Digital Editorial** | `references/digital-editorial.md` | Chimero's web-specific framework and responsive layout |
