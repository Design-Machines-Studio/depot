# AI Slop Detector

A deterministic checklist for catching generic AI-generated design output. Run as a quality gate by review agents after their primary evaluation phases.

## The Swiss Test

> "If someone told you an AI made this, would you believe them immediately?"

If yes, the output fails. AI-generated design converges on predictable choices because every LLM learned from the same templates. The result is the opposite of what Muller-Brockmann demands -- "systematize, clarify, penetrate to the essentials." AI slop is generic, decorative, and structurally shallow.

A design passes the Swiss Test when it shows **authorial intent**: choices that serve this specific content, this specific audience, in this specific medium. Gerstner's programme methodology requires that every decision derive from defined criteria -- not from training-data frequency.

---

## Checklist (score each item 0 or 1)

### Layout (5 points)

- [ ] **No centered hero stack** -- The page does NOT open with centered heading + centered subheading + centered CTA (the single most common AI layout pattern). Exception: intentional display typography at `--text-5xl+` on brand pages.
- [ ] **Card hierarchy exists** -- Card-based layouts have visual hierarchy (varied widths, spans, or prominence) rather than three-or-more equal-weight cards in a row. Gerstner: equal weight = no hierarchy = no guidance for the reader.
- [ ] **Section rhythm varies** -- Sections have different density, structure, or composition. Not every section follows the same heading + paragraph + button template. White: alternate between dense and open for pacing.
- [ ] **Horizontal composition present** -- At least one content area uses horizontal layout (`.grid`, `.sidebar`, `.cluster`) rather than pure vertical stacking. Muller-Brockmann's grid IS horizontal + vertical composition.
- [ ] **Whitespace is active** -- Empty space serves compositional purpose (grouping, separating, breathing room) rather than being leftover from layout defaults.

### Typography (5 points)

- [ ] **Scale-derived sizes** -- Type sizes derive from a modular scale or defined system, not round pixel values (16/18/24/36/48). The three-property scale (f0, r, n) produces distinctive, non-obvious sizes.
- [ ] **Intentional typeface** -- The typeface is a considered choice for this project, not a training-data default used without justification. (If using Inter, Poppins, Montserrat, etc. -- there should be a documented reason. For DM properties, GT Standard is always correct.)
- [ ] **Multi-dimensional hierarchy** -- Heading levels vary in more than just size. Weight, case, letter-spacing, or color also change between levels. A hierarchy that's only "bigger = more important" lacks craft.
- [ ] **Controlled measure** -- Body text line length stays within 45-75 characters (Bringhurst). No text running edge-to-edge.
- [ ] **Intentional letter-spacing** -- Tracking varies by context (tighter on display, default on body, wider on small caps/labels) rather than being identical everywhere.

### Color (5 points)

- [ ] **No decorative gradients** -- Backgrounds don't use saturated or neon gradients purely for decoration. Gradients encode meaning (progress, spectrum) or are absent.
- [ ] **Color encodes meaning** -- Color is used for status, hierarchy, or emphasis -- not just to "make it pop." Every colored element should answer: what does this color communicate?
- [ ] **Token-based palette** -- Colors come from project tokens or scheme classes, not arbitrary hex values. `.scheme-*` for themed sections, semantic tokens for status.
- [ ] **Comfortable contrast** -- Text contrast goes beyond WCAG minimum to genuinely comfortable reading. Dark-on-white body text isn't `#666` -- it's a tinted near-black with real weight.
- [ ] **Tinted neutrals** -- Gray tones carry a hint of the brand hue rather than being pure neutral gray. Even 0.01 chroma in OKLCH creates cohesion that pure gray cannot.

### Content (5 points)

- [ ] **No placeholder names** -- No "John Smith," "Jane Doe," "Acme Corp," "Sarah Johnson." Sample data uses contextually plausible names for the domain.
- [ ] **Realistic numbers** -- Data values are specific and plausible, not round numbers (10, 25, 50, 100, 99.9%). Real data has irregular values.
- [ ] **Specific CTAs** -- Buttons say what they do: "Submit proposal," "View member profile," "Export report." Not "Get Started," "Learn More," "Click Here."
- [ ] **No startup cliches** -- Copy avoids "Transform your X," "Empower your team," "Seamless experience," "Next-generation platform." Specific value propositions instead.
- [ ] **Personality in microcopy** -- Empty states, tooltips, and helper text have a human voice. Not template language that could belong to any product.

### Interaction (5 points)

- [ ] **Skeleton loaders for content** -- Data-loading states use skeleton placeholders matching the populated layout, not generic spinners. Spinners are acceptable only for brief, unknown-duration actions (form submission).
- [ ] **Composed empty states** -- Empty views include explanation + contextual illustration/icon + CTA. Not just "No data found."
- [ ] **Constructive error states** -- Error messages explain what went wrong, why, and how to fix it. Not just "An error occurred."
- [ ] **Smooth transitions** -- Hover/focus transitions use 150-200ms ease, not bounce/elastic easing. Real objects decelerate smoothly.
- [ ] **Destructive differentiation** -- Delete/remove/archive actions are visually distinct (color, position) from create/edit actions and require confirmation for irreversible operations.

---

## Scoring

| Score | Rating | Meaning |
|-------|--------|---------|
| 25/25 | **No AI tells** | Output shows authorial voice and structural intent |
| 20-24 | **Minor tells** | Polish pass recommended -- a few patterns need attention |
| 15-19 | **Moderate tells** | Several patterns need rethinking, not just polishing |
| 10-14 | **Significant tells** | Redesign specific sections rather than polishing |
| <10 | **Pervasive slop** | Fundamental rethinking needed -- output is generic throughout |

---

## Integration with Review Agents

### For ux-quality-reviewer

Run this checklist as Phase 10 (after Interaction Polish). Score the page on all 25 points. If the score is below 20, add a P2 finding:

```
AI output quality: [score]/25. Swiss Test: [PASS/FAIL].
Tells detected: [list the specific failed checklist items]
```

This phase runs AFTER all other evaluation phases so it incorporates observations from earlier phases rather than duplicating work. Many checklist items will already have been noted -- this phase collates them into a single score.

### For ui-standards-reviewer

Run this checklist as Phase 7 (after Comparative Assessment). The SaaS quality rating in Phase 6 evaluates polish -- this phase evaluates distinctiveness. A page can score 7/10 on SaaS standards but still feel AI-generated if every choice is the safe, predictable option.

Report the score alongside the SaaS rating:

```
Page: /proposals
SaaS Rating: 7/10 (Good SaaS)
AI Slop Score: 22/25 (Minor tells)
Tells: centered hero stack, round numbers in stat cards, generic "Get Started" CTA
```
