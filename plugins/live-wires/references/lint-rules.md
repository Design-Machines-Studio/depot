# Live Wires Lint Rules

The canonical generic rule definitions are in
[`quality-rules-v1.json`](quality-rules-v1.json). This document supplies linter
implementation hints for those stable IDs; it does not redefine their
semantics. Hard-fail and warning labels describe the current lint step only.
Repository quality-pulse profiles own scope, thresholds, exemptions, and final
classification.

The css-reviewer agent stays for nuanced cases the linter can't catch (layout choice evaluation, contextual token selection, whether a component is the right abstraction for the context, etc.).

Consumer profiles must bind `live-wires-quality-rules`, schema version `1`,
catalog version `1.0.0`, and the externally computed canonical content digest.
They reference catalog rule and metric IDs rather than copying or silently
redefining catalog entries.

---

## Hard-Fail Rules

### LW-INLINE

**Catalog rule:** `lw-inline-style`
**Severity:** hard-fail
**Applies to:** `.html`, `.templ`, `.twig`
**Detection:** `grep -n 'style="' <files>`
**What it catches:** Inline style attributes bypass the cascade and Live Wires token system. All styling must go through CSS classes, design tokens, or layout primitives.
**QA shortcode:** LW-INLINE

### LW-BASELINE

**Catalog rule:** `lw-raw-spacing`
**Severity:** hard-fail
**Applies to:** `.css`
**Detection:** `grep -nE '(margin|padding|gap):\s*[0-9]+(px|rem|em)' <files> | grep -vE ':\s*1px'`
**What it catches:** Raw numeric spacing values instead of `--line-*` tokens. The `1px` exclusion allows border widths. All spacing (margin, padding, gap) must use baseline rhythm tokens (`var(--line-05)`, `var(--line-1)`, `var(--line-2)`, etc.).
**QA shortcode:** LW-BASELINE

### LW-INVENTED

**Catalog rule:** `lw-framework-class`
**Severity:** hard-fail
**Applies to:** `.css`, `.html`, `.templ`, `.twig`
**Detection:** Judgment review -- inventory comparison can produce candidates, but dynamic class construction and justified components require context.
**What it catches:** Ad-hoc class names that bypass the Live Wires design system. Use existing layout primitives (`.stack`, `.grid`, `.cluster`, `.sidebar`, `.center`, `.section`, `.box`, `.cover`, `.reel`), utility classes, or component classes. If a pattern repeats 3+ times, propose a new component through the proper channel.
**QA shortcode:** LW-INVENTED

### LW-BEM

**Catalog rule:** `lw-bem-child-selector`
**Severity:** hard-fail
**Applies to:** `.css`, `.html`, `.templ`, `.twig`
**Detection:** `grep -nE '__' <files>`
**What it catches:** BEM double-underscore naming (`block__element`). Live Wires uses native CSS nesting for child elements. Layout primitive variants use a single dash (`stack-compact`), while component variants use a double dash (`button--accent`).
**QA shortcode:** LW-BEM

### LW-LAYER

**Catalog rule:** `lw-cascade-layer`
**Severity:** hard-fail
**Applies to:** `.css`
**Detection:** CSS-aware review for unlayered rules and role/layer mismatches; line-oriented searches may identify candidates but do not prove nesting.
**What it catches:** CSS outside the cascade layer system or in a layer that does not match its role. The canonical sequence is `tokens`, `reset`, `base`, `layouts`, `components`, `utilities`.
**QA shortcode:** LW-LAYER

---

## Warning Rules

### LW-STATE

**Catalog rule:** `lw-state-attribute`
**Severity:** warning
**Applies to:** `.css`, `.html`, `.templ`, `.twig`
**Detection:** `grep -nE '\.(is-|active|disabled)' <files>`
**What it catches:** jQuery-era state classes (`.is-active`, `.active`, `.disabled`). Live Wires uses `data-state="active"` and `data-state="disabled"` attributes for state management.
**QA shortcode:** LW-STATE

### LW-HARDCODED-COLOR

**Catalog rule:** `lw-raw-color`
**Severity:** warning
**Applies to:** `.css`
**Detection:** `grep -nE '#[0-9a-fA-F]{3,8}|rgb\(|rgba\(|hsl\(|hsla\(' <files>`
**What it catches:** Hardcoded color values instead of semantic tokens (`--color-accent`, `--color-bg`, `--color-fg`, `--ink`, `--paper`) or scheme classes (`.scheme-subtle`, `.scheme-accent`, `.scheme-dark`).
**QA shortcode:** LW-HARDCODED-COLOR

### LW-TRIPLET

**Catalog rule:** `lw-typography-triplet`
**Severity:** warning
**Applies to:** `.css`
**Detection:** Check for `font-size` declarations without matching `line-height` and `letter-spacing` (tracking) declarations in the same rule block.
**What it catches:** Incomplete typography declarations. Live Wires requires the full triplet (size + line-height + tracking) or a utility class (`.text-2xl`) that bundles all three. Bare `font-size` declarations break vertical rhythm.
**QA shortcode:** LW-TRIPLET

### LW-LOGICAL

**Catalog rule:** `lw-logical-property`
**Severity:** warning
**Applies to:** `.css`
**Detection:** `grep -nE '(margin|padding|border)-(top|bottom|left|right):' <files>`
**What it catches:** Physical CSS properties instead of logical properties. Use `margin-block-start` instead of `margin-top`, `padding-inline` instead of `padding-left`/`padding-right`, etc. Logical properties support RTL layouts and are the Live Wires convention.
**QA shortcode:** LW-LOGICAL

### LW-VARIANT

**Catalog rules:** `lw-layout-variant`, `lw-component-variant`
**Severity:** warning
**Applies to:** `.css`, `.html`, `.templ`, `.twig`
**Detection:** Check modifier naming convention. Layout primitives use a single dash (`stack-compact`, `grid-columns-3`).
Components use a double dash (`button--accent`, `card--flush`). Mismatched conventions are flagged.
**What it catches:** Wrong modifier convention. Layout variants use a single dash.
Component variants use a double dash, keeping composition and block naming distinct.
**QA shortcode:** LW-VARIANT
