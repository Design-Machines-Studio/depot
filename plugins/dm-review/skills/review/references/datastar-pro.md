# Datastar and Datastar Pro: Review Reference

Upstream source: `plugins/assembly/skills/development/datastar-pro.md`. This is a deliberate copy, not an import -- `dm-review` must stay dependency-free of `assembly`. When the upstream page changes, update this one. Both carry the same `Verified against:` line.

Verified against: `starfederation/datastar-pro` v1.0.2, commit `0f86778`, read 2026-07-10.

Applies when the project is Go + Templ + Datastar (a `.templ` file plus `go.mod`, or a vendored `datastar.js`).

## Finding: Hand-Rolled JS Where Datastar Suffices (P2)

A new `<script>` block or `.js` file whose behavior maps to a row in the table below, with no stated escape hatch, is a P2. Cite the row and name the replacement attribute in the finding.

The escape hatch is legitimate: some interactions have no Datastar equivalent. It must be *stated* -- in the chunk prompt, the PR body, or a comment on the script. An unexplained script is the finding, not the script itself.

| Hand-rolled JS | Use instead | Tier |
|---|---|---|
| `localStorage` / `sessionStorage` signal persistence | `data-persist`, `data-persist__session` | Pro |
| `history.pushState` / manual query-param sync | `data-query-string__history` | Pro |
| `history.replaceState` | `data-replace-url` | Pro |
| `window.matchMedia(...).addEventListener` | `data-match-media:signal` | Pro |
| `requestAnimationFrame` loop | `data-on-raf__throttle` | Pro |
| `ResizeObserver` | `data-on-resize__debounce` | Pro |
| `el.scrollIntoView({...})` | `data-scroll-into-view` | Pro |
| `el.setCustomValidity(...)` | `data-custom-validity` | Pro |
| `document.startViewTransition(...)` | `data-view-transition`, or `__viewtransition` on `data-on` | Pro |
| WAAPI / manual tween loops | `data-animate` | Pro |
| `navigator.clipboard.writeText(...)` | `@clipboard(text, isBase64?)` | Pro |
| `new Intl.NumberFormat(...).format(...)` | `@intl('number', value, options?)` | Pro |
| manual range-remap arithmetic | `@fit(...)` | Pro |
| `IntersectionObserver` | `data-on-intersect` | Free |
| `setInterval` polling | `data-on-interval__duration` | Free |
| `fetch()` | `@get` / `@post` / `@put` / `@patch` / `@delete` | Free |
| debounce / throttle utility functions | `__debounce` / `__throttle` modifiers | Free |
| manual loading-spinner toggling | `data-indicator` | Free |

Do not raise this finding against Live Wires CSS, the Datastar bundle itself, or build tooling. It targets application JS in templates and `web/static`.

## Finding: Inert Pro Attribute (P1)

A Pro **attribute** in a template whose plugin is absent from the vendored bundle. It does nothing -- no console error, no exception, no visual difference from a correct implementation. The page looks right in review and is silently broken in production.

This silence is what earns the P1. A missing Pro **action** (`@clipboard`, `@fit`, `@intl`) throws instead, so it surfaces on the first click; treat a missing action as P2.

Scale the attribute finding by what it gates. P1 when the inert attribute carries data integrity or security -- a `data-custom-validity` that should block an invalid submit, a `data-persist` holding state a server decision reads. P2 when it is cosmetic, such as an inert `data-view-transition` or a sidebar toggle that simply forgets its position. Say which one you concluded and why; do not apply P1 by reflex.

Each plugin self-registers under its kebab-case name, so check the bundle for the *registered name*, not the `data-` attribute:

```shell
grep -c "'query-string'\|\"query-string\"" $(git ls-files '*datastar*.js' | head -1)
```

Registered names: `animate`, `custom-validity`, `match-media`, `on-raf`, `on-resize`, `persist`, `query-string`, `replace-url`, `scroll-into-view`, `view-transition`, `clipboard`, `fit`, `intl`.

If the repo vendors no Datastar bundle (CDN or asset-pipeline build), say so and downgrade to P2 with the check the author should run -- do not guess.

## Correctness traps worth a finding

These are the ways a *present* Pro attribute still misbehaves. Each was read out of the plugin source.

- **`data-match-media` resets its signal to `null` on cleanup**, not to `false`. Code that reads the signal after the element is removed, or that does `if (!$isWide)`, conflates "no match" with "gone". P3.
- **`data-scroll-into-view` sets `tabindex="0"`** when the element has no `tabIndex`, silently adding it to the tab order. On a non-interactive scroll target that is an accessibility regression -- the author should set `tabindex="-1"` explicitly. P2, and a11y-html-reviewer's territory when it lands on a heading or region.
- **`data-view-transition` warns and no-ops** where View Transitions are unsupported. If a state change is visible *only* through the transition, the feature is broken on those browsers. P2.
- **`data-custom-validity` throws** on any element that is not `<input>`, `<select>`, or `<textarea>`, and throws again if the expression returns a non-string. Empty string means valid. P2 if the expression can return a boolean or `undefined`.
- **`@clipboard` throws `ClipboardNotAvailable`** in a non-secure context. A copy button with no error path fails silently for the user. P3, or P2 if it is the only way to obtain the value (an invite link, a federation token).
- **`data-animate` requires matching unit suffixes** between the element's current attribute value and the target, or it throws. It animates *element attributes*, not CSS properties. P2 when the start value is unset -- it defaults to `0<suffix>`, which is rarely what the author meant.
- **Unthrottled `data-on-raf`** that patches signals saturates the batch queue. P2 unless the work is genuinely per-frame.
- **Persisted authorization state.** `data-persist` writes to `localStorage`, which is attacker-controlled on the next load. A persisted signal carrying a member ID, role, or capability flag is P1 if any server decision reads it back without re-authorizing. Cross-reference the Auth Boundary Map.

## Public docs are wrong in three places

Reviewers reading `data-star.dev/reference/attributes` will see, and may propose, incorrect syntax. The source wins:

1. `data-animate` has five modifiers (`__duration`, `__ease.<name>`, `__delay`, `__loop`, `__pingpong`), not zero.
2. `__filter` is not a modifier on `data-persist` or `data-query-string`. Filtering is the attribute's *value*, a `{include, exclude}` signal filter. `data-query-string` denies a key.
3. `data-match-media`'s value is a raw media query string, not an expression.

Easing names are lowercase and fixed: `linear`, `quadratic`, `cubic`, `elastic`, `ingolden`, `outgolden`, `inoutgolden`, plus `in`/`out`/`inout` variants of `quad`, `cubic`, `quart`, `quint`, `sine`, `expo`, `circ`, `elastic`, `back`, `bounce`. An invalid name throws at apply time. Flag a guessed easing name as P2.

## Runtime verification

`data-persist` and `data-query-string` cannot be verified by reading the template -- presence of the attribute proves nothing when the plugin may be absent and the effect is a no-op. The `visual-browser-tester` verifies them at runtime:

- `data-persist` -- set the signal, reload, assert the value survived. `__session` -- assert it does not survive a new context.
- `data-query-string` -- change the signal, assert the URL query updated; with `__history`, navigate back and assert the signal reverted.
- `data-match-media` -- resize across the breakpoint, assert the signal flipped.

Absent a dev server, report these as `NOT-COVERED:` rather than passing them on template inspection.
