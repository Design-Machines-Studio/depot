# Chunk: Read-Only Review and Incremental Findings

## Context

This is Chunk 04 of Depot Mechanical Workflow Hardening. PR #12 established
stable finding identities, source provenance, disagreement preservation,
coverage gaps, and contribution receipts, but findings are still consolidated
from completed Markdown outputs. The public review workflow also contradicts its
read-only promise by simplifying code, committing changes, and creating tracking
artifacts or GitHub issues.

Chunks 01 and 03 provide exact evidence/build bindings and shared browser bundle
references. This chunk makes individual findings crash-survivable and moves all
product/provider mutation behind explicitly approved fix/loop workflows.

## Task

Add immutable content-addressed review finding/lane records that are referenced
immediately through Workflow Kernel's existing crash-safe `EventStore`. Generate
human Markdown/todo-compatible views from structured authority. Redefine review
as read-only for product files, Git index/history, PR/issue state, and repository
tracking artifacts while allowing declared immutable review evidence under its
owned artifact root.

## Files to Modify

| File | Action | Notes |
|------|--------|-------|
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/review_records.py` | Create | Immutable finding/lane records, canonical IDs, projection inputs |
| `plugins/workflow-kernel/skills/workflow-kernel/references/review-finding-record-schema.json` | Create | Strict version-1 finding record |
| `plugins/workflow-kernel/skills/workflow-kernel/references/review-lane-record-schema.json` | Create | Strict version-1 lane completion/coverage record |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/dm_review_adapter.py` | Modify | Accept record references and explicit finding/lane stages |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/_translation.py` | Modify | Add only required bounded receipt fields/aliases |
| `tests/test_review_findings.py` | Create | Partial survival, replay, identity, projection, boundary tests |
| `tests/test_dm_review_adapter.py` | Modify | Structured record reference translation/parity |
| `plugins/dm-review/skills/review/SKILL.md` | Modify | Remove simplification/tracking mutations; define evidence-only writes |
| `plugins/dm-review/commands/dm-review.md` | Modify | Public read-only promise and structured-output contract |
| `plugins/dm-review/commands/dm-review-fix.md` | Modify | Explicit owner of approved code mutations |
| `plugins/dm-review/commands/dm-review-loop.md` | Modify | Explicit owner of iterative mutation and tracking disposition |
| `plugins/dm-review/agents/workflow/review-consolidator.md` | Modify | Project Markdown and dispositions from structured records |

Do not modify generated command-skill aliases, plugin manifests/versions,
marketplace files, Pipeline orchestration, issue-tracking reference semantics,
Kernel CLI registration, or release inventories. Chunks 05, 07, and 08 own them.

## Files to Read (for context)

| File | Why |
|------|-----|
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/events.py` | Existing crash-safe EventStore and sequence/lease authority |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/schema.py` | Workflow event safety and immutable snapshot style |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/evidence_binding.py` | Exact binding from Chunk 01 |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/browser_bundle.py` | Shared browser evidence reference from Chunk 03 |
| `plugins/dm-review/skills/review/SKILL.md` | Existing phases, review lanes, simplification, issue tracking, cleanup |
| `plugins/dm-review/skills/review/references/output-format.md` | Finding fields, severity, evidence, stable identity |
| `plugins/dm-review/skills/review/references/issue-tracking.md` | Todo/GitHub projection compatibility; do not edit here |
| `plugins/dm-review/agents/workflow/review-consolidator.md` | Existing canonical/source IDs and disagreement synthesis |
| `tests/test_events.py` | EventStore concurrency/crash/sequence tests |

## Patterns to Follow

- Reuse EventStore append/replay and run leases; do not create a second JSONL
  lock file, independent sequence counter, or final-only collection authority.
- Write the immutable finding/lane document safely first, then append a bounded
  content-addressed reference through the authoritative event stream.
- Preserve current source finding ID, canonical finding ID, source agents,
  provider/model/attempt provenance, raw evidence references, severity,
  disagreement, disposition, and decision reason codes.
- Preserve unknown/missing lanes as explicit coverage gaps. A dead lane does not
  erase findings already persisted and does not become a clean result.
- Keep Markdown, inline report text, todo files, and issue bodies as projections.
  Generated views may be replaced; structured records and event references may not.

Define review's mechanical read-only boundary as:

- no product/source/config edits;
- no Git index mutation, commit, branch, stash, reset, or history rewrite;
- no PR/issue/comment/label/draft-state mutation;
- no `todos/` or repository tracking artifact creation;
- no cleanup of resources the review does not exactly own;
- allowed writes only to a declared review artifact root for immutable evidence,
  structured records, screenshots/traces, and generated reports.

Move the current active simplification pass into `dm-review-fix` and/or the
mutation phase of `dm-review-loop`. Move issue/todo creation behind the same
explicit approval boundary. Plain review can recommend and project candidate
tracking rows but cannot create them.

The repository-state boundary check should capture relevant before/after source,
index, HEAD, refs, and provider mutation receipts. Evidence-root additions are
classified separately and do not hide product-state changes.

## Companion Skills

Load `dm-review:review` for the current review orchestration vocabulary. Treat
the source files in this branch as authoritative if installed cache differs.

## Acceptance Criteria

- [ ] Finding and lane schemas are strict, bounded, versioned, secret-safe, and content-addressed with deterministic canonical IDs.
- [ ] A completed finding is persisted and referenced immediately; later lane crash, timeout, cap, or malformed output cannot erase it.
- [ ] EventStore remains the sole append/sequence/lease authority; no second mutable JSONL ledger or lock protocol is introduced.
- [ ] Duplicate source records are idempotent, conflicting reuse of an identity fails closed, and canonical merges preserve every source reference.
- [ ] Finding records preserve source/canonical IDs, severity, category, file/anchor, evidence refs, source agents, provider routing, attempt, agreement, disposition, and decision reason.
- [ ] Lane records preserve requested/completed/failed/degraded/unavailable state, expected coverage, missing case IDs, partial output, browser bundle refs, and exact build binding.
- [ ] Markdown review output and todo-compatible data are deterministic generated views; editing a view cannot mutate structured authority.
- [ ] `dm-review` and `review` make no product/source/config edits, Git index/history/ref changes, PR/issue mutations, or repository todo/tracking writes.
- [ ] Review may write only declared immutable evidence/records/reports under its owned artifact root, with classification and exact cleanup ownership.
- [ ] Automatic simplification edits/commits move to `dm-review-fix` or `dm-review-loop` and require their existing explicit mutation approval.
- [ ] Todo/GitHub issue creation moves to approved fix/loop disposition; plain review emits proposal rows and preserves zero-deferral reporting without mutation.
- [ ] A before/after boundary test detects product, index, HEAD, ref, todo, and provider mutations while allowing declared artifact-root evidence.
- [ ] Existing stable IDs, raw evidence, disagreement, contribution metrics, severity semantics, final report format, and zero-deferral compatibility remain intact.
- [ ] Focused verification passes with `PYTHONPATH=plugins/workflow-kernel/skills/workflow-kernel/references /opt/homebrew/bin/python3.12 -m unittest tests.test_review_findings tests.test_dm_review_adapter tests.test_events`.
- [ ] A prose-contract test or equivalent deterministic validator proves plain review contains no edit/stage/commit/issue-creation phase while fix/loop retain explicit mutation ownership.
- [ ] Generated aliases and manifests are not hand-edited in this chunk.
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
- Keep Workflow Kernel standard-library-only and reuse EventStore authority.
- Do not create issues, comments, labels, todos, commits, branches, or product edits while exercising the plain review path.
- Do not weaken zero-deferral, severity, evidence, browser, provider, or cleanup contracts.
- Do not turn review-generated Markdown into a second editable authority.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.
- Do not create or modify `*_templ.go` files. Run `docker compose exec app templ generate` to regenerate them after editing `.templ` source files.
- When adding database migrations, verify the next sequence number: `ls migrations/*.sql | sort | tail -1`. Use the next consecutive number.
- When this chunk touches `auth/`, `admin/`, `account/`, `install/`, `member/`, or `module`-level permission paths in Assembly code, the final acceptance criterion must include an Auth Boundary Map receipt covering: surfaces mapped, middleware gates, Authorizer action/resource pairs, default-deny UI capabilities, stale-session/operator/install edge cases, test coverage, and residual risk. Omit the receipt only when no auth surface is affected.

## Research Context

The existing consolidator already defines stable canonical/source IDs,
corroboration, unique findings, disagreement, raw references, and contribution
dispositions. The gap is timing and authority: findings become durable only after
lane completion and Markdown remains primary. The existing review skill's active
simplification and issue-tracking phases are the concrete read-only contradiction
this chunk must remove without deleting mutation capability from approved flows.

