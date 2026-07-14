# Chunk: Shadow Workflow Adapters

## Context

This is Chunk 05 of the AI Developer Workflow Kernel and depends on Chunks 01,
02, 03, and 04. The kernel can now model state, workflow policy, host
capabilities, owned resources, persona coverage, and browser recovery under
tests. Pipeline and dm-review are still unaware of it. This chunk adds adapters
that observe their existing execution contracts and emit shadow events without
changing authoritative outcomes.

The bootstrap constraint is absolute: the current Markdown orchestrators,
manifest, routing policy, and receipts remain authoritative in shadow mode.
Kernel predictions may report parity gaps, but may not select ready nodes, block
a merge, alter fallback routing, invoke cleanup, or convert a review result.
The Markdown orchestrator may explicitly execute a kernel-produced cleanup plan
as its existing authoritative lifecycle action; shadow observation only records
that action and compares its receipt.

## Task

Implement pipeline and dm-review translators, receipt replay, shadow comparison,
and reliability aggregation. Integrate shadow observation into canonical
pipeline/dm-review commands and agents using stable headings. Wire the new Docker
cleanup policy to the existing Step 3j per-chunk repository cleanup boundary and
Step 5b terminal reconciliation. Wire verification profiles and browser recovery
into UI/integration and visual-review paths. Preserve Claude, Codex-native, and
generic host parity and record honest fallback/misroute evidence.

## Files to Modify

| File | Action | Notes |
|------|--------|-------|
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/pipeline_adapter.py` | Create | Manifest/progress/receipt translation |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/dm_review_adapter.py` | Create | Review-lane/finding/convergence translation |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/shadow.py` | Create | Predicted vs authoritative comparison and parity reasons |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/metrics.py` | Create | Event-derived reliability report, proposal-only recommendations |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/cli.py` | Modify | Executable observe/compare/cleanup-plan/result/reconcile commands |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/test_pipeline_adapter.py` | Create | Manifest and named-stage fixture tests |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/test_dm_review_adapter.py` | Create | Lanes, fallbacks, convergence, coverage tests |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/test_shadow_parity.py` | Create | Authoritative receipt replay across hosts |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/test_metrics.py` | Create | Aggregation and no-policy-mutation tests |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/test_runtime_cli.py` | Create | Runtime resolution, commands, side-effect authority, exit codes |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/fixtures/receipts/pipeline-claude.json` | Create | Sanitized representative fixture |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/fixtures/receipts/pipeline-codex.json` | Create | Sanitized Codex-native fixture |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/fixtures/receipts/dm-review.json` | Create | Sanitized full-review fixture |
| `plugins/pipeline/commands/pipeline.md` | Modify | Phase and checkpoint shadow hooks |
| `plugins/pipeline/commands/pipeline-run.md` | Modify | Preflight and Codex-native shadow runtime |
| `plugins/pipeline/skills/promptcraft/SKILL.md` | Modify | Emit explicit workflow class into generated manifests |
| `plugins/pipeline/skills/promptcraft/references/manifest-schema.md` | Modify | Backward-compatible `workflowClass` field and default |
| `plugins/pipeline/agents/workflow/execution-orchestrator.md` | Modify | Stable-stage hooks, Step 3j Docker cleanup, Step 5b reconciliation |
| `plugins/pipeline/references/artifact-lifecycle.md` | Modify | Run-state/events/shadow report lifecycle |
| `plugins/pipeline/references/run-postmortem-schema.md` | Modify | Kernel reliability fields and proposal-only decisions |
| `plugins/dm-review/commands/dm-review.md` | Modify | Full-review shadow lifecycle |
| `plugins/dm-review/commands/dm-review-loop.md` | Modify | Convergence and cleanup shadow lifecycle |
| `plugins/dm-review/commands/dm-review-visual.md` | Modify | Shared browser/profile evidence |
| `plugins/dm-review/skills/review/SKILL.md` | Modify | Inline review protocol and coverage receipt integration |

## Files to Read (for context)

| File | Why |
|------|-----|
| `plugins/pipeline/references/routing-policy.json` | Existing executor/security decisions remain authoritative |
| `plugins/pipeline/references/harness-profile.json` | Host capability names and roles |
| `plugins/pipeline/agents/workflow/execution-orchestrator.md` | Named transition map and exact receipt anchors |
| `plugins/pipeline/skills/pipeline-run/SKILL.md` | Generated alias for context only; do not edit |
| `plugins/dm-review/commands/dm-review-loop.md` | Existing convergence signature and cleanup sequence |
| `plugins/dm-review/agents/review/visual-browser-tester.md` | Shared recovery contract consumer from Chunk 04 |
| `plugins/dm-review/skills/review/references/repo-cleanup-contract.md` | Git/Docker sibling lifecycle from Chunk 03 |
| `plugins/workflow-kernel/skills/workflow-kernel/references/verification-contract.md` | Required persona/browser behavior |
| `plugins/workflow-kernel/skills/workflow-kernel/references/docker-ownership.md` | Required cleanup timing and labels |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/adapters/base.py` | Closed builder outcomes, provenance-bound handles/results, validation feedback, observation helper |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/adapters/host.py` | Capability/rail enforcement, resume/replacement manager, protected restore boundary |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/adapters/__init__.py` | Public continuity contract and trusted-store exclusions |

## Required Interfaces

```python
def translate_manifest(
    manifest: Mapping[str, object],
    profile: HostCapabilities,
) -> RunSpec: ...

def translate_pipeline_receipts(
    receipts: Iterable[Mapping[str, object]],
) -> tuple[WorkflowEvent, ...]: ...

def translate_review(
    request: ReviewRequest,
    profile: HostCapabilities,
) -> RunSpec: ...

def translate_review_receipts(
    receipts: Iterable[Mapping[str, object]],
) -> tuple[WorkflowEvent, ...]: ...

class ShadowComparator:
    def compare(
        self,
        predicted: RunState,
        authoritative: ReceiptSet,
    ) -> ParityReport: ...

class MetricsAggregator:
    def aggregate(
        self,
        events: Iterable[WorkflowEvent],
    ) -> ReliabilityReport: ...
```

Extend `python3 -m workflow_kernel` with these stable commands (never use
`python -c` from Markdown):

```text
observe-pipeline --manifest PATH --receipts PATH --state-dir PATH
observe-review --request PATH --receipts PATH --state-dir PATH
compare --state-dir PATH --authoritative-receipts PATH --output PATH
plan-create --state-dir PATH --run-id ID --node-id ID --lifecycle SCOPE --cleanup-policy POLICY --argv-json PATH --output PATH
plan-compose --state-dir PATH --run-id ID --node-id ID --lifecycle SCOPE --cleanup-policy POLICY --argv-json PATH --output PATH
record-create --state-dir PATH --plan PATH --result PATH --before-inventory PATH --after-inventory PATH
plan-cleanup --state-dir PATH --run-id ID [--node-id ID] --output PATH
record-cleanup --state-dir PATH --plan PATH --results PATH
plan-reconcile --state-dir PATH --run-id ID --ttl-hours 24 --output PATH
metrics --events PATH --output PATH
```

Observation, comparison, and metrics commands are side-effect free. Planning
commands output exact argv plus proof/reason data but never execute them.
`record-create` reconciles every single- or multi-resource registration intent
against command results and before/after inventory. `record-cleanup` only consumes
orchestrator-produced command results. Use stable
exit codes: `0` success, `2` invalid input/schema, `3` unsafe/blocked plan, `4`
runtime unavailable/incompatible, `5` parity gap, and `6` write/state conflict.

`ParityReport` must distinguish `match`, `explained_host_difference`,
`missing_authoritative_evidence`, `unexpected_authoritative_transition`,
`kernel_prediction_gap`, and `unsafe_to_promote`. A raw text difference is not
automatically a semantic gap; normalize known host mechanism labels while
preserving required transition/evidence semantics.

## Pipeline Translation Map

Use stable heading/symbol anchors, not line numbers:

- `## Progress Ledger` → planned/phase/gate events.
- `## Step 0: Validate Manifest` → validated run spec or fatal schema event.
- `## Step 2: Execute by Level` → dependency-ready and dispatch events.
- `### 3e: Validate Subagent Output` → deterministic validation evidence.
- `### 3g: Run Evaluation Gate` and `EVAL_GATE_PASSED` → evaluation evidence.
- `### 3h: Visual Verification Protocol` and `BROWSER_VERIFIED` → verification
  attempts and coverage evidence.
- `### 3i: Merge Back` → merge disposition.
- `### 3j: Clean Up Worktree` → per-chunk Git and Docker cleanup.
- `## Step 4b: Requirements Cross-Check` → requirement evidence.
- `## Step 5b: Artifact and Repository Cleanup` → terminal reconciliation.
- `## Step 6: Summary Report` → terminal run summary.

Do not replace these anchors. Add compact adapter calls/receipt obligations next
to them and keep Markdown legible when the kernel is unavailable.

## Workflow Class Propagation

Add backward-compatible top-level manifest field `workflowClass` with enum
`chore|bug|feature|hotfix|security|investigation|migration`. Promptcraft must
emit it explicitly for new manifests. Legacy manifests default to `feature`
with `workflow_class_defaulted=true`; there is no content heuristic. Pipeline
and pipeline-run validate and pass it unchanged into `translate_manifest`,
`RunSpec`, events, receipts, and metrics. Security retains its existing provider
and approval overrides regardless of host. Chunk 02's separately versioned
trusted-policy safety anchor remains authoritative; Chunk 05 must not recreate
stage constants from `workflow-classes.json`. Tests cover all seven classes, the
legacy default, invalid values, full hotfix and migration stage/ancestry/
`executor_overridable` protection, rejection of unanchored executable work in
anchored classes and promotion, rejection of any executable node in the base
investigation graph independently of promotion, and security override
preservation.

## Builder Continuity Integration

Chunk 05 consumes the Chunk 02 adapter contract; it does not redesign or bypass
it. Choose one concrete agentic `HostRoute` declared by `HostCapabilities.routes`
and pass its provider, executor capability, and rail in `ResumeStateContext` to
builder dispatch. Aggregate `HostCapabilities.capabilities` is derived evidence,
not authorization: callers declare only non-route resume/isolation features,
while executor and dispatch entries derive exclusively from routes. Wrapper
routes are analysis/text-only and cannot run builder
nodes. Treat the module-owned weak identity seals over route, node, nested gate,
capability, context, handle, result, feedback, blob, and decision primitives or
digests as part of this boundary. Live identities may be registered only once,
so direct initialization re-entry cannot reseal changed state; guarded weakref
cleanup alone permits stale identity-slot reuse. Caller-added seal fields have no authority:
coherent route rewrites, coordinated security-node rewrites, and nested
gate/route mutation must fail before authorization or dispatch. Capture the
validated `SessionHandle` returned by builder dispatch
together with its immutable run/node/attempt and exact route provenance. On
deterministic validation failure, construct secret-safe
`ValidationFeedback` for the same node and call the manager's resume-or-replace
path. Preserve the closed outcome: resumed original session, replacement
dispatch, resume unavailable, gate/capability block, or adapter failure.
Ordinary caller-data exceptions from scalar/enum conversion, membership,
equality, hashing, iteration, or mapping access at reconstruction and projection
boundaries must map to stable secret-safe failures; do not intercept
`BaseException`. Consume only sealed snapshots that captured their public fields
and nested primitives once, validated the seal derived from that capture, and
reconstructed without rereading the caller object. Enum inputs accept only the
exact enum type or exact `str`; equality truth coercion belongs inside the same
safe boundary as the equality operation. Builder decisions capture outcome,
context, handle, and result before any nested snapshot, and retry-ledger
accessors normalize their public key before taking one sealed snapshot. Policy
maps consumed by adapters are exact module-owned tuple-subclass mappings whose
pair payload has no rewritable slot or instance dictionary, with content-derived
seals; caller mapping proxies and custom mappings are rejected without traversal.
Policy structure processing shares one exact-type taxonomy, rejects cycles, and
uses Chunk 01's depth `16` and aggregate item limit `10000`. Safety-anchor
projection charges the graph once before wrapping projected stage sets, ordered
fields reject sets and frozensets, and only canonical forbidden downgrades accept
a frozenset whose exact tuples are projected without re-entering them. Economics
mode accepts only the exact string `proposal_only`.

Protected restore is a control-plane operation. Store `ResumeStateBlob` bytes
only in permission-restricted package-owned storage with explicit retention and
deletion. Restore requires exact run/node/attempt/provider/rail/capability
context before any adapter call, plus an exact integer blob schema version whose
value is included with context and handle payload in the corruption checksum.
Never place blob bytes in ordinary artifacts,
shadow reports, events, receipts, Airlift payloads, or checkpoints; those paths
may carry only the safe digest projection and authoritative receipt reference.

Translation must require an authoritative dispatch/resume receipt reference.
Every `BuilderSessionDecision`, including blocked outcomes, owns the validated
request context; any handle/result must match it. Its event projection rejects
a different run or node and snapshots the decision before reading context.
`BuilderSessionDecision.to_evidence_event` is
observation-only: it records
builder observations but cannot stand in for that receipt. When a validated
`SessionResult` exists, merge its already-normalized evidence references with
the observation references, deduplicate without reordering, and keep the
authoritative receipt reference explicit. Tests must cover handle capture,
feedback validation and mutation snapshots, protected trusted restore,
resume/replacement translation, same-host wrong-rail rejection, and the rule
that no translated success exists without an authoritative receipt.

## dm-review Translation Map

- Review request and mode → run spec and required lanes.
- Agent dispatch/fallback → node attempt and host/provider evidence.
- Findings → normalized finding/evidence events, never dropped by fallback.
- Coverage matrix → expected/completed/failed/degraded/unavailable lanes.
- `prior_findings_signature` → convergence signature.
- Fix/re-review loop → reason-specific attempts.
- Browser/persona results → exact verification cases and recovery attempts.
- Repository cleanup → Git/Docker dispositions and final inventory.
- CLEAN/N findings → authoritative review terminal receipt.

## Shadow Runtime Rules

1. Resolve the workflow-kernel plugin from the realpath of the currently
   executing canonical Depot pipeline/dm-review plugin root, then Claude and
   Codex cache roots following the repository's dual-cache pattern. An in-repo
   runtime is eligible only beneath that same canonical Depot repository
   realpath. Never scan target-project cwd or `PATH`; reject symlink escapes.
   Verify manifest name and compatible version before invoking its CLI.
2. If the dependency is absent in shadow mode, preserve current behavior and
   emit an honest local “shadow unavailable” note; never fail the workflow.
3. Create run state under the existing feature/session artifact directory, not
   user home and not a global daemon directory.
4. Append the kernel observation after the authoritative action/receipt exists.
   Do not let prediction, comparison, or metrics authorize any action.
5. On adapter failure, preserve the authoritative result and record a parity
   gap with safe error evidence.
6. At phase/chunk boundaries, materialize state and allow Airlift to capture it
   through existing checkpoint behavior.
7. At run end, compare semantic transitions/evidence and write a shadow report.

## Per-Chunk Docker Integration

At Step 3j, after validation, review, evidence, and merge disposition:

1. Read registered resources for the chunk.
2. Run Git cleanup using the existing decision table.
3. Invoke `plan-cleanup`; treat its exact argv/proof output as a proposal, not an
   authorization from shadow state.
4. The Markdown orchestrator, as authoritative lifecycle owner, rechecks the
   plan's labels/registry/scope/dependencies and explicitly executes only its
   exact argv. Eligible running `stop-remove` containers are stopped with the
   bounded exact-argv policy before removal.
5. Invoke `record-cleanup` with those command results so the observer records
   dispositions. Preserve run-shared resources required by incomplete dependents.
6. A cleanup failure marks cleanup failed/blocked and cannot be written as clean.

At Step 5b, invoke `plan-reconcile` after artifact cleanup. The Markdown
orchestrator rechecks and explicitly executes the exact safe reconciliation and
stale-sweep argv, then records results. Include complete Docker before/after
inventory beside Git inventory. Never invoke broad prune. Comparator, metrics,
and observation code can never call a command runner or cleanup CLI.

Before any Depot-initiated Docker/Compose creation, the orchestrator must use
`plan-create` or `plan-compose` and execute only the returned label-instrumented
argv/Compose override. It then calls `record-create` with the command result and
before/after inventory so every created container, network, and volume is
registered, including partial multi-resource Compose creation. If
instrumentation cannot cover the command, record it `unmanaged` and do not
promise automatic cleanup.

## Verification Integration

- Assessment-produced verification profiles flow into UI/integration nodes.
- A project with no declaration records `not_declared`; a declared incomplete
  matrix blocks required verification.
- Initial browser failure enters the Chunk 04 recovery machine.
- Process/engine-session quit, fresh primary relaunch identity, and secondary-
  engine attempts each receive evidence; context-only recreation is insufficient.
- Curl can annotate reachability but cannot satisfy `BROWSER_VERIFIED`.
- Exhausted recovery creates blocked + human-help evidence; it never becomes
  skipped or an empty finding set.

## Host and Provider Parity

- Preserve `executionMode` values including Claude/full CLI, `codex_native`, and
  other currently documented modes through a versioned enum/compatibility map.
- Claude, Codex, and generic fixtures may dispatch differently but must require
  equivalent validation, review, persona/browser evidence, cleanup, and gates.
- Keep existing sensitive-path routing. Shadow payloads sent to any adapter must
  already be redacted and must never expand third-party provider access.
- When a requested executor is unavailable, record requested, attempted,
  implemented-by, fallback path, and reason. Never silently relabel the result.

## Reliability Aggregation

Derive, without mutating policy:

- duration and attempts per node;
- provider, model, host, workflow class, and isolation mode;
- retry/fallback reasons and convergence signatures;
- first-pass deterministic validation rate;
- findings per reviewer and unique reviewer yield;
- persona/browser expected, passed, recovered, and missing cases;
- cleanup removed, retained, blocked, and foreign counts;
- token/cost evidence when receipts supply it;
- completion rate, time-to-clean, cost-to-clean, fallback rate, and cleanup
  reliability.

Any routing change is a proposal with evidence and requires human approval.

## Companion Skills

- `plugin-dev:command-development` — canonical command edits and generated aliases.
- `plugin-dev:agent-development` — execution/review agent contract changes.
- `developer-essentials:error-handling-patterns` — adapter boundary failures.
- `dm-review:review` — inline review protocol and coverage semantics.
- `superpowers:test-driven-development` — receipt fixtures before integration.

## Implementation Sequence

1. Sanitize representative current receipts into deterministic fixtures. Do not
   copy secrets, production paths, or credentials.
2. Write failing manifest and pipeline receipt translation tests.
3. Write failing dm-review lane/finding/convergence translation tests.
4. Write failing cross-host parity tests and named explained-difference cases.
5. Write failing reliability aggregation and no-policy-mutation tests.
6. Write failing builder-continuity translation tests for receipt-bound handle
   capture, validation feedback, protected restore, resume/replacement outcomes,
   authoritative receipt requirements, and safe evidence merging.
7. Implement translators and shadow comparison as pure code.
8. Implement metrics from events only.
9. Extend the runtime CLI and add trust-anchored source/dual-cache compatible resolution to
   canonical commands with stable commands and exit codes.
10. Add `workflowClass` schema/emission/translation and named-stage shadow hooks.
11. Add create-time Docker instrumentation plus authoritative Step 3j cleanup
    and Step 5b reconciliation planning/execution/result receipts.
12. Add verification profile and recovery obligations to pipeline/dm-review.
13. Update artifact lifecycle and postmortem schemas.
14. Run kernel tests and all current workflow/Codex/cascade validators.

## Acceptance Criteria

- [ ] Manifest translation treats top-level `chunks` as authoritative,
      recomputes execution levels, and reports disagreement with cached
      `executionPlan` before dispatch.
- [ ] `workflowClass` is emitted by promptcraft and survives manifest validation,
      pipeline/pipeline-run, translation, RunSpec, events, receipts, and metrics;
      tests cover all seven values, legacy defaulting, invalid input, and security
      overrides.
- [ ] Every named pipeline stage above maps to a versioned event without
      replacing or reordering the authoritative Markdown action.
- [ ] dm-review translation preserves requested lanes, dispatch attempts,
      fallback reasons, findings, convergence signatures, coverage gaps, and
      terminal result.
- [ ] Shadow prediction/comparison/metrics never selects ready nodes, blocks
      merge, changes a gate/routing, invokes cleanup, or converts review outcome.
      Tests identify the Markdown orchestrator as cleanup decision authority.
- [ ] Missing/unavailable kernel runtime in shadow mode preserves current
      behavior and records an honest unavailable note.
- [ ] Adapter errors preserve authoritative outcomes and produce safe parity-gap
      evidence rather than aborting or silently disappearing.
- [ ] Claude, Codex-native, and generic-host fixtures have equivalent required
      validation, review, requirements, cleanup, persona/browser, and gate
      transitions.
- [ ] Known mechanism differences are normalized only through named compatibility
      rules; unexplained missing evidence is `unsafe_to_promote`.
- [ ] Every shadow event references its authoritative receipt/artifact and stores
      redacted data only.
- [ ] Builder continuity captures provenance-bound handles, validates and
      snapshots feedback, restores only from protected trusted storage, and
      translates every resume/replacement closed outcome without fabricating an
      authoritative receipt.
- [ ] Resume blobs have explicit retention/deletion and are excluded from
      ordinary artifacts, shadow reports, events, receipts, Airlift payloads,
      and checkpoints. Observation evidence safely merges normalized
      `SessionResult` evidence only beside an authoritative receipt reference.
- [ ] Canonical Markdown invokes documented runtime CLI commands, never
      `python -c`; canonical-root/Claude-cache/Codex-cache resolution validates
      realpath containment, no symlink escape, plugin name/version, and ignores
      a forged runtime under the target project. Safe non-zero failures preserve
      Markdown execution.
- [ ] Every supported Docker/Compose creation is label-instrumented before
      execution through `plan-create`/`plan-compose` and immediately registered
      through `record-create`; unsupported creation is `unmanaged` and retained.
      Exact-argv tests cover partial multi-resource Compose paths.
- [ ] Step 3j's authoritative orchestrator obtains, rechecks, and executes a
      chunk-scoped Docker cleanup plan after validation, review, evidence, and
      merge disposition, beside existing Git cleanup; shadow records results.
- [ ] Step 3j stops positively owned `stop-remove` chunk containers with a
      bounded timeout only after the last dependent, then removes them. Step 5b
      applies the same rule to run-scoped containers. Stop timeout/failure and
      post-stop removal failure remain distinct blocked dispositions.
- [ ] Step 3j retains explicit run-shared resources for incomplete dependents and
      records the dependent node IDs.
- [ ] Step 5b's authoritative orchestrator obtains, rechecks, and executes
      terminal reconciliation/labeled stale-sweep plans and reproduces Docker
      before/after/disposition inventory in the final receipt.
- [ ] Cleanup errors cannot be written as `clean`; every blocked resource has a
      reason and actionable follow-up.
- [ ] Declared persona cases flow into UI/integration verification and any missing
      required case blocks authoritative browser verification according to the
      existing gate.
- [ ] Browser failure records initial evidence, primary relaunch attempt,
      secondary engine attempt, and human-help terminal state when exhausted.
- [ ] Primary recovery proves a fresh process/engine-session identity. An
      unavailable restart records `primary_restart_unavailable`, tries the
      alternate engine, and then stops for human help if coverage remains absent.
- [ ] Curl/reachability fallback cannot emit `BROWSER_VERIFIED`.
- [ ] Requested executor, implemented provider, fallback path, and reason appear
      in every chunk/review receipt with honest misroute detection.
- [ ] Sensitive-path and content-redaction routing is unchanged and shadow mode
      does not send new repository content to third-party providers.
- [ ] Metrics calculate duration, attempts, validation rate, fallback rate,
      reviewer yield, persona/browser coverage, cleanup reliability, and
      token/cost when available.
- [ ] Metrics never modify routing or workflow policy; recommendations are
      explicitly proposal-only with a human-approval requirement.
- [ ] Run state/events/shadow reports have documented lifecycle tiers and survive
      failed runs for diagnosis.
- [ ] Canonical command edits remain source-of-truth; generated command-skill
      aliases are intentionally deferred to Chunk 06.
- [ ] Full checks pass:

```bash
PYTHONPATH=plugins/workflow-kernel/skills/workflow-kernel/references \
python3 -m unittest discover \
  -s plugins/workflow-kernel/skills/workflow-kernel/references/tests \
  -p 'test_*.py' -v
./tools/validate-workflow-contracts.sh
./tools/validate-codex-native-pipeline.sh
./tools/validate-openrouter-cascade.sh
./tools/validate-routing-economics.sh
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
- Shadow mode is observation-only. Do not enable enforce or native behavior.
- Do not change provider routing, sensitive-path rules, or review severity.
- Do not hand-edit generated Codex manifests or command-skill aliases; Chunk 06
  regenerates them from canonical sources.
- Chunk 06 owns package-level `SKILL.md` and final documentation synchronization;
  this chunk implements only the adapter integration contract above.
- Preserve existing Markdown headings used by validators; add stable subheadings
  rather than relying on line numbers.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.
- Do not create or modify `*_templ.go` files. Run `docker compose exec app templ generate` to regenerate them after editing `.templ` source files.
- When adding database migrations, verify the next sequence number: `ls migrations/*.sql | sort | tail -1`. Use the next consecutive number.
- When this chunk touches `auth/`, `admin/`, `account/`, `install/`, `member/`, or `module`-level permission paths in Assembly code, the final acceptance criterion must include an Auth Boundary Map receipt covering: surfaces mapped, middleware gates, Authorizer action/resource pairs, default-deny UI capabilities, stale-session/operator/install edge cases, test coverage, and residual risk. Omit the receipt only when no auth surface is affected.

## Research Context

The current execution orchestrator is a 1,589-line interpreted state machine,
but its named stages and receipts are proven compatibility anchors. dm-review has
mature lane accounting and convergence behavior, but no shared run model.
Historical Codex work established that host mechanisms may differ only if all
gates, cleanup, review, memory, and receipts remain equivalent. Shadow receipt
replay is the bootstrap gate because this workflow is changing its own control
plane.
