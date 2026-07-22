# Chunk: Artifact Safety and Staging

## Context

This is Chunk 02 of Depot Mechanical Workflow Hardening. Chunk 01 provides exact
repository/evidence identity. This chunk adds neutral facts about artifact
sensitivity, retention, redaction, and staging eligibility. Pipeline integration
is deliberately deferred to Chunk 07.

## Task

Implement strict artifact classification records and an exact staging-allowlist
builder in Workflow Kernel. Lifecycle and sensitivity are independent. A path is
staging-authorized only when it is both explicitly intended and classified safe.

## Files to Modify

| File | Action | Notes |
|------|--------|-------|
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/artifacts.py` | Create | Classification, artifact record, bounded inspection, allowlist builder |
| `plugins/workflow-kernel/skills/workflow-kernel/references/artifact-classification-schema.json` | Create | Strict content/lifecycle/sensitivity/provenance schema |
| `plugins/workflow-kernel/skills/workflow-kernel/references/staging-allowlist-schema.json` | Create | Strict exact-path allowlist and rejected-path reasons |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/redaction.py` | Modify if required | Reuse safe secret-shape rules without publishing matched values |
| `tests/test_artifact_safety.py` | Create | Hostile filesystem/content/allowlist cases |

Do not modify Pipeline staging prose, CLI registration, release inventories,
plugin versions, manifests, or generated files. Chunks 07 and 08 own those.

## Files to Read (for context)

| File | Why |
|------|-----|
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/redaction.py` | Existing structured durable-value safety |
| `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/_files.py` | Bound path, symlink, identity, and owned-resource primitives |
| `plugins/pipeline/references/artifact-lifecycle.md` | Existing retention tiers that must remain recognizable |
| `plugins/pipeline/agents/workflow/execution-orchestrator.md` | Current explicit-path and broad-directory staging behavior |
| `tests/test_schema.py` | Strict schema negative-test pattern |
| `tests/test_terminal_cleanup.py` | Artifact lifecycle and cleanup expectations |

## Patterns to Follow

- Use `bind_durable_path`/owned-resource path checks instead of `resolve()` plus trust.
- Reject traversal, symlinks, hard-link surprises, device/special files, and
  identity changes between classification and allowlist generation.
- Bound file size, number of paths, path length, and inspection work.
- Store rule IDs, normalized classifications, byte count, and content digest;
  never store the matched credential or unsafe excerpt.
- Preserve explicit `unknown`/`blocked_sensitive`; unknown is never committable.
- Model at least `committable`, `private_receipt`, `ephemeral`, and
  `blocked_sensitive`, with retention/lifecycle represented separately.
- Treat test fixtures such as `.example` or deliberate secret-pattern cases
  through explicit rule provenance. Do not exempt a whole extension globally.
- Inspect bounded text, screenshot/trace/console metadata, and normalized
  filenames for real email addresses, cookie and authorization-header values,
  tokens/passwords, MFA/QR/authenticator material, private URLs, and environment
  values. When an opaque binary cannot be inspected safely, classify it
  conservatively from declared provenance/metadata instead of assuming safe.
- Fictional `.test` domains and `.example` identities are allowed only when the
  artifact carries explicit test-fixture provenance; their presence does not
  exempt adjacent cookie, token, password, authorization, MFA, QR, private-URL,
  or environment-value matches.

The allowlist input is an exact set of intended changed paths plus classified
artifact records. Its output contains only the safe intersection, sorted
canonically, with a rejection record for every intended path excluded. It must
not accept directories as implicit recursive staging authority.

## Companion Skills

No companion skill is required. Follow Workflow Kernel's filesystem, redaction,
and strict-schema patterns.

## Acceptance Criteria

- [ ] Artifact records carry schema version, exact normalized path, artifact digest, byte count, sensitivity, lifecycle, redaction state, provenance, owner, committable state, and classification rule IDs.
- [ ] Lifecycle and sensitivity can vary independently; durable-private and ephemeral-safe examples are represented without contradiction.
- [ ] Classification rejects traversal, absolute paths outside scope, symlinks, hard links, special files, identity changes, oversized files, excessive path sets, control characters, and unsafe secret-shaped durable values.
- [ ] Receipt/error output contains digest/reason correlation only and never republishes matched credential text.
- [ ] The staging allowlist equals the exact intersection of caller-intended paths and `committable` records; no directory, glob, wildcard, implicit deletion, or repository-wide staging is authorized.
- [ ] Every rejected intended path has a deterministic reason such as unclassified, private, ephemeral, blocked-sensitive, stale digest, missing, or unsafe path.
- [ ] Deleted/renamed paths can be represented explicitly without weakening exact-path authorization.
- [ ] Deliberate test secrets and `.example` files require explicit test-fixture provenance and do not create a global bypass.
- [ ] Explicit fixtures cover real-email, cookie, authorization-header, token, password, MFA/QR/authenticator, private-URL, and environment-value detection across bounded text, trace/console metadata, and filenames, with conservative handling for uninspectable artifacts.
- [ ] Declared fictional `.test`/`.example` identities can remain eligible only when no other sensitive class matches; nearby secret material still produces private or blocked classification.
- [ ] No exception, receipt, reason, digest projection, or test failure republishes a matched sensitive value.
- [ ] Output ordering and digests are deterministic across process hash seeds and filesystem enumeration order.
- [ ] Focused verification passes with `PYTHONPATH=plugins/workflow-kernel/skills/workflow-kernel/references /opt/homebrew/bin/python3.12 -m unittest tests.test_artifact_safety tests.test_schema tests.test_terminal_cleanup`.
- [ ] No CLI, Pipeline, manifest, version, marketplace, or generated Codex surface changes are included.
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
- Do not add runtime dependencies, shell execution, broad repository scans, or a second staging authority.
- Do not persist secret values, matching excerpts, environment values, cookies, credentials, or private browser state.
- Do not alter the existing artifact-lifecycle prose in this chunk.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.
- Do not create or modify `*_templ.go` files. Run `docker compose exec app templ generate` to regenerate them after editing `.templ` source files.
- When adding database migrations, verify the next sequence number: `ls migrations/*.sql | sort | tail -1`. Use the next consecutive number.
- When this chunk touches `auth/`, `admin/`, `account/`, `install/`, `member/`, or `module`-level permission paths in Assembly code, the final acceptance criterion must include an Auth Boundary Map receipt covering: surfaces mapped, middleware gates, Authorizer action/resource pairs, default-deny UI capabilities, stale-session/operator/install edge cases, test coverage, and residual risk. Omit the receipt only when no auth surface is affected.

## Research Context

Depot already has structured redaction and artifact retention tiers, but it lacks
whole-artifact sensitivity classification and generated staging authority.
Current orchestration sometimes stages explicit directories to handle renames;
the new contract must preserve exact deletion/rename support without turning a
directory into recursive approval. The Improvement Scout will later consume only
the safe indexed subset produced from these records.
