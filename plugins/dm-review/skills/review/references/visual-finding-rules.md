## Visual Finding Rules

When a `## Prototype Parity Packet` is present, it is the PRIMARY evaluation
baseline. Check its bounded source hierarchy, significant components, exact
Live Wires classes, literal copy/metadata/action order, and matched rendered
cases. Generic product heuristics are secondary and cannot redesign a settled
prototype choice. A named functionality, authorization, accessibility, public
API, production-data, host-composition, or Fixture-boundary difference is not a
defect merely because it diverges.

When a `## Design Spec Context` section is present, it is also authoritative
for covered decisions. Locate each affected element, use the host-captured
element evidence, and evaluate the match before general heuristics. A page can
be generally acceptable and still drift from settled product design.

Classify prototype/spec mismatches by observable impact: P1 only when a primary
task is blocked, authorization/governance consequences are misleading, an
essential control is inaccessible, or parity is explicitly critical; P2 for a
meaningful structure/component/copy/control-placement/responsive/interaction
mismatch causing confusion or rework; P3 for minor spacing, alignment,
metadata, class, or presentation drift. Every supported P1/P2/P3 remains
mandatory before `CLEAN`.

When no relevant prototype counterpart or local design spec exists and the diff
contains template or CSS files, retain the existing P2 process finding:
"No design spec available -- visual quality evaluation is heuristic-only, which
has a documented history of missing implementation gaps (see
docs/post-mortems/2026-04-07-pipeline-ui-refinement-postmortem.md). Consider
running the pipeline assess phase to establish a design baseline before further
UI work." This warns about degraded review coverage; it is not a product
finding. Do not invent a counterpart or another finding from missing ceremony.

Every finding, spec-derived or heuristic, MUST cite its rule source: a CLAUDE.md section ("CLAUDE.md > Spacing System > baseline rhythm"), a Live Wires skill reference ("Live Wires layouts.md: use .stack not manual margin"), a benchmark product plus pattern ("Linear uses skeleton loaders for async table loading"), a token name ("--line-2 spacing token exists for this value"), or a WCAG criterion ("WCAG 2.4.7: focus must be visible"). Format each finding as:

"[element] violates [rule-source]: [citation]. Rendered: [X]. Expected: [Y]."

Findings without citations are INVALID and must be dropped. Never report "this could be better" without naming the rule that defines "better", and never invent a spec.
