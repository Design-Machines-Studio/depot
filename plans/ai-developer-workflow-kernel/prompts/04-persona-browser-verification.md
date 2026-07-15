# Chunk: Persona and Browser Verification

## Context

This is Chunk 04 of the AI Developer Workflow Kernel and depends on Chunks 01
and 02. Depot already contains persona-shaped UX guidance and one strong
browser fallback chain, but coverage is heuristic: some paths sample two or
three personas, other paths may mark browser work skipped, and pipeline may
accept curl fallback. None proves that every project-declared persona, scenario,
route, browser, and viewport actually ran.

This chunk builds the neutral verification model and updates assessment/review
contracts to reference it. Real pipeline/dm-review event wiring is deferred to
Chunk 05.

## Task

Implement verification profiles, project-local persona discovery, complete
declared-case coverage, secret redaction, and an explicit browser recovery state
machine. Required browser recovery order is: capture evidence, close the primary
browser, relaunch and retry the primary, try a genuinely different browser
engine, then stop with a human-help receipt. Curl can diagnose server
reachability but can never satisfy required browser evidence.

## Files to Modify

| File | Action | Notes |
|------|--------|-------|
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification.py` | Create | Profiles, required-case expansion, coverage gate, evidence |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/adapters/browser.py` | Create | Browser capabilities and recovery state machine |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/adapters/personas.py` | Create | Project persona discovery and execution protocol |
| `plugins/workflow-kernel/skills/workflow-kernel/references/verification-profile-schema.json` | Create | Versioned profile schema |
| `plugins/workflow-kernel/skills/workflow-kernel/references/browser-recovery-schema.json` | Create | Versioned attempt/evidence receipt schema |
| `plugins/workflow-kernel/skills/workflow-kernel/references/verification-contract.md` | Create | Shared discovery, completeness, recovery contract |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow-policy-schema.json` | Modify | Own schema-validated browser/viewport defaults |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow-policy.json` | Modify | Chromium/Firefox and desktop/mobile policy defaults |
| `plugins/pipeline/skills/assess/SKILL.md` | Modify | Emit project-declared verification profile safely |
| `plugins/pipeline/skills/promptcraft/SKILL.md` | Modify | Carry declared cases into UI/integration prompt criteria |
| `plugins/dm-review/agents/review/visual-browser-tester.md` | Modify | Reference shared recovery order and fail-closed behavior |
| `plugins/dm-review/agents/review/ux-quality-reviewer.md` | Modify | Replace fixed persona sample with declared coverage gate |
| `plugins/dm-review/skills/visual-test/SKILL.md` | Modify | Standalone visual test uses same recovery receipt |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/test_verification_profile.py` | Create | Schema and required matrix tests |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/test_persona_gates.py` | Create | Discovery, completeness, auth/redaction tests |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/test_browser_recovery.py` | Create | Ordered recovery and evidence tests |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/fixtures/ux/assembly/personas/_index.md` | Create | Sanitized Assembly persona index shape |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/fixtures/ux/assembly/personas/casual-member.md` | Create | Persona frontmatter/device/viewport shape |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/fixtures/ux/assembly/tasks/governance/sample-task.md` | Create | Legacy Assembly task omitting status/required fields |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/fixtures/ux/assembly/coverage-matrix.md` | Create | Generated summary explicitly marked non-authoritative |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/fixtures/ux/assembly-baseplate/tasks/baseplate/sample-mobile-task.md` | Create | Baseplate implementation status/mobile task shape |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/fixtures/ux/assembly-baseplate/suites/permissions.md` | Create | Baseplate suite/task-id selection shape |

## Files to Read (for context)

| File | Why |
|------|-----|
| `plugins/pipeline/skills/assess/references/ux-assessment-protocol.md` | Existing persona discovery and UX assessment vocabulary |
| `plugins/pipeline/agents/workflow/execution-orchestrator.md` | Existing Step 0b and Step 3h contradictions; read only |
| `plugins/dm-review/agents/review/visual-browser-tester.md` | Current strongest browser fallback precedent |
| `plugins/dm-review/agents/review/ux-quality-reviewer.md` | Current Assembly persona matrix behavior |
| `plugins/dm-review/skills/visual-test/references/state-testing.md` | Browser evidence/state matrix |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/redaction.py` | Reuse recursive redaction from Chunk 01 |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/policies.py` | Reuse gate and normalized failure decisions |
| `../assembly/tests/ux/personas/_index.md` and `../assembly/tests/ux/tasks/` | Real Assembly persona/task Markdown shapes; read only and sanitize |
| `../assembly-baseplate/tests/ux/personas/_index.md`, `tasks/`, `coverage-matrix.md`, and `suites/permissions.md` | Real baseplate status/suite shapes; read only and sanitize |
| `../assembly-baseplate/tests/ux/scripts/ux_task_index.py` | Existing task-frontmatter indexing and status-selection behavior; read only |

## Required Interfaces

```python
@dataclass(frozen=True)
class PersonaCase:
    persona_id: str
    scenario_id: str
    role: str
    route: str
    browser_engine: str
    viewport: str
    required: bool

@dataclass(frozen=True)
class VerificationProfile:
    schema_version: int
    source: str
    cases: tuple[PersonaCase, ...]
    auth_field_names: tuple[str, ...]

class PersonaAdapter:
    def discover(self, project_root: Path) -> VerificationProfile: ...
    def execute(self, case: PersonaCase) -> EvidenceRef: ...

class VerificationGate:
    def evaluate(
        self,
        profile: VerificationProfile,
        evidence: Iterable[EvidenceRef],
    ) -> CoverageDecision: ...

class BrowserAdapter(Protocol):
    def attempt(self, request: BrowserRequest, engine: str) -> BrowserAttempt: ...
    def quit_engine(self, engine: str) -> BrowserQuitEvidence: ...
    def launch_engine(self, engine: str, fresh_profile: bool = True) -> BrowserLaunchEvidence: ...

class BrowserRecovery:
    def run(
        self,
        request: BrowserRequest,
        adapter: BrowserAdapter,
    ) -> BrowserRecoveryReceipt: ...
```

The browser attempt receipt needs attempt number, engine, action, result,
normalized failure reason, screenshot/trace/console references when available,
and the final coverage gap. `human_help_required` is a terminal verification
outcome, not an exception swallowed by the caller.

## Persona Discovery Contract

Parse the real Assembly conventions only under the production `tests/ux/`
declaration root: `personas/_index.md`, persona Markdown frontmatter, actual task
frontmatter in `tasks/**/*.md`, `coverage-matrix.md`, optional `suites/*.md`, and
optional project verification config. Alternate sanitized fixture roots require
an explicit adapter argument; unrelated root `tasks/` paths are not declarations.
Supporting Markdown without frontmatter is ignored. Task frontmatter is the
source of truth; the generated coverage matrix is a discovery/index aid whose
drift may emit a safe diagnostic but must never override or invalidate valid task
frontmatter. Descriptive persona-assignment `reason` fields are accepted and
discarded. A missing legacy `requires_role` defaults to `member` when
`requires_auth:true` and `public` otherwise. `implementation_status` selects runnable
cases (`current` and `redirected-current` by default); future/inactive tasks are
reported but are not blocking unless an explicit suite/config opts them in. A
statusless task is a legacy Assembly declaration: record
`legacy_status_defaulted=true` and treat it as runnable unless explicit config
or suite selection excludes it.

Precedence is deterministic:

1. explicit project verification config for browsers/viewports and suite;
2. task frontmatter for route, personas, status, tags, and preconditions;
3. selected suite task IDs;
4. persona frontmatter for device and default viewport;
5. workflow-policy defaults only for fields the project does not declare.

The schema-validated `workflow-policy.json` browser default is Chromium plus
Firefox for required UI or integration proof. Default desktop viewport is
`1440x900`; mobile/responsive tasks use their declared viewport or `375x812`.
These are recorded with `source=workflow_policy_default`, never attributed to
the project. Extract identifiers, roles, routes, scenarios, viewports, and auth
field names without copying cookie values, bearer tokens, passwords, credential
usernames, or fixture secrets.

Every persona assignment on a selected runnable task is required by default;
explicit `required: false` is the only per-case opt-out. `SUCCESS`, `FRICTION`,
and expected permission `BLOCKED` are expected outcomes, not optionality. If no
suite is selected, all runnable declared tasks participate. Only a project with
no UX declaration directory records `not_declared`; do not fabricate coverage.
Non-UI/non-integration work does not block on absent declarations.

## Browser Recovery Contract

1. Attempt required verification in the configured primary engine.
2. On tooling/browser failure, capture safe error, console output, screenshot or
   trace references if available, URL, engine, and attempt metadata.
3. Quit the primary testing browser process/engine session. Closing a tab,
   page, or context inside the same process is insufficient.
4. Relaunch a clean primary engine with a fresh profile and retry once. A new
   process/session identity must prove the restart.
5. If primary still fails, launch a different configured engine and retry once.
6. If secondary fails or cannot launch, return blocked with
   `human_help_required`, all attempt evidence, and exact missing coverage.
7. Never translate this state to skipped, approved, or curl-verified.

If the host cannot prove a process/engine-session quit and fresh relaunch,
record `primary_restart_unavailable`, do not claim primary recovery, and proceed
to the different secondary engine. If that also fails or is unavailable, stop
and request human help.

An application/container restart is a separate diagnostic action from a testing
browser restart. The receipt must say which one occurred.

## Patterns to Follow

- Use complete set comparison: required case IDs minus passing evidence case IDs.
- Evidence belongs to one exact case and attempt. A screenshot without a case,
  engine, viewport, route, and evaluation is not passing evidence.
- A flaky primary that passes after relaunch records both the failed and passing
  attempts; do not erase recovery history.
- A secondary pass closes the browser-tooling gap but must still be reported as
  recovered/degraded rather than first-pass clean.
- Treat all profile files as untrusted input and reject traversal, duplicate
  case IDs, unknown engines, malformed viewports, and auth values.
- Keep stable heading anchors in modified Markdown. Do not depend on line numbers.

## Companion Skills

- `developer-essentials:e2e-testing-patterns` — cross-browser fixture strategy.
- `accessibility-compliance:screen-reader-testing` — runtime evidence semantics.
- `dm-review:visual-test` — current browser review surface and receipts.
- `superpowers:test-driven-development` — failure ladder tests before code.

## Implementation Sequence

1. Create sanitized fixtures matching both Assembly repositories' `_index.md`,
   persona/task frontmatter, coverage matrix, implementation status, and suite
   shapes, including deliberately secret-like values that must not survive.
2. Write failing profile schema and complete-set coverage tests.
3. Write failing browser adapter tests for every recovery transition.
4. Implement profile discovery, normalization, validation, and redaction.
5. Implement coverage comparison and blocking decisions.
6. Implement browser recovery with an injected fake adapter and fake clock.
7. Write the shared verification contract.
8. Update assessment, promptcraft, visual-browser, UX-quality, and standalone
   visual-test instructions to reference the shared contract and fail closed.
9. Run full kernel, description, and workflow contract checks.

## Acceptance Criteria

- [ ] Sanitized fixtures matching both Assembly layouts produce deterministic
      cases from `_index.md`, persona/task frontmatter, implementation statuses,
      coverage matrix, and suites; task frontmatter overrides summaries.
- [ ] Only `tests/ux/` is an implicit production declaration tree; supporting
      Markdown without frontmatter is ignored, and alternate fixture roots are
      explicit. Live Assembly assignment `reason` and legacy missing-role shapes
      discover without retaining descriptive or credential values.
- [ ] Coverage-matrix mismatch is diagnostic and never invalidates valid task
      frontmatter; profile cases and auth-field names have canonical ordering.
- [ ] Statusless legacy Assembly tasks remain runnable with recorded compatibility
      provenance, and a fixture omitting both `implementation_status` and
      `required` produces a non-empty blocking case set.
- [ ] Selected runnable task-persona pairs default to required; only explicit
      `required:false` opts out, while SUCCESS/FRICTION/expected-BLOCKED remain
      evaluative expected outcomes.
- [ ] Project configuration, task declarations, suite selection, persona
      defaults, and workflow-policy defaults follow the documented precedence.
      Undeclared engines are policy defaults, never fabricated declarations.
- [ ] Browser/viewport defaults are schema-validated values owned by
      `workflow-policy.json`; evidence records their policy provenance.
- [ ] Secret-like auth values are absent from profiles, events, exceptions,
      stderr, snapshots, and receipts; tests use sentinel values and scan output.
- [ ] Duplicate case IDs, traversal paths, unknown engines, malformed viewports,
      missing required fields, and contradictory declarations fail closed.
- [ ] Required persona coverage is complete-set comparison across every declared
      required case, not a sample count.
- [ ] UI/integration coverage blocks when any required persona/scenario case is
      missing, failed, unauthenticated, or lacks evaluative evidence.
- [ ] Projects with no UX declaration directory record `not_declared`; absence
      of an optional suite does not erase runnable tasks, no fake personas are
      created, and non-UI work remains unblocked.
- [ ] Browser recovery records the initial failure before attempting recovery.
- [ ] Recovery quits and relaunches the primary browser process/engine session
      with a fresh profile, proves a changed process/session identity, then
      retries the primary exactly once; context-only recreation does not pass.
- [ ] A host unable to prove a fresh primary records
      `primary_restart_unavailable` and proceeds to the alternate engine rather
      than silently skipping or claiming recovery.
- [ ] A blocked multi-engine receipt proves an alternate attempt or explicit
      alternate unavailability, and records `primary_restart_unavailable` when
      the primary retry was skipped.
- [ ] A continuing primary failure attempts exactly one genuinely different
      browser engine, not merely another tab or tool wrapper for the same engine.
- [ ] Exhausted/unavailable secondary verification returns blocked with
      `human_help_required`, preserved attempt evidence, and explicit missing
      cases.
- [ ] Curl/reachability diagnostics cannot produce browser-pass evidence or
      convert blocked verification to skipped.
- [ ] App/container restart and browser restart are distinct receipt actions.
- [ ] Recovered tests preserve failed-attempt evidence and report degraded first
      pass; they are not rewritten as first-attempt clean.
- [ ] Modified pipeline and dm-review instruction surfaces reference one shared
      recovery/coverage contract and no longer permit silent skip for required
      browser evidence.
- [ ] Markdown anchors remain stable and the existing visual state-testing
      protocol remains intact.
- [ ] Full checks pass:

```bash
PYTHONPATH=plugins/workflow-kernel/skills/workflow-kernel/references \
python3 -m unittest discover \
  -s plugins/workflow-kernel/skills/workflow-kernel/references/tests \
  -p 'test_*.py' -v
./tools/eval-descriptions.sh
./tools/validate-workflow-contracts.sh
```

## Tool-Call Budget & Partial-Return Contract

You run under a hard budget. Treat every tool call as spend you track.

- **Hard cap: 40 tool calls** (50 if this chunk drives a browser). Keep a running count.
- **At 80% of budget (32 calls) stop exploring and finish the edit + write-up.** A subagent that dies mid-flight (spend limit, context overflow, crash) returns NOTHING and its whole chunk is lost. Partial progress committed beats a perfect diff never returned.
- **End your response with two sections, even if you had to stop early:**
  - `NOT-COVERED:` -- acceptance criteria, files, or checks the budget did not reach.
  - `COMMANDS-RUN:` -- the build/test/search commands you actually ran.

## Ambiguity Protocol

This block is one of three layers in the pipeline's ambiguity defence. Sibling layers: `plan-adversary.md` Sprint Contract Negotiation (catches structural ambiguity at prompt-review time, cheapest) and `execution-orchestrator.md` Ambiguity Handling (autonomous-mode commit-trailer fallback). Keep the wording here in sync with those two.

If the Task or Acceptance Criteria allow more than one reasonable interpretation, do not pick silently.

- Name the interpretations in a single short list before you touch code. Example: "Task says 'make the members page faster' -- this could mean (a) reduce server render time, (b) reduce perceived load time via progressive rendering, (c) reduce bundle size. Proceeding with (a) because the assessment flagged a slow query; alternatives rejected for lack of evidence."
- When running under the execution-orchestrator's autonomous mode, record the chosen interpretation and rejected alternatives as two separate git-style trailer lines in the chunk's commit message: one `Chose: <interpretation>` line and one `Rejected: <alt-1>; <alt-2>` line. Multiple rejected alternatives are `; `-separated on the single `Rejected:` line. Follow the canonical `git interpret-trailers` shape so downstream tools can parse them.
- Flag the decision in the chunk receipt (`ambiguity_resolved: true` with a one-line summary) so the adversarial reviewer on the next round can evaluate whether the right path was taken.
- Fabricating certainty is a P1 failure. Surfacing ambiguity is never penalized.

## Constraints

- Only modify the files listed above.
- Use fake browser/persona adapters in unit tests; do not depend on a live dev
  server, real credentials, or installed browser binary.
- Do not integrate the execution orchestrator or dm-review review skill in this
  chunk; Chunk 05 performs runtime wiring.
- Do not weaken existing visual, state, responsive, or accessibility checks.
- Do not copy raw auth middleware lines into fixtures or artifacts.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.
- Do not create or modify `*_templ.go` files. Run `docker compose exec app templ generate` to regenerate them after editing `.templ` source files.
- When adding database migrations, verify the next sequence number: `ls migrations/*.sql | sort | tail -1`. Use the next consecutive number.
- When this chunk touches `auth/`, `admin/`, `account/`, `install/`, `member/`, or `module`-level permission paths in Assembly code, the final acceptance criterion must include an Auth Boundary Map receipt covering: surfaces mapped, middleware gates, Authorizer action/resource pairs, default-deny UI capabilities, stale-session/operator/install edge cases, test coverage, and residual risk. Omit the receipt only when no auth surface is affected.

## Research Context

Historical durable UX proof used both Chromium and Firefox plus privileged and
ordinary-member flows, but it was manually role-driven rather than discovered
from declarations. Playwright Test's own retry design discards the failed worker
and browser before starting a new one, supporting the clean-relaunch concept;
the MCP/browser-tool path still needs the explicit host-adapter ladder defined
here. Stale app output caused by an old container child is a separate runtime
diagnosis and must not be mislabeled as browser recovery.
