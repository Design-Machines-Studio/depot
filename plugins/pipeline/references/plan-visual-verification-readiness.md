# Perspective 4: visual verification readiness

Loaded by `plan-adversary` only when the plan or manifest touches a rendered
surface -- `.templ`, `.twig`, `.html`, `.css`, a route, `main.go`, navigation,
or wiring. A plan with no rendered surface never loads this file.

Apply the mode-specific rendered-surface audit:

- [ ] **[Full only]** Does the manifest carry `renderedSurface` and a non-empty `renderedSurfaceRationale` for every chunk?
- [ ] **[Full only]** Does each prompt agree with its manifest applicability and avoid contradictory visual/browser claims?
- [ ] **[Lean only]** Does the plan's single-pass scope state whether rendered verification is required and give a non-empty rationale?
- [ ] In either mode, does a `not_applicable` rationale account for every `.templ`, `.twig`, `.html`, `.css`, route, `main.go`, navigation, or wiring trigger? Mixed or uncertain scope is `required`.

For required rendered work, verify the applicable prompts (full) or single-pass
plan scope (Lean) enforce visual quality:

- [ ] Resolve any conditionally declared prototype through
  `prototype-authority.md` before local specs or heuristics. For a counterpart,
  carry its repository/commit, source paths, matched cases, parity map, and
  intentional differences. With no prototype, cite a local design spec, the
  `brainstorm.html` `visualDecisions` island, or approved visual requirements.
- [ ] Carry at least 2 visual acceptance criteria describing visual IMPRESSIONS, not just structural class names: "Block and Abstain buttons are visually smaller and lighter than the main position buttons" is an impression; "Button uses `button--outline-danger` class" is structural. Both are needed; impressions catch the gap between "correct class" and "correct visual effect."
- [ ] Give each visual criterion a browser-verifiable test (screenshot comparison or getComputedStyle extraction): "Button has font-size < 1rem per getComputedStyle" is verifiable; "Code is clean" is not.
- [ ] **[Full only]** Chunks modifying the same visual area (sidebar, form, card) carry aligned criteria -- not "prominent headings" in one and "subdued headings" in another.
- [ ] Where the approved scope or plan says "visually identical," "match the existing," "same as," or "these should be the same component" between two pages or elements, supply an explicit **Visual Parity Criterion** (below).

**Visual Diff Protocol.** Two triggers: (1) **stated parity** -- the scope or plan says "these should look the same," "visually identical," "match X," or "same component"; (2) **implied parity (auto-trigger)** -- one Templ component rendered on two or more routes (a shared editor, form, or dialog): sharing a component *is* the parity claim, written down or not, and a route-specific wrapper or stale CSS override breaks it silently while code review passes because the component source is identical. In full mode, inspect the planned `filesToModify`; in Lean mode, inspect the files named in the single-pass scope. A component invoked from more than one page package needs the criteria below.

In either case, the acceptance criteria MUST include:

1. Screenshot comparison: "Screenshot of [A] and [B] at same viewport should show visually identical [component/layout]"
2. Computed style comparison: "getComputedStyle on [selector] for [A] and [B] must match for: font-size, font-weight, color, padding, margin, background-color, border"
3. Classify mismatches by observable impact using `prototype-authority.md`:
   P1 only for a blocked primary task, misleading authorization/governance
   consequence, inaccessible essential control, or explicitly critical parity;
   P2 for meaningful structure/component/copy/placement/interaction drift; P3
   for minor spacing, alignment, metadata, or presentation drift. Every
   supported severity remains mandatory before clean completion.

If an approved visual-parity requirement lacks these criteria, emit one blocker scoped to the affected full-mode chunk or Lean single-pass scope.
