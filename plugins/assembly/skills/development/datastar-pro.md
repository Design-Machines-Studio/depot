# Datastar Pro

Verified against: `starfederation/datastar-pro` v1.0.2, commit `0f86778`, read 2026-07-10 from `library/src/pro/**`.

Datastar Pro is a commercial add-on to the free Datastar framework. The repo is private and Context7 carries no entry for it, so **this page is the reference** -- there is nothing to look up at runtime. Everything below was transcribed from the plugin sources, not the marketing page (which is wrong in three places, noted inline).

## Datastar-first, JS-last

Before writing any `<script>` block or `.js` file in an Assembly template, check the substitution table. Most client behavior an Assembly page needs already exists as a declarative attribute. Hand-rolled JS is allowed only when the table has no entry, and the chunk or PR must say which interaction needed it and why. "It was easier" is not a reason.

### JS -> Datastar substitution table

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

## Bundle-presence rule

A Pro attribute whose plugin is missing from the bundle is **inert** -- it silently does nothing. No console error, no exception. This is worse than the JS it replaced, because the template looks correct.

Every plugin self-registers under its kebab-case name (`attribute({ name: 'query-string', ... })`), so detection greps the vendored bundle for the *registered name*, never for the `data-` attribute as written in a template:

```shell
grep -c "'query-string'\|\"query-string\"" web/static/vendor/datastar.js
```

The 13 registered names, which are what you grep for:

`animate`, `custom-validity`, `match-media`, `on-raf`, `on-resize`, `persist`, `query-string`, `replace-url`, `scroll-into-view`, `view-transition`, `clipboard`, `fit`, `intl`

This list is the canonical copy. `datastar-sse.md` and dm-review's `datastar-pro.md` restate it; `tools/validate-workflow-contracts.sh` fails if they drift from this file.

Before prescribing a Pro attribute:

1. Grep the vendored bundle for its registered name.
2. Record the result in the chunk's Research Context, once per run.
3. If absent, either add "regenerate the bundle including `<plugin>`" as an explicit step, or fall back to the free tier.

Never emit a Pro attribute into a bundle that lacks its plugin.

Bundles are built per-account with the Bundler (`data-star.dev/pro/bundler`) and downloaded from `data-star.dev/pro/download`. Pro is under a commercial license. Do not `npm install` it, do not vendor it into a public repo, and do not commit a bundle to a repository whose license does not permit it.

## Pro attributes

`key` and `value` record each plugin's own `requirement`. Supplying a denied key, or omitting a required one, is a silent no-op or a throw -- not a warning.

| Attribute | Key | Value | Modifiers |
|---|---|---|---|
| `data-animate` | optional (attribute name) | required | `__duration`, `__ease.<name>`, `__delay`, `__loop`, `__pingpong` |
| `data-custom-validity` | denied | required | -- |
| `data-match-media` | required (signal name) | required (media query) | `__case` |
| `data-on-raf` | denied | required | `__delay`, `__debounce`, `__throttle`, `__viewtransition` |
| `data-on-resize` | denied | required | `__delay`, `__debounce`, `__throttle`, `__viewtransition` |
| `data-persist` | optional (storage key) | signal filter | `__session` |
| `data-query-string` | denied | signal filter | `__history` |
| `data-replace-url` | denied | required | -- |
| `data-scroll-into-view` | denied | denied | see below |
| `data-view-transition` | denied | required | -- |

### Corrections to the public docs

The docs site at `data-star.dev/reference/attributes` disagrees with the source on three points. The source wins.

1. **`data-animate` is listed with no modifiers.** It has five. It animates **element attributes**, not CSS properties, re-running whenever a signal in the expression changes.
2. **`__filter` is not a modifier** on `data-persist` or `data-query-string`. Filtering is the attribute's *value* -- a `{include, exclude}` signal filter. `data-query-string` also denies a key entirely.
3. **`data-match-media`'s value is a raw media query, not an expression.** Surrounding quotes are stripped and parentheses added if absent, so `data-match-media:isWide="min-width: 48rem"` and `"(min-width: 48rem)"` both work.

### data-animate

Interpolates an element **attribute** -- the one named by the key -- from its current value to the expression's value. Start and end must share a unit suffix or it throws.

Because it writes an attribute, not a style, the target must be an element whose attribute actually drives rendering: SVG geometry, a progress value, an ARIA value. Animating `width` on a `<div>` sets the legacy `width="320px"` presentational attribute, which modern CSS ignores -- it animates nothing you can see.

```html
<!-- CORRECT -- `width` is a rendering attribute on an SVG rect -->
<rect data-animate:width__duration.400ms__ease.inoutcubic="$isOpen ? '320' : '0'"></rect>

<!-- WRONG -- animates the presentational attribute; the div does not move -->
<div data-animate:width="$isOpen ? '320px' : '0px'"></div>
```

To animate a CSS property, drive it from a signal with `data-style` and let CSS transition it. `data-animate` is for attributes.

- `__duration` -- tag-to-ms (e.g. `400ms`, `1s`). Default `1000`.
- `__ease.<name>` -- default `linear`. Invalid names throw at apply time.
- `__delay` -- tag-to-ms.
- `__loop` -- restart on completion.
- `__pingpong` -- swap start and end on completion.

Easing names are lowercase and fixed:

`linear`, `quadratic`, `cubic`, `elastic`, `ingolden`, `outgolden`, `inoutgolden`, and `in`/`out`/`inout` variants of `quad`, `cubic`, `quart`, `quint`, `sine`, `expo`, `circ`, `elastic`, `back`, `bounce`.

Never guess an easing name. Copy one from this list.

### data-custom-validity

Expression must return a string. Empty string means valid; any other string is the validation message. Throws `CustomValidityInvalidElement` on anything that is not an `<input>`, `<select>`, or `<textarea>`, and `CustomValidityInvalidExpression` if the expression returns a non-string.

```html
<input data-bind:confirmPw data-custom-validity="$pw === $confirmPw ? '' : 'Passwords do not match'">
```

Prefer this over a `data-effect` that pokes `setCustomValidity` by hand. It participates in native form validation, so the server-side check stays the source of truth and the client only mirrors it.

### data-match-media

Sets the signal to the current match, keeps it in sync on `change`, and **resets the signal to `null` on cleanup**. Do not assume it is boolean after the element is removed.

```html
<div data-match-media:isWide="min-width: 48rem" data-show="$isWide"></div>
```

### data-on-raf, data-on-resize

Both wrap the expression in a signal batch. `data-on-resize` observes the element it is placed on via `ResizeObserver` and disconnects on cleanup.

`data-on-raf` runs every frame. Always pair it with `__throttle` unless the work is genuinely per-frame -- an unthrottled `data-on-raf` that patches signals will saturate the batch queue.

### data-persist

Loads from storage at apply time, then writes on every signal change. Key defaults to `datastar`. The value is a signal filter, not an expression.

```html
<div data-signals="{sidebarOpen: false, draft: ''}"
     data-persist:assembly-ui="{include: /^sidebarOpen$/}"></div>
```

Never persist a signal that carries authorization state, a member ID, or anything a server decision depends on. Persisted signals are attacker-controlled input on the next page load; the server re-authorizes regardless (see the Auth Boundary Map section of the development skill).

### data-query-string

Two-way sync between URL query params and filtered signals: params seed the signals on load, signal changes rewrite the query string, and `popstate` re-seeds. Add `__history` for back/forward support.

```html
<div data-signals="{status: 'all', q: ''}"
     data-query-string__history="{include: /^(status|q)$/}"></div>
```

This is the correct implementation of a filterable table's URL state. It replaces every hand-written `URLSearchParams` + `pushState` block.

### data-replace-url

Expression returns a URL string, resolved relative to the current `href`, applied with `history.replaceState`. No history entry is added.

### data-scroll-into-view

Key and value both denied -- it is a bare attribute that fires on apply.

- Behavior: `__smooth` (default), `__instant`, `__auto`
- Inline (horizontal): `__hstart`, `__hcenter` (default), `__hend`, `__hnearest`
- Block (vertical): `__vstart`, `__vcenter` (default), `__vend`, `__vnearest`
- `__focus` -- also call `el.focus()`

**Accessibility note:** the plugin sets `tabindex="0"` on the element when it has no `tabIndex`. That adds it to the tab order as a side effect. On a non-interactive scroll target that is usually wrong -- set `tabindex="-1"` yourself so the element is focusable programmatically but not tabbable.

### data-view-transition

Expression returns a string, applied as `el.style.viewTransitionName`. Logs a console warning and does nothing on browsers without View Transitions -- so it must never be the only mechanism a state change depends on.

## Pro actions

### @clipboard(text, isBase64 = false)

Throws `ClipboardNotAvailable` when `navigator.clipboard` is absent, which includes any non-secure context. Decodes with `atob` when `isBase64` is true.

```html
<button data-on:click="@clipboard($inviteLink)">Copy invite link</button>
```

### @fit(v, oldMin, oldMax, newMin, newMax, shouldClamp = false, shouldRound = false)

Scales `v` from the old range to the new one, **then** clamps -- so clamping applies to the output range. Returns a number.

### @intl(type, value, options?, locales?)

Locale defaults to `navigator.language`, then `en-US`. Types: `datetime`, `number`, `list`, `pluralRules`, `relativeTime`, `displayNames`. Throws `IntlInvalidDate` when `datetime` receives an unparseable value.

```html
<span data-text="@intl('number', $surplus, {style: 'currency', currency: 'CAD'})"></span>
```

Governance figures (surplus, patronage, vote counts) should render through `@intl` rather than being pre-formatted on the server, so the member's locale wins. Legal documents are the exception -- those are server-rendered and locale-pinned.

## Pro tooling

- **Bundler** -- builds custom bundles with only the plugins in use, plus aliased-syntax options.
- **Datastar Inspector** -- a web component that inspects signal changes, patches, and SSE events. Use it before reaching for `console.log` in a `data-effect`.
- **Rocket** -- a custom-element API with typed props, local state, local actions, and Datastar-aware rendering. Must load **last** in the bundle: its runtime queues custom-element definitions until the engine is ready. Not currently adopted in Assembly.
- **Stellar CSS** -- **not adopted.** Live Wires owns the CSS layer for every Design Machines project. Do not introduce Stellar into an Assembly install, and do not suggest it in a plan.
