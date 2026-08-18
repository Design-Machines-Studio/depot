## Visual Finding Rules

When a `## Design Spec Context` section is present, it is your PRIMARY evaluation baseline. For each approved decision, locate the element on the rendered page, capture an element-level screenshot, and evaluate the match. Flag any mismatch as P1: "Implementation deviates from approved design: spec says [X], rendered shows [Y]." Spec deviations outrank general heuristic violations and are evaluated before them -- a page can be "good enough" by general standards and still wrong against the approved design.

When it is absent and the diff contains template or CSS files, flag a P2 process finding: "No design spec available -- visual quality evaluation is heuristic-only, which has a documented history of missing implementation gaps (see docs/post-mortems/2026-04-07-pipeline-ui-refinement-postmortem.md). Consider running the pipeline assess phase to establish a design baseline before further UI work." This is a process finding, not a code finding: it signals that the review's ability to catch visual quality issues is degraded.

Every finding, spec-derived or heuristic, MUST cite its rule source: a CLAUDE.md section ("CLAUDE.md > Spacing System > baseline rhythm"), a Live Wires skill reference ("Live Wires layouts.md: use .stack not manual margin"), a benchmark product plus pattern ("Linear uses skeleton loaders for async table loading"), a token name ("--line-2 spacing token exists for this value"), or a WCAG criterion ("WCAG 2.4.7: focus must be visible"). Format each finding as:

"[element] violates [rule-source]: [citation]. Rendered: [X]. Expected: [Y]."

Findings without citations are INVALID and must be dropped. Never report "this could be better" without naming the rule that defines "better", and never invent a spec.
