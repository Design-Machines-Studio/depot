# Chunk: Kernel State Engine

## Context

This is Chunk 01 of the AI Developer Workflow Kernel. Depot currently expresses
pipeline and dm-review control flow in large Markdown contracts, but it lacks a
single executable run model that can reconstruct state, reject illegal
transitions, and survive interruption. This chunk creates the neutral leaf
plugin and the durable standard-library foundation; it does not integrate with
pipeline or dm-review yet.

The new plugin is deliberately neutral. Pipeline already depends on dm-review,
so placing the shared runtime inside pipeline would create a dependency cycle if
dm-review consumed it. Later chunks will make both plugins depend on this leaf.

## Task

Create the `workflow-kernel` plugin and implement its versioned schema, event
ledger, atomically materialized state, transition reducer, evidence receipts,
redaction helpers, and repo-local CLI. Use only the Python standard library.
Default every new run to shadow mode. Treat event files as untrusted input.

## Files to Modify

| File | Action | Notes |
|------|--------|-------|
| `plugins/workflow-kernel/.claude-plugin/plugin.json` | Create | Canonical v0.1.0 leaf-plugin manifest; do not create the Codex manifest in this chunk |
| `plugins/workflow-kernel/skills/workflow-kernel/SKILL.md` | Create | Internal/shared skill entrypoint and runtime resolution contract |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/__init__.py` | Create | Public exports and schema version |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/__main__.py` | Create | `python -m workflow_kernel` entrypoint |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/cli.py` | Create | `init`, `validate`, `append`, `replay`, `status` commands |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/schema.py` | Create | Enums, immutable dataclasses, validation, normalized errors |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/events.py` | Create | JSONL encoding, sequence checks, append and replay |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/state.py` | Create | Run lease, revision check, atomic materialized state |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/transitions.py` | Create | Pure legal-transition reducer and reconstruction |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/receipts.py` | Create | Deterministic evidence and transition receipt encoding |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/redaction.py` | Create | Recursive secret-safe serialization helpers |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/__init__.py` | Create | Test package marker |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/test_schema.py` | Create | Strict schema and normalized-error tests |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/test_events.py` | Create | Sequence, JSONL, truncation, replay tests |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/test_state.py` | Create | Atomic write, lease, and revision tests |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/test_transitions.py` | Create | Legal and illegal transition matrix |
| `plugins/workflow-kernel/skills/workflow-kernel/references/tests/test_cli.py` | Create | CLI exit status and filesystem behavior |

## Files to Read (for context)

| File | Why |
|------|-----|
| `docs/superpowers/specs/2026-07-14-ai-developer-workflow-kernel-design.md` | Approved run model, modes, error taxonomy, and acceptance criteria |
| `plugins/pipeline/agents/workflow/execution-orchestrator.md` | Existing named transitions and receipt anchors; do not edit |
| `plugins/pipeline/skills/promptcraft/references/manifest-schema.md` | Existing chunk/run vocabulary to preserve |
| `plugins/pipeline/references/campaign-state-schema.md` | Existing atomic-state convention and its limitations |
| `plugins/pipeline/references/run-postmortem-schema.md` | Existing deterministic receipt/economics vocabulary |
| `plugins/airlift/skills/airlift/references/airlift-engine.sh` | Local crash-safe handoff precedent if present; read only |
| `tools/generate-codex-manifests.py` | Repository Python standard-library style and deterministic file-generation precedent; read only |
| `plugins/openrouter/skills/openrouter-delegate/references/openrouter-wrapper.sh` | Existing dual-cache/runtime-wrapper and stable-exit behavior precedent; read only |

## Required Interfaces

Implement these names exactly so later chunks can import them:

```python
class RunMode(str, Enum):
    SHADOW = "shadow"
    ENFORCE = "enforce"
    NATIVE = "native"

class RunStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    WAITING = "waiting"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"

class NodeStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"

@dataclass(frozen=True)
class WorkflowEvent:
    schema_version: int
    sequence: int
    run_id: str
    node_id: str | None
    kind: str
    occurred_at: str
    payload: Mapping[str, object]

class EventStore:
    def append(self, event: WorkflowEvent, expected_sequence: int) -> None: ...
    def replay(self) -> tuple[WorkflowEvent, ...]: ...

class StateStore:
    def load(self) -> RunState: ...
    def write(self, state: RunState, expected_revision: int) -> None: ...

class TransitionEngine:
    def apply(self, state: RunState, event: WorkflowEvent) -> RunState: ...
    def reconstruct(self, events: Iterable[WorkflowEvent]) -> RunState: ...
```

Define a `KernelError` base with stable `code`, `message`, and safe `details`.
At minimum provide reason codes for invalid schema, corrupt event, sequence
conflict, revision conflict, lease conflict, illegal transition, missing
evidence, and unsafe payload.

`interrupted` is a first-class terminal status, not an alias for failed,
cancelled, or blocked. Replaying an interruption event must reconstruct the same
terminal status deterministically so later cleanup can run exactly once while
preserving why execution stopped.

## Patterns to Follow

- Claude plugin JSON is canonical. Follow the required manifest fields in
  existing leaf plugins, but do not hand-write `.codex-plugin/plugin.json`.
- Use immutable dataclasses and pure reducers. Filesystem code belongs in stores;
  transition legality belongs in `transitions.py`.
- Serialize JSON with stable key ordering, UTF-8, a trailing newline, and no
  Python-specific object encoding.
- Create state temporary files in the destination directory. Write, flush,
  `os.fsync`, close, then `os.replace`. Best-effort fsync the parent directory on
  Unix; a platform that cannot sync the directory must return an evidence note,
  not pretend the call ran.
- Atomic replacement is not a writer lock. Acquire a run-scoped lease and require
  `expected_revision` on state writes.
- A truncated final JSONL record may be reported and ignored only in `validate`
  or recovery mode. Corruption in any earlier record is fatal.
- Redaction is recursive and key-based. Values for token, key, secret, password,
  authorization, cookie, DSN, and environment-value fields must never appear in
  error details or receipts.

## Companion Skills

Load these skills before implementation:

- `plugin-dev:plugin-structure` — canonical plugin layout and manifest rules.
- `plugin-dev:skill-development` — correct `SKILL.md` structure and references.
- `developer-essentials:error-handling-patterns` — normalized error boundaries.
- `superpowers:test-driven-development` — tests before implementation.

## Implementation Sequence

1. Write strict schema and transition tests first.
2. Run them and confirm they fail because the new modules do not exist.
3. Implement schema types and normalized errors.
4. Implement deterministic event encoding and replay.
5. Implement the lease, revision guard, and atomic state write.
6. Implement the pure transition reducer and event reconstruction.
7. Implement receipts and recursive redaction.
8. Implement CLI parsing with `argparse`; every command returns a meaningful
   non-zero exit code on invalid input.
9. Run focused tests after each module, then the complete chunk suite.

## Acceptance Criteria

- [ ] The canonical workflow-kernel plugin manifest is valid JSON and declares a
      leaf plugin with no dependency on pipeline or dm-review.
- [ ] `SKILL.md` has valid frontmatter whose `name` matches the skill directory.
- [ ] The package imports with Python 3 using no third-party modules.
- [ ] An import/dependency scan proves the runtime uses only the Python standard
      library and introduces no daemon, database, service, or package installer.
- [ ] New runs default to `RunMode.SHADOW`; enforce/native must be explicit.
- [ ] Strict parsing rejects unknown major schema versions, unknown enum values,
      missing required fields, boolean-as-integer sequences, and negative
      revisions.
- [ ] Event append rejects duplicate or gapped sequences without modifying the
      existing ledger.
- [ ] Replay reconstructs the same `RunState` byte-for-byte across repeated runs.
- [ ] A corrupt non-final JSONL record is fatal; a truncated final record is
      reported with its byte offset and never silently treated as valid.
- [ ] Materialized state uses a same-directory temporary file, flush + fsync +
      replace, and leaves the prior valid file readable if failure occurs before
      replacement.
- [ ] A stale `expected_revision` and a second live writer lease both fail with
      stable reason codes and preserve state.
- [ ] Every terminal run status is reachable only through a legal event and
      terminal states reject further mutation events other than evidence or
      cleanup reconciliation allowed by the schema.
- [ ] Recursive redaction tests prove secret-looking fixture values do not appear
      in JSON, exceptions, CLI stderr, or receipts.
- [ ] `python -m workflow_kernel --help` lists `init`, `validate`, `append`,
      `replay`, and `status`.
- [ ] CLI invalid input exits non-zero and emits machine-readable safe errors;
      successful `replay` reconstructs `run-state.json` from `events.jsonl`.
- [ ] Test fixtures use temporary directories and fake clocks; they never write
      into the repository or user home.
- [ ] The full command below passes:

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
- Follow existing patterns; do not add a build system, package installer, daemon,
  database, or third-party Python dependency.
- Do not integrate pipeline or dm-review in this chunk.
- Do not create or edit generated Codex manifests.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.
- Do not create or modify `*_templ.go` files. Run `docker compose exec app templ generate` to regenerate them after editing `.templ` source files.
- When adding database migrations, verify the next sequence number: `ls migrations/*.sql | sort | tail -1`. Use the next consecutive number.
- When this chunk touches `auth/`, `admin/`, `account/`, `install/`, `member/`, or `module`-level permission paths in Assembly code, the final acceptance criterion must include an Auth Boundary Map receipt covering: surfaces mapped, middleware gates, Authorizer action/resource pairs, default-deny UI capabilities, stale-session/operator/install edge cases, test coverage, and residual risk. Omit the receipt only when no auth surface is affected.

## Research Context

The existing pipeline manifest, routing policy, receipts, Airlift checkpoints,
and Git cleanup contract are proven primitives. The missing capability is a
versioned append-only event model that reconstructs the run. Python documents
`os.replace` as atomic on success when source and destination are on the same
filesystem, but that does not prevent concurrent writers; this is why the lease
and revision checks are separate acceptance criteria.
