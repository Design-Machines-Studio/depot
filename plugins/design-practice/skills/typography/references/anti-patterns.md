# Typography Anti-Patterns

Named patterns to reject. Each includes the problem, why it fails (citing a DM source), and what to do instead.

---

## AI-Default Typography

Patterns that signal uncritical LLM output rather than considered design.

### Training-Data Default Fonts

LLMs gravitate toward fonts they've seen most in training data. When advising on typeface selection for non-DM projects, treat these as red flags -- not necessarily wrong, but requiring explicit justification:

- Inter, Poppins, Montserrat, Open Sans, Lato, Nunito, Raleway, Roboto, DM Sans, Source Sans
- These are the typographic equivalent of clip art -- not bad fonts, but their selection signals zero thought.
- Vignelli: "You need only a few basic typefaces" -- but those few must be CHOSEN, not defaulted to.

If a project uses one of these, ask: why THIS font? If the answer is "it's clean" or "it's modern," the selection is a default, not a decision.

For DM properties: GT Standard is always the correct answer. No discussion needed.

### The Physical Object Test

Before selecting a typeface, imagine holding a physical object that uses it. A book. A poster. A transit sign. A bottle label. If you can't picture a real-world artifact that would use this typeface well, the selection is abstract rather than grounded.

This test shifts font selection from category thinking ("I need a sans-serif") to artifact thinking ("I need the voice of a well-made field guide"). Spiekermann's four questions operationalize this: what is being said, to whom, in what medium, what response is desired?

### The "Looks AI" Hierarchy Test

If a type hierarchy uses exactly these sizes: 48/36/24/18/16/14 -- it wasn't derived from a three-property scale. It was guessed.

Derive the scale from f0, r, n. Round numbers are suspicious. A well-derived scale produces distinctive values (15.6, 19.5, 24.4, 30.5) that create subtly different rhythm from every other project.

---

## Structural Anti-Patterns

### Letterspaced Lowercase Body

- **Problem:** Positive letter-spacing added to lowercase running text
- **Why it fails:** Goudy: "Anyone who would letterspace blackletter would steal sheep." Bringhurst extends this to lowercase in general -- tracking disrupts the word-shapes that enable fluid reading.
- **Fix:** Zero letter-spacing for lowercase body text. Only letterspace capitals, small caps, and labels.

### Measure Blindness

- **Problem:** Text running edge-to-edge or exceeding 75 characters per line
- **Why it fails:** Bringhurst's 45-75 character range (ideal 66) exists for physiological reasons -- the eye loses its place on the return sweep when lines are too long.
- **Fix:** Constrain with `max-width` or `--measure` (Live Wires uses 65ch). For wider containers, use multi-column layout or increase margins.

### Arbitrary Size Jumps

- **Problem:** Type sizes with no mathematical relationship (16, 19, 23, 31, 44)
- **Why it fails:** Gerstner demands a programme. Random sizes mean no programme, no system, no coherence.
- **Fix:** Use the three-property scale (f0, r, n). Every size must be derivable from the formula. If it isn't, it doesn't belong.

### Rhythm-Breaking Spacing

- **Problem:** Margins and padding that aren't multiples of the baseline unit
- **Why it fails:** Latin: "Add and delete vertical space in measured intervals." Breaking the baseline rhythm makes the page feel subtly wrong even to readers who can't articulate why.
- **Fix:** All vertical spacing in `--line-*` multiples. No exceptions.

### Decorative Font Syndrome

- **Problem:** Script, display, or novelty fonts used for body text or UI elements
- **Why it fails:** Bringhurst: typography exists to honor content, not the designer's personality. Display faces are for display -- headlines, titles, hero moments. Using them for body text sacrifices readability for style.
- **Fix:** Classify the typeface (Craig's classification system). Body text requires Old Style, Transitional, Modern, or Sans Serif. Display faces belong at display scale only.

### Size-Only Hierarchy

- **Problem:** Heading levels differ only in font-size, with identical weight, case, spacing, and color
- **Why it fails:** A hierarchy built on one dimension (size) is weak. Muller-Brockmann's typographic compositions use multiple dimensions simultaneously.
- **Fix:** Vary at least two properties between heading levels: size + weight, size + case, size + letter-spacing. Each level should feel distinct, not just bigger.

---

## Web-Specific Anti-Patterns

### Fixed-Pixel Typography

- **Problem:** `font-size: 18px` with no responsive scaling
- **Why it fails:** The web is a fluid medium. Fixed sizes ignore viewport variation and user preferences.
- **Fix:** Use `clamp()` for responsive scaling tied to the three-property scale. Body text: `clamp(1rem, 0.95rem + 0.25vw, 1.125rem)`. Respect the user's base font size.

### Incomplete Type Packages

- **Problem:** Setting `font-size` without matching `line-height` and `letter-spacing`
- **Why it fails:** The three properties are interdependent. Size without leading produces unpredictable vertical rhythm. Size without tracking produces inconsistent texture.
- **Fix:** Always use triplets. In Live Wires: `--text-XX` + `--line-height-XX` + `--tracking-XX` together. Never set one without the others.

### Justified Without Hyphenation

- **Problem:** `text-align: justify` on the web without `hyphens: auto`
- **Why it fails:** Without hyphenation, justified text creates rivers of whitespace. The web's limited justification algorithms can't match InDesign's paragraph composer.
- **Fix:** Left-align body text (Latin's recommendation for web). If justification is required for editorial reasons, always pair with `hyphens: auto` and `hyphenate-limit-chars`.

### Font Loading Flash

- **Problem:** Web fonts that cause visible FOUT/FOIT without mitigation
- **Why it fails:** A flash of unstyled or invisible text breaks the reading experience. It signals technical neglect.
- **Fix:** Use `font-display: swap` with size-adjusted fallbacks (`size-adjust`, `ascent-override`, `descent-override`) to minimize layout shift. Preload critical font files.
