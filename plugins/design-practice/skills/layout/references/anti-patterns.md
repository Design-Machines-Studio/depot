# Layout Anti-Patterns

Named patterns to reject. Each includes the problem, why it fails (citing a DM source), and what to do instead.

---

## AI-Default Layouts

Patterns LLMs produce reflexively. If you see these in generated output, redesign.

### The Centered Hero Stack

- **Problem:** Full-width section with centered heading, centered subheading, centered CTA button. Every AI-generated landing page starts with this.
- **Why it fails:** White says readers scan for 2.5 seconds. Centered text in a left-reading culture slows scanning because the eye must find each line's start point. Muller-Brockmann: elements are placed precisely according to the grid, not defaulted to center alignment.
- **Fix:** Left-aligned hero with asymmetric composition. Editorial entry with image/type interplay (Turley). Grid-based hero with CTA in a predictable action zone. `.sidebar` layout with content left, visual right.
- **Exception:** For intentional display typography at large scale (`--text-5xl+`) on brand/marketing pages, centered headings can work. But the subheading and CTA should NOT also be centered -- break the axis.

### The Three-Equal-Cards Row

- **Problem:** Three cards, equal width, equal height, equal visual weight. The most generic AI layout pattern.
- **Why it fails:** Gerstner's programme demands hierarchy. Equal weight = no hierarchy = no guidance for the reader. The eye has nowhere to go first.
- **Fix:** Feature one card at 2x width (`.grid` with `span`). Use `.sidebar` with a primary card larger. Vary card height through content density. Use a numbered or sequential layout instead.

### The Side-Stripe Decoration

- **Problem:** Colored left border on cards or sections as the only visual treatment (`border-left: 4px solid var(--color-accent)`).
- **Why it fails:** It's a non-structural decoration that adds no information. Tufte's chartjunk principle applies to UI -- if removing the element changes nothing about the reader's understanding, it's chartjunk.
- **Fix:** Use `.scheme-*` classes for section differentiation (changes background + foreground as a system). Use typographic hierarchy to distinguish sections. Use `.box` with appropriate padding variant for containment.

### Cookie-Cutter Section Rhythm

- **Problem:** Every section follows the same structure: heading, paragraph, button. Same height, same padding, same visual weight. Repeat.
- **Why it fails:** White on pacing -- alternate between dense and open to maintain reader engagement. Turley on disruption -- energy comes from variation within structure. Identical sections create monotony.
- **Fix:** Vary section density: some with `.stack stack-compact`, others with generous `--line-6` spacing. Break with editorial elements (pull quotes, full-bleed images, data callouts). Change composition between sections -- some `.sidebar`, some full-width `.grid`, some single-column `.stack`.

### Grid Phobia (Everything is .stack)

- **Problem:** Vertical stacking of everything with no horizontal composition anywhere on the page.
- **Why it fails:** Muller-Brockmann's grid IS horizontal + vertical composition. Pure vertical stacking is a newspaper column, not a designed layout. It wastes the horizontal dimension entirely.
- **Fix:** Use `.grid`, `.sidebar`, `.cluster` for horizontal relationships. Reserve `.stack` for vertical content flow WITHIN grid cells. Even a simple `.sidebar` creates more visual interest than an endless vertical stack.

### The Symmetry Trap

- **Problem:** Every layout element is centered or evenly distributed. No asymmetry, no tension, no visual interest.
- **Why it fails:** Gerstner's flexible programme allows asymmetric configurations. Turley's editorial courage requires intentional disruption. Symmetry is safe but static -- it signals template thinking.
- **Fix:** Offset key elements. Use odd-numbered grid spans. Let whitespace accumulate on one side. Create visual tension through deliberate imbalance.

---

## Structural Anti-Patterns

### Gridless Design

- **Problem:** Elements positioned without reference to any column structure
- **Why it fails:** Muller-Brockmann: the grid IS the design method. Without a grid, element relationships are accidental rather than intentional.
- **Fix:** Establish a column grid. Use CSS Grid with `fr` units. In Live Wires, use `.grid` or `.sidebar` primitives that encode grid relationships.

### Decoration Over Content

- **Problem:** Visual effects (gradients, shadows, borders, background images) that don't serve the content hierarchy
- **Why it fails:** Chimero: ask Why before How. Tufte: maximize the data-ink ratio. Every visual element should communicate something. If removing a decoration changes nothing about the reader's understanding, it's unnecessary.
- **Fix:** Remove the decoration. If the design still works, it was unnecessary. If it doesn't, the decoration was compensating for a structural problem -- fix the structure instead.

### Fixed-Width Layouts

- **Problem:** Hardcoded pixel widths that ignore viewport variation
- **Why it fails:** Chimero's web grain: the web is fluid, vertical, and assembled from components. Fixed widths fight the medium.
- **Fix:** Use fluid layouts with `fr` units, `minmax()`, and container queries. In Live Wires, the layout primitives (`.grid`, `.sidebar`) are inherently fluid.

### Margin Collapse Avoidance

- **Problem:** Using padding or borders to prevent margin collapse instead of understanding it
- **Why it fails:** Margin collapse is a feature, not a bug. It produces the correct spacing when siblings meet. Fighting it with hacks signals misunderstanding of the box model.
- **Fix:** Use `.stack` (which handles spacing via `gap` or lobotomized owl) and `.box` (which handles containment padding). These primitives eliminate margin collapse problems by design.
