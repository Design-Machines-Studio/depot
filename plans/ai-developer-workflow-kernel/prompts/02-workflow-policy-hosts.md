# Chunk: Workflow Policy and Host Capabilities

## Context

This is Chunk 02 of the AI Developer Workflow Kernel and depends on Chunk 01.
The state engine exists, but it does not yet know which nodes a workflow class
requires, why a retry is allowed, which human gates apply, what isolation a host
can provide, or whether an original builder session can resume. This chunk adds
those deterministic policy decisions without dispatching real work.

Existing routing and security policies remain authoritative inputs. The kernel
must explain policy decisions and degradation; it must not silently invent a
host capability or change provider routing.

## Task

Implement workflow templates for chore, bug, feature, hotfix, security,
investigation, and migration runs. Add reason-specific retry/convergence rules,
risk-aware gates, host capability contracts, isolation selection, and durable
builder session handles. Provide fake adapters and complete deterministic tests.

## Files to Modify

| File | Action | Notes |
|------|--------|-------|
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/policies.py` | Create | Retry, convergence, risk, gate, and degradation decisions |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/workflows.py` | Create | Seven workflow templates and dependency expansion |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/adapters/__init__.py` | Create | Adapter exports |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/adapters/base.py` | Create | Protocols and fake-safe result types |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/adapters/host.py` | Create | Host capabilities, dispatch, resume, evidence |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/adapters/isolation.py` | Create | Isolation requirements, ordered selection, degradation |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow-policy-schema.json` | Create | Policy document schema |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow-policy.json` | Create | Default retry, gate, and isolation policy |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow-classes-schema.json` | Create | Workflow template schema |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow-classes.json` | Create | Seven class templates |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/test_workflow_classes.py` | Create | Template expansion matrix |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/test_retry_policy.py` | Create | Reason budgets and convergence signatures |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/test_host_capabilities.py` | Create | Claude, Codex, generic, and degraded host fixtures |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/test_isolation.py` | Create | Sandbox/container/worktree/branch selection |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/test_builder_resume.py` | Create | Resume and explicit non-resume behavior |

## Files to Read (for context)

| File | Why |
|------|-----|
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/schema.py` | Reuse Chunk 01 types and errors; do not rename them |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/transitions.py` | Emit only legal event transitions |
| `plugins/pipeline/references/routing-policy.json` | Provider/security source of truth |
| `plugins/pipeline/references/harness-profile.json` | Existing host and role capability vocabulary |
| `plugins/pipeline/agents/workflow/execution-orchestrator.md` | Existing retry, failure, gate, and isolation behavior; read only |
| `plugins/pipeline/skills/promptcraft/references/manifest-schema.md` | Chunk dependencies and executor fields |
| `plugins/dm-review/commands/dm-review-loop.md` | Bounded attempts and prior-findings signature precedent |

## Required Interfaces

Implement these names exactly:

```python
class WorkflowClass(str, Enum):
    CHORE = "chore"
    BUG = "bug"
    FEATURE = "feature"
    HOTFIX = "hotfix"
    SECURITY = "security"
    INVESTIGATION = "investigation"
    MIGRATION = "migration"

class IsolationMode(str, Enum):
    REMOTE_SANDBOX = "remote_sandbox"
    CONTAINER = "container"
    WORKTREE = "worktree"
    SEQUENTIAL_BRANCH = "sequential_branch"

class WorkflowTemplates:
    def expand(
        self,
        kind: WorkflowClass,
        context: WorkflowContext,
    ) -> tuple[NodeSpec, ...]: ...

class RetryPolicy:
    def decide(
        self,
        reason: FailureReason,
        attempts: AttemptLedger,
        signature: str | None,
    ) -> RetryDecision: ...

class HostAdapter(Protocol):
    def capabilities(self) -> HostCapabilities: ...
    def dispatch(self, node: NodeSpec) -> SessionHandle | None: ...
    def resume(
        self,
        handle: SessionHandle,
        feedback: ValidationFeedback,
    ) -> SessionResult: ...

class IsolationSelector:
    def select(
        self,
        requirements: IsolationRequirements,
        capabilities: HostCapabilities,
    ) -> IsolationDecision: ...
```

`SessionHandle` must carry a host name, opaque handle value, creation time, and
resume capability. It must serialize safely without assuming the value is a PID
or provider ID. Never fabricate a handle when dispatch returns none.

## Workflow Template Minimums

- Chore: assess → build → deterministic validation → review → cleanup.
- Bug: reproduce → build/fix → regression validation → review → cleanup.
- Feature: assess → research/plan evidence → build → validation → review →
  requirements evidence → cleanup.
- Hotfix: reproduce/impact → build → focused validation → mandatory risk gate →
  review → cleanup.
- Security: threat/risk evidence → security-routed build → validation → security
  review → human gate → cleanup. Sensitive-path routing always wins.
- Investigation: hypothesis → evidence gathering → conclusion/next-action gate →
  cleanup; no implementation node unless explicitly promoted.
- Migration: preflight → schema/data change → compatibility validation → rollback
  evidence → review → human gate → cleanup.

## Patterns to Follow

- Load policy from versioned JSON and validate before expansion. Do not hide
  policy in Python constants beyond enum and default schema versions.
- Retry budgets are keyed by normalized reason: provider unavailable,
  deterministic validation failure, reviewer finding, browser recovery,
  cleanup, and infrastructure. A global “try three times” rule is forbidden.
- Repeated identical failure signatures converge to blocked before exhausting
  unrelated budgets.
- Sensitive-path routing from `routing-policy.json` overrides class, economics,
  and requested executor.
- Gate resolution is deterministic: workflow class + risk + evidence state →
  gate decision. Human approval cannot repair missing mandatory evidence.
- Isolation selection uses only declared host capabilities. Degradation records
  from/to modes and a reason. If policy forbids a downgrade, return blocked.
- Builder resume feeds deterministic validation feedback to the original handle.
  A fresh builder is not a resume and must be labeled as replacement dispatch.
- Reliability and cost fields are observations only. This chunk must not mutate
  routing policy based on historical performance.

## Companion Skills

- `developer-essentials:error-handling-patterns` — normalized policy errors.
- `developer-essentials:e2e-testing-patterns` — scenario fixture design.
- `superpowers:test-driven-development` — table tests before implementation.
- `plugin-dev:skill-development` — shared reference documentation conventions.

## Implementation Sequence

1. Add failing table tests for all workflow classes and compare exact node IDs,
   dependencies, gate kinds, and cleanup nodes.
2. Add failing retry tests for each normalized reason and repeated signatures.
3. Add failing capability/isolation tests for all four modes and forbidden
   degradation.
4. Add failing session tests for resumable, non-resumable, stale, foreign-host,
   and invalid handles.
5. Define JSON schemas and defaults; validate them before any policy decision.
6. Implement templates as data-driven expansion with stable node IDs.
7. Implement retry/convergence and risk gates as pure decisions.
8. Implement host protocols, fake adapters, isolation selection, and resume.
9. Run the full kernel suite, not only new tests.

## Acceptance Criteria

- [ ] All seven workflow classes parse from JSON and expand to stable,
      dependency-valid node graphs with a cleanup node.
- [ ] Investigation does not gain an implementation node unless context
      explicitly requests promotion and the appropriate gate is satisfied.
- [ ] Security and sensitive-path rules override workflow class, requested
      provider, and economics without exposing prohibited path content.
- [ ] Retry decisions use separate budgets for provider, validation, review,
      browser, cleanup, and infrastructure reasons.
- [ ] A repeated identical failure signature reaches a convergence stop and
      records the prior signature and attempt count.
- [ ] Risk-aware gates preserve mandatory security, migration, hotfix, evidence,
      and human-approval boundaries; missing evidence cannot be approved away.
- [ ] Claude, Codex, and generic host fixtures expose only capabilities they can
      actually perform and produce the same required transition/evidence model.
- [ ] Isolation selection covers remote sandbox, container, worktree, and
      sequential branch, in policy order, with a reason for every downgrade.
- [ ] A policy-forbidden isolation downgrade returns blocked rather than silently
      choosing sequential-on-branch.
- [ ] A real resumable builder handle is stored and receives deterministic
      validation feedback on resume.
- [ ] A missing/non-resumable/stale/foreign handle emits
      `session_resume_unavailable`; it never claims the replacement builder is the
      original session.
- [ ] Session handle serialization is opaque and redacted; no token or provider
      credential can enter events or receipts.
- [ ] Economics aggregation fields remain proposal-only and no test observes a
      policy file mutation.
- [ ] Invalid policy versions, circular template dependencies, missing node IDs,
      or unknown capability names fail closed with stable reason codes.
- [ ] Full kernel tests pass using:

```bash
PYTHONPATH=plugins/workflow-kernel/skills/workflow-kernel/references \
python3 -m unittest discover \
  -s plugins/workflow-kernel/skills/workflow-kernel/references/tests \
  -p 'test_*.py' -v
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
- Do not dispatch a real agent, run Docker, create a worktree, or modify provider
  routing in this chunk; use fake adapters.
- Keep policy and workflow templates in versioned JSON; keep repeatable mechanics
  in Python.
- Do not edit Chunk 01 public names. Additive exports are allowed only when tests
  require them.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.
- Do not create or modify `*_templ.go` files. Run `docker compose exec app templ generate` to regenerate them after editing `.templ` source files.
- When adding database migrations, verify the next sequence number: `ls migrations/*.sql | sort | tail -1`. Use the next consecutive number.
- When this chunk touches `auth/`, `admin/`, `account/`, `install/`, `member/`, or `module`-level permission paths in Assembly code, the final acceptance criterion must include an Auth Boundary Map receipt covering: surfaces mapped, middleware gates, Authorizer action/resource pairs, default-deny UI capabilities, stale-session/operator/install edge cases, test coverage, and residual risk. Omit the receipt only when no auth surface is affected.

## Research Context

The existing dm-review loop has bounded attempts and a prior-findings signature,
but pipeline retries remain distributed across prose. Builder validation failure
currently fails the chunk and skips dependents; no durable original-session
handle exists. Codex compatibility already proved that host-specific mechanisms
must preserve the same gates, cleanup, review, and receipt semantics rather than
approximate the Claude path.
