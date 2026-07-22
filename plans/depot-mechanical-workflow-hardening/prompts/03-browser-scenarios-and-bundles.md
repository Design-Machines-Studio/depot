# Chunk: Browser Scenarios and Evidence Bundles

## Context

This is Chunk 03 of Depot Mechanical Workflow Hardening. Workflow Kernel already
models declared persona/browser cases and the required evidence-preserving
recovery sequence. This chunk extends those foundations into executable ordered
scenarios and one immutable evidence bundle that independent reviewers can share.

Chunk 01 supplies the exact build/profile/evidence binding. Do not replace the
existing recovery model, reinterpret curl as browser proof, or make one reviewer
authoritative for accessibility, visual, UX, and domain judgment.

## Task

Add strict scenario and bundle contracts, plus a new scenario adapter seam.
Represent ordered browser actions/assertions, human-action pauses, evidence
capture, process restart, alternate-engine recovery, and terminal status without
widening the existing `BrowserAdapter` protocol.

## Files to Modify

| File | Action | Notes |
|------|--------|-------|
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/browser_scenario.py` | Create | Closed scenario step union and canonical scenario identity |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/browser_bundle.py` | Create | Immutable evidence bundle and exact reuse/match rules |
| `plugins/workflow-kernel/skills/workflow-kernel/references/browser-scenario-schema.json` | Create | Strict version-1 scenario document |
| `plugins/workflow-kernel/skills/workflow-kernel/references/browser-evidence-bundle-schema.json` | Create | Strict version-1 bundle manifest |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification.py` | Modify | Bind existing `PersonaCase`/profile IDs to scenarios without overloading profile policy |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/browser_evidence.py` | Modify | Reuse immutable attempt/session/recovery receipts in bundle validation |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/adapters/browser.py` | Modify | Add a separate `BrowserScenarioAdapter` seam; keep `BrowserAdapter` compatible |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/adapters/__init__.py` | Modify | Export only the new adapter protocol as needed |
| `tests/test_browser_scenarios.py` | Create | Step, bundle, recovery, stale-binding, hostile-input tests |
| `tests/test_browser_recovery.py` | Modify if required | Prove existing recovery semantics remain exact |
| `tests/test_verification_profile.py` | Modify if required | Prove legacy profile compatibility |

Do not modify Assembly UX declarations, dm-review orchestration, Pipeline browser
prose, CLI registration, release inventories, manifests, or plugin versions.

## Files to Read (for context)

| File | Why |
|------|-----|
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification.py` | `PersonaCase`, `VerificationProfile`, evidence identity |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/browser_evidence.py` | Immutable attempts, session identity, evidence references |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/adapters/browser.py` | Existing adapter compatibility boundary |
| `plugins/workflow-kernel/skills/workflow-kernel/references/browser-recovery-schema.json` | Mandatory retry/restart/alternate-engine state machine |
| `plugins/workflow-kernel/skills/workflow-kernel/references/verification-profile-schema.json` | Existing declaration schema and legacy defaults |
| `plugins/workflow-kernel/skills/workflow-kernel/references/verification-contract.md` | Browser proof and persona coverage authority |
| `tests/test_browser_recovery.py` | Required negative and lifecycle cases |
| `tests/test_verification_profile.py` | Project/task/profile discovery expectations |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/evidence_binding.py` | Chunk 01 exact binding API |

## Patterns to Follow

- Existing persona/browser identity is content-addressed from persona, scenario,
  role, route, engine, viewport, and route digest.
- Existing browser recovery preserves each attempt and requires primary-process
  quit, demonstrably fresh primary launch/retry, a genuinely different configured
  engine, then `human_help_required` when infrastructure remains unavailable.
- Use frozen immutable records, tuples, strict field sets, bounded strings and
  collections, normalized evidence references, and canonical JSON digests.
- Reference screenshots, traces, console logs, accessibility output, and network
  summaries by safe durable reference plus digest; do not embed their raw contents.

The closed scenario step union must cover only approved mechanics:

- navigate to a concrete normalized route;
- perform a declared interaction against a stable selector/role/label;
- declare an isolated named browser profile/cookie-jar reference and bound
  environment-fixture reference without persisting their secret contents;
- establish a declared login lifecycle expectation (`success`, expected
  rejection, or `human_action_required`) and verify the resulting auth state;
- select JavaScript-enabled or JavaScript-disabled execution per scenario;
- assert URL, HTTP/application status, visibility, text, count, focus after
  morph/dialog, toast, validation state, accessibility, console, network,
  computed style, or horizontal/viewport overflow;
- capture screenshot, trace, console, accessibility, or computed-state evidence;
- pause for a named human action without fabricating completion;
- request an application restart and assert the expected post-restart session
  state separately from browser-process recovery;
- request primary process quit/fresh launch/session validation;
- retry the primary engine or select a declared alternate engine.

Do not permit arbitrary JavaScript, shell strings, credential values, free-form
code execution, unbounded selectors, `javascript:` URLs, query-string secrets,
or route origins outside the bound target.

The bundle must bind:

- scenario ID/digest and selected `PersonaCase`/profile ID;
- isolated named browser-state reference, environment-fixture reference, login
  expectation/result, JavaScript mode, and application-restart/session result;
- Chunk 01 build/evidence binding digest;
- requested and actual engine, viewport, target origin/route digests;
- session/profile identity and attempt/recovery receipt references;
- ordered step result records and per-step evidence references;
- screenshot/trace/console/accessibility/computed-state digests;
- coverage status, missing case IDs, terminal reason, and immutable bundle digest.

Bundle reuse is allowed only when build, profile, scenario, route, viewport,
authentication state, engine requirement, and relevant evidence digests match.
A reachability response or stale screenshot never upgrades the bundle.

## Companion Skills

No companion skill is required. Follow Workflow Kernel browser contracts. This
chunk does not drive a live browser; it implements and tests neutral contracts.

## Acceptance Criteria

- [ ] Scenario and bundle schemas are strict version-1 documents with exact keys, bounded collections, canonical IDs, and hostile-input rejection.
- [ ] The scenario step model is a closed tagged union; unknown actions/assertions fail instead of degrading to free-form execution.
- [ ] Navigation is restricted to the bound target origin and normalized route; traversal, credential-bearing URLs, `javascript:`, control characters, and unresolved route parameters fail closed.
- [ ] Interaction/assertion selectors are bounded and data-only; no arbitrary JavaScript, shell, Python, or eval payload can enter durable state.
- [ ] The closed scenario model has explicit data-only variants/configuration for isolated named profile/cookie-jar references, environment fixtures, login success or lifecycle rejection, JavaScript-disabled execution, and application restart followed by session-state verification.
- [ ] Assertion variants cover URL, application/HTTP status, focus after morph/dialog, toast, validation, console, and horizontal/viewport overflow in addition to existing visual/accessibility assertions.
- [ ] `human_action_required` is distinct from infrastructure `human_help_required` and product `application_failure`; none is normalized to passed or skipped.
- [ ] Required recovery preserves failed evidence, confirms primary quit, proves fresh primary launch/session identity, retries primary, then tries a genuinely different configured engine before `human_help_required`.
- [ ] A failed product assertion can terminate as `application_failure` without forcing meaningless browser restarts after the application itself is proven reachable and wrong.
- [ ] Bundle manifests reference screenshot, trace, console, accessibility, network, and computed-state artifacts by safe reference and digest, never raw private contents.
- [ ] Bundle identity binds exact build/evidence binding, profile, persona case, scenario, route, engine, viewport, authentication state, attempts, and ordered results.
- [ ] Reuse fails with a specific stale reason when any relevant binding component changes.
- [ ] The existing `BrowserAdapter` remains source-compatible; new scenario execution uses a separate adapter protocol.
- [ ] Legacy verification profiles and browser recovery receipts remain valid with explicit provenance and unchanged semantics.
- [ ] Deterministic tests cover first-pass success, fresh-primary recovery, alternate-engine recovery, human action, human help, application failure, missing evidence, tampered digest, and stale binding.
- [ ] Deterministic positive and hostile tests cover isolated-state identity without raw cookies, fixture/login lifecycle outcomes, JavaScript-disabled mode, application restart with retained/rejected session expectations, and focus/toast/validation/status/overflow assertions.
- [ ] Focused verification passes with `PYTHONPATH=plugins/workflow-kernel/skills/workflow-kernel/references /opt/homebrew/bin/python3.12 -m unittest tests.test_browser_scenarios tests.test_browser_recovery tests.test_verification_profile`.
- [ ] No live browser claim is made; this chunk provides contract/fixture evidence only.
- [ ] `git diff --check` passes and only declared files changed.

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
- Keep Workflow Kernel Python 3.12 standard-library-only.
- Do not widen the existing `BrowserAdapter`; add a new protocol for scenario execution.
- Do not duplicate the current recovery state machine or weaken its fail-closed ladder.
- Do not put raw credentials, cookies, session values, private DOM content, screenshots, traces, or console logs in structured durable records.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.
- Do not create or modify `*_templ.go` files. Run `docker compose exec app templ generate` to regenerate them after editing `.templ` source files.
- When adding database migrations, verify the next sequence number: `ls migrations/*.sql | sort | tail -1`. Use the next consecutive number.
- When this chunk touches `auth/`, `admin/`, `account/`, `install/`, `member/`, or `module`-level permission paths in Assembly code, the final acceptance criterion must include an Auth Boundary Map receipt covering: surfaces mapped, middleware gates, Authorizer action/resource pairs, default-deny UI capabilities, stale-session/operator/install edge cases, test coverage, and residual risk. Omit the receipt only when no auth surface is affected.

## Research Context

Assembly Baseplate already declares runnable UX tasks with persona IDs, concrete
routes, viewports, expected authorization outcomes, and screenshot points. The
current Kernel profile/recovery system can identify cases and recover sessions,
but cannot execute ordered scenarios or share one immutable runtime bundle among
reviewers. This chunk closes that mechanical seam while retaining independent
human interpretation.
