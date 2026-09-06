# Declared prototype authority

Load this reference only for rendered work when a prototype is declared by the
user, the current native Issue or PR, root repository instructions, or the
active product plan. For Assembly Baseplate or Fixture work, also load it when
`assembly:development` identifies a corresponding surface in the canonical
`Design-Machines-Studio/assembly` prototype. Do not guess a prototype for an
unrelated project or infer a counterpart from a vaguely similar page.

## Resolve once, source first

Before planning or editing, resolve and record a compact `prototypeReference`:

- canonical repository identity and exact commit;
- authority source (user, native Issue/PR, root instructions, active plan, or
  Assembly development guidance);
- affected prototype source files and target source files;
- matched prototype and target route/state pairs and viewports; and
- already approved intentional differences.

Resolve repository identity by canonical remote, never by a permanent absolute
workstation path. Conflicting or unresolved repository, commit, route, or
authority claims stop UI implementation with one plain `human_help_required`
explanation. If exact source inspection proves there is no counterpart, record
`no prototype counterpart`, name the inspected source, and fall back to the
target's existing production patterns. A missing counterpart is not a blocker.

Read the exact prototype templates and components before evaluating the target.
Do not create a prototype database, durable registry, copied template, or
second ledger.

## Bounded parity map

For each affected surface, retain one concise `prototypeParity` item in the
existing assessment/plan data island and project only the relevant subset into
each execution prompt or review packet:

- prototype and target routes, states, viewports, and source paths;
- semantic elements and meaningful wrapper hierarchy;
- significant Templ/component calls;
- exact Live Wires class strings controlling layout, spacing, schemes, and
  components;
- exact visible headings, labels, helper text, metadata phrasing, and action
  order;
- responsive and interaction decisions;
- source evidence status and rendered evidence status; and
- named intentional differences with their requirement or boundary.

Keep exact paths, commit, short structural excerpts, and a concrete checklist.
Do not paste complete mockups or whole templates. Distinguish `source parity`,
`rendered parity`, `intentional divergence`, `unavailable evidence`, and
`no prototype counterpart` rather than collapsing them into one verdict.

## Authority and permitted divergence

Where the prototype covers the surface, its settled structure, Live Wires
classes, component choices, literal copy, hierarchy, and control placement are
primary. Generic product benchmarks and design heuristics are secondary and
must not redesign those decisions merely because Stripe, Linear, Notion, or
another product chose differently.

This authority is not a byte-for-byte port. Preserve and name required
differences for dynamic IDs and values, URLs, authentication and CSRF,
authorization, public component APIs, production data, Baseplate/Fixture host
composition, Templ implementation details, and accessibility improvements.
Never weaken functionality, authorization, accessibility, security, or Fixture
boundaries to imitate the prototype. Theme variables and exact colors may
differ when the structural scheme is equivalent.

## Complementary source and browser proof

Compare prototype and target renders at matching meaningful routes, states,
and viewports. Capture only affected-surface evidence: screenshots,
accessibility/DOM snapshots, targeted hierarchy, actual class lists, visible
copy and action order, and computed layout/spacing properties when they explain
a mismatch. Do not require global DOM equality, pixel identity, or equal CSS
variable/color values.

Source and browser proof are both required for a declared counterpart:
screenshots cannot prove source hierarchy, components, classes, or literal
copy; source cannot prove resulting spacing, composition, interaction, or
responsive behavior. Matching class names never waive browser comparison, and
a close screenshot never waives source comparison.

In T3 Code, use the collaborative preview first: inspect status, open it when
needed, then navigate and capture the matched cases. Follow the existing
browser recovery ladder before any supported fallback. Curl, a target-only
screenshot, or `looks close` never completes required prototype browser proof.
If the prototype render is temporarily unavailable, preserve completed source
work and report rendered parity `human_help_required`; do not claim rendered
parity complete.

## Findings and completion

Classify observable defects by impact:

- **P1:** primary task blocked, misleading authorization or governance
  consequence, inaccessible essential control, or an explicitly critical
  parity requirement broken;
- **P2:** meaningful structure, component, copy, control-placement,
  responsive, or interaction mismatch that creates confusion or rework;
- **P3:** minor spacing, alignment, metadata formatting, or
  class/presentation drift.

Severity is proportional, never automatic. Every supported P1, P2, and P3
still enters the fix queue and must be rechecked before clean completion.
