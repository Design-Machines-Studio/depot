# UI-DEFAULTS-01 — complete prototype fidelity and existing-site review defaults

Prepared 2026-09-10 from authenticated Depot main. Complete replacement prompt
for a fresh Depot session, including existing prototype UX tasks and personas.
It does not require the previous session or planning PR to complete first.

Recommended start

- Model: GPT-6 Astra
- Harness/rail: Codex subscription (attemptable)
- Effort: medium
- Why: Reconcile existing cross-plugin guidance and verify the real browser path.
- Cost: included subscription; API-equivalent estimate unavailable
- Fallback: GPT-5.6 Sol via Codex subscription, medium (attemptable)
- Matrix evidence: 2026-08-27; installed-router recommendation refreshed 2026-09-10

```text
Task: UI-DEFAULTS-01 — finish prototype fidelity and existing-site review defaults

Repository: Design-Machines-Studio/depot
Prepared origin/main: 7e5475195ecab8c626b03ee79185d3b863852c82
Primary checkout: /home/ned/ai/depot — preserve exactly.
Existing implementation branch: fix/prototype-review-defaults
Existing implementation worktree:
  /home/ned/ai/depot-worktrees/prototype-review-defaults
Prepared implementation HEAD: 7e5475195ecab8c626b03ee79185d3b863852c82
Its uncommitted changes already cover this task. Continue them; do not replace
them or start a competing implementation. A dirty implementation tree is expected.
This fresh session is authorized to continue that task's existing diff.

executorRole: builder-deep
executorCapabilities: [read-repository, write-repository, tool-use, structured-output]
executorEffort: medium
Browser execution belongs to the host's actual tools, separately from routing.

OWNERSHIP AND START
Even if this session starts in another project, first set the working directory
to the exact Depot implementation worktree above. Before editing, verify
git rev-parse --show-toplevel and git remote get-url origin identify that
worktree and Design-Machines-Studio/depot. Accept equivalent SSH/HTTPS remotes.
Do not create or edit files in the project where the earlier prompt was run;
do not undo its work. Apply the instructions governing Depot files.

Refresh main, branch state, open PRs and actual file ownership. Read applicable
AGENTS/CLAUDE instructions and references, Assembly Coordinator, Design Machines
strategy, affected skills, and existing validation/release guidance.
PR #129 is merged; retain dm-review 1.80.2 / Kernel 0.22.0 repairs.
PR #135 is planning only, not an implementation prerequisite. Do not convert
that planning PR into the implementation PR. A dirty task-owned diff is not
an active-owner conflict; pause only for evidence of a concurrent writer.

Keep existing edits and all other worktrees intact. Do not stash, reset, clean,
force-push, delete worktrees or modify the protected primary checkout.
If a newer main must be incorporated, use a normal merge in the owned
implementation branch. No unrelated Issue/PR or planning-PR merge is a prerequisite.

PROBLEM AND BOUNDED OWNERS
Assembly's design authority is buried under prototype-era advice. Existing
parity guidance is too easy to satisfy with screenshots without exercising
Datastar saving. The installed review contract also forbids rebuilding any
pre-existing target, conflicting with the user's intended development loop.

Finish the existing changes in:
- assembly:development — definitive design authority and correct early scoping.
- Pipeline prototype-authority, promptcraft and execution/browser guidance.
- dm-review discovery, readiness, visual and source-review entrypoints.
- Assembly Coordinator prompt preparation.
- project-scaffolder's existing instruction templates.

These are the surfaces already being edited. Keep changes proportional.
Do not redesign Kernel, model routing, application code or shared components.

REQUIRED DESIGN RULE
For an existing prototype counterpart, inspect exact templates, rendered HTML,
Live Wires class strings, livewires-templ composition, and Datastar behavior
before implementing. Preserve the exact affected hierarchy, wrappers, classes,
copy and control placement. Do not substitute new UI or custom CSS because it
looks similar. Bring this rule into the early Assembly entrypoint and scope
prototype-only instructions explicitly.

Trace event -> signals/bindings -> request timing/payload -> handler/response
-> feedback -> persisted result. Exercise the same affected interaction in
prototype and app, including save/autosave and reload/revisit. Compare matching
desktop/mobile states, keyboard/focus and validation when affected.
A prototype stub is not proof of durable production storage.

Themes may change colors and small pixel measurements; they do not excuse
different structure, layout classes, spacing decisions or interaction flow.
Production auth, CSRF, storage and SDK wiring may differ without redesigning
the experience. A necessary security/accessibility correction must be narrow
and evidenced. Other design divergence requires explicit approved scope.
If there is no counterpart, identify what was inspected; do not invent one.

REUSE PROTOTYPE UX TASKS AND PERSONAS
Resolve the canonical Design-Machines-Studio/assembly prototype at the exact
reviewed commit. Local discovery path: /home/ned/assembly/assembly.
Read tests/ux/README.md, coverage-matrix.md, applicable tasks/**/*.md,
personas/_index.md, the selected persona files, and referenced heuristics.
Task frontmatter and steps are authoritative over the generated coverage matrix.
These are content-defined browser scenarios, not an invented CLI test runner.

Select the existing task IDs and persona/role/state/device combinations affected
by the change, including handler-only Datastar changes. Carry those references,
preconditions, steps, success criteria and screenshot points through Pipeline
planning/prompts into dm-review's existing case selection and evidence packet.
Do not duplicate the suite or run the full persona/task cross-product by default.

Execute the selected scenarios in both prototype and app with comparable demo
accounts, permissions and initial data. Explicitly map different route/account/
record IDs without weakening the scenario or production authorization. Record
prototype result, app result and observed difference for each selected case.
Include save/reload where relevant. Reading tasks or imagining a persona's
experience does not count as browser execution or real-user research.

An expected permission denial is a successful boundary check when verified,
not unavailable infrastructure. Expected FRICTION is a hypothesis to assess,
not an automatic finding. Report stale task/source conflicts and approved
production differences explicitly. Unimplemented out-of-scope product areas
do not become new feature requirements; selected required cases remain
incomplete if missing data/access prevents their execution.

REQUIRED REVIEW-SITE RULE
Default to the project's established development domain and designated serving
checkout. Project codes map to [project-code].asmbly.app, but verify the exact
local binding. Record the URL, served checkout and existing build/status commands
in root instructions or a directly linked runbook. Notion is optional; missing
catalog access must never block a known local mapping.

Known declarations: prototype dm006.asmbly.app; Governance dm027.asmbly.app.
Verify each runtime's actual source binding rather than assuming a folder name.

Use ordinary Git to select the feature branch in the clean, available serving
checkout and run its documented rebuild/restart. This maintenance is authorized
as part of the requested implementation/review; no repetitive approval.
Changing Git HEAD alone does not update a compiled binary.

If the feature branch is registered in a separate development worktree, a normal
detached checkout of its exact committed head in the free serving checkout is
acceptable; identify it honestly. Never force duplicate checkout or move another
worker's branch. Preserve owned in-progress edits with an exact source
fingerprint when reviewing them in place. Preserve unrelated dirty/concurrent
work and report that concrete collision instead of silently creating a harness.

Keep the same domain, service, data and configuration. Do not reconfigure DNS,
Caddy, tunnels, ports, env files or Compose topology. Do not reset shared data.
Check for concrete incompatible data migrations before a branch switch/rebuild;
ordinary development is not a blanket destructive-action approval.

Existing service maintenance is not review-owned infrastructure creation.
Do not adopt or tear down the established instance during cleanup.
Bind browser evidence to the source actually served, including build/assets,
not just the analysis worktree. Leave the reviewed state for the operator and
report it; restore/rebuild only when an agreed handoff requires restoration.

Use T3 first as transport, then an available suitable host browser fallback.
An attached tab or unavailable routed browser candidate does not determine
which project to review or whether host tools exist.
New browser environments require a concrete test need, such as simultaneous
federation peers. Ordinary isolated unit-test containers remain valid.
Preserve exact evidence reuse and honest incomplete-coverage reporting.

ACCEPTANCE AND VERIFICATION
Remove contradictions across the affected full/quick/visual and Pipeline paths.
Reuse existing readiness/parity evidence; add no service, broker, parser,
global registry, second ledger or new approval system.

Extend existing focused contract tests for:
- wrong attached tab versus the declared project site;
- clean branch selection/rebuild and the exact served source;
- branch already in another worktree, unrelated dirty work, and stale binary;
- existing-instance retention versus justified isolated-resource cleanup;
- exact structure/classes and handler-only Datastar interaction changes;
- save/reload behavior, theme differences, and approved minimal adaptations.
- existing UX task/persona selection and propagation from an external prototype,
  expected denial versus coverage failure, and paired browser observations.

Run relevant trigger tests only where descriptions change, affected readiness/
discovery/UI/Pipeline/scaffolder/coordinator checks, generated checks, and
./tools/validate-composition.sh --all. Fix every retained P1/P2/P3 finding.
Use one proportional review and affected rechecks; no repeated full rosters.

Canary with an applicable existing Governance UX task and its mapped personas
against the exact prototype counterpart (GOV-PL-003 draft editing is a candidate
only if that flow exists in the target's approved scope):
use dm027/dm006 through verified current bindings, build the selected source
through documented commands, and compare desktop/mobile interaction plus
save/reload on designated demo records. Do not change consumer product code.
Record source versus installed-plugin execution. If access, data, runtime
binding or prototype evidence is genuinely unavailable, name the exact gap,
continue independent verification/delivery, and do not claim the canary passed.

VERSION AND DELIVERY
At the prepared base: Assembly 3.16.0, Pipeline 1.67.0, dm-review 1.80.2,
project-manager 1.14.0, project-scaffolder 1.9.4, Kernel 0.22.0.
Bump only changed plugins according to actual scope from refreshed main.
Update canonical Claude plugin/marketplace versions; regenerate Codex manifests
and changed command aliases. Refresh the index/dependency graph as necessary.
Avoid dependency cycles or new dependencies merely to share prose.

Commit, push, and open/update one proper implementation PR against main.
Do not merge, tag, publish, or synchronize Claude/Codex caches. Report those
remaining release steps and the later installed-consumer canary separately.
Source push must not require caches to match unreleased code.

Use only Project 1, Assembly Coordination: Review / P1 / Tooling when ready.
Do not mutate native Issues. REST fallback is valid if GraphQL is limited;
Project access must not block verified commit/push/PR delivery.

Request optional participants by role/capabilities/effort through the installed
router. Prefer available subscription capacity; paid calls at most $0.25 total
within known remaining budget. The $50/month target is not observed headroom.

About 40 tool calls is an exploration checkpoint, not a reason to abandon
repair, verification, commit, push or PR creation.

FINAL
Report actual base/head, changes, tests, consumer coverage, versions, PR/Project
state, delivery level and one next action. Include SIMPLICITY-CHECK, NOT-COVERED
and COMMANDS-RUN. For routed work report role, attempted/served participant,
rail, effort, duration, outcome, measured tokens/cost, subscription calls,
fallbacks and unavailable measurements. No invented clean passes or costs.
```
