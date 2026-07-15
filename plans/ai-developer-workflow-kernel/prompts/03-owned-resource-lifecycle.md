# Chunk: Owned Resource Lifecycle

## Context

This is Chunk 03 of the AI Developer Workflow Kernel and depends on Chunks 01
and 02. Depot already has an unusually strong Git cleanup contract: resources
are registered, deletion requires proof, foreign refs are left alone, and
blocked removal is reported. Docker is currently only a verification runtime;
containers, networks, and volumes created by review/testing can accumulate with
no equivalent ownership lifecycle.

This chunk generalizes the ownership model and implements typed Git/Docker
adapters under fake command runners. Chunk-owned Docker resources clean at the
existing end-of-chunk repository cleanup boundary. Explicit run-shared
resources survive through their last dependent. Terminal cleanup reconciles
anything blocked or interrupted.

## Task

Implement a durable resource registry, cleanup scopes and dispositions, a Git
adapter that preserves the current safe-to-delete table, and a Docker adapter
that labels and cleans only positively owned Depot resources. Implement
resource-type-aware TTL sweeping: containers and networks may use label + age
filters; volumes must be listed by label, inspected for creation time, checked
for use, and removed by verified ID because volume prune has no `until` filter.

## Files to Modify

| File | Action | Notes |
|------|--------|-------|
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/resources.py` | Create | Registry, scopes, dispositions, cleanup coordinator |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/adapters/git.py` | Create | Git inventory and owned-ref disposition adapter |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/adapters/docker.py` | Create | Docker inventory, labels, chunk cleanup, reconciliation, TTL sweep |
| `plugins/workflow-kernel/skills/workflow-kernel/references/resource-registry-schema.json` | Create | Versioned resource registry schema |
| `plugins/workflow-kernel/skills/workflow-kernel/references/cleanup-receipt-schema.json` | Create | Versioned disposition receipt schema |
| `plugins/workflow-kernel/skills/workflow-kernel/references/docker-ownership.md` | Create | Runtime labels, timing, safe command contract |
| `plugins/dm-review/skills/review/references/repo-cleanup-contract.md` | Modify | Add Docker sibling contract and per-chunk/terminal boundaries |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/test_resource_registry.py` | Create | Registration, replay, scope, dependency tests |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/test_git_cleanup.py` | Create | Existing decision table mapped through fake Git adapter |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/test_docker_cleanup.py` | Create | Typed cleanup and ownership boundary tests |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/test_terminal_cleanup.py` | Create | Every terminal path and interrupted reconciliation |

## Files to Read (for context)

| File | Why |
|------|-----|
| `plugins/dm-review/skills/review/references/repo-cleanup-contract.md` | Canonical Git ownership model; preserve its decision table |
| `plugins/pipeline/agents/workflow/execution-orchestrator.md` | Read Step 0e registry init, Step 3j chunk cleanup, Step 5b final cleanup; do not edit |
| `plugins/pipeline/references/artifact-lifecycle.md` | Existing cleanup receipt and lifecycle vocabulary |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/schema.py` | Reuse evidence, run, node, and normalized error types |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/policies.py` | Reuse terminal and dependency policy decisions |

## Required Ownership Labels

Every Depot-created container, network, and volume must carry:

```text
com.designmachines.depot.managed=true
com.designmachines.depot.run-id=<run-id>
com.designmachines.depot.node-id=<node-id>
com.designmachines.depot.created-at=<RFC3339 timestamp>
com.designmachines.depot.lifecycle=chunk|run
com.designmachines.depot.cleanup-policy=stop-remove|remove-when-stopped|retain
```

Names are diagnostic only. Labels must be injected before creation because
Docker resources cannot be safely relabeled after the fact. Current-run cleanup
requires registry and label agreement. A stale-orphan sweep may act without a
registry row only when every required label is present and internally
consistent, the resource is strictly older than TTL, and its run has no active
lease. Missing/incomplete labels, registry disagreement, or an active lease
always retain the resource and emit a blocked/foreign disposition.

## Required Interfaces

```python
class ResourceKind(str, Enum):
    WORKTREE = "worktree"
    BRANCH = "branch"
    CONTAINER = "container"
    NETWORK = "network"
    VOLUME = "volume"

class CleanupDisposition(str, Enum):
    REMOVED = "removed"
    RETAINED_FOR_DEPENDENCY = "retained_for_dependency"
    BLOCKED = "blocked"
    FOREIGN = "foreign"
    MISSING = "missing"

class ResourceRegistry:
    def register(self, record: ResourceRecord) -> None: ...
    def resources_for(self, scope: CleanupScope) -> tuple[ResourceRecord, ...]: ...
    def record_disposition(self, disposition: ResourceDisposition) -> None: ...

@dataclass(frozen=True)
class DockerCreationPlan:
    argv: tuple[str, ...]
    labels: Mapping[str, str]
    lifecycle: str
    registration_intents: tuple[ResourceRegistrationIntent, ...]
    compose_override: Path | None = None

class DockerAdapter:
    def inventory(self) -> tuple[DockerResource, ...]: ...
    def labels_for(self, run_id: str, node_id: str, lifecycle: str, cleanup_policy: str) -> Mapping[str, str]: ...
    def plan_create(self, argv: Sequence[str], run_id: str, node_id: str, lifecycle: str, cleanup_policy: str) -> DockerCreationPlan: ...
    def plan_compose(self, argv: Sequence[str], run_id: str, node_id: str, lifecycle: str, cleanup_policy: str) -> DockerCreationPlan: ...
    def record_creation(self, plan: DockerCreationPlan, result: CommandResult, before: DockerInventory, after: DockerInventory) -> tuple[ResourceRecord, ...]: ...
    def plan_chunk_cleanup(self, run_id: str, node_id: str) -> CleanupPlan: ...
    def plan_reconcile_run(self, run_id: str) -> CleanupPlan: ...
    def plan_stale_sweep(self, ttl: timedelta) -> CleanupPlan: ...
    def record_results(self, plan: CleanupPlan, results: Iterable[CommandResult]) -> CleanupReceipt: ...

class GitAdapter:
    def inventory(self) -> GitInventory: ...
    def cleanup_owned(self, scope: CleanupScope) -> CleanupReceipt: ...
```

All external commands go through an injected `CommandRunner` protocol that
captures argv, exit code, stdout, and stderr. Never build commands with a shell
string. Tests use a fake runner and assert exact argv.

`plan_create` must recognize supported `docker run`, `docker container create`,
`docker network create`, and `docker volume create` argv and insert every label
before the image/name/driver-specific position required by that command.
`plan_compose` must inspect Compose configuration, generate a run-scoped
override/config that labels services, the implicit default network, declared
networks, and named declared volumes, and set a collision-safe
`COMPOSE_PROJECT_NAME`. Anonymous volumes, external resources, unsupported
Compose forms, or ambiguous creation argv return `unmanaged` and fail closed;
registration after an unlabeled creation never upgrades it to owned.

A creation plan carries one registration intent per resource that the command
may create. Compose therefore has multiple intents for service containers,
implicit/declared networks, and named volumes. `record_creation` reconciles the
before/after inventory delta and command result against every intent, registers
each successful resource, and records partial or missing creations explicitly.

## Cleanup Timing

1. Inventory existing Git and Docker resources before the run.
2. Instrument every Depot-initiated Docker creation before execution. Register
   each successfully created resource immediately from the post-create result;
   record partial/unregistered residue from the inventory delta.
3. After a chunk completes validation, review, evidence, and merge disposition,
   run chunk cleanup alongside repository cleanup.
4. Remove `lifecycle=chunk` resources owned by that run/node.
5. Retain `lifecycle=run` resources while an incomplete dependent names them.
6. On succeeded, failed, blocked, cancelled, or interrupted terminal paths, run
   reconciliation and record every current-run resource disposition.
7. During a cleanup boundary, sweep fully and consistently labeled stale
   resources older than the configured TTL (default 24 hours) only when their
   run has no active lease. This orphan rule deliberately permits crash-before-
   registration residue while retaining incomplete/contradictory labels.

## Docker Type Semantics

- Containers: at a chunk boundary, a running current-run container may be
  stopped with exact argv `docker stop --time <bounded-seconds> <id>` only when
  registry and all labels agree, `lifecycle=chunk`,
  `cleanup-policy=stop-remove`, and no incomplete dependent needs it. At terminal
  reconciliation the same rule applies to `lifecycle=run`. After a successful
  stop, remove by verified ID. Never stop stale-orphan, foreign, pre-existing,
  incompletely labeled, `retain`, or still-required containers. Stop timeout,
  stop failure, and post-stop removal failure are distinct blocked dispositions.
- Networks: target unused, positively labeled custom networks. System networks
  and networks referenced by containers are never removable.
- Volumes: `volume prune` accepts labels but not `until`. List by positive label,
  inspect each candidate's ID/labels/creation timestamp/use state, compare via
  the injected clock, then call explicit volume removal for verified stale IDs.
- A failed inspect means ownership/age is unproven: record blocked and retain.
- Never invoke `docker system prune`, unfiltered prune, or negative-label prune.
- Compose services, networks, and volumes must all receive the same run/node/
  lifecycle label set through the generated override; an unlabeled Compose
  resource is `unmanaged`, never inferred owned from its project/name prefix.

## Companion Skills

- `developer-essentials:error-handling-patterns` — command and cleanup errors.
- `developer-essentials:git-advanced-workflows` — merge-proof and worktree safety.
- `superpowers:test-driven-development` — fake-runner failure scenarios first.
- `plugin-dev:skill-development` — shared ownership reference contract.

## Implementation Sequence

1. Port the Git decision-table rows into failing adapter tests before code.
2. Add failing registry tests for registration, duplicate ID, conflicting owner,
   immediate process exit, scope, dependent retention, and idempotent replay.
3. Add fake-Docker tests for raw container/network/volume creation, multi-resource Compose
   service/network/volume labeling, partial creation, TTL boundary, foreign
   labels, missing labels, active leases, in-use resources, inspect failure, and
   removal failure.
4. Implement schemas, registry, and disposition receipts.
5. Implement Git inventory/cleanup as an adapter over the existing contract.
6. Implement label-aware raw Docker and Compose creation planning, immediate
   registration, Docker inventory, and exact label verification.
7. Implement per-chunk cleanup planning and run-shared dependency retention.
8. Implement terminal reconciliation planning, typed stale sweep, and result
   recording. Planning is pure; Chunk 05's authoritative orchestrator executes.
9. Update the cleanup contract prose to make Git and Docker sibling surfaces.
10. Run the full kernel suite and workflow contract validator.

## Acceptance Criteria

- [ ] Registry writes are durable events and duplicate/conflicting ownership
      fails closed with normalized reason codes.
- [ ] Process exit between creation and registration is detectable from the
      pre/post inventory delta and produces unregistered-residue evidence; it
      authorizes stale-orphan cleanup only with the complete consistent label
      set, strict TTL age, and no active run lease.
- [ ] Every Depot-created container, network, and volume receives all required
      ownership labels, including cleanup policy, with safe values at creation time or is recorded
      `unmanaged`; post-creation registration alone is never ownership proof.
- [ ] Exact-argv fake-runner tests cover `docker run`, container create, network
      create, volume create, and Compose services/networks/volumes. The Compose
      path generates a run-scoped override plus collision-safe project name and
      reconciles multiple registration intents, including partial creation.
- [ ] Current-run cleanup requires registry and label agreement. Stale-orphan
      cleanup permits a missing registry row only for complete consistent labels,
      strict age over TTL, and no active lease; exact-boundary, incomplete,
      contradictory, and active-run cases are retained.
- [ ] Chunk cleanup runs only after validation, review, evidence, and merge
      disposition, and targets only that run/node's `lifecycle=chunk` resources.
- [ ] Run-shared resources remain while any incomplete dependent needs them and
      emit `retained_for_dependency` with dependent node IDs.
- [ ] Succeeded, failed, blocked, cancelled, and interrupted paths all invoke
      terminal reconciliation and produce a complete before/after inventory.
- [ ] Stopped containers and unused networks are selected with positive Depot
      labels and age; current-run/live resources are excluded.
- [ ] Owned running chunk containers stop with a bounded timeout after their
      last dependent, then remove; owned run containers do the same only during
      terminal reconciliation. Exact-argv tests prove foreign, pre-existing,
      active-dependent, stale-orphan, and incompletely labeled containers are
      never stopped, and stop/remove failures remain blocked.
- [ ] Volume TTL cleanup lists by positive label, inspects creation/use state,
      compares with the fake clock, and removes only explicit verified IDs.
- [ ] At exactly the 24-hour boundary, policy behavior is defined and tested;
      use “older than,” not “older than or equal,” unless the JSON policy states
      otherwise.
- [ ] Running containers, in-use networks/volumes, inspect failures, command
      failures, foreign labels, and contradictory registry entries remain and
      are reported as blocked or foreign.
- [ ] No code path constructs `docker system prune`, unfiltered prune,
      negative-label prune, wildcard removal, or shell-evaluated Docker argv.
- [ ] Cleanup planners are side-effect free and result recording cannot execute
      commands; only the authoritative host integration in Chunk 05 may invoke
      the exact validated plan.
- [ ] Git adapter tests preserve merge proof, dirty-worktree retention,
      feature-branch protection, unreadable-path caution, and blocked-removal
      reporting from the current contract.
- [ ] Re-running cleanup is idempotent: already missing resources emit `missing`
      and do not turn a successful prior receipt into failure.
- [ ] Cleanup receipts distinguish resource kind, ID, owner, lifecycle, action,
      reason, command evidence, and follow-up without exposing secrets.
- [ ] The updated Markdown cleanup contract uses stable headings and does not
      weaken any current Git rule.
- [ ] Full tests and the existing workflow validator pass:

```bash
PYTHONPATH=plugins/workflow-kernel/skills/workflow-kernel/references \
python3 -m unittest discover \
  -s plugins/workflow-kernel/skills/workflow-kernel/references/tests \
  -p 'test_*.py' -v
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
- Use fake command runners in tests; do not create or delete real Git or Docker
  resources in this chunk's unit suite.
- Never infer ownership from a resource name alone.
- Never weaken the existing Git cleanup contract.
- Do not edit the execution orchestrator yet; Chunk 05 performs integration.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.
- Do not create or modify `*_templ.go` files. Run `docker compose exec app templ generate` to regenerate them after editing `.templ` source files.
- When adding database migrations, verify the next sequence number: `ls migrations/*.sql | sort | tail -1`. Use the next consecutive number.
- When this chunk touches `auth/`, `admin/`, `account/`, `install/`, `member/`, or `module`-level permission paths in Assembly code, the final acceptance criterion must include an Auth Boundary Map receipt covering: surfaces mapped, middleware gates, Authorizer action/resource pairs, default-deny UI capabilities, stale-session/operator/install edge cases, test coverage, and residual risk. Omit the receipt only when no auth surface is affected.

## Research Context

Docker documents that container and network prune support both `label` and
`until`, while volume prune supports labels but no age filter. This makes a
single generic prune implementation unsafe. Historical Depot evidence shows
strong scoped Git/worktree ownership in practice but no Docker ownership
registry, label namespace, or selective stale sweep.
