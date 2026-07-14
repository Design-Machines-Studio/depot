# AI Developer Workflow Kernel Design

**Status:** Approved design  
**Date:** 2026-07-14  
**Branch:** `codex/ai-developer-workflow-kernel`  
**Pipeline epic:** `plans/ai-developer-workflow-kernel/`

## Summary

Depot will add a dependency-free Python workflow kernel that makes pipeline and
dm-review control flow executable and testable while preserving their Markdown
policy and expertise. The kernel launches in compatibility shadow mode, then
progresses through enforce mode to an opt-in native mode only after behavioral
parity and failure-injection suites pass.

The current Markdown orchestrators remain authoritative during shadow mode. The
kernel observes manifests and actions, predicts legal transitions, records a
structured event ledger, and reports parity gaps without changing outcomes.

This epic is repo-local. It does not add a daemon or external GitHub, Notion,
Slack, or ticket-queue ingestion.

## Goals

1. Create a shared run-state and event model for pipeline and dm-review.
2. Move repeatable control-flow mechanics into dependency-free Python.
3. Preserve existing commands, manifests, receipts, generated Codex shims,
   provider boundaries, human gates, and cleanup guarantees.
4. Test workflow behavior through transition, scenario, failure-injection, and
   receipt-replay suites.
5. Preserve builder context across deterministic validation failures when the
   host supports resumable agents.
6. Route top-level workflow classes with risk-appropriate gates.
7. Make Git, Docker, browser, persona, and isolation lifecycles explicit.
8. Measure node and provider reliability without automatically changing policy.

## Non-goals

- A long-running workflow service or daemon.
- External issue, chat, or project-management ingestion.
- Automatic routing-policy edits.
- Removal of Markdown expertise or current human gates.
- Immediate replacement of the current orchestrators.
- Sending sensitive workflow data to providers prohibited by existing policy.

## Architectural principle

Depot separates judgment from mechanics:

```text
Markdown policy and expertise
            |
            v
Host and system adapters
            |
            v
Dependency-free Python workflow kernel
            |
            v
Git, Docker, browsers, agents, validators, and receipts
```

Markdown remains canonical for reviewer expertise, security policy, routing
rationale, fix philosophy, acceptance guidance, and human-readable workflows.
The kernel owns deterministic state, transitions, dependencies, retry limits,
gates, evidence requirements, resource ownership, and cleanup obligations.

The kernel returns decisions such as `READY`, `RETRY_BUILDER`,
`FALLBACK_REQUIRED`, `REQUIRES_HUMAN`, or `CLEANING_UP`. In shadow and enforce
modes the existing host orchestrator performs the action. Native mode may allow
the kernel to select ready nodes, but host adapters still perform external work.

## Proposed repository structure

```text
tools/workflow_kernel/
  __init__.py
  __main__.py
  cli.py
  schema.py
  events.py
  state.py
  transitions.py
  policies.py
  workflows.py
  receipts.py
  redaction.py
  adapters/
    base.py
    host.py
    isolation.py
    git.py
    docker.py
    browser.py
    personas.py
  tests/
    test_schema.py
    test_transitions.py
    test_recovery.py
    test_workflow_classes.py
    test_cleanup.py
    test_browser_recovery.py
    test_persona_gates.py
    scenarios/
    fixtures/

plugins/pipeline/references/
  workflow-run-schema.json
  workflow-event-schema.json
  workflow-policy.json
  workflow-classes.json

plugins/pipeline/references/workflow-kernel.md
plugins/dm-review/skills/review/references/workflow-kernel.md
tools/validate-workflow-kernel.py
```

Exact filenames may be refined during assessment and planning, but the kernel
must stay a focused package rather than becoming another monolithic script.

## Durable run model

Each run stores two machine-readable artifacts:

- `run-state.json`: the current materialized state, written atomically using a
  temporary file plus rename.
- `events.jsonl`: an append-only audit log from which state can be reconstructed.

### Core entities

#### WorkflowRun

Records schema version, run ID, workflow class, rollout mode, host, status,
requirements, creation/update timestamps, required gates, and terminal outcome.

#### Node

Represents a bounded unit such as assess, diagnose, build, validate, review,
human gate, merge, persona test, browser verification, or cleanup.

Each node declares:

- Dependencies.
- Required capabilities.
- Provider class.
- Isolation preference and minimum acceptable isolation.
- Retry and convergence policy.
- Evidence requirements.
- Gate policy.
- Whether its agent session may be resumed.

#### Attempt

Records provider, model when available, agent session handle, isolation target,
input references, output references, result, failure signature, and timing.

#### Evidence

References commands, files, screenshots, traces, tests, findings, and receipts.
Evidence stores redacted references rather than credentials or raw secrets.

#### Gate

Represents machine, human, review, security, persona, browser, cleanup, or caller
verification requirements. Required gates must be satisfied before completion.

#### Capability

Describes host support for agent spawn/resume, browser control, browser engines,
containers, worktrees, external providers, and other execution facilities.

### Event shape

Every event includes:

```json
{
  "schemaVersion": "1.0",
  "runId": "run-...",
  "sequence": 14,
  "nodeId": "chunk-02.validate",
  "eventType": "transition",
  "actor": "workflow-kernel",
  "provider": null,
  "priorState": "VERIFYING",
  "newState": "RETRYABLE",
  "reasonCode": "TEST_FAILED",
  "failureSignature": "sha256:...",
  "evidence": ["evidence/chunk-02-test.txt"],
  "coverageGaps": [],
  "timestamp": "2026-07-14T00:00:00Z"
}
```

Events use monotonic sequence numbers. State reconstruction rejects gaps,
duplicates, illegal transitions, and conflicting run IDs.

## State machine

The minimum node states are:

```text
PENDING -> READY -> RUNNING -> VERIFYING -> SUCCEEDED
                        |          |
                        v          v
                      FAILED <- RETRYABLE
                        |
                        v
                      BLOCKED
```

`REQUIRES_HUMAN`, `FALLBACK_REQUIRED`, `CANCELLED`, and `CLEANING_UP` are
explicit states or decisions as appropriate. Every active run can enter
`CLEANING_UP`. A run cannot become `COMPLETED` until required final gates and
cleanup have succeeded.

Retries are reason-specific and bounded. Repeating the same input, provider,
and failure signature does not cause another blind retry; it triggers fallback,
human escalation, or a terminal blocked state.

## Rollout modes

### Shadow

- Existing Markdown orchestration is authoritative.
- The kernel consumes manifests and observed actions.
- It records predicted transitions and parity gaps.
- It cannot block or alter the run.

### Enforce

- The existing orchestrator still performs actions.
- The kernel rejects illegal transitions, missing evidence, and unsafe cleanup.
- A rejected transition blocks the run with an actionable reason.

### Native

- The kernel selects ready nodes and required transitions.
- Host adapters perform agent, command, browser, Git, and Docker actions.
- Markdown remains the policy and expertise source.
- Native mode remains opt-in until a separately approved default-promotion
  decision.

Promotion between modes is explicit. Metrics may recommend promotion but never
perform it automatically.

## Workflow classes

Every run has one top-level `workflowClass`:

### Chore

Build, deterministic validation, quick review, and human ship gate.

### Bug

Reproduce, diagnose, approve diagnosis, fix, regression validation, independent
review, and human ship gate.

### Feature

The current full pipeline: assess, research, plan, prompt generation,
adversarial review, chunk execution, final review, and delivery.

### Hotfix

Parallel read-only diagnoses, human solution approval, one controlled
implementation, targeted regression checks, required sensitive review when
applicable, and a human deploy gate. The fastest unverified result never wins.

### Security

Restricted context and providers, diagnosis, remediation, full sensitive-path
review, verification evidence, and human approval.

### Investigation

Gather evidence, synthesize, and present a human decision. Mutation is disabled
by default.

### Migration

Preflight and backup evidence, implementation, forward verification, rollback
verification, review, and human release gate.

Classification is explicit when supplied. Deterministic rules classify clear
cases. Ambiguous cases require human selection instead of silently spending an
agent call.

## Builder session continuity

When deterministic validation fails after an agent implementation:

1. Record the exact validation evidence and a normalized failure signature.
2. If the host supports resume, send the evidence to the original builder
   session.
3. Re-run deterministic validation.
4. Use a fresh independent evaluator for review.

If the host cannot resume, dispatch a new builder with a structured handoff and
record `session_resume_unavailable` as a coverage gap. A new builder must not be
reported as the original session.

## Risk-aware gates

Gate placement depends on workflow class without weakening existing guarantees:

- Creative feature work retains assessment, research, plan, prompt, and final
  approval gates.
- Chores may use an approved input plus final review gate.
- Bugs require agreement on reproduction or expected behavior before mutation.
- Hotfixes require solution and deployment approval.
- Security, federation, secrets, and other sensitive paths retain full review
  and provider restrictions.

Required gates cannot silently become advisory due to unavailable tooling.

## Isolation abstraction

Supported isolation modes are:

```text
remote sandbox -> container -> worktree -> sequential branch
```

The order expresses isolation strength, not universal availability. Nodes
declare a preferred and minimum mode. The kernel selects the strongest available
permitted mode and records any degradation. A node blocks if no acceptable mode
exists.

The current root-mounted Docker detection remains valid: when verification would
target the wrong checkout, `sequential-branch` is truthful and preferred over a
fake worktree claim.

## Git and Docker resource ownership

Resources are registered immediately after creation. The event ledger is the
ownership source; cleanup does not reconstruct ownership only from naming
conventions.

### Git

The existing cleanup contract remains authoritative:

- Prune stale worktree registrations.
- Delete only owned branches with merge proof.
- Preserve the feature branch without merge proof.
- Leave foreign refs alone and report exact follow-up commands.
- Record repository residue honestly.

### Docker

Every owned container, network, and volume receives labels:

```text
com.designmachines.depot.managed=true
com.designmachines.depot.run-id=<run-id>
com.designmachines.depot.node-id=<node-id>
com.designmachines.depot.created-at=<timestamp>
```

The kernel:

- Inventories Docker resources before execution.
- Registers every created resource.
- Removes current-run resources during node or terminal cleanup.
- Automatically removes Depot-managed resources older than 24 hours.
- Allows a configurable TTL for long-running workflows.
- Never removes unlabelled or foreign-namespace resources.
- Never runs broad commands such as `docker system prune`.
- Records successful, failed, and blocked removals.

Current-run cleanup failure is a cleanup failure. Inaccessible stale resources
are reported residue, not falsely claimed as removed.

## UX personas and browser verification

Assessment discovers project-local UX suites, personas, roles, auth-switching
field names, routes, scenarios, browsers, and viewports. Secret values are never
copied into pipeline artifacts.

The manifest and run state carry a `verificationProfile` containing:

- Suite location and invocation.
- Available and required personas.
- Auth-switching mechanism by field name only.
- Routes and scenarios.
- Required browsers and viewports.
- Setup and teardown commands.
- Blocking or advisory status.

If a project declares a UX/persona suite, its required personas are blocking for
UI and integration work. A project with no declared suite may continue with an
explicit coverage gap.

Persona evidence includes scenario, role, route, browser, viewport, result,
screenshot or trace, runtime assertions, and failure details. Running only the
default logged-in persona never satisfies a multi-persona requirement.

## Browser recovery policy

Once browser verification is required, it cannot be silently skipped.

The recovery ladder is:

1. Attempt the configured primary testing browser.
2. Capture the error and current state.
3. Close the page/context and quit the testing browser.
4. Restart the browser and retry once.
5. Verify the dev server, target URL, and auth fixture independently.
6. Start a different configured browser engine and retry.
7. If verification still cannot run, enter `REQUIRES_HUMAN` with exact evidence
   and requested assistance.

Application failures remain product findings. Switching browsers must not hide
an application failure by misclassifying it as tooling trouble.

Browser nodes may be skipped only when the feature is backend-only or the
project has no UI surface and no browser node was required.

This policy applies consistently to assessment, persona tests, visual review,
and final caller verification.

## Failure classes

- `RETRYABLE`: transient failure with remaining reason-specific budget.
- `FALLBACK_REQUIRED`: current provider or isolation rail is unavailable.
- `REVIEW_INCOMPLETE`: required evaluator coverage could not be completed.
- `BLOCKED`: safe continuation requires a human or unavailable capability.
- `FATAL`: invalid schema, corrupt state, unsafe transition, or cleanup invariant
  failure.

Failures always carry normalized reason codes, evidence, attempted recovery, and
remaining coverage gaps.

## Testing strategy

### Unit tests

Cover schema validation, legal transitions, dependency readiness, retry budgets,
convergence signatures, workflow classification, gate resolution, redaction,
atomic writes, and event reconstruction.

### Scenario tests

Use fake host, provider, Git, Docker, clock, browser, persona, and agent adapters
to execute complete workflows deterministically.

### Failure injection

At minimum, force:

- Empty or dead agent output.
- Provider cap and unavailable model.
- Repeated identical failure signatures.
- Partial worktree, container, network, or volume creation.
- Docker cleanup failure.
- Missing browser capability.
- Primary-browser lock, failed restart, and secondary-browser failure.
- Missing required persona or failed persona authentication.
- Truncated event log or stale materialized state.
- Core review failure after fallback.
- Process exit between resource creation and registration.
- Cleanup invocation from every terminal path.

### Compatibility and receipt replay

Representative existing pipeline and dm-review receipts are replayed through
shadow mode. Expected and observed transitions are compared for Claude, Codex,
and generic-host fixtures.

### Composition validation

Existing Markdown-anchor validators remain. The behavioral suite is added to
`validate-composition.sh --all`, so both policy drift and execution drift fail
loudly.

## Observability and calibration

Events support aggregation of:

- Duration and attempts per node.
- Provider, model, host, and isolation mode.
- Retry and fallback reasons.
- First-pass validation rate.
- Reviewer findings and unique reviewer yield.
- Human rejection or correction.
- Persona and browser coverage.
- Cleanup residue.
- Token and cost evidence when available.
- Escaped defects linked to workflow class and node.

Reports derive completion rate, time-to-clean, cost-to-clean, fallback rate,
reviewer yield, and cleanup reliability. Recommendations remain proposal-only
and require human approval before routing policy changes.

## Security and privacy

- Existing sensitive-path routing overrides all workflow-class routing.
- Events and verification profiles store redacted references, not secrets.
- Auth fixture field names may be recorded; values may not.
- Third-party providers never receive prohibited files or content.
- Docker and Git cleanup operate only on resources with verified ownership.
- Event files are treated as untrusted input during replay and validation.

## Delivery slices

### Slice 1: Kernel foundation

Schemas, event ledger, atomic state, transitions, workflow templates, CLI, fake
adapters, and shadow mode.

### Slice 2: Pipeline integration

Manifest translation, workflow classes, risk-aware gates, builder continuity,
isolation selection, Docker lifecycle, and browser recovery.

### Slice 3: dm-review and UX integration

Review lanes, fallbacks, convergence, findings, coverage gaps, persona suites,
browser evidence, and cleanup receipts.

### Slice 4: Hardening and promotion

Failure injection, receipt replay, host fixtures, metrics aggregation,
documentation, generated-shim validation, and enforce/native promotion gates.

Each slice must preserve a runnable baseline and pass composition validation.

## Promotion criteria

Shadow-to-enforce promotion requires:

- Zero unexplained parity gaps across representative pipeline and dm-review
  receipts.
- Every illegal-transition and terminal-cleanup scenario passing.
- Claude, Codex, and generic-host fixtures passing.
- Required persona and browser recovery scenarios passing.
- No weakening of provider security boundaries.

Enforce-to-native availability requires:

- All shadow-to-enforce criteria.
- Successful real shadow runs across supported hosts.
- State reconstruction after injected interruption.
- Builder resume and non-resume fallback evidence.
- Git and Docker cleanup evidence on success, failure, and blocking paths.

Making native mode the default is a separate human-approved decision.

## Acceptance criteria

1. Existing pipeline and dm-review invocations remain compatible.
2. Shadow mode observes real runs without altering outcomes.
3. `run-state.json` can be reconstructed from `events.jsonl`.
4. Enforce/native modes reject illegal or evidence-free transitions.
5. Builder validation failures resume the original session when supported.
6. Workflow classes expand into documented, testable templates.
7. Isolation degradation is explicit and policy-bounded.
8. Current-run Git and Docker resources are cleaned on every terminal path.
9. Depot-managed Docker resources older than 24 hours are swept safely.
10. Declared UX personas block incomplete UI/integration verification.
11. Browser failures restart the primary browser, try a secondary engine, then
    stop for human assistance.
12. Failure-injection tests cover every fallback and terminal path.
13. Claude, Codex, and generic-host compatibility fixtures pass.
14. Reliability recommendations remain proposal-only.
15. Full composition validation and final dm-review are clean.

## Approved decisions

- Additive adapter-first kernel.
- Python standard library only.
- Compatibility shadow mode before enforcement.
- Repo-local CLI, not a daemon.
- No external ticket intake in this epic.
- Automatic 24-hour cleanup of labeled stale Docker resources.
- Blocking declared UX personas for UI/integration work.
- Browser restart, alternate-browser retry, then human escalation.

## Open questions

None. Assessment and research may refine implementation details without
reopening the approved architectural decisions above.
