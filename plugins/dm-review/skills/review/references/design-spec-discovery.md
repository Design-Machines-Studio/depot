# Design spec discovery

Loaded at Phase 3.25 only when the change includes `.templ`, `.twig`, `.html`,
or `.css`. A non-UI diff never loads this file.

### Phase 3.25: Design Spec Discovery

Resolve design authority once at the host and inject a bounded packet into
applicable UI lanes -- individual agents do not discover external source.

1. Prefer caller-provided Pipeline `prototypeReference` and `prototypeParity`
   context. Otherwise inspect the current native PR/Issue, root instructions,
   and active product plan for an exact declared prototype repository and
   commit. Do not guess one.
2. When a declared prototype covers the changed surface, read its exact
   external templates/components once at the host and create a bounded
   `prototype_parity_packet` containing repository + commit, authority source,
   relevant prototype/target paths, matched route-state-viewport pairs,
   meaningful semantic/wrapper hierarchy, significant components, exact Live
   Wires classes, literal copy/metadata/action order, evidence status, and
   approved intentional differences. Include short excerpts only, never whole
   templates or permanent workstation paths.
3. Conflicting or unresolved prototype identity/commit/route claims make
   required UI review `human_help_required`. If exact source inspection proves
   no counterpart exists, record `no prototype counterpart` and continue with
   the existing heuristic path; never borrow a vaguely similar page.
4. If no relevant prototype counterpart exists, look for local spec files in
   order of specificity:
   - `docs/superpowers/specs/*.md` -- formal design specs (use most recently modified)
   - `.superpowers/brainstorm/` -- brainstorm mockups (HTML files with visual decisions as inline styles)
   - `plans/*/brainstorm.html` -- pipeline brainstorm output (HTML with a `visualDecisions` JSON island)
5. If local spec files are found, read them and extract a structured summary:
   - Visual decisions (layout choices, spacing tokens, component variants, color usage)
   - Approved design patterns (specific markup structures, class choices)
   - Visual hierarchy decisions (what should be prominent, what should be subdued)
   - Specific visual treatments called out in the approved design
6. Store the prototype packet (primary when present), local
   `design_spec_context`, and already matched host browser evidence for
   injection into rendered UI lanes in Phase 4. Source and browser proof are
   complementary: screenshots cannot prove source hierarchy/classes/copy, and
   source cannot prove spacing/composition. Required prototype browser evidence
   uses matching routes, states, and viewports and cannot be replaced by a
   target-only screenshot, curl, or `looks close`.
7. Report to the user:

```text
Design spec found: [path]. Will inject into visual review agents.
```

Or: "No relevant prototype counterpart or local design spec found. Visual
agents will evaluate against general heuristics."

Prototype-covered decisions are primary. Generic Stripe/Linear/Notion/SaaS
heuristics are secondary and cannot recommend different copy, components,
hierarchy, or control placement solely because a benchmark differs. Objective
usability, accessibility, responsiveness, security, and broken-state defects
remain reviewable. When the prototype render is temporarily unavailable,
preserve source findings but do not claim rendered parity complete.

This context is injected only into applicable rendered UI lanes
(ux-quality-reviewer, visual-browser-tester, ui-standards-reviewer). Code-only
agents do not need it.

---
