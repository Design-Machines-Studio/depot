# Declared prototype authority

Load this reference for rendered work, including handler/Datastar changes that
alter an existing interaction even without a template diff, when a prototype is declared by the
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

Read the exact prototype templates, shared components, Datastar attributes,
supporting handlers, and relevant client code before evaluating the target.
Copy the affected HTML structure and exact Live Wires classes into the
implementation, using the same livewires-templ components where available.
The restriction on whole templates concerns prompt/evidence duplication, not
implementation reuse. Do not create a prototype database, durable registry, or
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
- responsive behavior and a short interaction trace: initiating event,
  Datastar signals/bindings, request timing and payload, handler/response,
  feedback/error state, and what persists after reload;
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

The affected rendered HTML hierarchy, Live Wires class strings, shared
component composition, spacing, and interaction behavior are the implementation
baseline. Do not substitute equivalent-looking custom CSS, different wrappers,
new controls, or a new save flow. Any design change starts from this foundation
and needs an explicit approved requirement; agent preference is not approval.

Adapt dynamic IDs/values, URLs, authentication/CSRF, authorization, storage,
and host wiring to production while preserving the observable design and
behavior. Those adaptations are not blanket permission to redesign. A concrete
security, accessibility, or public-API constraint permits only its necessary
minimal difference, recorded with source evidence and its effect on parity.
Never weaken those boundaries to imitate the prototype. Theme variables and exact colors may
differ; theme variation does not waive class, structure, or spacing comparison.

For example, production storage does not justify replacing change/blur
autosave with a Save button, or the reverse. Trace when a change is sent, what
is saved, and how success/failure appears before porting it. A prototype stub
is evidence of intended interaction, not proof of production persistence.

For prototype-covered cases, apply dm-review’s `ui-case-selection.md` existing
prototype tasks and personas contract. Carry the exact task source/commit,
selected task IDs and persona/role/state/device combinations, preconditions,
steps, success criteria and screenshot points into the existing prompts and
browser evidence. Execute the paired cases and record prototype result,
application result and observed difference; expected permission denial is a
verified boundary check, and expected FRICTION remains a hypothesis.

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

Actually perform each affected interaction in both apps using comparable roles
and disposable or designated demo records. For editing, change a value, trigger
the prototype's save/autosave event, observe pending/success/error behavior,
then reload or revisit to check persistence. Include cancel/discard, keyboard
and focus behavior, and validation when affected. Record observed behavior on
each side and distinguish a synthetic/stubbed save from durable storage.
Do not reset shared data or use real member records to manufacture evidence.

Resolve each app's established review domain and canonical checkout through
dm-review's `repository-browser-target-discovery.md` before browser navigation.
In T3 Code, use the collaborative preview as the browser transport: inspect
status, open it when needed, then navigate to those verified targets and capture
the matched cases. An attached tab does not establish the correct target. Follow the existing
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
