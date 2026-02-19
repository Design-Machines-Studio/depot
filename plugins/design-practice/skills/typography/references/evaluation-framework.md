# Typography Evaluation Framework

A systematic methodology for critiquing typographic decisions, synthesized from all ten primary influences.

---

## The Evaluation Process

### Step 1: Read the Text (Bringhurst)

Before evaluating any typography, read the content it presents. Discover the outer logic of the typography in the inner logic of the text. The typeface, size, leading, and measure should all emerge from the text's character.

### Step 2: Assess the System (Gerstner)

Is there a visible programme? Can you identify the rules that generated these typographic decisions? Or do the choices appear arbitrary?

**Signs of a programme:** Consistent scale relationships (strongest: a three-property scale with identifiable f₀, r, and n), predictable spacing, clear hierarchy rules, coherent typeface pairing logic.

**Signs of no programme:** Random size jumps, inconsistent spacing, mixed alignment without reason, typefaces that don't relate to each other.

### Step 3: Measure the Fundamentals

| Criterion | Target | Severity if Violated |
|---|---|---|
| **Measure** | 45--75 characters/line (66 ideal) | Critical -- affects all readability |
| **Body line-height** | 1.4--1.6 (sans: higher end) | Critical -- rhythm foundation |
| **Body font size** | 16px+ on screen; 9--12pt in print | Critical -- legibility threshold |
| **Typeface count** | Maximum 2 families | Major -- discipline indicator |
| **Vertical rhythm** | All spacing as multiples of base leading | Major -- visual coherence |
| **Heading connection** | Top margin > bottom margin | Minor -- scannability |
| **Letter-spacing** | No letterspacing of lowercase body | Major -- readability violation |
| **Scale consistency** | Sizes from a three-property scale (f₀, r, n) or demonstrable mathematical relationship | Major -- system integrity |

### Step 4: Evaluate Typeface Selection

**Context fitness (Spiekermann):**
- Does the typeface match the communication context?
- What is being said? To whom? In what medium? What response is desired?

**Classification awareness (Craig):**
- Can you identify the typeface's family (Old Style, Transitional, Modern, Slab, Sans)?
- Is the choice historically and contextually appropriate?

**Structural analysis:**
- x-height: Does it support legibility at the chosen size?
- Stroke contrast: Is it appropriate for the medium (screen favors lower contrast)?
- Width: Does it work with the chosen measure?

**Timelessness (Vignelli):**
- Is this typeface a trend or a classic?
- Will it look dated in 5 years?

### Step 5: Assess Web/Screen Specifics (if applicable)

| Check | Pass | Fail |
|---|---|---|
| **Fluid scaling** | Uses `clamp()` or responsive approach | Fixed pixel sizes |
| **Viewport adaptation** | Measure, size, and leading all respond | Only size changes |
| **OpenType features** | Kerning, ligatures, proper numerals enabled | Default browser rendering |
| **Text wrapping** | `balance` for headings, `pretty` for body | Default wrapping |
| **Measure control** | `max-width` in `ch` units | Unconstrained text width |
| **Font loading** | Progressive with `font-display: swap` or similar | Flash of invisible text |

### Step 6: Check the Details (Bringhurst)

"Give full typographic attention even to incidental details."

- Are quotation marks curly, not straight?
- Are dashes correct (en-dash for ranges, em-dash for breaks)?
- Are ellipses proper characters, not three periods?
- Are numbers set appropriately (oldstyle for running text, lining for tables)?
- Are abbreviations in small caps with slight letter-spacing?
- Is there hanging punctuation where appropriate?

---

## Severity Levels

### Critical
Issues that fundamentally undermine readability:
- Measure outside 30--90 character range
- Line-height below 1.2 or above 2.0 for body text
- Body text below 14px on screen
- Zero visual hierarchy (everything same size and weight)

### Major
Issues that degrade the typographic experience:
- Letterspacing lowercase body text
- More than 3 typeface families
- No discernible scale system
- Inconsistent spacing breaking vertical rhythm
- Justified text without hyphenation on web

### Minor
Issues that indicate lack of polish:
- Heading margins not connecting to content
- Straight quotation marks
- Missing OpenType features
- Suboptimal line-height (within range but not ideal for the typeface)
- Abbreviations not in small caps

### Stylistic
Not errors but opportunities for improvement:
- Could benefit from a tighter modular scale ratio
- Type pairing functional but not inspired
- Responsive behavior adequate but not refined
- Details correct but lacking personality

---

## The Twelve Questions

A complete typographic evaluation answers these questions:

1. **Does the typography honor the content?** (Bringhurst) -- Is there evidence that someone read the text before designing it?

2. **Is there a visible system?** (Gerstner) -- Can you reverse-engineer the programme? Or are decisions arbitrary?

3. **Is the measure comfortable?** (Bringhurst) -- 45--75 characters per line, 66 ideal.

4. **Is the vertical rhythm maintained?** (Latin, Bringhurst) -- All spacing as multiples of the base leading unit.

5. **Is the typeface palette disciplined?** (Vignelli, Santa Maria) -- Maximum two families. Do they have a reason to coexist?

6. **Is the hierarchy clear?** (Lupton, Santa Maria) -- Can you scan and find information intuitively? Is importance communicated through size, weight, and placement?

7. **Is the type size appropriate for the column width?** (Vignelli, Müller-Brockmann) -- Does the font size create a comfortable measure for the column?

8. **Is the leading appropriate?** (Bringhurst, Brown) -- For this specific typeface, at this size, at this measure?

9. **Does it work across viewports?** (Brown, Rutter) -- Is there a responsive strategy? Does the system hold at different sizes?

10. **Is it timeless rather than trendy?** (Vignelli) -- Will this look dated in 5 years? Does it rely on a fashion moment?

11. **Is full attention given to details?** (Bringhurst) -- Quotation marks, dashes, numerals, small caps, ligatures, kerning?

12. **Does the typography invite, then disappear?** (Rutter) -- Can you read without noticing the typography? Does it serve transparently?

---

## Output Format for Typography Critique

When providing a typographic evaluation, structure it as:

```
## Typography Evaluation

### System Assessment
[Programme / No Programme] -- [Description of the typographic system or lack thereof]

### Fundamentals
| Check | Status | Notes |
|---|---|---|
| Measure | [pass/issue] | [Specific measurement and recommendation] |
| Line-height | [pass/issue] | [Current value and recommendation] |
| Scale | [pass/issue] | [Identified ratio or lack thereof] |
| Typeface count | [pass/issue] | [Count and pairing assessment] |
| Vertical rhythm | [pass/issue] | [Consistency assessment] |

### Typeface Assessment
[Context fitness, classification, structural analysis, timelessness]

### Details
[Quotation marks, dashes, numerals, OpenType features, small caps]

### Responsive (if applicable)
[Fluid scaling, viewport adaptation, measure control]

### Verdict
[Critical/Major/Minor issues summary]
[Specific recommendations in priority order]
```
