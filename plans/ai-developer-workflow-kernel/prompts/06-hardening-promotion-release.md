# Chunk: Hardening, Promotion, and Release

## Context

This is Chunk 06, the final implementation chunk of the AI Developer Workflow
Kernel, and depends on Chunk 05. The neutral runtime and shadow adapters now
exist, but they are not yet a supported Depot release: failure scenarios are not
exhaustive, full composition does not enforce the behavioral suite, plugin
dependencies and generated Codex surfaces are not synchronized, and operators
do not have a complete runbook.

This chunk hardens the system and ships shadow mode. It implements promotion
evaluation but does not promote the repository to enforce/native authority.
Shadow remains the default. Making native the default is explicitly outside this
epic and requires a separate human-approved decision after successful real runs.

## Task

Add deterministic failure-injection scenarios and a behavioral validator. Wire
the validator into full composition checks. Complete documentation, plugin
dependencies, versions, marketplace metadata, description evals, and generated
Codex manifests/command-skill aliases. Prove that promotion gates fail closed
when evidence is missing, that the Markdown path remains usable, and that all
current repository validators remain clean.

## Files to Modify

### Behavioral validation and tests

| File | Action | Notes |
|------|--------|-------|
| `tools/validate-workflow-kernel.py` | Create | Executable behavioral/composition validator |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/promotion.py` | Create | Pure importable promotion evaluator and reasoned decisions |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/test_failure_scenarios.py` | Create | Complete failure-injection matrix |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/test_promotion.py` | Create | Shadow/enforce/native evidence gates |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/test_compatibility.py` | Create | Claude/Codex/generic receipt parity and fallback |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/fixtures/scenarios/terminal-paths.json` | Create | Success/failure/blocked/cancelled/interrupted scenarios |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/fixtures/scenarios/provider-failures.json` | Create | Cap/unavailable/empty-output/repeat-signature scenarios |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/fixtures/scenarios/verification-failures.json` | Create | Browser/persona recovery exhaustion scenarios |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/fixtures/scenarios/resource-failures.json` | Create | Partial create/register/remove/reconcile scenarios |
| `tools/validate-composition.sh` | Modify | Run unit and behavioral kernel checks in `--all` |
| `tools/validate-workflow-contracts.sh` | Modify | Stable kernel integration and cleanup anchors |
| `tools/check-dependencies.sh` | Modify | Validate new leaf dependencies and no cycles |

### Documentation and evaluation

| File | Action | Notes |
|------|--------|-------|
| `docs/workflow-kernel.md` | Create | Operator/developer architecture and runbook |
| `tools/README.md` | Modify | Document validator and CLI entrypoints |
| `description-evals/workflow-kernel-workflow-kernel.json` | Create | Positive/negative skill trigger cases |
| `CLAUDE.md` | Modify | Plugin count/table and workflow-kernel architecture notes; preserve Airlift marker |
| `AGENTS.md` | Modify | Codex-facing plugin count/table and adapter notes |

### Canonical release metadata

| File | Action | Notes |
|------|--------|-------|
| `plugins/workflow-kernel/.claude-plugin/plugin.json` | Modify | Finalize v0.1.0 capability metadata |
| `plugins/pipeline/.claude-plugin/plugin.json` | Modify | Bump 1.26.0 → 1.27.0 and depend on workflow-kernel >=0.1.0 |
| `plugins/dm-review/.claude-plugin/plugin.json` | Modify | Bump 1.41.0 → 1.42.0 and depend on workflow-kernel >=0.1.0 |
| `.claude-plugin/marketplace.json` | Modify | Add workflow-kernel 0.1.0 and synchronize pipeline/dm-review versions |

### Generated outputs

These files are changed only by the repository generators after canonical edits:

| File | Action | Notes |
|------|--------|-------|
| `.agents/plugins/marketplace.json` | Generate | Never hand-edit |
| `plugins/workflow-kernel/.codex-plugin/plugin.json` | Generate | Never hand-edit |
| `plugins/pipeline/.codex-plugin/plugin.json` | Generate | Never hand-edit |
| `plugins/dm-review/.codex-plugin/plugin.json` | Generate | Never hand-edit |
| `plugins/pipeline/skills/pipeline/SKILL.md` | Generate | From `commands/pipeline.md` |
| `plugins/pipeline/skills/pipeline-run/SKILL.md` | Generate | From `commands/pipeline-run.md` |
| `plugins/dm-review/skills/dm-review/SKILL.md` | Generate | From `commands/dm-review.md` |
| `plugins/dm-review/skills/dm-review-loop/SKILL.md` | Generate | From `commands/dm-review-loop.md` |
| `plugins/dm-review/skills/dm-review-visual/SKILL.md` | Generate | From `commands/dm-review-visual.md` |

If a generator legitimately changes another generated manifest/alias because its
output is repository-wide, include that generated diff and explain it. Do not
manually edit generated content to reduce the diff.

## Files to Read (for context)

| File | Why |
|------|-----|
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/` | All implemented public APIs and shadow adapters |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow-policy.json` | Default mode and promotion evidence names |
| `tools/generate-codex-manifests.py` | Canonical-to-Codex generation contract |
| `tools/generate-codex-command-skills.py` | Canonical-command alias generation contract |
| `tools/validate-composition.sh` | Existing `--all` composition structure |
| `tools/validate-dual-compat.sh` | Cache fallback and generated parity expectations |
| `tools/validate-codex-native-pipeline.sh` | Codex host parity checks |
| `tools/validate-openrouter-cascade.sh` | Best existing executable validator precedent |
| `.claude-plugin/marketplace.json` | Canonical plugin entry shape and ordering |
| `docs/html-artifacts.md` | Pipeline artifact and data-island lifecycle docs |

## Promotion Contract

Implement a pure promotion evaluator with these states:

```text
shadow
  -> enforce_available only when:
     zero unexplained representative receipt gaps
     every illegal transition and terminal cleanup scenario passes
     Claude, Codex, and generic host fixtures pass
     persona completeness and browser recovery scenarios pass
     provider security boundaries are unchanged

enforce_available
  -> native_available only when:
     every shadow-to-enforce criterion remains true
     successful real shadow-run evidence exists for supported hosts
     injected interruption reconstructs state
     builder resume and non-resume evidence exists
     Git and Docker success/failure/blocking cleanup evidence exists

native_available
  -> native_default is forbidden in this epic
```

The release may expose CLI validation for all modes, but default configuration
must remain `shadow`. No test fixture can masquerade as successful real-run
evidence.

The evaluator lives in `workflow_kernel/promotion.py`, is importable without the
validator, and returns a deterministic decision containing target state,
allowed/blocked, stable reason codes, and exact missing evidence. Export it from
the package only if that is consistent with the Chunk 01 public API. The
validator consumes this evaluator; it must not contain a second implementation.

## Failure-Injection Matrix

Every scenario must assert final state, emitted reason codes, retained evidence,
cleanup invocation count, resource dispositions, and promotion impact.

### Agent/provider failures

- empty agent output;
- malformed agent output;
- dead/stalled session;
- provider unavailable;
- model cap/rate limit;
- requested executor misroute;
- repeated identical failure signature;
- core review failure after fallback.

### State failures

- duplicate and gapped events;
- truncated final record;
- corrupt middle record;
- stale materialized revision;
- concurrent writer lease;
- process exit before state replacement;
- unknown major schema version;
- replay of an already terminal run.

### Resource failures

- partial worktree/container/network/volume creation;
- process exit between creation and registration;
- foreign or contradictory labels;
- running/in-use resources;
- volume inspect failure;
- per-chunk removal failure;
- terminal reconciliation failure;
- cleanup called from success, failure, blocked, cancelled, and interrupted paths;
- second cleanup/replay idempotency.

### Verification failures

- no declared personas;
- legacy statusless tasks with requiredness omitted;
- missing required persona;
- failed persona authentication;
- secret-bearing persona fixture;
- primary browser lock;
- failed primary close/relaunch;
- failed primary retry;
- secondary engine unavailable;
- secondary failure;
- human-help terminal state;
- curl reachability present but browser evidence absent.

### Runtime trust failures

- forged workflow-kernel under the downstream project root;
- symlink escape from an otherwise plausible source candidate;
- wrong plugin name or incompatible cache version;
- trusted canonical Depot root and both supported cache roots.

## Behavioral Validator Contract

`tools/validate-workflow-kernel.py` must:

1. locate the canonical workflow-kernel runtime in the repository;
2. validate every JSON schema and policy document;
3. run the kernel `unittest` suite with a deterministic environment;
4. replay all scenario fixtures;
5. verify state reconstruction and event ordering;
6. prove terminal cleanup coverage and exact-once reconciliation intent;
7. scan for forbidden broad/negative-label Docker cleanup commands;
8. scan scenario outputs for secret sentinel leakage;
9. compare Claude/Codex/generic required transitions and receipts;
10. validate promotion evidence and assert default shadow mode;
11. emit concise PASS/FAIL sections and exit non-zero on any gap.
12. exercise every base and integration runtime CLI command, including safe
    non-zero invalid/blocked/unavailable cases;
13. validate all seven workflow classes and both Assembly-shaped persona fixture
    layouts through their public adapters;

Use standard-library subprocess/JSON/path handling only. The script must be
executable and support `--help` plus an optional `--verbose`. It must not need
Docker, a browser, network access, API keys, or a running project.

## Composition Integration

- Add one named `validate_workflow_kernel` stage to
  `tools/validate-composition.sh` and invoke it under `--all`.
- Preserve every existing validation stage and exit behavior.
- Add stable anchor checks for the shared recovery, resource cleanup, shadow
  observation, and promotion contracts without treating text checks as a
  substitute for behavioral tests.
- Dependency validation must prove workflow-kernel is a leaf and that both
  pipeline and dm-review can depend on it without a cycle.
- Dual compatibility must verify the new Claude/Codex manifest pair and the
  dual-cache runtime resolution added in Chunk 05.

## Documentation Requirements

`docs/workflow-kernel.md` must explain:

- why the kernel is a neutral leaf plugin;
- state directory layout: `events.jsonl`, `run-state.json`, lease, receipts,
  shadow parity report, verification and cleanup evidence;
- schema/version evolution and unknown-version behavior;
- the base state CLI plus every shadow observation, comparison, cleanup-plan,
  result-recording, reconciliation, and metrics command with safe examples;
- shadow authority boundaries and how to disable shadow observation;
- workflow classes, retry reasons, gates, isolation, and builder resumption;
- Git/Docker labels, per-chunk cleanup, run-shared retention, terminal
  reconciliation, volume TTL inspection, and no-broad-prune rule;
- persona declaration discovery/redaction and required-case completeness;
- browser recovery order and human-help escalation;
- metrics and proposal-only routing recommendations;
- promotion criteria and why native default is outside scope;
- rollback to Markdown-only authority without deleting event history;
- troubleshooting corrupt state, blocked cleanup, missing browser tools, and
  unavailable runtime.

Update root documentation counts from 18 to 19 plugins and add workflow-kernel
to the plugin table. Preserve the Airlift-managed marker block in `CLAUDE.md`.

## Release Metadata

- Workflow-kernel version: `0.1.0`.
- Pipeline version: `1.27.0`.
- dm-review version: `1.42.0`.
- Both consumers add required plugin dependency
  `"workflow-kernel": ">=0.1.0"`.
- Marketplace canonical versions exactly match plugin manifests.
- New skill capability description should describe internal deterministic run
  state/replay and trigger on explicit workflow-kernel/run-recovery requests,
  not ordinary pipeline use.

## Description Eval Requirements

Add positive cases for explicit requests such as validating/replaying a workflow
run, inspecting kernel state, and diagnosing a corrupt run ledger. Add negative
cases for normal feature development, ordinary dm-review, Docker cleanup advice,
browser testing, and unrelated Python state machines. The internal skill should
not steal broad pipeline/dm-review triggers.

## Companion Skills

- `plugin-dev:plugin-structure` — new plugin dependency and manifest release.
- `plugin-dev:command-development` — generated aliases from canonical commands.
- `plugin-dev:skill-development` — skill description and trigger evaluation.
- `superpowers:verification-before-completion` — evidence before clean claims.
- `developer-essentials:error-handling-patterns` — validator and promotion errors.

## Implementation Sequence

1. Add failing failure-scenario, compatibility, and promotion tests.
2. Implement the importable `workflow_kernel/promotion.py` evaluator required by those tests without
   enabling enforce/native authority.
3. Implement `tools/validate-workflow-kernel.py`; make it executable.
4. Run it standalone and fix only kernel-owned failures.
5. Wire it into composition and workflow contract checks.
6. Write operator/developer documentation and tools README entries.
7. Add description evals and verify trigger precision.
8. Update canonical plugin manifests and marketplace versions/dependencies.
9. Run the Codex manifest generator.
10. Run the Codex command-skill generator.
11. Run both generators in `--check` mode.
12. Run dependency, dual-compat, description, workflow, cascade, routing, and
    full composition validations.
13. Inspect the final diff for generated-only changes, secret sentinels, stale
    versions, forbidden commands, and unintentional instruction changes.

## Acceptance Criteria

- [ ] Failure fixtures cover every agent/provider, state, resource, and
      verification scenario listed above with deterministic fake adapters.
- [ ] Every terminal scenario asserts cleanup/reconciliation invocation and a
      complete disposition receipt; no terminal path silently skips cleanup.
- [ ] State interruption scenarios reconstruct exactly from valid events and
      reject corrupt/unknown input with stable safe errors.
- [ ] Secret sentinel values never appear in events, materialized state,
      exceptions, validator output, shadow reports, or receipts.
- [ ] Provider cap, unavailable executor, misroute, and repeated signatures retain
      requested/attempted/implemented/fallback evidence.
- [ ] Browser exhaustion retains all attempts and ends blocked with
      `human_help_required`; curl evidence does not satisfy the browser gate.
- [ ] Persona fixtures prove declared completeness and secret redaction; absent
      declarations remain honest `not_declared`.
- [ ] Compatibility proves legacy statusless tasks with omitted requiredness form
      a non-empty blocking set, while explicit opt-outs and future statuses stay
      non-blocking.
- [ ] Partial Git/Docker creation, registration gaps, removal errors, and
      reconciliation errors never authorize foreign or unproven deletion.
- [ ] The behavioral validator supports `--help`, runs offline with Python
      standard library only, emits named PASS/FAIL sections, and exits non-zero
      for every injected contract violation.
- [ ] The validator exercises every runtime CLI command and verifies stable safe
      non-zero failures; compatibility fixtures cover all seven workflow classes
      and both Assembly persona-discovery layouts.
- [ ] The validator detects `docker system prune`, unfiltered prune,
      negative-label prune, and shell-built cleanup commands in kernel-owned
      runtime surfaces.
- [ ] Security fixtures prove target-project runtime shadowing, symlink escape,
      wrong-name, and incompatible-version candidates are rejected while the
      canonical Depot root and supported caches resolve deterministically.
- [ ] An opt-in live-Docker smoke test creates, stops, and removes only its own
      unique fully labeled fixture resources. It is excluded from default/offline
      composition and cannot inspect or act on pre-existing resources.
- [ ] Full composition invokes the behavioral validator under `--all` and keeps
      every pre-existing validation stage.
- [ ] Dependency validation proves workflow-kernel is a leaf and the resulting
      graph has no cycle.
- [ ] Promotion remains blocked without zero-gap parity, host fixtures,
      verification scenarios, cleanup scenarios, real shadow evidence, and
      interruption evidence as appropriate to the target mode.
- [ ] The promotion evaluator is independently importable, returns deterministic
      reason/evidence-gap decisions, is the validator's single source of truth,
      and rejects `native_default`.
- [ ] Repository default remains `shadow`; no command, policy, fixture, or docs
      claim enforce/native is currently authoritative.
- [ ] Native-default transition is rejected with a stable “separate human
      approval required” reason.
- [ ] `docs/workflow-kernel.md` covers architecture, files, CLI, security,
      resources, verification, metrics, promotion, rollback, and troubleshooting.
- [ ] Root documentation lists 19 plugins and preserves the Airlift marker.
- [ ] Workflow-kernel is version 0.1.0, pipeline is 1.27.0, dm-review is 1.42.0,
      and canonical marketplace versions match.
- [ ] Pipeline and dm-review canonical manifests both require
      workflow-kernel >=0.1.0.
- [ ] Description evals trigger the internal skill narrowly and do not steal
      ordinary pipeline, review, Docker, browser, or general Python requests.
- [ ] Codex manifests and command-skill aliases are generated from canonical
      sources; no generated file was hand-edited.
- [ ] Generator `--check`, dependency, dual compatibility, workflow contracts,
      Codex-native pipeline, OpenRouter cascade, routing economics, description
      evals, and full composition all exit 0.
- [ ] Final diff contains no secret sentinel, stale version, invalid JSON,
      untracked generated output, or whitespace error.
- [ ] Release verification writes a machine-readable compatibility/promotion
      evidence summary that the final pipeline requirements cross-check can
      reference criterion by criterion.
- [ ] The execution-orchestrator can still run the Markdown-authoritative path
      when shadow observation is disabled or the kernel runtime is unavailable.

## Required Verification Commands

Run in this order and record every exit code:

```bash
PYTHONPATH=plugins/workflow-kernel/skills/workflow-kernel/references \
python3 -m unittest discover \
  -s plugins/workflow-kernel/skills/workflow-kernel/references/tests \
  -p 'test_*.py' -v

./tools/validate-workflow-kernel.py
./tools/generate-codex-command-skills.py
./tools/generate-codex-command-skills.py --check
./tools/generate-codex-manifests.py
./tools/generate-codex-manifests.py --check
./tools/check-dependencies.sh
./tools/validate-dual-compat.sh
./tools/validate-workflow-contracts.sh
./tools/validate-codex-native-pipeline.sh
./tools/validate-openrouter-cascade.sh
./tools/validate-routing-economics.sh
./tools/eval-descriptions.sh
./tools/validate-composition.sh --all
git diff --check
```

Expected: every command exits 0. If full composition fails because another
chunk left an integration gap, fix it only when the file is listed in this
prompt; otherwise return the exact failure under `NOT-COVERED:` for orchestrator
reconciliation rather than expanding scope silently.

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

- Only modify the files listed above, plus additional generated files changed by
  a repository-wide generator; explain every additional generated path.
- Ship shadow mode only. Do not enable enforce/native authority or default.
- Do not claim real shadow-run evidence from deterministic fixtures.
- Edit Claude manifests/commands first; regenerate Codex outputs afterward.
- Preserve the Airlift marker in `CLAUDE.md` and all unrelated user changes.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.
- Do not create or modify `*_templ.go` files. Run `docker compose exec app templ generate` to regenerate them after editing `.templ` source files.
- When adding database migrations, verify the next sequence number: `ls migrations/*.sql | sort | tail -1`. Use the next consecutive number.
- When this chunk touches `auth/`, `admin/`, `account/`, `install/`, `member/`, or `module`-level permission paths in Assembly code, the final acceptance criterion must include an Auth Boundary Map receipt covering: surfaces mapped, middleware gates, Authorizer action/resource pairs, default-deny UI capabilities, stale-session/operator/install edge cases, test coverage, and residual risk. Omit the receipt only when no auth surface is affected.

## Research Context

Depot's strongest executable validator is the OpenRouter cascade dry-run;
workflow validation otherwise leans heavily on Markdown anchors. Generated Codex
manifests and command aliases are intentionally derived from Claude-canonical
sources and full composition already checks drift. The kernel must add behavioral
proof beside these checks, not replace them. Real enforce/native promotion
requires evidence that cannot be created in this release chunk, so the only
honest shipped authority is shadow mode.
