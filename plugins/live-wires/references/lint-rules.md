# Live Wires Lint Rules

These rules are consumed by the pipeline execution-orchestrator's livewires-lint step. Hard-fail rules block chunk commits. Warning rules are reported but don't block.

The css-reviewer agent stays for nuanced cases the linter can't catch (layout choice evaluation, contextual token selection, whether a component is the right abstraction for the context, etc.).

---

## Hard-Fail Rules

### LW-INLINE

**Severity:** hard-fail
**Applies to:** `.html`, `.templ`, `.twig`
**Detection:** `grep -n 'style="' <files>`
**What it catches:** Inline style attributes bypass the cascade and Live Wires token system. All styling must go through CSS classes, design tokens, or layout primitives.
**QA shortcode:** LW-INLINE

### LW-BASELINE

**Severity:** hard-fail
**Applies to:** `.css`
**Detection:** `grep -nE '(margin|padding|gap):\s*[0-9]+(px|rem|em)' <files> | grep -vE ':\s*1px'`
**What it catches:** Raw numeric spacing values instead of `--line-*` tokens. The `1px` exclusion allows border widths. All spacing (margin, padding, gap) must use baseline rhythm tokens (`var(--line-half)`, `var(--line-1)`, `var(--line-2)`, etc.).
**QA shortcode:** LW-BASELINE

### LW-INVENTED

**Severity:** hard-fail
**Applies to:** `.css`, `.html`, `.templ`, `.twig`
**Detection:** Manual check -- extract class names from changed files and compare against the canonical inventory in `layouts.md`, `utilities.md`, and `components.md`. Classes not in the inventory are invented.
**What it catches:** Ad-hoc class names that bypass the Live Wires design system. Use existing layout primitives (`.stack`, `.grid`, `.cluster`, `.sidebar`, `.center`, `.section`, `.box`, `.cover`, `.reel`), utility classes, or component classes. If a pattern repeats 3+ times, propose a new component through the proper channel.
**QA shortcode:** LW-INVENTED

### LW-BEM

**Severity:** hard-fail
**Applies to:** `.css`, `.html`, `.templ`, `.twig`
**Detection:** `grep -nE '__' <files>`
**What it catches:** BEM double-underscore naming (`block__element`). Live Wires uses single-dash modifiers for components (`button-accent`) and double-dash modifiers for layout primitives (`stack--compact`). BEM naming is not part of the system.
**QA shortcode:** LW-BEM

### LW-LAYER

**Severity:** hard-fail
**Applies to:** `.css`
**Detection:** Check for CSS rules outside `@layer` blocks. Rules at the top level of a CSS file (not inside any `@layer`) violate the cascade layer architecture.
**What it catches:** CSS rules outside the cascade layer system. All CSS must be placed in the appropriate `@layer` (settings, generic, elements, blocks, utilities, overrides). Unlayered CSS has unpredictable specificity.
**QA shortcode:** LW-LAYER

---

## Warning Rules

### LW-STATE

**Severity:** warning
**Applies to:** `.css`, `.html`, `.templ`, `.twig`
**Detection:** `grep -nE '\.(is-|active|disabled)' <files>`
**What it catches:** jQuery-era state classes (`.is-active`, `.active`, `.disabled`). Live Wires uses `data-state="active"` and `data-state="disabled"` attributes for state management.
**QA shortcode:** LW-STATE

### LW-HARDCODED-COLOR

**Severity:** warning
**Applies to:** `.css`
**Detection:** `grep -nE '#[0-9a-fA-F]{3,8}|rgb\(|rgba\(|hsl\(|hsla\(' <files>`
**What it catches:** Hardcoded color values instead of semantic tokens (`--color-accent`, `--color-bg`, `--color-fg`, `--ink`, `--paper`) or scheme classes (`.scheme-subtle`, `.scheme-accent`, `.scheme-dark`).
**QA shortcode:** LW-HARDCODED-COLOR

### LW-TRIPLET

**Severity:** warning
**Applies to:** `.css`
**Detection:** Check for `font-size` declarations without matching `line-height` and `letter-spacing` (tracking) declarations in the same rule block.
**What it catches:** Incomplete typography declarations. Live Wires requires the full triplet (size + line-height + tracking) or a utility class (`.text-2xl`) that bundles all three. Bare `font-size` declarations break vertical rhythm.
**QA shortcode:** LW-TRIPLET

### LW-LOGICAL

**Severity:** warning
**Applies to:** `.css`
**Detection:** `grep -nE '(margin|padding|border)-(top|bottom|left|right):' <files>`
**What it catches:** Physical CSS properties instead of logical properties. Use `margin-block-start` instead of `margin-top`, `padding-inline` instead of `padding-left`/`padding-right`, etc. Logical properties support RTL layouts and are the Live Wires convention.
**QA shortcode:** LW-LOGICAL

### LW-VARIANT

**Severity:** warning
**Applies to:** `.css`, `.html`, `.templ`, `.twig`
**Detection:** Check modifier naming convention -- layout primitives use double-dash (`stack--compact`, `grid--3`), components use single-dash (`button-accent`, `card-flush`). Mismatched conventions are flagged.
**What it catches:** Wrong modifier convention. Double-dash for layout primitive variants, single-dash for component variants. Mixing conventions makes the system harder to read.
**QA shortcode:** LW-VARIANT
