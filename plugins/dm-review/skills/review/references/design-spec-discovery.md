# Design spec discovery

Loaded at Phase 3.25 only when the change includes `.templ`, `.twig`, `.html`,
or `.css`. A non-UI diff never loads this file.

### Phase 3.25: Design Spec Discovery

Check for design specifications that browser-based agents should evaluate against. This step loads the spec ONCE and injects it into visual agents -- individual agents do not discover specs independently.

1. Look for spec files in order of specificity:
   - `docs/superpowers/specs/*.md` -- formal design specs (use most recently modified)
   - `.superpowers/brainstorm/` -- brainstorm mockups (HTML files with visual decisions as inline styles)
   - `plans/*/brainstorm.html` -- pipeline brainstorm output (HTML with a `visualDecisions` JSON island)
2. If ANY spec files are found, read them and extract a structured summary:
   - Visual decisions (layout choices, spacing tokens, component variants, color usage)
   - Approved design patterns (specific markup structures, class choices)
   - Visual hierarchy decisions (what should be prominent, what should be subdued)
   - Specific visual treatments called out in the approved design
3. Store this summary as `design_spec_context` for injection into browser-based agents in Phase 4.
4. Report to the user:

```text
Design spec found: [path]. Will inject into visual review agents.
```

Or: "No design spec found. Visual agents will evaluate against general heuristics only."

This context is injected ONLY into the browser-based agents (ux-quality-reviewer, visual-browser-tester, ui-standards-reviewer). Code-only agents do not need it.

---

