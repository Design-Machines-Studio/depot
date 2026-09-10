# Design spec discovery

Loaded at Phase 3.25 for rendered changes, including `.templ`, `.twig`, `.html`,
`.css`, and handler/Datastar/JS changes that alter an existing interaction.
A handler-only save change is UI behavior even without a template diff.
A genuinely non-UI diff never loads this file.

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
   Wires classes, literal copy/metadata/action order, Datastar signal/event and
   request/response traces (including save timing and persistence), evidence status, and
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
   `design_spec_context`, and any already matched host browser evidence for
   injection into applicable UI lanes in Phase 4. UI-standards and UX receive
   the source packet even when browser evidence is absent; visual-browser does
   not run without rendered proof. Source and browser proof are complementary:
   screenshots cannot prove source hierarchy/classes/copy, and source cannot
   prove spacing/composition. Required prototype browser evidence uses matching
   routes, states, and viewports and cannot be replaced by a target-only
   screenshot, curl, or `looks close`. Actually exercise affected interactions
   in both apps: edit, save/autosave, feedback/error, and reload/revisit, plus
   cancel and focus behavior when affected. Keep synthetic saves distinct from
   durable persistence and use designated demo/disposable records.
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

For prototype-covered cases, apply dm-review’s `ui-case-selection.md` existing
prototype tasks and personas contract. Carry the exact task source/commit,
selected task IDs and persona/role/state/device combinations, preconditions,
steps, success criteria and screenshot points into the existing prompts and
browser evidence. Execute the paired cases and record prototype result,
application result and observed difference; expected permission denial is a
verified boundary check, and expected FRICTION remains a hypothesis.

Inject this context into applicable UI lanes
(ux-quality-reviewer, visual-browser-tester, ui-standards-reviewer). Also give
the bounded interaction trace to the reviewer of affected handlers/client code;
unrelated code-only lanes do not need the visual packet.

---
