# Digital Editorial Design

Frank Chimero's framework for web-native editorial design, plus principles for translating editorial design to screen.

---

## Frank Chimero -- The Shape of Design

### How vs. Why

Designers overemphasize How (craft, technique, execution) at the expense of Why (purpose, meaning, intent). The metaphor: a painter works near the canvas for execution and far from it for assessment. Both are essential, but Why is typically neglected because How is more easily framed.

"How enables, but Why motivates." Understanding objectives enables forward movement despite execution missteps. Extraordinary craft without purpose becomes hollow imitation -- like a mockingbird expertly mimicking car alarms without understanding why.

### Design as Gift

"Design gains the ability to nourish when it acts as a gift" rather than something designed to create yearning. The story of successful design: begins with the maker's movement during creation, amplifies through publishing, continues in the feeling it stirs in the audience, and intensifies as the audience passes it on.

### Consistent Voice Over Consistent Style

"Consistent voice is more important than consistent style." What you communicate matters more than how it looks. The content's character should shape the design's character, not the reverse.

### The Ten Principles

1. Be honest
2. Consistent voice > consistent style
3. Does it have heart?
4. Modest expectations -- one primary goal, executed excellently
5. Don't be scared of your tools
6. Embrace the subconscious
7. Edit ruthlessly
8. Being too comfortable is dangerous
9. Nothing keeps you from doing the work you wish
10. Execute -- an idea on the page is worth 100x an idea in the mind

---

## The Web's Grain (2015)

The single most important text for understanding how editorial design principles translate to digital.

### Every Material Has a Grain

The web's grain favors fluidity, verticality, and assembly. Working against it creates fragile, difficult experiences. Design must work *with* the grain, not against it.

### The Web Is an Edgeless Surface of Unknown Proportions

Comprised of small, individual, variable elements assembled into a readable whole. There is no fixed page, no predetermined dimensions, no reliable context.

### Build Up, Don't Break Down

Responsive design should focus on how elements compose, not how they decompose. Sketch content arrangements first, then determine size.

**The traditional approach (wrong for the web):** Start with a large canvas, break it down for smaller screens.

**Chimero's approach (working with the grain):** Start with individual content elements, define how they compose into arrangements at any size.

### Patterns That Honor the Grain

| Pattern | Why It Works |
|---|---|
| **Flat colors** | Render identically everywhere |
| **Simple gradients** | Lightweight, scalable |
| **Horizontal content stripes** | Natural flow in a vertical medium |
| **Large typography over atmospheric images** | Typography is native to the web; images are supporting |
| **Mosaic layouts** | Modular, recomposable |
| **Text as interface** | The web's primary material |

### Patterns That Fight the Grain

| Pattern | Why It Struggles |
|---|---|
| **Fixed-width layouts** | Breaks on unexpected viewports |
| **Pixel-perfect compositions** | Impossible to maintain across devices |
| **Heavy image dependence** | Slow, fragile, not universally accessible |
| **Complex layered compositions** | Difficult to reflow |
| **Print metaphors forced onto screen** | Different material, different grain |

### Edgelessness at Every Level

| Level | Manifestation |
|---|---|
| **Structural** | Infinite linking between content |
| **Visual** | Fluid, unbounded canvases |
| **Technical** | Spectrum of device sizes |
| **Organizational** | Dissolved disciplinary boundaries |

---

## Translating Editorial Design to Screen

### What Transfers Directly

- **Grid systems**: CSS Grid implements Müller-Brockmann's grid theory natively
- **Typographic hierarchy**: Scale, weight, and spacing work the same way
- **Visual storytelling**: Hook, entry, orientation, development, resolution
- **Reader service**: The WIIFM principle applies everywhere
- **Pacing**: Macro-pacing through scroll, not page turns

### What Must Transform

| Print Concept | Web Equivalent |
|---|---|
| **Spread** | Viewport-height section or scroll sequence |
| **Page turn** | Scroll position or route change |
| **Fixed margins** | Responsive margins via `clamp()` or container queries |
| **Baseline grid** | CSS rhythm system with consistent spacing units |
| **Bleeding images** | Full-width sections or `object-fit: cover` |
| **Pull quotes** | Sticky or scroll-activated emphasis |
| **Captions** | `<figcaption>` with responsive positioning |
| **Column layout** | CSS Grid with responsive column counts |

### What Has No Print Equivalent

- **Interaction**: Hover states, click targets, focus indicators
- **Motion**: Scroll-driven animation, transitions, reveals
- **Adaptive content**: Content that changes based on viewport, context, or user state
- **Linking**: Every element can connect to every other element
- **Performance**: Load time and perceived responsiveness as design concerns

---

## CSS Editorial Layout Patterns

### The Horizontal Content Stripe

```css
.section {
  padding-block: calc(var(--baseline) * 4);
}

.section--hero {
  min-height: 100svh;
  display: grid;
  place-items: center;
}

.section--feature {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: var(--gutter);
  max-width: var(--max-width);
  margin-inline: auto;
}
```

### The Mosaic Layout

```css
.mosaic {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(300px, 100%), 1fr));
  gap: var(--gutter);
}
```

### The Sidebar Layout

```css
.with-sidebar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(250px, 25%);
  gap: var(--gutter);
}

@container (max-width: 600px) {
  .with-sidebar {
    grid-template-columns: 1fr;
  }
}
```

### Scroll-Driven Pacing

```css
/* Reveal sections on scroll */
.section {
  animation: fade-in linear;
  animation-timeline: view();
  animation-range: entry 0% entry 30%;
}

@keyframes fade-in {
  from { opacity: 0; transform: translateY(2rem); }
  to { opacity: 1; transform: translateY(0); }
}
```
